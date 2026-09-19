"""Contains application logger.

Log files are written to the `[LOGGING] directory` folder (default `logs`
next to rapo.ini):

* `rapo-server_YYYYMMDD.log` - the server, scheduler and run manager, one
  file per day;
* `controls/<control_id>/<process_id>.log` - one file per control run,
  written by the run process (see `open_run_log`).
"""

import os

import pepperoni

from . import config as configurator
from .config import config


# [LOGGING] options passed as they are to pepperoni.
PEPPERONI_OPTIONS = ['console', 'file', 'info', 'debug', 'warning', 'error',
                     'critical', 'format', 'maxsize', 'maxlevel', 'maxerrors']
SERVER_LOG_NAME = 'rapo-server_{root.logger.start_date:%Y%m%d}'


def get_setting(name, default=None):
    """Get LOGGING option or default when it is not set."""
    if config.check('LOGGING'):
        value = config['LOGGING'].get(name)
        if value is not None:
            return value
    return default


def get_log_dir():
    """Get absolute log folder, relative paths start at rapo.ini folder."""
    directory = os.path.expanduser(str(get_setting('directory', 'logs')))
    base = os.path.dirname(configurator.path)
    return os.path.abspath(os.path.join(base, directory))


def run_log_path(control_id, process_id):
    """Get path of the log file of one control run."""
    return os.path.join(LOG_DIR, 'controls', str(control_id),
                        f'{process_id}.log')


def open_run_log(control_id, process_id):
    """Write the log of this process to the file of the given control run.

    The file is never rotated, so each run has exactly one file.
    """
    directory = os.path.dirname(run_log_path(control_id, process_id))
    logger.configure(directory=directory, filename=str(process_id),
                     maxsize=False, maxdays=False)


LOG_DIR = get_log_dir()

logger = pepperoni.logger(file=True)
logger.configure(format='{isodate}\t{thread}\t{rectype}\t{message}\n')

if config.check('LOGGING'):
    parameters = {key: value for key, value in config['LOGGING'].items()
                  if key in PEPPERONI_OPTIONS}
    logger.configure(**parameters)

logger.configure(directory=LOG_DIR, filename=SERVER_LOG_NAME)
