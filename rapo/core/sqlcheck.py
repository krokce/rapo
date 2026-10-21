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
import time
import string
import datetime as dt

from ..database import db
from ..utils import utils
from .case import find_case_ids


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


# Where a literal (q-quoted too), a quoted name or a comment starts. They are
# read left to right as Oracle reads them (`tokens`), so a quote inside a
# comment or a comment mark inside a literal starts nothing.
TOKEN_START = re.compile(r"(?P<q>(?<![\w$#])n?q'(?P<open>.))|(?P<quote>')"
                         r'|(?P<name>")|(?P<line>--)|(?P<block>/\*)',
                         flags=re.I | re.S)
LITERAL_REST = re.compile(r"(?:[^']|'')*'")
Q_CLOSE = {'[': ']', '{': '}', '(': ')', '<': '>'}


def tokens(statement):
    """Yield (kind, start, end, closed) of every literal, q-quoted literal,
    quoted name and comment of a statement (kind `literal`, `q_literal`,
    `name` or `comment`); one not closed runs to the end of the text."""
    text, position = statement, 0
    while True:
        found = TOKEN_START.search(text, position)
        if not found:
            return
        if found.group('q'):
            kind = 'q_literal'
            close = Q_CLOSE.get(found.group('open'), found.group('open'))
            end = text.find(close + "'", found.end())
            end = end + 2 if end >= 0 else -1
        elif found.group('quote'):
            kind = 'literal'
            rest = LITERAL_REST.match(text, found.end())
            end = rest.end() if rest else -1
        elif found.group('name'):
            kind = 'name'
            end = text.find('"', found.end())
            end = end + 1 if end >= 0 else -1
        elif found.group('line'):
            kind = 'comment'
            end = text.find('\n', found.end())
            end = end if end >= 0 else len(text)
        else:
            kind = 'comment'
            end = text.find('*/', found.end())
            end = end + 2 if end >= 0 else -1
        closed = end >= 0
        end = end if closed else len(text)
        yield kind, found.start(), end, closed
        position = end


def code_only(statement):
    """Drop comments, string literals and quoted names, which may hold any
    word (a name is left as "")."""
    parts, position = [], 0
    for kind, start, end, _ in tokens(statement):
        parts.append(statement[position:start])
        parts.append({'comment': ' ', 'name': '""'}.get(kind, "''"))
        position = end
    parts.append(statement[position:])
    return ''.join(parts)


# What a filter on a dataset may call without Free SQL (`plain_filter`): the
# functions the discrepancy analysis' filters and common predicates use.
FILTER_FUNCTIONS = frozenset((
    'abs', 'add_months', 'cast', 'ceil', 'coalesce', 'decode', 'extract',
    'floor', 'greatest', 'instr', 'last_day', 'least', 'length', 'lnnvl',
    'lower', 'ltrim', 'mod', 'months_between', 'nvl', 'nvl2', 'regexp_like',
    'replace', 'round', 'rtrim', 'sign', 'substr', 'to_char', 'to_date',
    'to_number', 'to_timestamp', 'trim', 'trunc', 'upper',
    # Type names of a cast, and the keywords a parenthesis may follow.
    'char', 'date', 'integer', 'number', 'nvarchar2', 'timestamp',
    'varchar', 'varchar2', 'and', 'or', 'not', 'in', 'as', 'when', 'then',
    'else', 'between', 'like', 'is'))
FILTER_FORBIDDEN = re.compile(
    r'\b(select|from|with|union|intersect|minus|except|insert|update|'
    r'delete|merge|into|begin|declare|execute|call|table|lateral|model)\b',
    flags=re.I)
FILTER_CALL = re.compile(r'\b([a-z_][\w$#]*)\s*\(', flags=re.I)
def _filter_code(where):
    """Get a filter with its literals as '' and quoted names as x, or the
    reason it can not be read so: a comment, a q-quoted literal or an
    unclosed quote."""
    text = str(where or '')
    parts, position = [], 0
    for kind, start, end, closed in tokens(text):
        if kind == 'comment':
            return None, 'Comments are not allowed in a filter.'
        if not closed:
            return None, 'A quote of the filter is not closed.'
        if kind == 'q_literal':
            return None, 'Q-quoted literals are not allowed in a filter.'
        parts.append(text[position:start])
        parts.append("''" if kind == 'literal' else 'x')
        position = end
    parts.append(text[position:])
    return ''.join(parts), None


