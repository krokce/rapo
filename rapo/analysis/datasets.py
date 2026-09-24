"""Resolves the datasets of a control run to SQL.

A dataset is named by the Results column it stands for:
- `result_a`/`result_b`: the discrepancies the run saved, from `rapo_resa_`/
  `rapo_resb_<name>` of a REC, or `rapo_rest_<name>` of any other type
  (either side), filtered on the indexed `rapo_process_id`. The `Match` rows a
  REC saves with `need_recons_*` are left out, as the run's error number
  does not count them.
- `fetched_a`/`fetched_b`: the records the run read from its datasource, as
  the engine selects them (`Parser.parse_select*`) for the run's window. The
  select is built from the *current* configuration, so a control changed
  after the run may give other records (`stale`). A chain-rule side reads the
  upstream run that the puller pulled. A REP saves exactly what it fetched,
  so its `fetched_a` is its result table.
"""

import datetime as dt
import math

import sqlalchemy as sa

from ..database import db
from ..core import sqlcheck
from ..core.control import Control
from .frame import DATETIME, NUMERIC, column_kind


MATCH = 'Match'
DATASETS = ('fetched_a', 'fetched_b', 'result_a', 'result_b')


class DatasetError(ValueError):
    """The dataset does not exist for this run."""


def resolve(process_id, dataset):
    """Get the SQL and the description of a run's dataset.

    Returns
    -------
    sql : str
        The select, with its literals inline.
    meta : dict
        Run, control and dataset facts shown by the analysis page.
    """
    if dataset not in DATASETS:
        raise DatasetError(f'Unknown dataset {dataset}')
    try:
        control = Control(process_id=process_id)
    except ValueError as error:
        raise DatasetError(str(error))
    kind, side = dataset.split('_')
    run = control.result
    if control.is_report and kind == 'fetched':
        if side == 'b':
            raise DatasetError('A report has no side B')
        kind = 'result'
    if kind == 'result':
        sql, table_name = _result_select(control, side)
        total = count(sql)
        exact = True
    else:
        select, table_name = _fetched_select(control, side)
        sql = db.compile(select).string
        total = _fetched_number(control, side)
        exact = False
    meta = {
        'process_id': control.process_id,
        'control_id': control.id,
        'control_name': control.name,
        'control_type': control.type,
        'control_engine': control.engine,
        'status': control.status,
        'date_from': control.date_from,
        'date_to': control.date_to,
        'start_date': control.start_date,
        'end_date': control.end_date,
        'dataset': dataset,
        'kind': kind,
        'side': side.upper() if control.is_reconciliation
        or control.is_comparison else None,
        'table_name': table_name.upper() if table_name else None,
        'total': total,
        'total_exact': exact,
        'stale': kind == 'fetched' and _changed_since(control, run),
    }
    return sql, meta


def sql_text(process_id, dataset):
    """Get the formatted SQL of a run's dataset, for the clipboard."""
    sql, meta = resolve(process_id, dataset)
    return display(sql, meta), meta


def display(sql, meta):
    """Get the dataset's SQL formatted for the user.

    Only for showing: the formatter lower-cases identifiers, which would
    break a quoted mixed-case name, so the raw statement is the one run.
    """
    if meta['kind'] == 'result':
        return sql
    return db.formatter(sql)


def _result_select(control, side):
    if control.is_reconciliation:
        name = control.output_name_a if side == 'a' else control.output_name_b
    else:
        name = control.output_name
    if not db.exists(name):
        raise DatasetError(f'Result table {name.upper()} does not exist')
    sql = (f'select * from {name.upper()} '
           f'where RAPO_PROCESS_ID = {int(control.process_id)}')
    if control.is_reconciliation:
        sql += f" and RAPO_RESULT_TYPE != '{MATCH}'"
    return sql, name


def _fetched_select(control, side):
    if control.is_analysis:
        if side == 'b':
            raise DatasetError('An analysis has no side B')
        control.upstream_pids = _upstream_pids(control)
        control.source_table = control.parser.parse_source_table()
        return control.parser.parse_select(), control.source_name
    control.upstream_pids = _upstream_pids(control)
    if side == 'a':
        control.source_table_a = control.parser.parse_source_table_a()
        return control.parser.parse_select_a(), control.source_name_a
    control.source_table_b = control.parser.parse_source_table_b()
    return control.parser.parse_select_b(), control.source_name_b


