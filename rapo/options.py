"""Contains the catalogue of the rapo.ini options.

Every option rapo reads is listed here once, in the order the Configuration
tab shows it, with its type, the default used when rapo.ini does not set it,
and a short description. Modules read their defaults from here, so that what
the UI says is what the code does. A new option is added here and to
rapo.ini.example.
"""

import collections

from .config import config, is_secret, needs_restart


Option = collections.namedtuple(
    'Option', ['section', 'name', 'type', 'default', 'description', 'choices',
               'minimum', 'secret', 'deprecated'])

# Types: bool, int, float, text, choice (one of choices), path.
TYPES = ('bool', 'int', 'float', 'text', 'choice', 'path')

SECTIONS = collections.OrderedDict([
    ('SCHEDULER', 'The scheduler and run manager of this server'),
    ('DATABASE', 'The Oracle database rapo works in (read at start)'),
    ('API', 'The web server: address, port and access token (read at start)'),
    ('LOGGING', 'Server and run log files'),
    ('ALGORITHM', 'Instance defaults of the reconciliation algorithm (REC), used where a control sets none'),
    ('EMAIL', 'Sending of control results per email'),
    ('ANALYSIS', 'Data analysis and discrepancy analysis of run records'),
    ('KPI', 'KPI calculation from the control editor and the run menus'),
    ('VIEWS', 'Editing the SQL of view datasources from the control editor'),
    ('DATASOURCES', 'PDI Core datasources and files pages'),
    ('HEALTH', 'Instance health: sampling, history and warning levels'),
])

CATALOGUE = []


def _add(section, name, type, default, description, choices=None,
         minimum=None, secret=False, deprecated=()):
    CATALOGUE.append(Option(section, name, type, default, description,
                            choices, minimum, secret, tuple(deprecated)))


# [SCHEDULER]
_add('SCHEDULER', 'instance_name', 'text', None,
     'Name of this instance in the UI header and browser tab, e.g. AUT Dev')
_add('SCHEDULER', 'enabled', 'bool', True,
     'Run the scheduler here; off: API only (RAPO_SCHEDULER overrides it)')
_add('SCHEDULER', 'control_parallelism', 'int', 10,
     'Runs executed at once on this server; more wait in a queue', minimum=1)
_add('SCHEDULER', 'refresh_interval', 'int', 300,
     'Seconds between full reloads of the schedules (changes apply anyway)',
     minimum=5)
_add('SCHEDULER', 'maintenance_interval', 'int', None,
     'Seconds between maintenance runs (clean-up, retention); empty: none',
     minimum=60)
_add('SCHEDULER', 'database_report_interval', 'int', None,
     'Seconds between connection pool reports in the server log; empty: none',
     minimum=60)
_add('SCHEDULER', 'lease_timeout', 'int', 60,
     'Seconds without heartbeat before another server takes over',
     minimum=20)
_add('SCHEDULER', 'event_retention_days', 'int', 90,
     'Days scheduler events (fires, manual runs, missed fires) are kept',
     minimum=1)
_add('SCHEDULER', 'missed_window_hours', 'int', 24,
     'Hours back that fires missed while no scheduler ran are recorded',
     minimum=0)

# [DATABASE]
_add('DATABASE', 'vendor_name', 'text', None,
     'Database vendor, oracle', deprecated=['vendor'])
_add('DATABASE', 'driver_name', 'text', None,
     'SQLAlchemy driver, cx_oracle (served by python-oracledb)')
_add('DATABASE', 'host', 'text', None, 'Database host')
_add('DATABASE', 'port', 'int', None, 'Listener port, usually 1521')
_add('DATABASE', 'service_name', 'text', None,
     'Service name to connect to; or sid', deprecated=['service'])
_add('DATABASE', 'sid', 'text', None, 'SID to connect to, instead of '
     'service_name')
_add('DATABASE', 'path', 'text', None,
     'A full address instead of host, port and service, e.g. a TNS alias')
_add('DATABASE', 'username', 'text', None, 'Database user (schema of rapo)',
     deprecated=['user'])
_add('DATABASE', 'password', 'text', None, 'Password of the database user',
     secret=True)
_add('DATABASE', 'client_path', 'path', None,
     'Folder of the Oracle Instant Client; empty: the library path')
_add('DATABASE', 'pool_size', 'int', 5,
     'Connections kept open in the pool of each process', minimum=1)
_add('DATABASE', 'max_overflow', 'int', 10,
     'Connections opened beyond pool_size at peaks', minimum=0)
