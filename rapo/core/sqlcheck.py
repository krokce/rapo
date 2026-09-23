"""Contains the checker behind the editor's Check buttons.

A statement is parsed by Oracle (`cursor.parse`) and never executed. Parsing
compiles queries, DML and PL/SQL blocks, and resolves their names and
privileges, but it **runs DDL** such as truncate, create or drop, so a
statement that is not a query, DML or a PL/SQL block is refused before it
reaches the parser.

Each kind of statement is wrapped the way the engine runs it, so a filter is
checked against its own datasource and a variable in braces is replaced with a
sample value first.
"""

import re
import json
import string
import datetime as dt

from ..database import db
from ..utils import utils


# The keywords a statement parsed as it is may start with. Everything else
# (create, drop, truncate, alter, grant...) would be executed by the parser.
SAFE_KEYWORDS = ('select', 'with', 'insert', 'update', 'delete', 'merge',
                 'begin', 'declare')
QUERY_KEYWORDS = ('select', 'with')
PLSQL_KEYWORDS = ('begin', 'declare')

# How sqlalchemy's text() finds a bind parameter. Filters, mismatch criteria and
# case mappings reach Oracle through text(), so a colon there must be escaped.
TEXT_BIND = re.compile(r'(?<![:\w\\]):(\w+)(?!:)')

KINDS = ('filter', 'error_sql', 'case_definition', 'prerequisite',
         'preparation', 'completion', 'email_filter', 'email_sql')

# The variables that limit a Free SQL sheet to the run being mailed.
RUN_VARIABLES = re.compile(r'\{(process_id|control_date\w*)[}:!]')


class CheckError(Exception):
    """A statement that can not be checked, with the reason for the user."""


def parse(statement):
    """Parse a statement with Oracle without executing it.

    Parameters
    ----------
    statement : str
        A query, DML or PL/SQL block. The caller makes sure it is not DDL.

    Returns
    -------
    result : dict
        `{'valid': True, 'columns': [{name, type}]}` or
        `{'valid': False, 'error': ...}`.
    """
    connection = db.engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.parse(statement)
        description = cursor.description or []
    except Exception as error:
        return {'valid': False, 'error': str(error).strip()}
    finally:
        connection.close()
    columns = [{'name': column[0], 'type': str(column[1]).split()[-1]
                .rstrip('>').replace('DB_TYPE_', '')}
               for column in description]
    return {'valid': True, 'columns': columns}


def strip_query(statement):
    """Drop the trailing semicolon a query or DML is often written with.

    Not in PL/SQL, where the last semicolon is part of the block.
    """
    statement = statement.strip()
    if first_keyword(statement) not in PLSQL_KEYWORDS:
        statement = statement.rstrip().rstrip(';').rstrip()
    return statement


def first_keyword(statement):
    """Get the first word of a statement, after comments and parentheses."""
    text = re.sub(r'/\*.*?\*/', ' ', statement, flags=re.S)
    text = re.sub(r'--[^\n]*', ' ', text)
    match = re.match(r'[\s(]*([A-Za-z_]+)', text)
    return match.group(1).lower() if match else ''


def sample_variables(control_name=None, email=False):
    """Get sample values of the variables a statement may use.

    The dates are today's midnight, so a format like `{control_date:%Y%m%d}`
    renders as it would in a run.
    """
    today = dt.datetime.combine(dt.date.today(), dt.time())
    variables = dict(control_name=control_name or 'CONTROL',
                     control_date=today,
                     control_date_from=today,
                     control_date_to=today + dt.timedelta(days=1,
                                                          seconds=-1),
                     process_id=0)
    if email:
        # The extra variables of mailer.build_variables.
        variables.update(control_description='', status='D',
                         start_date=today, end_date=today,
                         fetched_number=0, success_number=0, error_number=0,
                         fetched_number_a=0, fetched_number_b=0,
                         success_number_a=0, success_number_b=0,
                         error_number_a=0, error_number_b=0,
                         text_error='', attachment_rows=0)
    return variables


def render(statement, variables):
    """Substitute {variables} the way the engine does (`str.format`)."""
    try:
        return string.Formatter().vformat(statement, (), variables)
    except KeyError as error:
        name = error.args[0]
        known = ', '.join(f'{{{key}}}' for key in variables)
        raise CheckError(f'Unknown variable {{{name}}}. Known: {known}.')
    except (ValueError, IndexError) as error:
        raise CheckError(f'Braces can not be substituted: {error}. '
                         'A literal brace is written twice, {{ or }}.')


def result_table(control_name, control_type, side=None):
    """Get the name of the result table of a control."""
    if control_type == 'REC':
        return f'RAPO_RES{"B" if side == "b" else "A"}_{control_name}'
    return f'RAPO_REST_{control_name}'


def check(kind, statement, context=None):
    """Check one statement of the control editor.

    Parameters
    ----------
    kind : str
        One of KINDS: which box the statement comes from.
    statement : str
        The text as it is in the box.
    context : dict, optional
        The unsaved editor values it depends on: `control_name`,
        `control_type`, `source_name` (the datasource of a filter),
        `side` (`a`/`b` of an email sheet) and `case_ids`. An `email_sql`
        (the Free SQL sheet of an email) needs none of them.

    Returns
    -------
    result : dict
        `valid`, then `error` or `columns`, optionally `warning`, and the
        `statement` that was parsed.
    """
    context = context or {}
    if kind not in KINDS:
        return {'valid': False, 'error': f'Unknown kind {kind!r}.'}
    if not statement or not statement.strip():
        return {'valid': False, 'error': 'Statement is empty.'}
    if not db.configured:
        return {'valid': False, 'error': 'Database is not configured.'}
    try:
        return _check(kind, statement.strip(), context)
    except CheckError as error:
        return {'valid': False, 'error': str(error)}