def _upstream_pids(control):
    """Find the upstream runs a chain-rule run read, by side.

    The puller does not record them. They are the `D` runs of the upstream
    control for the same window, started after the puller was initiated and
    before it started; failing that, the latest such run of that window.
    """
    pids = {}
    log = db.tables.log
    config = db.tables.config
    run = control.result
    for upstream in control.upstreams:
        select = (
            sa.select(log.c.process_id, log.c.added)
            .join(config, config.c.control_id == log.c.control_id)
            .where(config.c.control_name == upstream['control_name'],
                   log.c.status == 'D',
                   log.c.date_from == control.date_from,
                   log.c.date_to == control.date_to)
            .order_by(log.c.process_id.desc())
        )
        runs = db.execute(select, as_table=True)
        if not runs:
            raise DatasetError(
                f"No finished run of {upstream['control_name']} for this "
                'window, whose results this chain-rule read')
        begin = run.get('added')
        end = run.get('start_date') or run.get('end_date')
        within = [item for item in runs
                  if begin and end and item['added']
                  and begin <= item['added'] <= end]
        pids[upstream['side']] = (within or runs)[0]['process_id']
    return pids


def count(sql):
    return db.execute(sa.text(f'select count(*) from ({sql})'),
                      as_scalar=True)


def _fetched_number(control, side):
    if control.is_analysis:
        return control.fetched_number
    if side == 'a':
        return control.fetched_number_a
    return control.fetched_number_b


def _changed_since(control, run):
    """Whether the configuration was saved after the run started.

    `updated_date` is stamped with the database clock and the run's dates
    with the application clock, so the difference between them is removed.
    """
    started = run.get('start_date') or run.get('added')
    updated = control.config.get('updated_date')
    if not started or not updated:
        return False
    database_now = db.execute(sa.select(sa.func.sysdate()), as_scalar=True)
    skew = database_now - dt.datetime.now()
    return updated - skew > started


def trend(process_id, dataset, limit=30):
    """Get the fetched and discrepancy counts of a dataset's side over runs.

    A period (the days of the run's date_from and date_to) is often run more
    than once, e.g. by manual runs whose windows start at other times of the
    day, so it is counted once, by its last done run (the highest process
    ID). The period of the run itself is shown by that run, even when it was
    run again later.

    Returns
    -------
    trend : dict
        {side, process_id, runs: [{process_id, date_from, date_to,
        start_date, fetched, discrepancies, error_level}]}, the latest
        `limit` periods in the order of their dates.
    """
    if dataset not in DATASETS:
        raise DatasetError(f'Unknown dataset {dataset}')
    log = db.tables.log
    run = db.execute(log.select().where(log.c.process_id == process_id),
                     as_dict=True)
    if not run:
        raise DatasetError(f'no process with ID {process_id} found')
    config = db.tables.config
    control_type = db.execute(
        sa.select(config.c.control_type)
        .where(config.c.control_id == run['control_id']), as_scalar=True)
    side = dataset.split('_')[1]
    if control_type in ('REC', 'CMP'):
        fields = (f'fetched_number_{side}', f'error_number_{side}',
                  f'error_level_{side}')
    else:
        fields = ('fetched_number', 'error_number', 'error_level')
    columns = [log.c.process_id, log.c.date_from, log.c.date_to,
               log.c.start_date, log.c.status] + \
        [log.c[field] for field in fields]
    day_from = sa.func.trunc(log.c.date_from)
    day_to = sa.func.trunc(log.c.date_to)
    same_period = sa.and_(day_from == sa.func.trunc(sa.literal(run['date_from'])),
                          day_to == sa.func.trunc(sa.literal(run['date_to'])))
    last = sa.func.row_number().over(
        partition_by=(day_from, day_to),
        order_by=log.c.process_id.desc()).label('last')
    periods = (
        sa.select(*columns, last)
        .where(log.c.control_id == run['control_id'], log.c.status == 'D',
               sa.not_(same_period))
        .subquery())
    select = (sa.select(*[periods.c[column.name] for column in columns])
              .where(periods.c.last == 1)
              .order_by(periods.c.date_from.desc(), periods.c.date_to.desc())
              .limit(max(limit - 1, 1)))
    rows = db.execute(select, as_table=True) + [dict(run)]
    rows.sort(key=lambda row: (row['date_from'] or dt.datetime.min,
                               row['date_to'] or dt.datetime.min))
    rows = rows[-limit:]
    return {'side': side.upper() if control_type in ('REC', 'CMP') else None,
            'process_id': process_id,
            'runs': [{'process_id': row['process_id'],
                      'date_from': row['date_from'],
                      'date_to': row['date_to'],
                      'start_date': row['start_date'],
                      'status': row['status'],
                      'fetched': row[fields[0]],
                      'discrepancies': row[fields[1]],
                      'error_level': row[fields[2]]} for row in rows]}


