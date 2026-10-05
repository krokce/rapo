"""Temporary tables left in the schema by runs, and dropping them.

A run drops its RAPO_TEMP_* tables only when it finishes without debug mode,
so failed, canceled, killed and debug runs leave them behind. This is the only
code that recognizes such an object, and it never touches anything else:

- a candidate comes from user_objects only (the own schema), as a TABLE or a
  MATERIALIZED VIEW; views, synonyms and other schemas never are;
- its name must fully match a kind a run creates or once created (KINDS),
  followed by the process ID, or be a scratch table of a schema check;
- a drop re-reads the dictionary and drops only what it found itself, by the
  dictionary's exact name; a name from a request is only compared with it;
- the tables of a run in progress (by rapo_log, any server) are never listed
  or dropped, nor a scratch table younger than an hour.

Other RAPO_TEMP_* objects are listed as not recognized, for manual handling.
"""

import datetime as dt
import re

import sqlalchemy as sa

from ..database import db
from ..logger import logger


# Every kind of temporary table the engine creates, and those older versions
# created, which may still be left in a schema.
KINDS = (
    'SOURCE', 'SOURCE_A', 'SOURCE_B', 'ERROR', 'ERROR_A', 'ERROR_B',
    'STAGE', 'STAGE_A', 'STAGE_B', 'T01_MOD', 'T02_ORG_A', 'T02_ORG_B',
    'T03_DUP_A', 'T03_DUP_B', 'T04_DUP', 'T05_MAC', 'VERDICT_A', 'VERDICT_B',
    'MD', 'NMD',
    # Legacy.
    'ERR', 'ERR_A', 'ERR_B', 'DUP', 'DUP_A', 'DUP_B', 'COMB', 'FD', 'FDA',
    'FDB', 'MA', 'NMA', 'NF_A', 'NF_B', 'RES_A', 'RES_B',
)
RUN_NAME = re.compile(rf'RAPO_TEMP_(?:{"|".join(KINDS)})_([0-9]+)')
# Executor.expected_output_schema: rapo_temp_schema_<16 hex digits>; the
# view check of views.check_view: rapo_temp_view_<16 hex digits>.
SCRATCH_NAME = re.compile(r'RAPO_TEMP_(?:SCHEMA|VIEW)_[0-9A-F]{16}')
# A schema or view check drops its scratch table or view within seconds.
SCRATCH_AGE = dt.timedelta(hours=1)
# A voided run (status NULL) is still being killed by its owner.
ACTIVE = ('I', 'W', 'S', 'P', 'F', None)
DEBUG_MESSAGE = 'Control execution in debug mode.'

_warned = set()


def temp_tables():
    """Get the temporary tables of the schema that can be dropped.

    Returns
    -------
    tables : dict
        runs: [{process_id, control_id, control_name, status, started, debug,
        in_log, tables, mb}] newest first, one per run not in progress;
        scratch: [{table, created, mb}] scratch tables of schema checks older
        than an hour; unknown: [{table, type, created, mb}] other RAPO_TEMP_*
        objects, never dropped here; total_tables and total_mb of them all.
    """
    now = db.execute('select sysdate from dual', as_scalar=True)
    runs, scratch, unknown = _classify(_candidates(), now)
    states = _run_states(runs)
    answer = {'runs': [], 'scratch': [_rounded(item) for item in scratch],
              'unknown': [_rounded(item) for item in unknown]}
    for pid, objects in runs.items():
        state = states.get(pid)
        if state and state['status'] in ACTIVE:
            continue
        state = state or {}
        answer['runs'].append({
            'process_id': pid,
            'control_id': state.get('control_id'),
            'control_name': state.get('control_name'),
            'status': state.get('status'),
            'started': state.get('started'),
            'debug': bool(state.get('debug')),
            'in_log': bool(state),
            'tables': sorted(item['table'] for item in objects),
            'mb': _mb(objects)})
    answer['runs'].sort(key=lambda run: run['process_id'], reverse=True)
    for item in unknown:
        if item['table'] not in _warned:
            _warned.add(item['table'])
            logger.warning(f'{item["table"]} looks like a temporary table '
                           f'but is not one Rapo creates: not dropped')
    kept = [item for run in answer['runs'] for item in runs[run['process_id']]]
    listed = [*kept, *scratch, *unknown]
    answer['total_tables'] = len(listed)
    answer['total_mb'] = _mb(listed)
    return answer


