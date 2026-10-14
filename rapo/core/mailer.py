"""Contains the sending of control results per email.

The configuration of a control is the `email` key of its rule_config (ANL,
REP and REC; CMP keeps its rule_config as a list and has no email). The SMTP
parameters come from the [EMAIL] section of rapo.ini.

The attachments are `files`, each an Excel file of `sheets`: result sheets
(a filtered select from a result table) and Free SQL sheets. An older
configuration (one `attachment_name`, `attach` and a fixed `sheets` object)
is converted on read by `read_files`, as the editor does on load.
"""

import io
import re
import ssl
import json
import smtplib
import decimal
import datetime as dt

from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import sqlalchemy as sa

from ..config import config
from .. import options
from ..database import db
from ..logger import logger
from ..utils import utils


SEND_WHEN = ('done_with_results', 'done', 'done_or_error', 'evaluate_sql')
DEFAULT_SEND_WHEN = 'done_with_results'
EMAIL_TYPES = ('ANL', 'REP', 'REC')
DEFAULT_MAX_ROWS = options.default('EMAIL', 'max_attachment_rows')
DEFAULT_MAX_MB = options.default('EMAIL', 'max_attachment_mb')
EXCEL_MAX_DIGITS = 15
EXCEL_MAX_TEXT = 32767
REC_RESULT_TYPES = ('Loss', 'Discrepancy', 'Match')


class EmailError(Exception):
    """A resend or test send that cannot be performed."""


def settings():
    """Get the [EMAIL] section of rapo.ini, empty when there is none."""
    return config.get('EMAIL') or {}


def read_email_config(control):
    """Get the email configuration of the control, or None.

    Parameters
    ----------
    control : rapo.Control
        The control whose rule_config is read.

    Returns
    -------
    email_config : dict or None
        The `email` object of rule_config.
    """
    if control.type not in EMAIL_TYPES:
        return None
    raw = control.config['rule_config']
    try:
        rule_config = json.loads(raw) if raw else None
    except ValueError:
        return None
    if not isinstance(rule_config, dict):
        return None
    email_config = rule_config.get('email')
    return email_config if isinstance(email_config, dict) else None


def read_last_done_run(control_name):
    """Get the process ID of the last run of the control that ended D."""
    config_table = db.tables.config
    log = db.tables.log
    control_id = (sa.select(config_table.c.control_id)
                    .where(config_table.c.control_name == control_name)
                    .scalar_subquery())
    query = (sa.select(sa.func.max(log.c.process_id))
               .where(log.c.control_id == control_id)
               .where(log.c.status == 'D'))
    return db.execute(query, as_scalar=True)


def render(text, variables):
    """Substitute {variables} in the text, leaving unknown ones untouched."""
    return utils.render(text, variables)


def attachment_name(control, file_config=None, variables=None, index=0,
                    taken=None):
    """Get the name of an attached file of a control run.

    The configured `name` with its {variables} rendered, else the control
    name, then the date the window starts, then the date it ends when that is
    another day, in ISO format, then _2, _3... from the second file on. A name
    already in `taken` (case-insensitive) gets ' (2)', ' (3)'...
    """
    name = None
    template = (file_config or {}).get('name')
    if template and template.strip():
        name = render(template, variables or {})
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name)
        name = name.strip().strip('.')
        if name.lower().endswith('.xlsx'):
            name = name[:-5].rstrip()
    if not name:
        date_from = control.date_from.date()
        date_to = control.date_to.date()
        dates = f'{date_from:%Y-%m-%d}'
        if date_to != date_from:
            dates = f'{dates}_{date_to:%Y-%m-%d}'
        name = re.sub(r'[^\w.-]+', '_', control.name)
        name = f'{name}_{dates}' + (f'_{index + 1}' if index else '')
    title, number = name, 2
    while taken is not None and title.lower() in taken:
        title = f'{name} ({number})'
        number += 1
    if taken is not None:
        taken.add(title.lower())
    return f'{title}.xlsx'


def read_text_error(control):
    """Get the error of an E run: the live traceback, else the stored one."""
    if control.status != 'E':
        return None
    return control.text_error or (control.result or {}).get('text_error')


