"""Contains the editing of view datasources from the control editor.

The only code that writes the DDL of a view. A view of the own schema is
edited by its query (user_views.text) only: the rest of its DDL (name, column
alias list, editioning, WITH READ ONLY / CHECK OPTION) comes from
dbms_metadata.get_ddl and is kept as it is, so nothing but a query can be
written into the CREATE statement.

- A check creates the view under a scratch name (rapo_temp_view_<16 hex
  digits>), reads its columns and drops it, so it finds every error a real
  CREATE would, and the columns the view would have.
- The views are created without FORCE: a CREATE that fails leaves the old view
  untouched, and a replace is refused unless the check passes.
- The previous DDL of a replaced view is written to the server log, the only
  copy kept.
- A preview runs the edited query read only (sqlcheck.run_read_only).

Statements go through a raw connection, never sa.text(), which would take a
colon inside the view's text (e.g. 'HH24:MI') for a bind parameter.
"""

import datetime as dt
import decimal
import re
import uuid

import sqlalchemy as sa

from .. import options
from ..database import db
from ..logger import logger
from ..reader import reader
from . import sqlcheck


# temp.py lists and drops what a check could not drop itself.
SCRATCH_PREFIX = 'RAPO_TEMP_VIEW_'
NOT_QUERY = 'The view SQL must be a query (select or with).'
# How dbms_metadata.get_ddl starts a view: options, name, column alias list
# and clauses such as BEQUEATH or DEFAULT COLLATION before AS.
HEADER = re.compile(
    r'\s*CREATE\s+OR\s+REPLACE\s+(?P<options>(?:[A-Z]+\s+)*?)VIEW\s+'
    r'(?P<name>"[^"]+"(?:\."[^"]+")?)\s*(?P<columns>\(.*\))?'
    r'(?P<rest>.*?)\bAS\s*', flags=re.S | re.I)
PLAIN_NAME = re.compile(r'[A-Z][A-Z0-9_$#]*')
SOURCE_TYPES = ('TABLE', 'VIEW', 'MATERIALIZED VIEW')