def drop(process_ids=(), tables=()):
    """Drop the temporary tables of runs and scratch tables of schema checks.

    Parameters
    ----------
    process_ids : iterable of int
        Runs whose recognized temporary tables are dropped. A run in progress
        or one without such tables is skipped.
    tables : iterable of str
        Scratch tables of schema checks. Anything that is not one of those
        listed by temp_tables() raises ValueError, and nothing is dropped.

    Returns
    -------
    result : dict
        dropped: [table], skipped: [{process_id or table, reason}],
        failed: [{table, error}]. One failure never stops the others.
    """
    process_ids = {int(pid) for pid in process_ids}
    names = {str(name).upper() for name in tables}
    now = db.execute('select sysdate from dual', as_scalar=True)
    runs, scratch, _ = _classify(_candidates(), now)
    listed = {item['table']: item for item in scratch}
    for name in names:
        if name not in listed:
            raise ValueError(f'{name} is not a scratch table of a schema '
                             f'check older than an hour')
    wanted = {pid: runs[pid] for pid in process_ids if pid in runs}
    states = _run_states(wanted)
    result = {'dropped': [], 'skipped': [], 'failed': []}
    targets = [listed[name] for name in sorted(names)]
    for pid in sorted(process_ids):
        if pid not in runs:
            result['skipped'].append({'process_id': pid,
                                      'reason': 'no temporary tables left'})
        elif pid in states and states[pid]['status'] in ACTIVE:
            result['skipped'].append({'process_id': pid,
                                      'reason': 'the run is in progress'})
        else:
            targets.extend(runs[pid])
    for item in targets:
        try:
            _drop(item)
        except Exception as error:
            logger.warning(f'Temporary table {item["table"]} cannot be '
                           f'dropped: {type(error).__name__}: {error}')
            result['failed'].append({'table': item['table'],
                                     'error': str(error).split('\n')[0]})
        else:
            logger.info(f'Temporary table {item["table"]} dropped')
            result['dropped'].append(item['table'])
    return result


def _drop(item):
    # The dictionary's exact name, checked against the patterns once more.
    name = item['table']
    if not (RUN_NAME.fullmatch(name) or SCRATCH_NAME.fullmatch(name)):
        raise ValueError(f'{name} is not a temporary table')
    if item['type'] == 'MATERIALIZED VIEW':
        db.execute(f'DROP MATERIALIZED VIEW "{name}"')
    elif item['type'] == 'VIEW':
        db.execute(f'DROP VIEW "{name}"')
    else:
        db.execute(f'DROP TABLE "{name}" PURGE')


def _candidates():
    """Get every RAPO_TEMP_* table, view and materialized view of the schema.

    A materialized view has a TABLE object of the same name, so each name is
    one entry, typed as the view. The size adds the table's index and LOB
    segments.
    """
    query = sa.text(
        "select o.object_name name, "
        "case when max(case when o.object_type = 'MATERIALIZED VIEW' "
        "then 1 else 0 end) = 1 then 'MATERIALIZED VIEW' "
        "when max(o.object_type) = 'VIEW' then 'VIEW' else 'TABLE' end "
        "type, "
        "min(o.created) created, max(s.bytes) bytes "
        "from user_objects o "
        "left join (select nvl(i.table_name, nvl(l.table_name, "
        "g.segment_name)) table_name, sum(g.bytes) bytes "
        "from user_segments g "
        "left join user_indexes i on i.index_name = g.segment_name "
        "left join user_lobs l on l.segment_name = g.segment_name "
        "group by nvl(i.table_name, nvl(l.table_name, g.segment_name))) s "
        "on s.table_name = o.object_name "
        r"where o.object_name like 'RAPO\_TEMP\_%' escape '\' "
        "and o.object_type in ('TABLE', 'VIEW', 'MATERIALIZED VIEW') "
        "group by o.object_name")
    return db.execute(query, as_table=True)


def _classify(candidates, now):
    runs, scratch, unknown = {}, [], []
    for row in candidates:
        name = row['name']
        item = {'table': name, 'type': row['type'], 'created': row['created'],
                'mb': (row['bytes'] or 0) / 1024 / 1024}
        match = RUN_NAME.fullmatch(name)
        if match:
            runs.setdefault(int(match.group(1)), []).append(item)
        elif SCRATCH_NAME.fullmatch(name):
            if row['created'] and now - row['created'] >= SCRATCH_AGE:
                scratch.append(item)
        else:
            unknown.append(item)
    return runs, scratch, unknown


def _run_states(runs, chunk=500):
    """Get the rapo_log state of the given process IDs; absent when none."""
    pids = sorted(runs)
    states = {}
    for i in range(0, len(pids), chunk):
        part = pids[i:i + chunk]
        params = {f'p{j}': pid for j, pid in enumerate(part)}
        names = ', '.join(f':{key}' for key in params)
        query = sa.text(
            'select l.process_id, l.control_id, c.control_name, l.status, '
            'nvl(l.start_date, l.added) started, '
            f"dbms_lob.instr(l.text_message, '{DEBUG_MESSAGE}') debug "
            'from rapo_log l '
            'left join rapo_config c on c.control_id = l.control_id '
            f'where l.process_id in ({names})').bindparams(**params)
        for row in db.execute(query, as_table=True):
            states[int(row.pop('process_id'))] = row
    return states


def _mb(objects):
    return round(sum(item['mb'] for item in objects), 1)


def _rounded(item):
    return dict(item, mb=round(item['mb'], 1))