def build_variables(control):
    """Get the variables available to the subject, body and filters."""
    variables = dict(control.variables)
    variables.update(
        control_description=control.config['control_description'],
        status=control.status,
        start_date=control.start_date,
        end_date=control.end_date,
        fetched_number=control.fetched_number,
        success_number=control.success_number,
        error_number=control.error_number,
        fetched_number_a=control.fetched_number_a,
        fetched_number_b=control.fetched_number_b,
        success_number_a=control.success_number_a,
        success_number_b=control.success_number_b,
        error_number_a=control.error_number_a,
        error_number_b=control.error_number_b,
        text_error=read_text_error(control),
        attachment_rows=None,
        evaluate_value=None)
    return variables


def evaluate(control, email_config):
    """Run the Evaluate SQL of send_when 'evaluate_sql'.

    The statement is prepared as the Prerequisite SQL: strict str.format()
    with the control variables. The email is sent only when its value is a
    number above 0.

    Returns
    -------
    value : object
        The first column of the first row, None when it failed.
    error : str or None
        Why the value can not be used as a number.
    """
    statement = (email_config.get('evaluate_sql') or '').strip()
    if not statement:
        return None, 'Evaluate SQL is empty'
    try:
        statement = statement.format(**control.variables)
        statement = db.formatter(statement)
        value = db.execute(statement, as_scalar=True)
    except Exception as error:
        logger.error()
        message = str(error).splitlines()[0] if str(error) else ''
        return None, f'Evaluate SQL failed: {type(error).__name__}: {message}'
    if value is None:
        return None, 'Evaluate SQL returned no value'
    if isinstance(value, decimal.Decimal) and value == value.to_integral():
        value = int(value)
    try:
        float(value)
    except (TypeError, ValueError):
        return value, f'Evaluate SQL returned {value!r}, not a number'
    return value, None


class Sheet:
    """One sheet of the attachment: a filtered select from a result table."""

    # Whether its rows are results for send_when 'done_with_results'.
    counts_as_result = True

    def __init__(self, control, title, table_name, sheet_config,
                 variables, result_types=None):
        self.control = control
        self.title = title
        self.table_name = table_name
        self.config = sheet_config or {}
        self.variables = variables
        self.result_types = result_types
        self.table = None
        self.columns = []
        self.labels = []
        self.count = 0

    def prepare(self):
        """Reflect the table, resolve the fields and count the rows."""
        if not db.exists(self.table_name):
            logger.warning(f'{self.control} Email: table {self.table_name} '
                           'does not exist, sheet skipped')
            return False
        self.table = db.table(self.table_name)
        fields = self.config.get('fields') or []
        if fields:
            for field in fields:
                name = (field.get('column') or '').lower()
                if name in self.table.c:
                    self.columns.append(self.table.c[name])
                    self.labels.append(field.get('label') or name.upper())
                else:
                    logger.warning(f'{self.control} Email: column {name} '
                                   f'not found in {self.table_name}, '
                                   'skipped')
        if not self.columns:
            self.columns = list(self.table.c)
            self.labels = [column.name.upper() for column in self.columns]
        self.count = db.execute(self.count_query(), as_scalar=True) or 0
        logger.info(f'{self.control} Email: {self.count} rows for sheet '
                    f'{self.title} from {self.table_name}')
        return True

    def where(self, query):
        table = self.table
        query = query.where(
            table.c.rapo_process_id == self.control.process_id)
        if self.result_types:
            query = query.where(
                table.c.rapo_result_type.in_(self.result_types))
        where = self.config.get('filter')
        if where and where.strip():
            # A colon would be read as a bind parameter, e.g. in 'HH24:MI'.
            where = render(where, self.variables).replace(':', r'\:')
            query = query.where(sa.text(f'({where})'))
        return query

    def count_query(self):
        query = sa.select(sa.func.count()).select_from(self.table)
        return self.where(query)

    def select_query(self):
        query = sa.select(*self.columns)
        return self.where(query)

    def fetch(self):
        """Get the rows of the sheet."""
        return db.execute(self.select_query(), as_records=True)