def plain_filter(where):
    """Tell why a `where` on a dataset is more than a plain filter of its
    columns (None when it is one): a subquery, another object (a `.` or
    `@`), more than one statement, or a function outside FILTER_FUNCTIONS
    could read or change what the dataset does not hold.
    """
    code, problem = _filter_code(where)
    if problem:
        return problem
    code = re.sub(r'\b\d+(\.\d+)?(e[+-]?\d+)?\b', '0', code, flags=re.I)
    if re.search(r'[;@.]', code):
        return 'Only the columns of the dataset may be named.'
    found = FILTER_FORBIDDEN.search(code)
    if found:
        return f'{found.group(1).upper()} is not allowed in a filter.'
    for call in FILTER_CALL.finditer(code):
        if call.group(1).lower() not in FILTER_FUNCTIONS:
            return f'Function {call.group(1).upper()} is not allowed.'
    return None


def guard_query(statement, not_query):
    """Tell why a statement may not be run as a read-only preview.

    Only one plain query passes: no FOR UPDATE lock, no PL/SQL declared in a
    WITH clause and nothing after the first statement. run_read_only() also
    runs it read only, so DML in the same transaction is refused by Oracle; a
    function with an autonomous transaction is the one thing neither check can
    stop.

    Parameters
    ----------
    statement : str
    not_query : str
        The answer for a statement that is not a query.

    Returns
    -------
    problem : str or None
    """
    if first_keyword(statement) not in QUERY_KEYWORDS:
        return not_query
    code = code_only(strip_query(statement))
    if re.match(r'[\s(]*with\s+(function|procedure)\b', code, flags=re.I):
        return 'PL/SQL declared in a WITH clause is not allowed.'
    if ';' in code:
        return 'Only one statement is allowed.'
    if re.search(r'\bfor\s+update\b', code, flags=re.I):
        return 'FOR UPDATE is not allowed: it locks rows.'
    return None


def run_read_only(statement, params, timeout, timeout_option, rows=1):
    """Run a guarded query read only and get its first rows.

    The connection is the pool's own driver connection, so its timeout is put
    back and the read-only transaction is always rolled back. A statement
    interrupted by the timeout leaves the connection unusable, so after any
    failure it is dropped from the pool.

    Parameters
    ----------
    statement : str
    params : dict
        Bind values.
    timeout : float
        Seconds before the statement is stopped.
    timeout_option : str
        The option setting the timeout, named in the TimeoutError.
    rows : int
        Rows fetched at most.

    Returns
    -------
    description : list
        The cursor's description.
    rows : list of tuple
        LOBs read.
    elapsed : int
        Milliseconds the statement and the fetch took.
    """
    connection = db.engine.raw_connection()
    driver = (getattr(connection, 'dbapi_connection', None)
              or connection.connection)
    previous = driver.call_timeout
    failed = False
    try:
        driver.rollback()
        driver.call_timeout = int(float(timeout) * 1000)
        cursor = driver.cursor()
        cursor.execute('set transaction read only')
        started = time.monotonic()
        cursor.execute(statement, params)
        fetched = cursor.fetchmany(rows)
        elapsed = round((time.monotonic() - started) * 1000)
        fetched = [tuple(_read_lob(item) for item in row) for row in fetched]
        return list(cursor.description or []), fetched, elapsed
    except Exception as error:
        failed = True
        if 'DPY-4024' in str(error):
            raise TimeoutError(f'Stopped after {timeout} s '
                               f'({timeout_option}).') from error
        raise
    finally:
        try:
            driver.rollback()
            driver.call_timeout = previous
        except Exception:
            failed = True
        if failed:
            connection.invalidate()
        connection.close()


def _read_lob(value):
    read = getattr(value, 'read', None)
    return read() if read else value


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
                         text_error='', attachment_rows=0,
                         evaluate_value=0)
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
    used = {case_id for _, _, case_id in find_case_ids(statement)}
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
