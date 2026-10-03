"""Contains the readers of the instance health metrics.

OS metrics are this server's host and its own process tree (the server, its
runs, analysis and scan workers). DB metrics are the container rapo is
connected to; rapo's own sessions are those tagged `module = 'rapo'`
(`Database.tag`). Only views free of the Diagnostics Pack are read.
"""

import concurrent.futures
import os
import socket
import time

import psutil
import sqlalchemy as sa

from ..config import config, path as CONFIG_PATH
from ..database import db, MODULE
from ..logger import LOG_DIR


GB = 1024 ** 3
MB = 1024 ** 2

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
    'instance': ('V_$INSTANCE', 'select 1 from v$instance where 1 = 0'),
}


def labels():
    """Get the names of this server and of the database rapo connects to,
    as `user@host:port/service`; the password is never part of it.
    """
    section = config.get('DATABASE') or {}
    user = section.get('username') or section.get('user') or ''
    if section.get('path'):
        address = section.get('path')
    else:
        address = f"{section.get('host') or ''}:{section.get('port') or ''}"
        service = (section.get('service_name') or section.get('service')
                   or section.get('sid'))
        if service:
            address += f'/{service}'
    return {'server': socket.gethostname(),
            'database': f'{user}@{address}' if user else address}


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
        cpu = rss = fds = sockets = 0
        count = 0
        port = (config.get('DATABASE') or {}).get('port')
        for process in current.values():
            try:
                with process.oneshot():
                    cpu += process.cpu_percent()
                    rss += process.memory_info().rss
                    if hasattr(process, 'num_fds'):
                        fds += process.num_fds()
                    if port:
                        connections = getattr(process, 'net_connections',
                                              process.connections)('tcp')
                        sockets += sum(
                            1 for item in connections
                            if item.raddr and item.raddr.port == port
                            and item.status == psutil.CONN_ESTABLISHED)
                count += 1
            except psutil.Error:
                continue
        return {'cpu': cpu, 'rss': rss, 'fds': fds, 'count': count,
                'sockets': sockets if port else None}


tree = None
# The previous network counters and their time, for the rates.
network = None


def read_network():
    """Get the receive and send rates of all interfaces but loopback, and
    the errors and drops since the previous sample; None at the first one.
    """
    global network
    counters = psutil.net_io_counters(pernic=True)
    now = time.monotonic()
    total = [0, 0, 0, 0]
    for name, item in counters.items():
        if name == 'lo':
            continue
        total[0] += item.bytes_recv
        total[1] += item.bytes_sent
        total[2] += item.errin + item.errout
        total[3] += item.dropin + item.dropout
    previous, network = network, (now, total)
    output = dict.fromkeys(['net_rx_mbs', 'net_tx_mbs', 'net_errors',
                            'net_drops'])
    if previous is None:
        return output
    seconds = now - previous[0]
    deltas = [value - before for value, before in zip(total, previous[1])]
    # Counters start anew when an interface goes away or is reset.
    if seconds <= 0 or any(delta < 0 for delta in deltas):
        return output
    return {'net_rx_mbs': round(deltas[0] / MB / seconds, 3),
            'net_tx_mbs': round(deltas[1] / MB / seconds, 3),
            'net_errors': deltas[2], 'net_drops': deltas[3]}


def read_connections():
    """Count the TCP connections of the host by state."""
    try:
        connections = psutil.net_connections('tcp')
    except psutil.Error:
        return dict.fromkeys(['tcp_established', 'tcp_close_wait',
                              'tcp_time_wait'])
    states = {}
    for item in connections:
        states[item.status] = states.get(item.status, 0) + 1
    return {'tcp_established': states.get(psutil.CONN_ESTABLISHED, 0),
            'tcp_close_wait': states.get(psutil.CONN_CLOSE_WAIT, 0),
            'tcp_time_wait': states.get(psutil.CONN_TIME_WAIT, 0)}


def read_os(directories=()):
    """Read the OS metrics of this host, and rapo's share of them.

    `directories` are the datasource directories, [(role, path)], whose file
    systems are measured with those of the logs and of rapo.
    """
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
    disks = read_disks(directories)
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
        'disk': max((disk['used_percent'] for disk in disks
                     if 'used_percent' in disk), default=None),
        'disks': disks,
        'fds_rapo': rapo['fds'],
        **read_network(),
        **read_connections(),
        'rapo_db_sockets': rapo['sockets'],
        'uptime': int(time.time() - psutil.boot_time()),
        'rapo_uptime': int(time.time() - tree.root.create_time()),
    }


def read_directories():
    """Get the input and archive directories of every datasource, as
    [(role, path)]; none when the PDI Core tables cannot be read.
    """
    from ..pdi.store import pdi, split_directories
    if not pdi.available:
        return []
    directories = []
    for row in pdi.read_datasources():
        directories += [('input', path)
                        for path in split_directories(row['input_directory'])]
        if row.get('archive_directory'):
            directories.append(('archive', row['archive_directory']))
    return directories