class SqlSheet:
    """The Free SQL sheet of the attachment: a query of the user's own.

    Only a query (select/with) is run, so an email never executes DML or DDL.
    Its headers are the column names as Oracle returns them, so a quoted
    alias keeps its case and spaces.
    """

    counts_as_result = False

    def __init__(self, control, title, sheet_config, variables):
        self.control = control
        self.title = title
        self.config = sheet_config or {}
        self.variables = variables
        self.query = None
        self.columns = []
        self.labels = []
        self.count = 0

    def prepare(self):
        """Render the query and count its rows."""
        from .sqlcheck import first_keyword

        query = (self.config.get('query') or '').strip()
        if not query:
            logger.warning(f'{self.control} Email: Free SQL sheet has no '
                           'query, sheet skipped')
            return False
        if first_keyword(query) not in ('select', 'with'):
            logger.warning(f'{self.control} Email: Free SQL sheet is not a '
                           'query (select/with), sheet skipped')
            return False
        query = render(query, self.variables).strip().rstrip(';').rstrip()
        # A colon would be read as a bind parameter, e.g. in 'HH24:MI'.
        self.query = query.replace(':', r'\:')
        try:
            count = sa.text(f'select count(*) from ({self.query})')
            self.count = db.execute(count, as_scalar=True) or 0
        except Exception:
            logger.warning(f'{self.control} Email: Free SQL sheet failed, '
                           'sheet skipped')
            logger.error()
            return False
        logger.info(f'{self.control} Email: {self.count} rows for sheet '
                    f'{self.title} from Free SQL')
        return True

    def fetch(self):
        """Get the rows of the sheet and set its columns from the cursor."""
        connection = db.connect()
        try:
            result = connection.execute(sa.text(self.query))
            names = [column[0] for column in result.cursor.description]
            rows = result.fetchall()
        finally:
            connection.close()
        # Untyped columns: their Excel formats come from the values alone.
        self.columns = [sa.column(name) for name in names]
        self.labels = names
        return rows


def sheet_title(sheet_config, default, taken):
    """Get the Excel name of a sheet: its configured name, else the default.

    Excel allows 31 characters, none of []:*?/\\, no leading or trailing
    apostrophe, and names unique regardless of case.
    """
    name = re.sub(r'[\[\]:*?/\\]', '_', sheet_config.get('name') or '')
    name = name.strip().strip("'")[:31] or default[:31]
    title, number = name, 2
    while title.lower() in taken:
        suffix = f' ({number})'
        title = name[:31 - len(suffix)] + suffix
        number += 1
    taken.add(title.lower())
    return title


def available_result_types(control, side):
    """Get the result types a REC side saves: Loss and Discrepancy with its
    issues, Match with its matches; none when the side saves nothing."""
    rule_config = control.rule_config
    types = []
    if rule_config.get(f'need_issues_{side}'):
        types.extend(['Loss', 'Discrepancy'])
    if rule_config.get(f'need_recons_{side}'):
        types.append('Match')
    return types


def read_files(control, email_config):
    """Get the `files` of the email configuration.

    An older configuration is converted: one file named `attachment_name`,
    attached per `attach`, with its enabled sheets in the order main (or A,
    B), then the Free SQL. A REC sheet without a name keeps its old default
    A / B; disabled sheets were never sent and are left out.
    """
    files = email_config.get('files')
    if isinstance(files, list):
        return [file for file in files if isinstance(file, dict)]
    sheets_config = email_config.get('sheets') or {}
    sheets = []
    sides = ['a', 'b'] if control.is_reconciliation else ['main']
    for side in sides:
        sheet_config = sheets_config.get(side) or {}
        if not sheet_config.get('enabled', side == 'main'):
            continue
        sheet = {'kind': 'result', 'side': side,
                 'name': sheet_config.get('name'),
                 'filter': sheet_config.get('filter'),
                 'fields': sheet_config.get('fields') or []}
        if side != 'main':
            sheet['name'] = sheet['name'] or side.upper()
            sheet['result_types'] = list(sheet_config.get('result_types')
                                         or REC_RESULT_TYPES)
        sheets.append(sheet)
    sql_config = sheets_config.get('sql') or {}
    if sql_config.get('enabled'):
        sheets.append({'kind': 'sql', 'name': sql_config.get('name'),
                       'query': sql_config.get('query')})
    return [{'name': email_config.get('attachment_name'),
             'attach': email_config.get('attach', True),
             'sheets': sheets}]


def chosen_result_types(control, sheet_config):
    """Get the result types a REC sheet exports: its chosen ones the side
    saves, all of them when none is chosen."""
    available = available_result_types(control, sheet_config.get('side'))
    chosen = sheet_config.get('result_types') or available
    return [type for type in REC_RESULT_TYPES
            if type in chosen and type in available]