class ViewError(Exception):
    """A view request that can not be done, with the HTTP status to answer."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def enabled():
    """Check whether [VIEWS] edit allows editing views."""
    value = options.get('VIEWS', 'edit')
    if isinstance(value, str):
        return value.strip().lower() not in ('false', 'no', 'off', '0')
    return bool(value)


def read_view(name):
    """Get a view of the own schema as the editor needs it.

    Returns
    -------
    view : dict
        name, status, last_ddl_time, body (the query), editable and reason
        (why not), aliases (the column names of the view's column alias
        list when it renames the query's columns, else None), columns [{column_name, data_type}], errors [{line,
        position, text}], dependencies {completion name: [column]} of the
        tables and views it reads, dependents: controls [name] reading it and
        objects [{owner, name, type}] depending on it.
    """
    view = _load(name)
    problem = sqlcheck.guard_query(view['body'], NOT_QUERY)
    return {
        'name': view['name'],
        'status': view['status'],
        'last_ddl_time': view['last_ddl_time'],
        'body': view['body'],
        'editable': problem is None and view['header'] is not None,
        'aliases': _aliases(view),
        'reason': problem or view['split_error'],
        'columns': [{'column_name': column['column_name'],
                     'data_type': _type_text(column)}
                    for column in view['columns']],
        'errors': _errors(view['name']),
        'dependencies': _dependencies(view['name']),
        'dependents': {'controls': _controls(view['name']),
                       'objects': _objects(view['name'])},
    }


def check_view(name, body, view=None):
    """Check a new query of a view by creating it under a scratch name.

    Returns
    -------
    result : dict
        valid; error (and error_line/error_position in the query when Oracle
        tells) when not; else the new columns [{column_name, data_type}] and
        diff {added: [name], removed: [name], retyped: [{column_name, old,
        new}]} against the view's columns.
    """
    _require_enabled()
    view = view or _load(name)
    body = _clean(body)
    problem = sqlcheck.guard_query(body, NOT_QUERY)
    if problem:
        return {'valid': False, 'error': problem}
    if view['header'] is None:
        return {'valid': False, 'error': view['split_error']}
    scratch = f'{SCRATCH_PREFIX}{uuid.uuid4().hex[:16].upper()}'
    header = _header(view, f'"{scratch}"')
    statement = f'{header}{body}{_trailer(view, scratch=True)}'
    try:
        _ddl(statement)
    except Exception as error:
        result = _error(error, len(header))
        aliases = _aliases(view)
        if aliases and 'ORA-01730' in result['error']:
            result['error'] += (f'. The view names its columns in a list '
                                f'({", ".join(aliases)}), which must name '
                                f'each column of the query.')
        return result
    try:
        columns = reader.read_schema_columns([(None, scratch)])
        columns = columns.get((None, scratch), [])
        status = db.execute(sa.text(
            "select status from user_objects where object_name = :name "
            "and object_type = 'VIEW'").bindparams(name=scratch),
            as_scalar=True)
    finally:
        try:
            _ddl(f'DROP VIEW "{scratch}"')
        except Exception as error:
            logger.warning(f'Scratch view {scratch} cannot be dropped: '
                           f'{type(error).__name__}: {error}')
    if status != 'VALID':
        return {'valid': False, 'error': f'The view would be {status}.'}
    return {'valid': True,
            'columns': [{'column_name': column['column_name'],
                         'data_type': _type_text(column)}
                        for column in columns],
            'diff': _diff(view['columns'], columns)}


def compile_view(name, body, expected_ddl_time=None, force=False,
                 control_name=None):
    """Replace the query of a view, refused while the new one is invalid.

    Parameters
    ----------
    name : str
    body : str
        The new query.
    expected_ddl_time : str, optional
        The view's last_ddl_time the editor loaded: a view changed since then
        is not replaced (409) unless `force`.
    force : bool
    control_name : str, optional
        The control whose editor asked, for the server log.

    Returns
    -------
    view : dict
        read_view() of the replaced view, plus the diff of the check.
    """
    _require_enabled()
    view = _load(name)
    if expected_ddl_time and not force:
        expected = dt.datetime.fromisoformat(str(expected_ddl_time))
        if view['last_ddl_time'] != expected:
            changed = f"{view['last_ddl_time']:%d.%m.%Y %H:%M:%S}"
            raise ViewError(f'The view was changed at {changed}.', 409)
    body = _clean(body)
    result = check_view(name, body, view)
    if not result['valid']:
        raise ViewError(f'The view is not replaced: {result["error"]}')
    source = f' from the editor of {control_name}' if control_name else ''
    logger.info(f'View {view["name"]} is replaced{source}. Previous DDL:\n'
                f'{view["ddl"].strip()}')
    _ddl(f'{_header(view)}{body}{_trailer(view)}')
    logger.info(f'View {view["name"]} replaced')
    answer = read_view(view['name'])
    answer['diff'] = result['diff']
    return answer


def preview_view(body, rows=10):
    """Run a query of a view read only and get its first rows.

    Returns
    -------
    preview : dict
        columns [{name, type}], rows [[value]], elapsed (ms), limit (the rows
        asked for, after the cap), more (whether the limit was reached).
    """
    _require_enabled()
    body = _clean(body)
    problem = sqlcheck.guard_query(body, NOT_QUERY)
    if problem:
        raise ViewError(problem)
    limit = int(options.get('VIEWS', 'preview_max_rows'))
    rows = max(1, min(int(rows or 10), limit))
    timeout = options.get('VIEWS', 'preview_timeout')
    statement = f'select * from (\n{body}\n) fetch first :n rows only'
    try:
        description, fetched, elapsed = sqlcheck.run_read_only(
            statement, {'n': rows}, timeout, '[VIEWS] preview_timeout',
            rows=rows)
    except TimeoutError as error:
        raise ViewError(str(error))
    except Exception as error:
        raise ViewError(_message(error))
    columns = [{'name': column[0],
                'type': str(column[1]).split()[-1].rstrip('>')
                .replace('DB_TYPE_', '')}
               for column in description]
    return {'columns': columns,
            'rows': [[_to_json(value) for value in row] for row in fetched],
            'elapsed': elapsed, 'limit': rows, 'more': len(fetched) == rows}


def format_body(body):
    """Format a query of a view in rapo's style (db.formatter)."""
    return db.format(_clean(body))


