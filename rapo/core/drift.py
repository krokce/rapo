"""Schema drift of the result tables of all controls at once.

The editor's check (Executor.diff_output_table) creates each expected table
empty to learn Oracle's types, which is exact but too heavy for a whole
catalogue. This builds the expected columns from the dictionary instead: a
result table is a CTAS copy of plain datasource columns, so their dictionary
types are what the CTAS would create. It mirrors
Executor._prepare_output_columns and compares with the same diff_column rules.

What only a CTAS can type is reported as not checked: CMP output columns that
coalesce A and B, datasource names with {variables}, and datasources over a
database link.

It also finds orphaned result tables, which no run writes any more: those of a
control whose configuration stopped writing them (a reconciliation side whose
output was unticked, a changed control type), and those of no control at all
(a deleted control, or one renamed outside the application).
"""

import json

import sqlalchemy as sa

from ..database import db
from ..reader import reader
from .control import Control, RESULT_PREFIXES, diff_column, output_table_names
from .fields import (
    PROCESS_ID, RESULT_KEY, RESULT_VALUE, RESULT_TYPE, DISCREPANCY_ID,
    DISCREPANCY_DESCRIPTION
)


MANDATORY = {'ANL': [RESULT_KEY, RESULT_VALUE, RESULT_TYPE],
             'REC': [RESULT_TYPE, DISCREPANCY_ID, DISCREPANCY_DESCRIPTION]}


class NotChecked(Exception):
    """The expected schema cannot be told from the dictionary."""


def schema_drift():
    """Get the schema drift and orphaned tables of all controls.

    Returns
    -------
    drift : dict
        controls: {control_id: {level, changes, incompatible, tables,
        orphans, reason}}. level is ok, update (safe changes), recreate
        (incompatible columns), error (the configuration names a column the
        datasource lacks), missing (no result table yet), not_checked, or
        rebuilt (the control drops its tables on every run). orphans are its
        existing tables runs no longer write.
        unowned: [{table, rows, rows_analyzed, oldest}], the result tables of
        no control.
    """
    config = db.tables.config
    select = sa.select(
        config.c.control_id, config.c.control_name, config.c.control_type,
        config.c.with_drop, config.c.need_a, config.c.need_b,
        config.c.source_name, config.c.source_name_a,
        config.c.source_name_b, config.c.source_date_field,
        config.c.source_date_field_a, config.c.source_date_field_b,
        config.c.source_key_field_a, config.c.source_key_field_b,
        config.c.output_table, config.c.output_table_a,
        config.c.output_table_b)
    controls = db.execute(select, as_table=True)
    existing = _existing_result_tables()

    wanted = set()
    for control in controls:
        if control['with_drop'] == 'Y':
            continue
        for table in _result_tables(control):
            wanted.add((None, table.upper()))
        for side in ('', '_a', '_b'):
            key = _table_key(control[f'source_name{side}'])
            if key:
                wanted.add(key)
    columns = reader.read_schema_columns(wanted) if wanted else {}

    answer = {'controls': {}, 'unowned': []}
    owned = set()
    for control in controls:
        names = output_table_names(control['control_name'])
        owned.update(names)
        written = _result_tables(control)
        orphans = [name.upper() for name in names
                   if name not in written and name in existing]
        if control['with_drop'] == 'Y':
            drift = {'level': 'rebuilt', 'changes': 0, 'incompatible': 0,
                     'tables': [], 'reason': None}
        else:
            drift = _checked_drift(control, columns)
        drift['orphans'] = orphans
        answer['controls'][str(control['control_id'])] = drift
    for name, stats in sorted(existing.items()):
        if name not in owned:
            answer['unowned'].append({'table': name.upper(), **stats,
                                      'oldest': _oldest_run(name)})
    return answer


def _checked_drift(control, columns):
    try:
        return _control_drift(control, columns)
    except NotChecked as error:
        return {'level': 'not_checked', 'changes': 0, 'incompatible': 0,
                'tables': [], 'reason': str(error)}
    except KeyError as error:
        return {'level': 'error', 'changes': 0, 'incompatible': 0,
                'tables': [],
                'reason': f'column {str(error).strip(chr(39)).upper()} '
                          f'is not in the datasource'}


