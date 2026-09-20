"""Command-line entry points for running rapo as a standalone app."""

import os
import signal
import sys

from .web import Server


def run_scheduler():
    """Stop a standalone scheduler of an older version, or explain the move.

    The scheduler runs inside the web server since v0.8.0.
    """
    argv = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    if argv and argv[0] == 'stop':
        from .reader import reader
        from .database import db
        record = reader.read_scheduler_record()
        if record and record['status'] == 'Y' and not record['instance_id']:
            try:
                os.kill(int(record['pid']), signal.SIGTERM)
            except OSError:
                pass
            table = db.tables.scheduler
            db.execute(table.update().values(status='N'))
            print(f'Standalone scheduler at PID {record["pid"]} stopped.')
            return
    print('rapo-scheduler is deprecated: the scheduler runs inside the web '
          'server now.\nUse "rapo-server start" and stop or start the '
          'scheduler from the UI (Instance details).', file=sys.stderr)


def run_server():
    """Start or stop the web API server as asked on the command line."""
    argv = sys.argv[1:]
    actions = [arg for arg in argv if not arg.startswith('-')]
    action = actions[0] if actions else None
    dev = 'dev' in actions
    # A reload restarts the scheduler with every change, so development
    # servers run without it unless asked to.
    scheduler = False if dev and '--scheduler' not in argv else None
    server = Server(dev=dev, scheduler=scheduler)
    if action == 'start':
        server.start()
    elif action == 'stop':
        server.stop()
    else:
        print('Usage: rapo-server start [dev] [--scheduler] | rapo-server '
              'stop', file=sys.stderr)