def _check(kind, statement, context):
    control_name = (context.get('control_name') or '').strip().upper()
    source_name = (context.get('source_name') or '').strip()
    warning = None

    if kind in ('filter', 'error_sql', 'case_definition'):
        if kind == 'error_sql' and utils.is_json(statement):
            return _check_json_error(statement, source_name)
        if not source_name:
            raise CheckError('Choose the datasource first: the statement is '
                             'checked against its columns.')
        bind = TEXT_BIND.search(statement)
        if bind:
            warning = (f'":{bind.group(1)}" is read as a bind variable when '
                       f'the control runs; write it as "\\:{bind.group(1)}".')
        if kind in ('filter', 'error_sql'):
            # Rendered as the engine does: only known {variables}, every other
            # brace is kept as written.
            variables = sample_variables(control_name)
            unknown = utils.find_unknown_variables(statement, variables)
            if unknown and not warning:
                names = ', '.join(f'{{{name}}}' for name in unknown)
                warning = (f'Unknown variable {names} is left as written. '
                           'Known: ' + ', '.join(f'{{{key}}}'
                                                 for key in variables) + '.')
            statement = utils.render(statement, variables)
        condition = statement.rstrip(';').replace('\\:', ':')
        if kind == 'case_definition':
            query = f'select {condition} as rapo_case_id from {source_name}'
            warning = warning or _case_warning(statement,
                                               context.get('case_ids'))
        else:
            query = f'select * from {source_name} where ({condition})'
    elif kind == 'email_filter':
        if not control_name:
            raise CheckError('Save the control first: the filter is checked '
                             'against its result table.')
        variables = sample_variables(control_name, email=True)
        condition = render(statement, variables).rstrip(';')
        table = result_table(control_name, context.get('control_type'),
                             context.get('side'))
        query = f'select * from {table} where ({condition})'
        if not db.tables.check(table.lower()):
            return {'valid': True, 'statement': query,
                    'warning': f'{table} does not exist yet, so only the '
                               'variables were checked. The first run '
                               'creates it.'}
    elif kind == 'email_sql':
        if first_keyword(statement) not in QUERY_KEYWORDS:
            raise CheckError('The Free SQL sheet must be a query (select or '
                             'with).')
        variables = sample_variables(control_name, email=True)
        query = strip_query(render(statement, variables))
        if not RUN_VARIABLES.search(statement):
            warning = ('The query uses neither {process_id} nor '
                       '{control_date...}, so it is not limited to this run.')
    else:
        keywords = QUERY_KEYWORDS if kind == 'prerequisite' else SAFE_KEYWORDS
        keyword = first_keyword(statement)
        if keyword not in keywords:
            if kind == 'prerequisite':
                raise CheckError('A prerequisite must be a query (select) '
                                 'returning one number.')
            raise CheckError(
                f'"{keyword.upper() or statement[:20]}" is not checked: the '
                'parser would execute it. Wrap DDL in a block, e.g. '
                "begin execute immediate 'truncate table x'; end;")
        query = strip_query(render(statement, sample_variables(control_name)))

    result = parse(query)
    result['statement'] = query
    if result['valid'] and kind in ('filter', 'error_sql', 'email_filter'):
        target = table if kind == 'email_filter' else source_name
        result['message'] = f'OK — valid condition on {target}'
    if result['valid']:
        columns = result.get('columns') or []
        if kind == 'prerequisite':
            warning = warning or number_warning(columns)
        if warning:
            result['warning'] = warning
    return result


def number_warning(columns):
    if not columns:
        return 'Statement returns no columns, so it can not produce a value.'
    if len(columns) > 1:
        return (f'Statement returns {len(columns)} columns, only the first '
                'one is used.')
    if columns[0]['type'] != 'NUMBER':
        return f'Column {columns[0]["name"]} is {columns[0]["type"]}, ' \
               'not a number.'
    return None


def _case_warning(statement, case_ids):
    """Warn about case IDs used in THEN/ELSE but not in Case config."""
    if case_ids is None:
        return None
    known = {int(i) for i in case_ids if str(i).strip().lstrip('-').isdigit()}
    used = {int(i) for i in re.findall(r'\b(?:then|else)\s+(\d+)', statement,
                                       re.I)}
    missing = sorted(used - known)
    if not used:
        return 'No THEN <case ID> found: the mapping has to return the ' \
               'IDs of Case config.'
    if missing:
        return ('Case ID ' + ', '.join(map(str, missing)) + ' is not in '
                'Case config, so the run will fail.')
    return None


def _check_json_error(statement, source_name):
    """Check the JSON form of the ANL mismatch criteria."""
    try:
        items = json.loads(statement)
    except ValueError as error:
        return {'valid': False, 'error': f'Invalid JSON: {error}'}
    if not isinstance(items, list) or \
       not all(isinstance(item, dict) for item in items):
        return {'valid': False,
                'error': 'Expected a JSON list of {"column": ...} objects.'}
    names = []
    for item in items:
        if not item.get('column'):
            return {'valid': False,
                    'error': f'Condition without "column": {item}'}
        names.append(item['column'])
        if item.get('is_column') and item.get('value'):
            names.append(item['value'])
    result = {'valid': True, 'statement': statement}
    if source_name:
        columns = ', '.join(dict.fromkeys(names))
        parsed = parse(f'select {columns} from {source_name}')
        if not parsed['valid']:
            return {'valid': False, 'statement': statement,
                    'error': f'Columns of {source_name}: {parsed["error"]}'}
    return result