def read_object_columns(names):
    """Get the columns of tables and views for the editor's autocomplete.

    Parameters
    ----------
    names : iterable of str
        Names as written in a query, OWNER.NAME or NAME, quoted or not.

    Returns
    -------
    columns : dict
        {name as given: [column completion]}; names without columns absent.
    """
    keys = {}
    for name in names:
        parts = [part.strip('"') if part.startswith('"') else part.upper()
                 for part in str(name).strip().split('.')]
        if len(parts) == 1:
            keys[name] = (None, parts[0])
        elif len(parts) == 2:
            keys[name] = (parts[0], parts[1])
    found = reader.read_schema_columns(set(keys.values())) if keys else {}
    own = db.execute("select sys_context('userenv', 'current_schema') "
                     "from dual", as_scalar=True)
    answer = {}
    for name, key in keys.items():
        columns = found.get(key) or found.get((None, key[1]) if key[0] == own
                                              else key)
        if columns:
            answer[name] = [_completion(column['column_name'])
                            for column in columns]
    return answer


def _require_enabled():
    if not enabled():
        raise ViewError('Editing views is switched off on this server '
                        '([VIEWS] edit).', 403)


def _load(name):
    """Read a view of the own schema with its DDL split around its query."""
    name = str(name or '').strip()
    row = db.execute(sa.text(
        "select o.object_name, o.status, o.last_ddl_time "
        "from user_objects o where o.object_type = 'VIEW' "
        "and o.object_name in (:name, upper(:name)) "
        "order by case when o.object_name = :name then 0 else 1 end"
    ).bindparams(name=name), as_dict=True)
    if not row:
        raise ViewError(f'{name.upper()} is not a view of the own schema.',
                        404)
    name = row['object_name']
    connection = db.engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('select text from user_views where view_name = :name',
                       {'name': name})
        body = cursor.fetchone()[0] or ''
        cursor.execute("select dbms_metadata.get_ddl('VIEW', :name) "
                       "from dual", {'name': name})
        ddl = cursor.fetchone()[0]
        ddl = ddl.read() if hasattr(ddl, 'read') else ddl
    finally:
        connection.close()
    columns = reader.read_schema_columns([(None, name)]).get((None, name), [])
    view = {'name': name, 'status': row['status'],
            'last_ddl_time': row['last_ddl_time'], 'body': body, 'ddl': ddl,
            'columns': columns, 'header': None, 'trailer': '',
            'split_error': None}
    start = ddl.find(body) if body else -1
    match = HEADER.fullmatch(ddl[:start]) if start >= 0 else None
    if not match:
        view['split_error'] = ('The DDL of this view can not be split around '
                               'its query, so it is not edited here.')
        return view
    view['header'] = match
    view['trailer'] = ddl[start + len(body):].rstrip()
    view['aliased'] = _aliased(body, columns)
    return view


def _aliased(body, columns):
    """Check whether the column alias list renames the query's columns.

    get_ddl always writes the list. It is kept only when the query's own
    column names differ, so that a query with a column more or less is not
    refused for the list's length.
    """
    if sqlcheck.guard_query(body, NOT_QUERY):
        return True
    parsed = sqlcheck.parse(sqlcheck.strip_query(body))
    if not parsed['valid']:
        return False
    return ([column['name'] for column in parsed['columns']]
            != [column['column_name'] for column in columns])


def _aliases(view):
    if view['header'] is None or not view['aliased']:
        return None
    return [column['column_name'] for column in view['columns']]


def _header(view, name=None):
    """Build CREATE OR REPLACE ... VIEW <name> [(<aliases>)] ... AS, no FORCE."""
    match = view['header']
    words = [word for word in match.group('options').split()
             if word.upper() != 'FORCE']
    columns = match.group('columns') if view['aliased'] else None
    parts = ['CREATE OR REPLACE', *words, 'VIEW', name or match.group('name')]
    if columns:
        parts.append(columns)
    rest = match.group('rest').strip()
    if rest:
        parts.append(rest)
    return ' '.join(parts) + ' AS\n'


def _trailer(view, scratch=False):
    """The clauses after the query (WITH READ ONLY / CHECK OPTION).

    A scratch view names no constraint, which would clash with the view's own.
    """
    trailer = view['trailer']
    if scratch:
        trailer = re.sub(r'\s*\bCONSTRAINT\s+"[^"]+"', '', trailer,
                         flags=re.I)
    return f'\n{trailer.strip()}' if trailer.strip() else ''


def _clean(body):
    return sqlcheck.strip_query(str(body or ''))


