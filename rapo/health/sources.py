"""Contains the readers of the instance health metrics.

OS metrics are this server's host and its own process tree (the server, its
runs, analysis and scan workers). DB metrics are the container rapo is
connected to; rapo's own sessions are those tagged `module = 'rapo'`
(`Database.tag`). Only views free of the Diagnostics Pack are read.
"""

import os
import time

import psutil
import sqlalchemy as sa

from ..config import path as CONFIG_PATH
from ..database import db, MODULE
from ..logger import LOG_DIR


GB = 1024 ** 3

# DB sources: what each reads, the grant it needs, and a statement that
# changes nothing yet makes Oracle check the privilege.
DB_SOURCES = {
    'sysmetric': ('V_$CON_SYSMETRIC',
                  'select 1 from v$con_sysmetric where 1 = 0'),
    'parameter': ('V_$PARAMETER', 'select 1 from v$parameter where 1 = 0'),
    'session': ('V_$SESSION', 'select 1 from v$session where 1 = 0'),
    'sgainfo': ('V_$SGAINFO', 'select 1 from v$sgainfo where 1 = 0'),
    'pgastat': ('V_$PGASTAT', 'select 1 from v$pgastat where 1 = 0'),
    'tablespace': ('DBA_TABLESPACE_USAGE_METRICS',
                   'select 1 from dba_tablespace_usage_metrics where 1 = 0'),
}


def probe():
    """Get which DB sources this user may read, {source: error or None}."""
    errors = {}
    for name, (_, statement) in DB_SOURCES.items():
        try:
            db.execute(sa.text(statement))
            errors[name] = None
        except Exception as error:
            errors[name] = str(error).strip().splitlines()[0][:200]
    return errors


class ProcessTree:
    """Measures this server's process and its descendants.

    psutil measures CPU between two calls of the same Process object, so the
    objects are kept from one sample to the next.
    """

    def __init__(self):
        self.root = psutil.Process()
        self.processes = {}

    def sample(self):
        try:
            children = self.root.children(recursive=True)
        except psutil.Error:
            children = []
        current = {}
        for process in [self.root, *children]:
            current[process.pid] = self.processes.get(process.pid, process)
        self.processes = current
        cpu = rss = fds = 0
        count = 0
        for process in current.values():
            try:
                with process.oneshot():
                    cpu += process.cpu_percent()
                    rss += process.memory_info().rss
                    if hasattr(process, 'num_fds'):
                        fds += process.num_fds()
                count += 1
            except psutil.Error:
                continue
        return {'cpu': cpu, 'rss': rss, 'fds': fds, 'count': count}


tree = None


def read_os():
    """Read the OS metrics of this host, and rapo's share of them."""
    global tree
    if tree is None:
        tree = ProcessTree()
        psutil.cpu_percent()
        tree.sample()
        time.sleep(0.5)
    cpus = psutil.cpu_count() or 1
    rapo = tree.sample()
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    try:
        load = os.getloadavg()[0]
    except OSError:
        load = None
    disks = []
    seen = set()
    for path in (LOG_DIR, os.path.dirname(CONFIG_PATH)):
        try:
            device = os.stat(path).st_dev
            if device in seen:
                continue
            seen.add(device)
            usage = psutil.disk_usage(path)
        except OSError:
            continue
        disks.append({'path': path, 'used_percent': usage.percent,
                      'free_gb': round(usage.free / GB, 2),
                      'total_gb': round(usage.total / GB, 2)})
    return {
        'cpu': psutil.cpu_percent(),
        'cpu_rapo': round(rapo['cpu'] / cpus, 1),
        'cpus': cpus,
        'load': round(load, 2) if load is not None else None,
        'memory': memory.percent,
        'memory_rapo': round(rapo['rss'] / memory.total * 100, 1),
        'memory_rapo_gb': round(rapo['rss'] / GB, 2),
        'memory_total_gb': round(memory.total / GB, 1),
        'swap': swap.percent,
        'processes': len(psutil.pids()),
        'processes_rapo': rapo['count'],
        'disk': max((disk['used_percent'] for disk in disks), default=None),
        'disks': disks,
        'fds_rapo': rapo['fds'],
    }


def read_db(available):
    """Read the DB metrics, from the sources in `available` only."""
    point = {}
    errors = {}

    def read(name, function):
        try:
            point.update(function())
        except Exception as error:
            errors[name] = str(error).strip().splitlines()[0][:200]

    if 'parameter' in available:
        read('parameter', _parameters)
    if 'sysmetric' in available:
        read('sysmetric', lambda: _sysmetric(point.get('cpu_count')))
    if 'session' in available:
        read('session', _sessions)
    if 'sgainfo' in available and 'pgastat' in available:
        read('memory', lambda: _memory(point.get('pga_limit_gb')))
    if 'tablespace' in available:
        read('tablespace', _tablespaces)
    point['errors'] = errors
    return point


def _parameters():
    rows = db.execute(sa.text(
        "select name, value from v$parameter "
        "where name in ('cpu_count', 'pga_aggregate_limit')"),
        as_records=True)
    values = {name: value for name, value in rows}
    limit = int(values.get('pga_aggregate_limit') or 0)
    return {'cpu_count': int(values.get('cpu_count') or 0) or None,
            'pga_limit_gb': round(limit / GB, 2) if limit else None}