def targets(process_id, dataset):
    """Get the datasets a run's dataset is usually compared with.

    Returns
    -------
    targets : list of dict
        {key, label, process_id, dataset}: the other kind of the same side
        (discrepancies against what was fetched), the same dataset of the
        previous done run, and the same kind of the other side.
    """
    if dataset not in DATASETS:
        raise DatasetError(f'Unknown dataset {dataset}')
    log = db.tables.log
    config = db.tables.config
    run = db.execute(log.select().where(log.c.process_id == process_id),
                     as_dict=True)
    if not run:
        raise DatasetError(f'no process with ID {process_id} found')
    control_type = db.execute(
        sa.select(config.c.control_type)
        .where(config.c.control_id == run['control_id']), as_scalar=True)
    kind, side = dataset.split('_')
    sided = control_type in ('REC', 'CMP')
    result = []
    if control_type == 'REP':
        pass
    elif kind == 'result':
        result.append({'key': 'source', 'process_id': process_id,
                       'dataset': f'fetched_{side}',
                       'label': f"Fetched{' ' + side.upper() if sided else ''}"
                                ' of this run'})
    else:
        result.append({'key': 'source', 'process_id': process_id,
                       'dataset': f'result_{side}',
                       'label': f"Discrepancies{' ' + side.upper() if sided else ''}"
                                ' of this run'})
    previous = db.execute(
        sa.select(log.c.process_id, log.c.date_from, log.c.date_to)
        .where(log.c.control_id == run['control_id'], log.c.status == 'D',
               log.c.process_id < process_id)
        .order_by(log.c.process_id.desc()).limit(1), as_dict=True)
    if previous:
        result.append({'key': 'previous', 'process_id': previous['process_id'],
                       'dataset': dataset,
                       'label': 'Previous run, PID '
                                f"{previous['process_id']} "
                                f"({previous['date_from']:%Y-%m-%d})"})
    other = 'b' if side == 'a' else 'a'
    if sided and not (control_type == 'CMP' and kind == 'result'):
        name = 'Discrepancies' if kind == 'result' else 'Fetched'
        result.append({'key': 'other_side', 'process_id': process_id,
                       'dataset': f'{kind}_{other}',
                       'label': f'{name} {other.upper()} of this run'})
    return result


def control_runs(control_name, limit=50):
    """Get the latest done runs of a control, for picking one to compare."""
    log = db.tables.log
    config = db.tables.config
    select = (
        sa.select(log.c.process_id, log.c.date_from, log.c.date_to,
                  log.c.start_date, config.c.control_type,
                  log.c.fetched_number, log.c.fetched_number_a,
                  log.c.fetched_number_b, log.c.error_number,
                  log.c.error_number_a, log.c.error_number_b)
        .join(config, config.c.control_id == log.c.control_id)
        .where(config.c.control_name == control_name, log.c.status == 'D')
        .order_by(log.c.process_id.desc()).limit(limit))
    return db.execute(select, as_table=True)