def _existing_result_tables():
    """Get the result tables of the schema with their statistics."""
    query = ("select lower(table_name) name, num_rows, last_analyzed "
             "from user_tables "
             "where regexp_like(table_name, '^RAPO_RES[TAB]_')")
    return {row['name']: {'rows': row['num_rows'],
                          'rows_analyzed': row['last_analyzed']}
            for row in db.execute(query, as_table=True)}


def _oldest_run(table_name):
    # min() reads the ends of the rapo_process_id index only.
    pid = db.execute(f'select min(rapo_process_id) from {table_name}',
                     as_scalar=True)
    if pid is None:
        return None
    log = db.tables.log
    select = sa.select(log.c.added).where(log.c.process_id == pid)
    return db.execute(select, as_scalar=True)


def _owner(table_name):
    """Get the name of the control a result table belongs to, or None."""
    if not table_name.startswith(RESULT_PREFIXES):
        raise ValueError(f'{table_name.upper()} is not a result table')
    control_name = table_name[len('rapo_resx_'):]
    config = db.tables.config
    select = (sa.select(config.c.control_name)
                .where(sa.func.lower(config.c.control_name) == control_name))
    return db.execute(select, as_scalar=True)


def drop_orphaned_table(table_name):
    """Drop a result table that no run writes any more.

    A table of a control must be one its saved configuration no longer
    writes; a table of no control is dropped as it is.
    """
    owner = _owner(table_name)
    if owner:
        Control(owner).executor.drop_orphan_table(table_name)
    elif db.exists(table_name):
        db.drop(table_name)
    else:
        raise ValueError(f'{table_name.upper()} does not exist')


def count_unowned_rows(table_name):
    """Count the rows of a result table of no control exactly."""
    owner = _owner(table_name)
    if owner:
        raise ValueError(f'{table_name.upper()} belongs to {owner}')
    if not db.exists(table_name):
        return None
    return db.execute(f'select count(*) from {table_name}', as_scalar=True)


def _result_tables(control):
    """Get the result tables runs write, as Parser.parse_written_output_names."""
    name = control['control_name'].lower()
    if control['control_type'] == 'REC':
        return ([f'rapo_resa_{name}'] if control['need_a'] == 'Y' else []) \
            + ([f'rapo_resb_{name}'] if control['need_b'] == 'Y' else [])
    return [f'rapo_rest_{name}']


def _table_key(source_name):
    """Get the (owner, TABLE) of a datasource name, None if it has none."""
    if not source_name or '{' in source_name or '@' in source_name:
        return None
    parts = source_name.upper().split('.')
    return (parts[0], parts[1]) if len(parts) == 2 else (None, parts[-1])


def _source(control, side, columns):
    source_name = control[f'source_name{side}']
    if source_name and '{' in source_name:
        raise NotChecked(f'datasource {source_name} has variables')
    if source_name and '@' in source_name:
        raise NotChecked(f'datasource {source_name.upper()} is remote')
    source = columns.get(_table_key(source_name))
    if not source:
        raise NotChecked(f'datasource {(source_name or "").upper()} '
                         f'not found in the dictionary')
    return {column['name']: column for column in source}


def _output_columns(value):
    """Parse output columns like Parser._parse_output_columns."""
    config = json.loads(value) if isinstance(value, str) else None
    if not config:
        return []
    columns = []
    for item in config.get('columns', []):
        new = dict.fromkeys(['column', 'column_a', 'column_b'])
        if isinstance(item, str):
            new['column'] = item.lower()
        elif isinstance(item, dict):
            for key in new:
                if isinstance(item.get(key), str):
                    new[key] = item[key].lower()
        columns.append(new)
    return columns


def _renamed(column, name):
    return dict(column, name=name)