_add('DATABASE', 'pool_timeout', 'int', 30,
     'Seconds to wait for a free connection of the pool', minimum=1)
_add('DATABASE', 'pool_recycle', 'int', -1,
     'Seconds after which a connection is opened anew; -1: never')
_add('DATABASE', 'pool_pre_ping', 'bool', True,
     'Test a connection before use, so a dropped one is replaced')
_add('DATABASE', 'max_identifier_length', 'int', 128,
     'Longest table or column name the database accepts', minimum=30)

# [API]
_add('API', 'host', 'text', '127.0.0.1',
     'Address the web server listens on; 0.0.0.0 for all interfaces')
_add('API', 'port', 'int', 8080, 'Port of the web server, API and UI',
     minimum=1)
_add('API', 'token', 'text', None,
     'Bearer token every /api request and the UI login need', secret=True)
_add('API', 'docs', 'bool', False,
     'Serve Swagger at /api/docs and /api/openapi.json, without the token')

# [LOGGING]
_add('LOGGING', 'directory', 'path', 'logs',
     'Folder of the server and run logs, relative to the folder of rapo.ini')
_add('LOGGING', 'retention_days', 'int', None,
     'Days server logs and logs of deleted controls are kept; empty: '
     'forever', minimum=1)
_add('LOGGING', 'console', 'bool', True,
     'Write log records to the console (the web server starts without)')
_add('LOGGING', 'file', 'bool', True, 'Write log records to the log files')
_add('LOGGING', 'info', 'bool', True, 'Write INFO records')
_add('LOGGING', 'debug', 'bool', False, 'Write DEBUG records')
_add('LOGGING', 'warning', 'bool', True, 'Write WARNING records')
_add('LOGGING', 'error', 'bool', True, 'Write ERROR records')
_add('LOGGING', 'critical', 'bool', True, 'Write CRITICAL records')
_add('LOGGING', 'format', 'text', '{isodate}\t{thread}\t{rectype}\t{message}\n',
     'Template of a log record (pepperoni placeholders)')
_add('LOGGING', 'maxsize', 'int', 10485760,
     'Bytes after which a log file continues in a new one', minimum=1024)
_add('LOGGING', 'maxlevel', 'int', 2,
     'Depth of the traceback written with an error', minimum=0)
_add('LOGGING', 'maxerrors', 'int', None,
     'Errors after which the logger stops the process; empty: no limit',
     minimum=1)

# [ALGORITHM]
_add('ALGORITHM', 'fuzzy_optimization', 'bool', True,
     'Match records by their closest dates within the time shift')
_add('ALGORITHM', 'normalization_type', 'choice', 'default',
     'How field distances are scaled before ranking candidate matches',
     choices=['default', 'none', 'minmax', 'rank', 'z_norm', 'srd'])
_add('ALGORITHM', 'discrepancy_matching', 'bool', False,
     'Pair the records left over on both sides as value discrepancies')

# [EMAIL]
_add('EMAIL', 'enabled', 'bool', False,
     'Send control results per email; off: no email leaves this instance')
_add('EMAIL', 'host', 'text', None, 'SMTP server')
_add('EMAIL', 'port', 'int', None,
     'SMTP port; empty: 465 with ssl, else 587', minimum=1)
_add('EMAIL', 'security', 'choice', 'starttls',
     'Encryption of the SMTP connection', choices=['starttls', 'ssl', 'none'])
_add('EMAIL', 'user', 'text', None, 'SMTP login, when the server needs one')
_add('EMAIL', 'password', 'text', None, 'Password of the SMTP login',
     secret=True)
_add('EMAIL', 'timeout', 'int', 30, 'Seconds to wait for the SMTP server',
     minimum=1)
_add('EMAIL', 'sender', 'text', None, 'Sender address (From)')
_add('EMAIL', 'sender_name', 'text', None, 'Display name of the sender')
_add('EMAIL', 'reply_to', 'text', None, 'Reply-To address')
_add('EMAIL', 'max_attachment_rows', 'int', 100000,
     'Rows above which a result file is not attached (a note instead)',
     minimum=1)
_add('EMAIL', 'max_attachment_mb', 'int', 20,
     'Megabytes above which a result file is not attached', minimum=1)

# [ANALYSIS]
_add('ANALYSIS', 'initial_rows', 'int', 50000,
     'Rows of the sample loaded when Data analysis opens', minimum=1)
_add('ANALYSIS', 'extend_rows', 'int', 50000,
     'Rows added to the sample by each Extend', minimum=1)