def _sysmetric(cpu_count):
    # v$con_sysmetric holds only the 60 second interval, for the container.
    rows = db.execute(sa.text(
        "select metric_name, value from v$con_sysmetric "
        "where metric_name in ('CPU Usage Per Sec', "
        "'Average Active Sessions')"), as_records=True)
    values = {name: float(value) for name, value in rows}
    cores = values.get('CPU Usage Per Sec')
    cores = cores / 100 if cores is not None else None
    cpu = None
    if cores is not None and cpu_count:
        cpu = round(min(cores / cpu_count * 100, 100), 1)
    aas = values.get('Average Active Sessions')
    return {'db_cpu': cpu,
            'db_cpu_cores': round(cores, 2) if cores is not None else None,
            'aas': round(aas, 2) if aas is not None else None}


def _sessions():
    row = db.execute(sa.text(
        "select count(*) total, "
        "count(case when status = 'ACTIVE' then 1 end) active, "
        "count(case when module = :module then 1 end) rapo, "
        "count(case when module = :module and status = 'ACTIVE' "
        "then 1 end) rapo_active, "
        "count(case when blocking_session is not null then 1 end) blocked, "
        "max(case when blocking_session is not null "
        "then round(wait_time_micro / 1e6) end) blocked_wait "
        "from v$session where type = 'USER'"
    ).bindparams(module=MODULE), as_dict=True)
    return {'sessions': row['total'], 'sessions_active': row['active'],
            'sessions_rapo': row['rapo'],
            'sessions_rapo_active': row['rapo_active'],
            'locks': row['blocked'],
            'locks_wait': int(row['blocked_wait'] or 0)}


def _memory(pga_limit_gb):
    sga = db.execute(sa.text(
        "select bytes from v$sgainfo where name = 'Maximum SGA Size'"),
        as_scalar=True)
    pga = db.execute(sa.text(
        "select value from v$pgastat where name = 'total PGA allocated'"),
        as_scalar=True)
    pga_gb = round(float(pga or 0) / GB, 2)
    return {'sga_gb': round(float(sga or 0) / GB, 2), 'pga_gb': pga_gb,
            'pga_percent': (round(pga_gb / pga_limit_gb * 100, 1)
                            if pga_limit_gb else None)}


def _tablespaces():
    # Used percent counts autoextend: the size is what the files may grow to.
    rows = db.execute(sa.text(
        "select m.tablespace_name name, round(m.used_percent, 1) used "
        "from dba_tablespace_usage_metrics m, user_users u "
        "where m.tablespace_name in (u.default_tablespace, "
        "u.temporary_tablespace) order by m.used_percent desc"),
        as_table=True)
    tablespaces = [{'name': row['name'], 'used_percent': float(row['used'])}
                   for row in rows]
    return {'storage': max((row['used_percent'] for row in tablespaces),
                           default=None),
            'tablespaces': tablespaces}


def read_footprint():
    """Read the size of rapo's result and temporary tables."""
    row = db.execute(sa.text(
        r"select round(nvl(sum(bytes), 0) / power(1024, 3), 3) gb, "
        r"count(*) segments from user_segments "
        r"where segment_name like 'RAPO\_RES%' escape '\' "
        r"or segment_name like 'RAPO\_TEMP\_%' escape '\'"), as_dict=True)
    return {'rapo_gb': float(row['gb']), 'rapo_segments': row['segments']}


SESSION_LIMIT = 500


def read_sessions(kind):
    """Get the user sessions of the container, or with `kind='locks'` the
    blocked ones and the sessions blocking them, at most SESSION_LIMIT.

    `wait_seconds` is the current wait of a waiting session, else the time
    since its last call. The action of a rapo run is its control's name,
    resolved to `control_id` when it still exists.
    """
    where = "type = 'USER'"
    if kind == 'locks':
        where += (" and (blocking_session is not null or sid in "
                  "(select blocking_session from v$session "
                  "where blocking_session is not null))")
    rows = db.execute(sa.text(
        "select * from ("
        "select sid, serial# serial, username, module, action, status, "
        "machine, program, event, sql_id, blocking_session, logon_time, "
        "case when state = 'WAITING' then round(wait_time_micro / 1e6) "
        "else last_call_et end wait_seconds, "
        "case when module = :module then 'Y' else 'N' end is_rapo "
        f"from v$session where {where} "
        "order by case when blocking_session is not null then 0 "
        "when status = 'ACTIVE' then 1 else 2 end, wait_seconds desc"
        ") where rownum <= :limit"
    ).bindparams(module=MODULE, limit=SESSION_LIMIT + 1), as_table=True)
    actions = {row['action'] for row in rows
               if row['is_rapo'] == 'Y' and row['action']}
    controls = {}
    if actions:
        table = db.tables.config
        select = (sa.select(table.c.control_name, table.c.control_id)
                  .where(table.c.control_name.in_(actions)))
        controls = dict(db.execute(select, as_records=True))
    for row in rows:
        row['is_rapo'] = row['is_rapo'] == 'Y'
        row['control_id'] = controls.get(row['action']) if row['is_rapo'] \
            else None
    return {'rows': rows[:SESSION_LIMIT],
            'truncated': len(rows) > SESSION_LIMIT}