def _expected_columns(control, table_name, columns):
    """Build the columns Executor._prepare_output_columns would create."""
    kind = control['control_type']
    output = []
    date_fields = []
    if kind in ('ANL', 'REP'):
        source = _source(control, '', columns)
        chosen = _output_columns(control['output_table'])
        if chosen:
            output = [source[item['column']] for item in chosen]
        else:
            output = list(source.values())
        date_fields = [control['source_date_field']]
    elif kind == 'REC':
        side = '_a' if table_name.startswith('rapo_resa') else '_b'
        source = _source(control, side, columns)
        chosen = _output_columns(control[f'output_table{side}'])
        if chosen:
            output = [source[item['column']] for item in chosen]
        else:
            output = list(source.values())
            key_field = (control[f'source_key_field{side}'] or '').lower()
            table_type = next(iter(source.values()))['object_type']
            if table_type == 'TABLE' and key_field not in source:
                # The engine keys such a table by its ROWID, as db.get_rowid.
                output.append({'name': key_field, 'data_type': 'ROWID',
                               'data_length': 10, 'char_length': 0,
                               'char_used': None, 'data_precision': None,
                               'data_scale': None, 'nullable': 'N'})
        date_fields = [control[f'source_date_field{side}']]
    elif kind == 'CMP':
        source_a = _source(control, '_a', columns)
        source_b = _source(control, '_b', columns)
        chosen = _output_columns(control['output_table'])
        if not chosen:
            chosen = ([{'column': f'a_{name}', 'column_a': name,
                        'column_b': None} for name in source_a]
                      + [{'column': f'b_{name}', 'column_a': None,
                          'column_b': name} for name in source_b])
        for item in chosen:
            if item['column_a'] and item['column_b']:
                raise NotChecked(f'output column '
                                 f'{(item["column"] or "").upper()} '
                                 f'coalesces A and B')
            if item['column_a']:
                column = source_a[item['column_a']]
            elif item['column_b']:
                column = source_b[item['column_b']]
            else:
                column = source_a[item['column']]
            output.append(_renamed(column, item['column'] or column['name']))
        date_fields = [control['source_date_field_a'],
                       control['source_date_field_b']]

    mandatory = [_field_column(field) for field in MANDATORY.get(kind, [])]
    reserved = {column['name'] for column in mandatory} | {'rapo_process_id'}
    output = [column for column in output if column['name'] not in reserved]
    output += mandatory
    output.append(_field_column(PROCESS_ID))

    # db.normalize: a TIMESTAMP date field is cast to DATE, and a cast column
    # is created nullable.
    date_fields = {(field or '').lower() for field in date_fields}
    return [dict(column, data_type='DATE', data_length=7, nullable='Y')
            if column['name'] in date_fields
            and column['data_type'].startswith('TIMESTAMP')
            else column for column in output]


def _field_column(field):
    """Type a mandatory column as its CAST(NULL AS ...) creates it."""
    column = {'name': field.column_name, 'char_used': None, 'char_length': 0,
              'data_precision': None, 'data_scale': None, 'nullable': 'Y'}
    if isinstance(field.data_type, sa.String) or field.data_type is sa.String:
        length = field.data_type.length
        return dict(column, data_type='VARCHAR2', data_length=length,
                    char_length=length, char_used='C')
    if field is PROCESS_ID:
        # A run's process ID is a number literal: an unconstrained NUMBER.
        return dict(column, data_type='NUMBER', data_length=22)
    return dict(column, data_type='NUMBER', data_length=22, data_scale=0)


def _control_drift(control, columns):
    answer = {'level': 'ok', 'changes': 0, 'incompatible': 0, 'tables': [],
              'reason': None}
    existing = 0
    for table_name in _result_tables(control):
        current = columns.get((None, table_name.upper()))
        if not current:
            continue
        existing += 1
        expected = {column['name']: column for column
                    in _expected_columns(control, table_name, columns)}
        current = {column['name']: column for column in current}
        diffs = [diff_column(current.get(name), column)
                 for name, column in expected.items()]
        diffs += [diff_column(column, None) for name, column in current.items()
                  if name not in expected]
        changes = sum(1 for diff in diffs if diff['ddl'])
        incompatible = sum(1 for diff in diffs
                           if diff['status'] == 'incompatible')
        if changes or incompatible:
            answer['tables'].append(table_name.upper())
        answer['changes'] += changes
        answer['incompatible'] += incompatible
    if not existing:
        answer['level'] = 'missing'
    elif answer['incompatible']:
        answer['level'] = 'recreate'
    elif answer['changes']:
        answer['level'] = 'update'
    return answer