def default_sheet_names(control, sheets_config):
    """Get the default names of the sheets of a file.

    A result sheet is named after the control (ANL/REP) or its side (REC),
    with its result types when they are not all the side saves, e.g.
    'A Loss+Discrepancy'. Free SQL sheets are SQL, SQL 2, ... Repeats are
    numbered by sheet_title.
    """
    names = []
    sql_number = 0
    for sheet_config in sheets_config:
        if sheet_config.get('kind') == 'sql':
            sql_number += 1
            names.append('SQL' if sql_number == 1 else f'SQL {sql_number}')
        elif control.is_reconciliation:
            side = str(sheet_config.get('side') or '')
            available = available_result_types(control, side)
            chosen = chosen_result_types(control, sheet_config)
            name = side.upper()
            if chosen and len(chosen) < len(available):
                name = f'{name} {"+".join(chosen)}'
            names.append(name)
        else:
            names.append(control.name)
    return names


class File:
    """One attached file of the email: its configuration and sheets."""

    def __init__(self, config, index, sheets):
        self.config = config
        self.index = index
        self.sheets = sheets

    @property
    def attach(self):
        return self.config.get('attach', True) is not False

    @property
    def count(self):
        return sum(sheet.count for sheet in self.sheets)


def build_sheet(control, sheet_config, title, variables):
    """Get the sheet of a sheet configuration, None when it cannot be one."""
    kind = sheet_config.get('kind')
    if kind == 'sql':
        return SqlSheet(control, title, sheet_config, variables)
    if kind != 'result':
        logger.warning(f'{control} Email: sheet kind {kind!r} unknown, '
                       'sheet skipped')
        return None
    if not control.is_reconciliation:
        return Sheet(control, title, control.output_name, sheet_config,
                     variables)
    side = sheet_config.get('side')
    if side not in ('a', 'b'):
        logger.warning(f'{control} Email: sheet {title} has no side, '
                       'sheet skipped')
        return None
    need = control.need_a if side == 'a' else control.need_b
    result_types = chosen_result_types(control, sheet_config)
    if not need or not result_types:
        logger.warning(f'{control} Email: side {side.upper()} saves none of '
                       f'the result types of sheet {title}, sheet skipped')
        return None
    table_name = control.output_name_a if side == 'a' \
        else control.output_name_b
    return Sheet(control, title, table_name, sheet_config, variables,
                 result_types=result_types)


def build_files(control, email_config, variables):
    """Get the files of the email with their prepared sheets."""
    files = []
    for index, file_config in enumerate(read_files(control, email_config)):
        sheets_config = [sheet for sheet in file_config.get('sheets') or []
                         if isinstance(sheet, dict)]
        defaults = default_sheet_names(control, sheets_config)
        taken = set()
        sheets = []
        for sheet_config, default in zip(sheets_config, defaults):
            title = sheet_title(sheet_config, default, taken)
            sheet = build_sheet(control, sheet_config, title, variables)
            if sheet and sheet.prepare():
                sheets.append(sheet)
        files.append(File(file_config, index, sheets))
    return files


def count_results(files):
    """Get the rows that count as results for 'done_with_results'.

    The result-table sheets of every file, attached or not; the Free SQL
    sheets only when there is no result sheet, since a summary query returns
    rows for every run.
    """
    sheets = [sheet for file in files for sheet in file.sheets]
    results = [sheet for sheet in sheets if sheet.counts_as_result]
    return sum(sheet.count for sheet in results or sheets)