# Seconds a file system may take to answer its usage; one that does not (a
# hung network mount) is reported with an error and not asked again until it
# answered.
DISK_SECONDS = 2
disk_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix='rapo-health-disk')
disk_pending = {}


def mount_of(path, mounts):
    """Get the mount point holding `path`, the longest one it starts with."""
    best = '/'
    for mount in mounts:
        if ((path == mount or path.startswith(mount.rstrip('/') + '/'))
                and len(mount) > len(best)):
            best = mount
    return best


def read_disks(directories):
    """Get the usage of each file system holding the logs, rapo or one of
    the `directories`, with how many of them it holds by role.

    Datasource paths are matched to the mounts by name only, so a missing
    directory or a hung network mount never blocks the sample.
    """
    try:
        partitions = psutil.disk_partitions(all=True)
    except Exception:
        partitions = []
    devices = {item.mountpoint: item.device for item in partitions}
    paths = [('logs', os.path.realpath(LOG_DIR)),
             ('home', os.path.realpath(os.path.dirname(CONFIG_PATH))),
             *((role, os.path.normpath(path)) for role, path in directories
               if path and os.path.isabs(path))]
    roles = {}
    for role, path in dict.fromkeys(paths):
        counts = roles.setdefault(mount_of(path, devices), {})
        counts[role] = counts.get(role, 0) + 1
    futures = {}
    for mount in roles:
        future = disk_pending.get(mount)
        if future is None or future.done():
            future = disk_pending[mount] = disk_pool.submit(
                psutil.disk_usage, mount)
        futures[mount] = future
    deadline = time.monotonic() + DISK_SECONDS
    disks = []
    for mount in sorted(roles):
        disk = {'mount': mount, 'device': devices.get(mount),
                'roles': roles[mount]}
        try:
            usage = futures[mount].result(
                timeout=max(deadline - time.monotonic(), 0.01))
        except concurrent.futures.TimeoutError:
            disk['error'] = f'No answer in {DISK_SECONDS} s'
        except Exception as error:
            disk['error'] = str(error).strip().splitlines()[0][:200]
        else:
            disk.update({'used_percent': usage.percent,
                         'used_gb': round(usage.used / GB, 2),
                         'free_gb': round(usage.free / GB, 2),
                         'total_gb': round(usage.total / GB, 2)})
        disks.append(disk)
    return disks


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
    if 'instance' in available:
        read('instance', _instance)
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
        "'Average Active Sessions', 'Physical Read Total Bytes Per Sec', "
        "'Physical Write Total Bytes Per Sec', 'Redo Generated Per Sec', "
        "'User Commits Per Sec')"), as_records=True)
    values = {name: float(value) for name, value in rows}
    cores = values.get('CPU Usage Per Sec')
    cores = cores / 100 if cores is not None else None
    cpu = None
    if cores is not None and cpu_count:
        cpu = round(min(cores / cpu_count * 100, 100), 1)

    def rate(name, divisor=MB, places=3):
        value = values.get(name)
        return round(value / divisor, places) if value is not None else None

    return {'db_cpu': cpu,
            'db_cpu_cores': round(cores, 2) if cores is not None else None,
            'aas': rate('Average Active Sessions', 1, 2),
            'io_read_mbs': rate('Physical Read Total Bytes Per Sec'),
            'io_write_mbs': rate('Physical Write Total Bytes Per Sec'),
            'redo_mbs': rate('Redo Generated Per Sec'),
            'commits': rate('User Commits Per Sec', 1, 2)}


def _instance():
    # Counted by the database, whose clock may differ from this server's.
    seconds = db.execute(sa.text(
        "select round((sysdate - startup_time) * 86400) from v$instance"),
        as_scalar=True)
    return {'db_uptime': int(seconds) if seconds is not None else None}


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
    # The size counts autoextend: what the files may grow to.
    rows = db.execute(sa.text(
        "select m.tablespace_name name, round(m.used_percent, 1) used, "
        "round(m.used_space * t.block_size / power(1024, 3), 2) used_gb, "
        "round(m.tablespace_size * t.block_size / power(1024, 3), 2) size_gb, "
        "case when m.tablespace_name = u.default_tablespace then 1 end "
        "is_default "
        "from dba_tablespace_usage_metrics m "
        "join user_tablespaces t on t.tablespace_name = m.tablespace_name, "
        "user_users u "
        "where m.tablespace_name in (u.default_tablespace, "
        "u.temporary_tablespace) "
        "order by case when m.tablespace_name = u.default_tablespace "
        "then 0 else 1 end, m.tablespace_name"),
        as_table=True)
    tablespaces = [{'name': row['name'], 'used_percent': float(row['used']),
                    'used_gb': float(row['used_gb']),
                    'size_gb': float(row['size_gb']),
                    'default': bool(row['is_default'])}
                   for row in rows]
    default = next((row for row in tablespaces if row['default']), None)
    return {'storage': max((row['used_percent'] for row in tablespaces),
                           default=None),
            'storage_gb': default['used_gb'] if default else None,
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
