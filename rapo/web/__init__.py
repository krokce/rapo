"""Contains web API elements."""

import datetime as dt
import getpass
import os
import platform
import signal
import subprocess as sp
import sys

import psutil

from .api import app
from ..config import config
from ..database import db
from ..reader import reader


APP = 'rapo.web.api.app:app'


def is_running(record, url=None):
    """Check that the recorded server is really running on this host.

    A server that crashed leaves its row marked as running. Trusting that
    PID makes `start` refuse to start and `stop` signal whatever process has
    taken the number since, so the record counts only when it names this
    host and the PID still belongs to a rapo server.

    The table holds one row, so a second instance overwrites it. Passing the
    URL of the server asking makes the record count only when it is that
    server's own, and never makes it signal another instance.
    """
    if not record or record['status'] != 'Y' or not record['pid']:
        return False
    if record['server'] != platform.node():
        return False
    if url and record['url'] != url:
        return False
    try:
        process = psutil.Process(int(record['pid']))
        return APP in ' '.join(process.cmdline())
    except (psutil.Error, ValueError):
        return False


def find_server(host, port):
    """Find the server process serving the given host and port.

    The record names one instance only, so a server whose row was taken over
    by another one finds its own process by the command line it was started
    with, the way `rapoctl.sh` does.

    Returns
    -------
    process : psutil.Process or None
        Process of the server, None when it is not running.
    """
    args = f'--host {host} --port {port}'
    found = []
    # A process of another user or a zombie gives None instead of raising, so
    # one unreadable process does not stop the search.
    for process in psutil.process_iter(['cmdline', 'create_time'],
                                       ad_value=None):
        command = ' '.join(process.info['cmdline'] or ())
        if APP in command and args in command:
            found.append(process)
    # A development server reloads through a parent process, which is the one
    # to signal, so the oldest match is the server itself.
    return min(found, key=lambda process: process.info['create_time'] or 0,
               default=None)


class Server:
    """Represents application server."""

    def __init__(self, host=None, port=None, dev=False, scheduler=None):
        self.app = app
        self.host = host or config['API'].get('host') or '127.0.0.1'
        self.port = port or config['API'].get('port') or 8080
        self.url = f'{self.host}:{self.port}'
        self.dev = bool(dev)
        # A reload restarts the scheduler with every change, so development
        # servers run without it unless asked to.
        self.scheduler = scheduler if scheduler is not None \
            else (False if self.dev else None)

        self.table = db.tables.web_api
        self.record = reader.read_web_api_record()
        # Whether the record describes this very server, which is the only
        # case where it may be written. Another instance keeps its own row
        # until it stops or until the next start overwrites it.
        self.record_is_mine = bool(self.record) \
            and self.record['server'] == platform.node() \
            and self.record['url'] == self.url
        if is_running(self.record, self.url):
            self.server = self.record['server']
            self.username = self.record['username']
            self.pid = int(self.record['pid'])
            self.start_date = self.record['start_date']
            self.stop_date = self.record['stop_date']
            self.status = True if self.record['status'] == 'Y' else False
        else:
            self.server = platform.node()
            self.username = getpass.getuser()
            self.start_date = None
            self.stop_date = None
            # The record may belong to another instance, so this server is
            # looked for by its command line instead of by that PID.
            process = find_server(self.host, self.port)
            self.pid = process.pid if process else None
            self.status = True if process else None

    def start(self):
        """Start web API server."""
        if self.status is True and self.pid and psutil.pid_exists(self.pid):
            message = f'web API already running at PID {self.pid}'
            raise Exception(message)
        script = [sys.executable, '-m', 'uvicorn', APP]
        args = ['--host', self.host, '--port', str(self.port)]
        env = os.environ.copy()
        if self.scheduler is False:
            env['RAPO_SCHEDULER'] = '0'
        self.start_date = dt.datetime.now()
        self.status = True
        # The record is overwritten below, so from now on it is this server's,
        # whichever instance wrote it before.
        self.record_is_mine = True
        if self.dev is True:
            cmd = [*script, *args, '--reload']
            try:
                proc = sp.Popen(cmd, env=env)
                self.pid = proc.pid
                update = (self.table.update()
                                    .values(server=self.server,
                                            username=self.username,
                                            pid=self.pid,
                                            url=self.url,
                                            debug='X',
                                            start_date=self.start_date,
                                            stop_date=self.stop_date,
                                            status='Y'))
                db.execute(update)
                proc.wait()
            except KeyboardInterrupt:
                self.stop_date = dt.datetime.now()
                update = (self.table.update()
                                    .values(stop_date=self.stop_date,
                                            status='N'))
                db.execute(update)
                proc.terminate()
        else:
            cmd = [*script, *args]
            proc = sp.Popen(cmd, env=env, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            self.pid = proc.pid
            update = self.table.update().values(server=self.server,
                                                username=self.username,
                                                pid=self.pid,
                                                url=self.url,
                                                debug=None,
                                                start_date=self.start_date,
                                                stop_date=self.stop_date,
                                                status='Y')
            db.execute(update)

    def stop(self):
        """Stop web API server."""
        if self.status is not True:
            if self.record_is_mine and self.record['status'] == 'Y':
                self._record_stop()
                print('Web API was not running, its record was cleared.')
            elif self.record and self.record['status'] == 'Y':
                print(f'Web API was not running, the record belongs to '
                      f'{self.record["server"]} at {self.record["url"]}.')
            return
        self.status = False
        if psutil.pid_exists(self.pid):
            os.kill(self.pid, signal.SIGTERM)
        if self.record_is_mine:
            self._record_stop()

    def _record_stop(self):
        """Mark the web API record as stopped."""
        self.stop_date = dt.datetime.now()
        update = self.table.update().values(stop_date=self.stop_date,
                                            status='N')
        db.execute(update)