def attach_files(control, email_config, files, variables):
    """Build the workbooks of the files that can be attached.

    A file is left out when its Attach is off, its sheets have no rows, it
    has more rows than the limit, or it would take the attachments above the
    size limit; the files are attached in their order.

    Returns
    -------
    attachments : list of tuple
        The (name, content) of each attached file.
    lines : list of dict
        Per file: `name`, `rows`, `sheets`, and `reason` when not attached.
    """
    params = settings()
    ceiling = params.get('max_attachment_rows') or DEFAULT_MAX_ROWS
    limit = email_config.get('max_records') or ceiling
    limit = min(int(limit), int(ceiling))
    max_mb = params.get('max_attachment_mb') or DEFAULT_MAX_MB
    attachments, lines = [], []
    used = 0
    taken = set()
    for file in files:
        name = attachment_name(control, file.config, variables, file.index,
                               taken)
        line = {'name': name, 'rows': file.count,
                'sheets': len(file.sheets), 'reason': None}
        lines.append(line)
        if not file.attach:
            line['reason'] = 'Attach off'
        elif file.count == 0:
            line['reason'] = 'no rows'
        elif file.count > limit:
            line['reason'] = f'above the limit of {limit:,} rows'
        else:
            content = build_workbook(file.sheets)
            size = len(content) / 1024 / 1024
            if used + size > max_mb:
                line['reason'] = (f'{size:.1f} MB would take the attachments '
                                  f'above the limit of {max_mb} MB')
            else:
                used += size
                attachments.append((name, content))
                logger.info(f'{control} Email: attachment {name} with '
                            f'{file.count} rows, {size:.2f} MB')
        if line['reason'] and line['reason'] != 'Attach off':
            logger.warning(f'{control} Email: {name} not attached: '
                           f'{line["reason"]}')
    return attachments, lines


def describe_file(line):
    """Get the summary line of an attached or left-out file."""
    rows = f'{line["rows"]:,}'.replace(',', ' ') + \
        (' row' if line['rows'] == 1 else ' rows')
    sheets = f'{line["sheets"]} sheet' + ('' if line['sheets'] == 1 else 's')
    text = f'{line["name"]}: {rows}, {sheets}'
    if line['reason']:
        text += f', not attached ({line["reason"]})'
    return text


def column_formats(column, values):
    """Get the kind of an Excel column: 'date', 'datetime', 'int', 'dec'."""
    present = [value for value in values if value is not None]
    if isinstance(column.type, sa.TIMESTAMP):
        return 'datetime'
    if isinstance(column.type, (sa.DateTime, sa.Date)) or (
            present and all(isinstance(value, dt.datetime)
                            for value in present)):
        if all(not isinstance(value, dt.datetime) or
               value.time() == dt.time() for value in present):
            return 'date'
        return 'datetime'
    if isinstance(column.type, sa.Numeric) or (
            present and all(isinstance(value, (int, float, decimal.Decimal))
                            and not isinstance(value, bool)
                            for value in present)):
        if getattr(column.type, 'scale', None) == 0:
            return 'int'
        if all(isinstance(value, (int, float, decimal.Decimal))
               and value == int(value) for value in present):
            return 'int'
        return 'dec'
    return 'text'


def build_workbook(sheets):
    """Write the sheets to an in-memory xlsx file.

    Returns
    -------
    content : bytes
        The xlsx file.
    """
    import xlsxwriter

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {'in_memory': True,
                                            'strings_to_numbers': False,
                                            'strings_to_formulas': False,
                                            'strings_to_urls': False})
    header = workbook.add_format({'bold': True, 'bg_color': '#E0E0E0',
                                  'border': 1})
    formats = {
        'date': workbook.add_format({'num_format': 'dd.mm.yyyy'}),
        'datetime': workbook.add_format(
            {'num_format': 'dd.mm.yyyy hh:mm:ss'}),
        'int': workbook.add_format({'num_format': '0'}),
        'dec': workbook.add_format({'num_format': '0.00'}),
        'text': None
    }
    widths = {'date': 10, 'datetime': 19, 'int': 0, 'dec': 0, 'text': 0}
    for sheet in sheets:
        worksheet = workbook.add_worksheet(sheet.title)
        rows = sheet.fetch()
        for index, label in enumerate(sheet.labels):
            worksheet.write_string(0, index, label, header)
        for index, column in enumerate(sheet.columns):
            values = [row[index] for row in rows]
            kind = column_formats(column, values)
            cell_format = formats[kind]
            width = max(len(sheet.labels[index]), widths[kind])
            for number, value in enumerate(values, start=1):
                if value is None:
                    continue
                if kind in ('date', 'datetime'):
                    worksheet.write_datetime(number, index, value,
                                             cell_format)
                elif kind in ('int', 'dec'):
                    if kind == 'int' and len(str(abs(int(value)))) > \
                            EXCEL_MAX_DIGITS:
                        text = str(int(value))
                        worksheet.write_string(number, index, text)
                        width = max(width, len(text))
                        continue
                    number_value = int(value) if kind == 'int' \
                        else float(value)
                    worksheet.write_number(number, index, number_value,
                                           cell_format)
                    if kind == 'int':
                        width = max(width, len(str(number_value)))
                    else:
                        width = max(width, len(f'{number_value:.2f}'))
                else:
                    text = str(value)[:EXCEL_MAX_TEXT]
                    worksheet.write_string(number, index, text)
                    width = max(width, min(len(text), 60))
            worksheet.set_column(index, index, min(width + 2, 62))
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, max(len(rows), 1),
                             max(len(sheet.columns) - 1, 0))
    workbook.close()
    return buffer.getvalue()