_add('ANALYSIS', 'max_rows', 'int', 1000000, 'Largest sample', minimum=1)
_add('ANALYSIS', 'max_sessions', 'int', 4,
     'Samples open at once on this server (a comparison holds two)',
     minimum=1)
_add('ANALYSIS', 'idle_minutes', 'int', 15,
     'Minutes an unused analysis is kept before its memory is freed',
     minimum=1)
_add('ANALYSIS', 'max_memory_mb', 'int', 2048,
     'Memory of a sample process above which the sample stops growing',
     minimum=64)
_add('ANALYSIS', 'discrepancy_quick_rows', 'int', 100000,
     'Records per dataset of the quick look of a discrepancy analysis',
     minimum=1000)
_add('ANALYSIS', 'discrepancy_exact_rows', 'int', 1000000,
     'Records counted exactly when refining; larger datasets are sampled',
     minimum=1000)
_add('ANALYSIS', 'discrepancy_parallel', 'int', 4,
     'Degree of the parallel hint of the refining scans; 0: none', minimum=0)
_add('ANALYSIS', 'discrepancy_timeout_minutes', 'int', 20,
     'Minutes after which a discrepancy analysis is stopped', minimum=1)

# [KPI]
_add('KPI', 'calculate_timeout', 'int', 120,
     'Seconds a KPI or alarm statement may run in Calculate KPIs', minimum=1)

# [VIEWS]
_add('VIEWS', 'edit', 'bool', True,
     'Allow replacing the SQL of a view datasource from the control editor')
_add('VIEWS', 'preview_max_rows', 'int', 1000,
     'Rows a view preview may fetch at most', minimum=1)
_add('VIEWS', 'preview_timeout', 'int', 30,
     'Seconds a view preview may run', minimum=1)

# [DATASOURCES]
_add('DATASOURCES', 'scan_interval', 'int', 60,
     'Seconds between counts of the waiting files, while the UI is open',
     minimum=5)
_add('DATASOURCES', 'scan_max_entries', 'int', 200000,
     'Files read per directory and count at most', minimum=1)
_add('DATASOURCES', 'scan_budget_seconds', 'int', 20,
     'Seconds one count may take; the rest is counted first next time',
     minimum=1)
_add('DATASOURCES', 'list_max_files', 'int', 10000,
     'Files listed by the file dialogs at most', minimum=1)
_add('DATASOURCES', 'list_budget_seconds', 'int', 10,
     'Seconds a listing may read before it is shown cut', minimum=1)
_add('DATASOURCES', 'clean_max_bytes', 'int', 1024,
     'Size below which a file matching the clean-up mask is listed',
     minimum=0)
_add('DATASOURCES', 'dir_mode', 'text', '2775',
     'Mode (octal) of directories created from the UI')
_add('DATASOURCES', 'stalled_minutes', 'int', 60,
     'Age of the oldest waiting file that flags a datasource Stalled',
     minimum=1)
_add('DATASOURCES', 'lock_stale_minutes', 'int', 30,
     'Age of a lane lock shown as probably stale', minimum=1)
_add('DATASOURCES', 'file_download', 'bool', True,
     'Allow downloading loaded files from the file log')
_add('DATASOURCES', 'max_download_mb', 'int', 500,
     'Largest download (one file or a ZIP of several)', minimum=1)
_add('DATASOURCES', 'view_lines', 'int', 100,
     'Lines the file viewer reads at a time', minimum=1)
_add('DATASOURCES', 'view_max_lines', 'int', 50000,
     'Lines the file viewer keeps at most; further: search or download',
     minimum=100)
_add('DATASOURCES', 'view_line_chars', 'int', 10000,
     'Characters of a line the file viewer shows and searches; longer cut',
     minimum=100)
_add('DATASOURCES', 'view_grep_seconds', 'int', 20,
     'Seconds one search of the file viewer may read before it pauses',
     minimum=1)
_add('DATASOURCES', 'view_grep_matches', 'int', 500,
     'Matching lines one search of the file viewer returns at most',
     minimum=1)
_add('DATASOURCES', 'file_upload', 'bool', False,
     'Allow uploading files into the input directory of a datasource')
_add('DATASOURCES', 'max_upload_mb', 'int', 2048,
     'Largest uploaded file', minimum=1)

# [HEALTH]
_add('HEALTH', 'enabled', 'bool', True,
     'Sample the OS and database metrics of the Health tab')
_add('HEALTH', 'os_interval', 'int', 10, 'Seconds between OS samples',
     minimum=1)
