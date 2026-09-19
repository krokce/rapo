"""Contains reading and retention of log files.

Log files are local to the server that wrote them, so every server reads and
cleans its own log folder. Run logs are kept as long as the results of their
control (`days_retention`); server logs and logs of deleted controls follow
`[LOGGING] retention_days`.
"""

import datetime as dt
import glob
import os
import platform
import threading as th

import sqlalchemy as sa

from ..database import db
from ..logger import logger, get_setting, run_log_path, LOG_DIR
from ..reader import reader


READ_LIMIT = 2*1024*1024
CLEAN_INTERVAL = 24*60*60
# Files written recently may belong to runs still in progress.
ACTIVE_WINDOW = 60*60


def read_run_log(process_id, max_bytes=READ_LIMIT):
    """Read the log file of a control run.

    Only the last `max_bytes` are returned, starting at a line boundary.

    Returns
    -------
    log : dict
        Path, existence, size, modification time, text, truncation flag,
        this host and the server that performed the run.
    """
    result = reader.read_control_result(process_id)
    path = run_log_path(result['control_id'], process_id)
    log = {
        'path': path,
        'exists': os.path.isfile(path),
        'size': None,
        'modified': None,
        'truncated': False,
        'text': '',
        'host': platform.node(),
        'runner': read_runner(process_id),
    }
    if not log['exists']:
        return log
    stat = os.stat(path)
    log['size'] = stat.st_size
    log['modified'] = dt.datetime.fromtimestamp(int(stat.st_mtime))
    with open(path, 'rb') as file:
        if stat.st_size > max_bytes:
            file.seek(stat.st_size-max_bytes)
            data = file.read()
            data = data[data.find(b'\n')+1:]
            log['truncated'] = True
        else:
            data = file.read()
    log['text'] = data.decode('utf-8', errors='replace')
    return log


def read_runner(process_id):
    """Get the server (host:port) that performed the run, if recorded."""
    event = db.tables.scheduler_event
    select = (sa.select(event.c.runner)
                .where(event.c.process_id == process_id)
                .order_by(event.c.event_id.desc())
                .limit(1))
    return db.execute(select, as_scalar=True)


def clean_logs(now=None):
    """Delete log files older than their retention.

    Run logs follow `days_retention` of their control (0 means any finished
    run). Server logs and logs of deleted controls or controls without
    `days_retention` follow `[LOGGING] retention_days` (empty or 0 keeps
    them). Files modified within the last hour are never deleted.

    Returns
    -------
    deleted : list of str
        Paths of deleted files.
    """
    now = now or dt.datetime.now().timestamp()
    retention_days = get_setting('retention_days')
    config = db.tables.config
    select = sa.select(config.c.control_id, config.c.days_retention)
    retentions = {int(row.control_id): row.days_retention
                  for row in db.execute(select, as_records=True)}

    deleted = []

    def delete_older(paths, days):
        if days is None:
            return
        border = min(now-days*86400, now-ACTIVE_WINDOW)
        for path in paths:
            try:
                if os.path.getmtime(path) < border:
                    os.remove(path)
                    deleted.append(path)
            except OSError:
                logger.warning(f'Log file {path} could not be deleted')

    controls_dir = os.path.join(LOG_DIR, 'controls')
    for folder in glob.glob(os.path.join(controls_dir, '*')):
        name = os.path.basename(folder)
        if not os.path.isdir(folder) or not name.isdigit():
            continue
        days = retentions.get(int(name))
        if days is None:
            days = retention_days or None
        delete_older(glob.glob(os.path.join(folder, '*.log')), days)
        try:
            if not os.listdir(folder):
                os.rmdir(folder)
        except OSError:
            pass

    server_logs = glob.glob(os.path.join(LOG_DIR, 'rapo-server_*.log'))
    delete_older(server_logs, retention_days or None)

    logger.info(f'Log cleanup in {LOG_DIR}: {len(deleted)} files deleted')
    return deleted


class LogCleaner:
    """Represents a thread cleaning log files at start and then daily."""

    def __init__(self):
        self.thread = None
        self.stopping = th.Event()

    def start(self):
        """Start the cleaner thread."""
        if self.thread is None:
            self.stopping.clear()
            self.thread = th.Thread(name='Log-Cleaner', target=self._run,
                                    daemon=True)
            self.thread.start()

    def stop(self):
        """Stop the cleaner thread."""
        self.stopping.set()
        self.thread = None

    def _run(self):
        while not self.stopping.is_set():
            try:
                clean_logs()
            except Exception:
                logger.error()
            self.stopping.wait(CLEAN_INTERVAL)


cleaner = LogCleaner()