def build_summary(control, variables, files):
    """Get the run summary block appended to the body, with a line per file
    (attach_files)."""
    def number(value):
        return '' if value is None else f'{value:,}'.replace(',', ' ')

    def moment(value):
        return '' if value is None else f'{value:%d.%m.%Y %H:%M:%S}'

    lines = ['', '-' * 40,
             f'Control: {control.name}',
             f'Description: {variables["control_description"] or ""}',
             f'Process ID: {control.process_id}',
             f'Window: {moment(control.date_from)} - '
             f'{moment(control.date_to)}',
             f'Status: {control.status}',
             f'Started: {moment(control.start_date)}',
             f'Ended: {moment(control.end_date)}']
    if control.is_reconciliation:
        lines += [f'Fetched A / B: {number(control.fetched_number_a)} / '
                  f'{number(control.fetched_number_b)}',
                  f'Success A / B: {number(control.success_number_a)} / '
                  f'{number(control.success_number_b)}',
                  f'Errors A / B: {number(control.error_number_a)} / '
                  f'{number(control.error_number_b)}']
    else:
        lines += [f'Fetched: {number(control.fetched_number)}',
                  f'Success: {number(control.success_number)}',
                  f'Errors: {number(control.error_number)}']
    if files:
        lines.append('Attachments:')
        lines += [f'  {describe_file(line)}' for line in files]
    return '\n'.join(lines)


def addresses(values):
    """Get a clean list of addresses from a list or a delimited string."""
    if isinstance(values, str):
        values = re.split(r'[;,\s]+', values)
    return [value.strip() for value in values or [] if value and
            value.strip()]


def deliver(message, recipients):
    """Send the message through the SMTP server of rapo.ini."""
    params = settings()
    host = params.get('host')
    if not host:
        raise EmailError('[EMAIL] host is not set in rapo.ini')
    # rapo.ini reads 'none' (and an empty value) as None, so an option that
    # is present but None means no TLS, and a missing one means starttls.
    if 'security' in params:
        security = str(params['security'] or 'none').lower()
    else:
        security = 'starttls'
    port = params.get('port') or (465 if security == 'ssl' else 587)
    timeout = params.get('timeout') or options.default('EMAIL', 'timeout')
    context = ssl.create_default_context()
    if security == 'ssl':
        smtp = smtplib.SMTP_SSL(host, int(port), timeout=timeout,
                                context=context)
    else:
        smtp = smtplib.SMTP(host, int(port), timeout=timeout)
    with smtp:
        if security == 'starttls':
            smtp.starttls(context=context)
        user = params.get('user')
        if user:
            smtp.login(str(user), str(params.get('password') or ''))
        return smtp.send_message(message, to_addrs=recipients)