def counterpart(meta, columns, row, limit=100):
    """Get the records of the other side of a reconciliation for a row.

    The row's correlation key is evaluated from its values with the
    control's own expressions (a formula field too), then looked up in the
    other side's result table of the run and in its datasource for the run's
    window.

    Parameters
    ----------
    meta : dict
        The session's dataset description.
    columns : list of dict
        name and kind of the row's values, in order.
    row : list
        The values, as the viewer has them.
    """
    if meta['control_type'] != 'REC':
        raise DatasetError('Counterparts exist for reconciliations only')
    if len(row) != len(columns):
        raise DatasetError('The row does not match the dataset')
    control = Control(process_id=meta['process_id'])
    own = meta['side'].lower()
    other = 'b' if own == 'a' else 'a'
    keys = control.rule_config.get('correlation_config') or []
    if not keys:
        raise DatasetError('The control has no correlation fields')
    expressions_own, expressions_other = [], []
    for item in keys:
        field_own, field_other = item[f'field_{own}'], item[f'field_{other}']
        if not item.get('formula_mode'):
            field_own = f'{own}."{str(field_own).upper()}"'
            field_other = f'{other}."{str(field_other).upper()}"'
        expressions_own.append(field_own)
        expressions_other.append(field_other)
    literals = []
    for column, value in zip(columns, row):
        if isinstance(value, str) and len(value) > 4000:
            value = None
        literals.append(f'{_literal(value, column["kind"])} as '
                        f'"{column["name"].upper()}"')
    evaluate = (f'select {", ".join(expressions_own)} '
                f'from (select {", ".join(literals)} from dual) {own}')
    try:
        values = list(db.execute(sa.text(evaluate), as_one=True))
    except Exception as error:
        raise DatasetError(f'The correlation key can not be evaluated: '
                           f'{_oracle_message(error)}')
    conditions = []
    for expression, value in zip(expressions_other, values):
        if value is None:
            conditions.append(f'{expression} is null')
        else:
            conditions.append(f'{expression} = {_python_literal(value)}')
    condition = ' and '.join(conditions)
    result = {'side': own.upper(), 'other_side': other.upper(),
              'keys': [{'expression': expression, 'value': value}
                       for expression, value in zip(expressions_own, values)]}
    table = (control.output_name_a if other == 'a'
             else control.output_name_b)
    if db.exists(table):
        sql = (f'select * from {table.upper()} {other} '
               f'where {other}.rapo_process_id = {int(meta["process_id"])} '
               f'and {condition}')
        result['results'] = _lookup(sql, limit)
        result['results']['table'] = table.upper()
    else:
        result['results'] = {'table': table.upper(), 'columns': [],
                             'rows': [], 'more': False,
                             'error': 'The result table does not exist'}
    try:
        base, _ = resolve(meta['process_id'], f'fetched_{other}')
        sql = f'select * from ({base}) {other} where {condition}'
        result['source'] = _lookup(sql, limit)
    except Exception as error:
        result['source'] = {'columns': [], 'rows': [], 'more': False,
                            'error': _oracle_message(error)}
    return result


def _lookup(sql, limit):
    """Get the first rows of a select as JSON-safe lists."""
    from .frame import to_json
    connection = db.engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(f'select * from ({sql}) where rownum <= {limit + 1}')
        names = [item[0].lower() for item in cursor.description]
        rows = cursor.fetchall()
    finally:
        connection.close()
    return {'columns': names,
            'rows': [[to_json(_plain(value)) for value in row]
                     for row in rows[:limit]],
            'more': len(rows) > limit}


def _plain(value):
    read = getattr(value, 'read', None)
    return read() if read else value