def _ddl(statement):
    connection = db.engine.raw_connection()
    try:
        connection.cursor().execute(statement)
    finally:
        connection.close()


def _message(error):
    """Oracle's message without the Help line python-oracledb appends."""
    lines = [line for line in str(error).strip().split('\n')
             if not line.startswith('Help:')]
    return '\n'.join(lines).strip()


def _error(error, header_length):
    """The answer of a failed check, with the place in the query if known."""
    result = {'valid': False, 'error': _message(error)}
    offset = getattr(error.args[0], 'offset', 0) if error.args else 0
    if offset and offset > header_length:
        result['error_offset'] = offset - header_length
    return result


def _type_text(column):
    """A column's type as written in DDL, e.g. VARCHAR2(40) or NUMBER(10,2)."""
    kind = column['data_type']
    if kind in ('VARCHAR2', 'NVARCHAR2', 'CHAR', 'NCHAR'):
        return f'{kind}({column["char_length"]})'
    if kind == 'RAW':
        return f'{kind}({column["data_length"]})'
    if kind == 'NUMBER':
        precision, scale = column['data_precision'], column['data_scale']
        if precision is None:
            return 'NUMBER' if scale is None else f'NUMBER(*,{scale})'
        return (f'NUMBER({precision},{scale})' if scale
                else f'NUMBER({precision})')
    return kind


def _diff(old, new):
    old_types = {column['column_name']: _type_text(column) for column in old}
    new_types = {column['column_name']: _type_text(column) for column in new}
    return {
        'added': [name for name in new_types if name not in old_types],
        'removed': [name for name in old_types if name not in new_types],
        'retyped': [{'column_name': name, 'old': old_types[name],
                     'new': new_types[name]}
                    for name in new_types
                    if name in old_types and old_types[name] != new_types[name]],
    }


def _errors(name):
    return db.execute(sa.text(
        "select line, position, text from user_errors "
        "where type = 'VIEW' and name = :name order by sequence"
    ).bindparams(name=name), as_table=True)


def _dependencies(name):
    """Columns of the tables and views the view reads, for autocomplete."""
    rows = db.execute(sa.text(
        "select referenced_owner owner, referenced_name name "
        "from user_dependencies where type = 'VIEW' and name = :name "
        "and referenced_type in ('TABLE', 'VIEW', 'MATERIALIZED VIEW')"
    ).bindparams(name=name), as_table=True)
    own = db.execute("select sys_context('userenv', 'current_schema') "
                     "from dual", as_scalar=True)
    keys = {(None if row['owner'] == own else row['owner'], row['name'])
            for row in rows}
    found = reader.read_schema_columns(keys) if keys else {}
    answer = {}
    for (owner, table), columns in sorted(found.items(),
                                          key=lambda item: str(item[0])):
        label = _completion(table)
        if owner:
            label = f'{_completion(owner)}.{label}'
        answer[label] = [_completion(column['column_name'])
                         for column in columns]
    return answer


def _completion(identifier):
    """How a name is written in a query: as it is, quoted unless plain."""
    if PLAIN_NAME.fullmatch(identifier):
        return identifier
    return f'"{identifier}"'


def _controls(name):
    rows = db.execute(sa.text(
        'select control_name from rapo_config '
        'where upper(source_name) = :name or upper(source_name_a) = :name '
        'or upper(source_name_b) = :name order by control_name'
    ).bindparams(name=name), as_table=True)
    return [row['control_name'] for row in rows]


def _objects(name):
    """Objects of any schema (that this user sees) depending on the view."""
    rows = db.execute(sa.text(
        "select owner, name, type from all_dependencies "
        "where referenced_owner = sys_context('userenv', 'current_schema') "
        "and referenced_name = :name and referenced_type = 'VIEW' "
        "order by owner, type, name"
    ).bindparams(name=name), as_table=True)
    return rows


def _to_json(value):
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%S')
    if isinstance(value, dt.date):
        return value.strftime('%Y-%m-%dT00:00:00')
    if isinstance(value, decimal.Decimal):
        if value == value.to_integral_value():
            # Beyond 2^53 a JavaScript number is no longer exact.
            return int(value) if abs(value) < 2 ** 53 else str(value)
        return float(value)
    if isinstance(value, float):
        return value if value == value and abs(value) != float('inf') else None
    if isinstance(value, (bytes, bytearray)):
        return value.hex().upper()
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)