_add('HEALTH', 'db_interval', 'int', 30, 'Seconds between database samples',
     minimum=1)
_add('HEALTH', 'footprint_interval', 'int', 600,
     "Seconds between reads of the size of rapo's tables", minimum=1)
_add('HEALTH', 'history_minutes', 'int', 60,
     'Minutes of samples kept (the 1h span)', minimum=1)
_add('HEALTH', 'history_hours', 'int', 24,
     'Hours of one-minute aggregates kept (the longer spans)', minimum=1)
HEALTH_LEVELS = [
    ('cpu', 80, 95, 'host CPU %, average of the last 3 samples'),
    ('memory', 85, 95, 'host memory used %'),
    ('disk', 85, 95, 'used % of the fullest file system of the logs, rapo or the datasource directories'),
    ('close_wait', 50, None, 'host TCP connections in CLOSE_WAIT'),
    ('db_cpu', 80, 95, 'database CPU % of cpu_count'),
    ('db_memory', 85, 95, 'PGA allocated, % of pga_aggregate_limit'),
    ('storage', 85, 95, 'used % of the fullest default or temp tablespace'),
    ('locks', 1, None, 'sessions blocked by another'),
    ('locks_wait', None, 60, 'seconds the longest blocked session waits'),
]
for _rule, _warn, _crit, _text in HEALTH_LEVELS:
    _add('HEALTH', f'{_rule}_warn', 'float', _warn, f'Warning level: {_text}')
    _add('HEALTH', f'{_rule}_crit', 'float', _crit,
         f'Critical level: {_text}')

INDEX = {(option.section, option.name): option for option in CATALOGUE}


def find(section, name):
    """Get the option, by its name or a deprecated one, or None."""
    section = section.upper()
    name = name.lower()
    option = INDEX.get((section, name))
    if option:
        return option
    for option in CATALOGUE:
        if option.section == section and name in option.deprecated:
            return option
    return None


def default(section, name):
    """Get the default of an option."""
    return INDEX[(section.upper(), name.lower())].default


def defaults(section):
    """Get {name: default} of the options of a section."""
    return {option.name: option.default for option in CATALOGUE
            if option.section == section}


def get(section, name):
    """Get the value of an option: rapo.ini's when set, else the default.

    Read at every call, so a reload of rapo.ini applies at once.
    """
    values = config.get(section) or {}
    value = values.get(name)
    if value is None:
        for alias in INDEX[(section, name)].deprecated:
            if values.get(alias) is not None:
                return values.get(alias)
        return default(section, name)
    return value


def is_hidden(option):
    """Check whether the option's value is never shown."""
    return option.secret or is_secret(option.name)


def is_editable(option):
    """Check whether the option can be changed from the UI: not a secret and
    applied without a restart.
    """
    return not is_hidden(option) and not needs_restart(option.section,
                                                       option.name)


class OptionError(ValueError):
    """A value that does not fit its option."""


def parse(option, value):
    """Get the text written to rapo.ini for a value sent by the UI.

    Raises OptionError when the value does not fit the option.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return ''
    if option.type == 'bool':
        if isinstance(value, bool):
            return 'True' if value else 'False'
        text = str(value).strip().lower()
        if text in ('true', 'false'):
            return text.capitalize()
        raise OptionError(f'{option.name} is True or False')
    if option.type in ('int', 'float'):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise OptionError(f'{option.name} is a number')
        if option.type == 'int' and number != int(number):
            raise OptionError(f'{option.name} is a whole number')
        if number == int(number):
            number = int(number)
        if option.minimum is not None and number < option.minimum:
            raise OptionError(f'{option.name} is at least {option.minimum}')
        return str(number)
    text = str(value)
    if '\n' in text or '\r' in text:
        raise OptionError(f'{option.name} is a single line')
    text = text.strip()
    if option.type == 'choice' and text not in option.choices:
        raise OptionError(f'{option.name} is one of '
                          f'{", ".join(option.choices)}')
    return text


def missing_from_catalogue():
    """Get the options of rapo.ini.example (next to the package, in a source
    checkout) this catalogue lacks, as SECTION.name; empty without the file.
    """
    import configparser
    import os
    example = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                           'rapo.ini.example')
    parser = configparser.ConfigParser(allow_no_value=True)
    try:
        if not parser.read(example, encoding='utf-8'):
            return []
    except configparser.Error:
        return []
    return [f'{section}.{name}' for section in parser.sections()
            for name in parser.options(section) if not find(section, name)]