def _python_literal(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        return _literal(value, NUMERIC)
    if isinstance(value, dt.datetime):
        return _literal(value.isoformat(), DATETIME)
    return _text_literal(value)


def _oracle_message(error):
    text = str(getattr(error, 'orig', None) or error).strip()
    return text.splitlines()[0] if text else type(error).__name__


def pushdown(sql, filters=None, search=None, where=None, shown=None):
    """Get the dataset's SQL with viewer filters, a search and a WHERE applied.

    The filters and the search become literal predicates (quotes doubled,
    numbers checked, dates as to_date), so the statement is the one a user
    can copy. `where` is a condition of the user's own over the dataset's
    columns; the whole statement is parsed by Oracle before it is used.

    Returns
    -------
    sql : str
        The statement to run.
    shown : str
        The same around `shown`, the formatted dataset SQL, for the user.
    """
    shown = shown or sql
    columns = describe(sql)
    names = {column['name'].lower(): column for column in columns}
    predicates = []
    for item in filters or []:
        predicates.append(_predicate(item, names))
    if search:
        term = _like_literal(f'%{search}%')
        texts = [f'upper({_text_expression(column)}) like upper({term}) '
                 "escape '\\'" for column in columns]
        if texts:
            predicates.append('(' + '\n        or '.join(texts) + ')')
    if where and where.strip():
        condition = where.strip().rstrip(';').strip()
        if ';' in condition:
            raise DatasetError('The SQL filter must be a single condition')
        predicates.append(f'({condition})')
    if not predicates:
        return sql, shown
    condition = '\n   and '.join(predicates)
    result = f'select *\n  from ({sql}) q\n where {condition}'
    check = sqlcheck.parse(result)
    if not check['valid']:
        raise DatasetError(f"The filter is not valid SQL: {check['error']}")
    indented = shown.replace('\n', '\n        ')
    return result, f'select *\n  from ({indented}) q\n where {condition}'



def describe(sql):
    """Get the columns of a select, parsed by Oracle, with their kinds."""
    check = sqlcheck.parse(f'select * from ({sql}) q where 1 = 0')
    if not check['valid']:
        raise DatasetError(f"The dataset can not be parsed: {check['error']}")
    return [{'name': column['name'], 'kind': column_kind(column['type'])}
            for column in check['columns']]


def check_where(process_id, dataset, where):
    """Parse a SQL filter against a dataset, answering like validate-sql."""
    try:
        sql, meta = resolve(process_id, dataset)
        statement, _ = pushdown(sql, where=where)
    except DatasetError as error:
        return {'valid': False, 'error': str(error)}
    result = sqlcheck.parse(statement)
    if result['valid']:
        result['message'] = 'OK — the condition compiles'
    return result


def _column(column):
    return 'q."' + column['name'].replace('"', '') + '"'


def _text_expression(column):
    if column['kind'] == DATETIME:
        return f"to_char({_column(column)}, 'YYYY-MM-DD HH24:MI:SS')"
    if column['kind'] == NUMERIC:
        return f'to_char({_column(column)})'
    return _column(column)


def _like_literal(pattern):
    """Get a LIKE pattern literal whose % and _ inside the value are escaped."""
    head, body, tail = pattern[:1], pattern[1:-1], pattern[-1:]
    if head != '%':
        head, body = '', pattern[:-1]
    body = body.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return _text_literal(head + body + tail)


def _text_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _literal(value, kind):
    if value is None:
        return 'null'
    if kind == NUMERIC:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise DatasetError(f'{value!r} is not a number')
        if math.isnan(number) or math.isinf(number):
            raise DatasetError(f'{value!r} is not a number')
        if isinstance(value, int) or number.is_integer() and \
                abs(number) < 1e15:
            return str(int(value) if isinstance(value, int) else int(number))
        return repr(number)
    if kind == DATETIME:
        try:
            moment = dt.datetime.fromisoformat(str(value).replace(' ', 'T'))
        except ValueError:
            raise DatasetError(f'{value!r} is not a date')
        return (f"to_date('{moment:%Y-%m-%d %H:%M:%S}', "
                "'YYYY-MM-DD HH24:MI:SS')")
    return _text_literal(value)


def _predicate(item, names):
    op = item.get('op')
    if op == 'duplicated':
        raise DatasetError('The duplicate rows filter can only be applied to '
                           'the sample, not in the database')
    column = names.get(str(item.get('column', '')).lower())
    if column is None:
        raise DatasetError(f"Unknown column {item.get('column')}")
    name, kind = _column(column), column['kind']
    value = item.get('value')
    if op == 'null' or (op == 'eq' and value is None):
        return f'{name} is null'
    if op == 'notnull' or (op == 'ne' and value is None):
        return f'{name} is not null'
    if op == 'eq':
        return f'{name} = {_literal(value, kind)}'
    if op == 'ne':
        return f'({name} != {_literal(value, kind)} or {name} is null)'
    if op == 'in':
        present = [item for item in value or [] if item is not None]
        parts = []
        if present:
            literals = ', '.join(_literal(item, kind) for item in present)
            parts.append(f'{name} in ({literals})')
        if len(present) < len(value or []):
            parts.append(f'{name} is null')
        return '(' + ' or '.join(parts or ['1 = 0']) + ')'
    if op in ('contains', 'starts'):
        pattern = f'%{value}%' if op == 'contains' else f'{value}%'
        return (f'upper({_text_expression(column)}) like '
                f"upper({_like_literal(pattern)}) escape '\\'")
    if op == 'range':
        value = value or {}
        parts = []
        if value.get('min') is not None:
            parts.append(f"{name} >= {_literal(value['min'], kind)}")
        if value.get('max') is not None:
            sign = '<=' if value.get('max_inclusive', True) else '<'
            parts.append(f"{name} {sign} {_literal(value['max'], kind)}")
        return '(' + ' and '.join(parts or [f'{name} is not null']) + ')'
    raise DatasetError(f'Unknown filter {op}')
