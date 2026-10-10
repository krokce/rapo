"""Contains the spare process of the analysis.

A spawned process imports rapo first, which connects to the database and
reflects its tables: over a second before an analysis can start. So one
process is kept spawned and connected ahead; an analysis session or a
discrepancy analysis job takes it (`Spare.take`), and the next spare is
spawned in the background. The spare's first message on its pipe says what
it becomes:
- `('analysis', (sql, settings))`: the worker of a session (`worker.py`);
- `('explain', (process_id, side, result_type, settings))`: a discrepancy
  analysis job (`explain_job.work`);
- `('stop', None)`: nothing, it exits.

A spare read rapo.ini when it was spawned, so `reload-config` replaces it
(`Spare.reset`). Without the server's lifespan (`start`) every take spawns.
"""

import multiprocessing as mp
import os
import threading as th


def serve(conn, parent_pid):
    """Wait in the spare process for what to become."""
    from ..core.runner import watch
    th.Thread(target=watch, args=(parent_pid,), daemon=True).start()
    from ..database import db
    from . import explain, worker  # noqa: F401, loaded ahead of the task
    try:
        # The pool keeps it, so the task's first statement needs no logon.
        db.engine.raw_connection().close()
    except Exception:
        pass
    try:
        kind, arguments = conn.recv()
    except (EOFError, OSError):
        os._exit(0)
    if kind == 'analysis':
        sql, settings = arguments
        worker.Worker(conn, sql, settings).run()
    elif kind == 'explain':
        from .explain_job import work
        work(conn, *arguments, parent_pid)
    os._exit(0)


def _spawn():
    context = mp.get_context('spawn')
    conn, child = context.Pipe()
    process = context.Process(name='rapo-analysis-spare', target=serve,
                              args=(child, os.getpid()), daemon=True)
    process.start()
    child.close()
    return process, conn


class Spare:
    """Represents the spare process of this server."""

    def __init__(self):
        self.lock = th.Lock()
        self.process = None
        self.conn = None
        self.active = False

    def start(self):
        """Keep a spare from now on."""
        self.active = True
        self._refill()

    def stop(self):
        """Stop keeping a spare, and end the one waiting."""
        self.active = False
        self._retire()

    def reset(self):
        """Replace the spare, e.g. once rapo.ini was reloaded."""
        self._retire()
        if self.active:
            self._refill()

    def take(self):
        """Get a spawned process waiting for its task, and its pipe; the
        caller sends the task (see the module)."""
        with self.lock:
            process, conn = self.process, self.conn
            self.process = self.conn = None
        if process is None or not process.is_alive():
            if conn is not None:
                conn.close()
            process, conn = _spawn()
        if self.active:
            self._refill()
        return process, conn

    def _refill(self):
        th.Thread(target=self._fill, daemon=True,
                  name='analysis-spare').start()

    def _fill(self):
        with self.lock:
            if self.process is None and self.active:
                self.process, self.conn = _spawn()

    def _retire(self):
        with self.lock:
            process, conn = self.process, self.conn
            self.process = self.conn = None
        if process is None:
            return
        try:
            conn.send(('stop', None))
        except Exception:
            pass
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        conn.close()


spare = Spare()