def send_run_email(control, trigger='run', override_to=None):
    """Send the email of a finished control run, if it is configured to.

    The run itself is never affected: every failure is logged, and the
    function returns whether an email was sent. A resend or a test
    (trigger other than 'run') raises EmailError instead of skipping
    silently, so that the caller can report why.

    Parameters
    ----------
    control : rapo.Control
        The control run, status D or E.
    trigger : str
        'run' after a run, 'resend' from the Results menu, 'test' from the
        editor.
    override_to : list or str, optional
        Recipients replacing To, CC and BCC.

    Returns
    -------
    sent : bool
        Whether an email was sent.
    """
    manual = trigger != 'run'

    def skip(reason):
        if manual:
            raise EmailError(reason)
        logger.info(f'{control} Email not sent: {reason}')
        return False

    email_config = read_email_config(control)
    if not email_config or not email_config.get('enabled'):
        if manual:
            raise EmailError('email is not enabled for this control')
        return False
    if not settings().get('enabled'):
        return skip('email is disabled in rapo.ini ([EMAIL] enabled)')
    send_when = email_config.get('send_when') or DEFAULT_SEND_WHEN
    if send_when not in SEND_WHEN:
        send_when = DEFAULT_SEND_WHEN
    if control.status not in ('D', 'E'):
        return skip(f'run status is {control.status}, not D')
    if control.status == 'E' and not manual and \
            send_when not in ('done_or_error', 'evaluate_sql'):
        return False

    # Evaluated before the sheets are built, so that nothing is fetched for
    # an email that is not sent. A resend or a test is sent anyway.
    evaluate_value = None
    evaluate_note = None
    if send_when == 'evaluate_sql':
        evaluate_value, evaluate_error = evaluate(control, email_config)
        if evaluate_error:
            evaluate_note = f'{evaluate_error}, so a run would not send ' \
                            'this email.'
            if not manual:
                logger.warning(f'{control} Email not sent: {evaluate_error}')
                return False
            logger.warning(f'{control} Email: {evaluate_error}')
        else:
            logger.info(f'{control} Email: Evaluate SQL returned '
                        f'{evaluate_value}')
            if float(evaluate_value) <= 0:
                evaluate_note = f'Evaluate SQL returned {evaluate_value}, ' \
                                'so a run would not send this email.'
                if not manual:
                    logger.info(f'{control} Email not sent: Evaluate SQL '
                                f'returned {evaluate_value}')
                    return False

    logger.info(f'{control} Preparing email ({trigger}, '
                f'send when {send_when})...')
    try:
        to = addresses(email_config.get('to'))
        cc = addresses(email_config.get('cc'))
        bcc = addresses(email_config.get('bcc'))
        if override_to:
            to, cc, bcc = addresses(override_to), [], []
        if not to and not cc and not bcc:
            return skip('no recipients')

        variables = build_variables(control)
        variables['evaluate_value'] = evaluate_value
        attachments, lines = [], []
        if control.status == 'D':
            files = build_files(control, email_config, variables)
            variables['attachment_rows'] = sum(file.count for file in files)
            if send_when == 'done_with_results' and not manual and \
                    count_results(files) == 0:
                logger.info(f'{control} Email not sent: no result rows')
                return False
            attachments, lines = attach_files(control, email_config, files,
                                              variables)

        subject = render(email_config.get('subject') or
                         '{control_name} {control_date_from:%Y-%m-%d}',
                         variables)
        subject = ' '.join(subject.split())
        body = render(email_config.get('body') or '', variables)
        if control.status == 'E':
            body += f'\n\nThe run ended with an error:\n\n' \
                    f'{variables["text_error"] or ""}'
        if email_config.get('include_summary', True):
            body += '\n' + build_summary(control, variables, lines)
        else:
            notes = [describe_file(line) for line in lines
                     if line['reason'] and line['reason'] != 'Attach off']
            if notes:
                body += '\n\n' + '\n'.join(notes)
        if trigger == 'test':
            subject = f'[TEST] {subject}'
            if evaluate_note:
                body += f'\n\n{evaluate_note}'

        params = settings()
        sender = params.get('sender')
        if not sender:
            raise EmailError('[EMAIL] sender is not set in rapo.ini')
        message = EmailMessage()
        message['From'] = formataddr((params.get('sender_name') or '',
                                      str(sender)))
        if to:
            message['To'] = ', '.join(to)
        if cc:
            message['Cc'] = ', '.join(cc)
        if params.get('reply_to'):
            message['Reply-To'] = str(params.get('reply_to'))
        message['Subject'] = subject
        message['Date'] = dt.datetime.now().astimezone()
        message['Message-ID'] = make_msgid()
        message.set_content(body.strip() + '\n')
        for name, content in attachments:
            message.add_attachment(content, maintype='application',
                                   subtype='vnd.openxmlformats-officedocument'
                                           '.spreadsheetml.sheet',
                                   filename=name)
        recipients = to + cc + bcc
        logger.info(f'{control} Sending email "{subject}" to {to}, cc {cc}, '
                    f'bcc {bcc}...')
        refused = deliver(message, recipients)
        if refused:
            logger.warning(f'{control} Email refused for {refused}')
        logger.info(f'{control} Email sent to {len(recipients)} recipients')
        return True
    except EmailError:
        if manual:
            raise
        logger.error()
        return False
    except Exception as error:
        logger.error()
        if manual:
            raise EmailError(f'{type(error).__name__}: {error}') from error
        return False
