"""Contains the access scopes of API tokens and the scope of every route.

A token holds a level per area (`none` < `view` < `operate` < `edit`, each
level allowing the ones below it) and the `free_sql` flag. A route needs one
(area, level), or one of its ALSO; a route in FREE_SQL_ROUTES also needs the flag. A route in neither
PUBLIC nor ROUTES is refused (`check_routes` stops the server at start).
The UI takes AREAS and PRESETS from get-api-tokens; its pages need the
levels set as `meta.scope` of their routes (rapo-ui/src/router.js).
"""

LEVELS = ('none', 'view', 'operate', 'edit')

# Area: (title, levels it offers, what each level allows).
AREAS = {
    'dashboard': ('Dashboard', ('none', 'view')),
    'runs': ('Runs', ('none', 'view', 'operate')),
    'data': ('Data', ('none', 'view')),
    'controls': ('Controls', ('none', 'view', 'edit')),
    'kpis': ('KPIs', ('none', 'view', 'operate', 'edit')),
    'scheduler': ('Scheduler', ('none', 'view', 'operate')),
    'datasources': ('Datasources', ('none', 'view', 'edit')),
    'files': ('Files', ('none', 'view', 'operate')),
    'instance': ('Instance', ('none', 'view', 'operate', 'edit')),
}

# What each level of an area allows, for the token editor (none: no access).
DESCRIPTIONS = {
    'dashboard': {
        'view': 'Open the Dashboard with all of its panels: runs, scheduler, '
                'files, KPIs and the instance health'},
    'runs': {
        'view': 'See the results of the runs and their logs (Results, the '
                "editor's Run log); counts only, no records",
        'operate': 'See results and run logs; run, re-run, cancel and revoke '
                   'runs, run missed fires, resend the email'},
    'data': {
        'view': 'Read the records behind runs and files: Data analysis, '
                'Discrepancy analysis, the file viewer, loaded records and '
                'file downloads'},
    'controls': {
        'view': 'See the controls, their versions and result table state; the '
                'editor opens read only',
        'edit': 'Create, change, clone and delete controls, update or recreate '
                'their result tables, delete versions, edit view SQL'},
    'kpis': {
        'view': 'See the KPI types, the KPIs of the controls and their values',
        'operate': 'See KPIs; calculate them for a run and store them again '
                   '(re-ingest)',
        'edit': 'See and calculate KPIs; create, change and delete KPI types, '
                'clean up orphan KPIs'},
    'scheduler': {
        'view': 'See the Scheduler page: running, upcoming and past fires',
        'operate': 'See the Scheduler page; stop and start the scheduler for '
                   'every server'},
    'datasources': {
        'view': 'See the PDI Core datasources, their directories, waiting '
                'files, archive and ASN.1 grammars',
        'edit': 'Change, enable, disable and delete datasources, create '
                'directories, edit ASN.1 grammars and viewer settings'},
    'files': {
        'view': 'See the file log by day and the lane locks; file names and '
                'counts only',
        'operate': 'See the file log; recycle, reload and delete files, set '
                   'and remove lane locks, upload files, re-sum the summary'},
    'instance': {
        'view': 'See Instance details: rapo.ini, health, database sessions and '
                'leftover temporary tables',
        'operate': 'See Instance details; drop leftover temporary tables',
        'edit': 'See Instance details; change rapo.ini options and reload '
                'them'},
}

FREE_SQL = ('Free SQL', 'Send SQL that runs as the schema owner and can '
            'read any table: Check, Preview, Data analysis filters, draft '
            'KPIs, view SQL')

# Levels that save SQL text, which runs as the schema owner later.
NEEDS_FREE_SQL = {'controls': 'edit', 'kpis': 'edit'}

PRESETS = {
    'viewer': {'scopes': {'dashboard': 'view', 'runs': 'view',
                          'controls': 'view', 'kpis': 'view',
                          'scheduler': 'view', 'datasources': 'view',
                          'files': 'view'},
               'free_sql': False},
    'operator': {'scopes': {'dashboard': 'view', 'runs': 'operate',
                            'data': 'view', 'controls': 'view',
                            'kpis': 'operate', 'scheduler': 'operate',
                            'datasources': 'view', 'files': 'operate',
                            'instance': 'view'},
                 'free_sql': False},
    'editor': {'scopes': {'dashboard': 'view', 'runs': 'operate',
                          'data': 'view', 'controls': 'edit',
                          'kpis': 'edit', 'scheduler': 'operate',
                          'datasources': 'edit', 'files': 'operate',
                          'instance': 'view'},
               'free_sql': True},
    'full': {'scopes': {area: levels[-1]
                        for area, (_, levels) in AREAS.items()},
             'free_sql': True},
}

# Open to every valid token (reset-my-token acts only on the caller's own).
PUBLIC = {'help', 'status', 'session', 'version', 'info', 'whoami',
          'reset-my-token'}

# Only the master token ([API] token of rapo.ini).
MASTER = {'get-api-tokens', 'create-api-token', 'update-api-token',
          'extend-api-token', 'regenerate-api-token', 'revoke-api-token',
          'delete-api-token'}

# Routes taking SQL text that is run or parsed as given. calculate-kpi (a
# draft statement) checks it itself (`auth.require_free_sql`); a raw `where` of
# analysis-start(-file) and validate-analysis-where needs it only beyond a
# plain filter of the dataset's columns (`auth.require_filter`).
FREE_SQL_ROUTES = {'validate-sql', 'validate-kpi-sql', 'check-view', 'preview-view',
            'compile-view', 'check-control-schema',
            'save-control', 'save-kpi-type'}


def _routes(area, level, *names):
    return {name: (area, level) for name in names}


ROUTES = {
    **_routes('dashboard', 'view', 'get-dashboard'),
    **_routes('runs', 'view',
              'get-control-runs', 'get-control-run', 'get-run-calendar',
              'read-control-logs', 'get-control-run-log',
              'download-control-run-log', 'get-running-controls',
              'get-control-trend'),
    **_routes('runs', 'operate',
              'run-control', 'cancel-control', 'revoke-control-run',
              'run-missed', 'send-control-email', 'iteration-preview'),
    **_routes('data', 'view',
              'get-run-dataset-sql', 'analysis-start', 'analysis-start-file',
              'analysis-status', 'analysis-extend', 'analysis-cancel',
              'analysis-close', 'analysis-rows', 'analysis-profile',
              'analysis-groups', 'validate-analysis-where',
              'analysis-counterpart', 'analysis-export',
              'start-discrepancy-analysis', 'stop-discrepancy-analysis',
              'get-discrepancy-analysis', 'get-file-tables',
              'get-file-records', 'download-ds-files', 'view-ds-file',
              'grep-ds-file', 'get-ds-file-asn1', 'get-ds-file-asn1-node',
              'locate-ds-file-asn1', 'get-ds-file-bytes',
              'render-ds-file-asn1', 'search-ds-file-asn1'),
    **_routes('controls', 'view',
              'get-all-controls', 'get-schema-drift', 'get-control-versions',
              'get-datasources', 'get-datasource-columns', 'get-view',
              'check-view', 'preview-view', 'format-view',
              'get-object-columns', 'count-control-table-rows',
              'schedule-preview', 'get-next-fires', 'validate-sql'),
    **_routes('controls', 'edit',
              'save-control', 'delete-control', 'check-control-schema',
              'update-control-schema', 'recreate-control-schema',
              'delete-control-output-tables', 'drop-orphaned-table',
              'delete-control-versions', 'send-test-email', 'compile-view'),
    **_routes('kpis', 'view',
              'get-kpi-types', 'get-control-kpis', 'get-kpi-type-usage',
              'get-orphan-kpis', 'get-kpi-history', 'get-kpi-runs',
              'validate-kpi-sql'),
    **_routes('kpis', 'operate', 'calculate-kpi', 'reingest-kpis'),
    **_routes('kpis', 'edit',
              'save-kpi-type', 'delete-kpi-type', 'delete-orphan-kpis',
              'reassign-orphan-kpi'),
    **_routes('scheduler', 'view',
              'scheduler-status', 'scheduler-upcoming', 'scheduler-events',
              'get-missed-fires'),
    **_routes('scheduler', 'operate', 'scheduler-stop', 'scheduler-start'),
    **_routes('datasources', 'view',
              'get-ds-list', 'get-ds-status', 'get-ds-config',
              'check-ds-directories', 'count-ds-file-log', 'get-ds-files',
              'check-ds-mask', 'list-ds-archive', 'get-ds-table-facts',
              'get-asn1-grammars', 'get-asn1-grammar-types',
              'get-asn1-grammar', 'get-viewer-settings'),
    **_routes('datasources', 'edit',
              'save-ds-config', 'set-ds-active', 'delete-ds-config',
              'create-ds-directory', 'save-asn1-grammar',
              'delete-asn1-grammar', 'save-viewer-settings'),
    **_routes('files', 'view',
              'get-ds-file-log', 'get-ds-file-log-text', 'get-files-day',
              'search-files', 'get-pdi-state'),
    **_routes('files', 'operate',
              'set-file-status', 'remove-lane-lock', 'set-lane-lock',
              'set-global-lock', 'check-ds-upload', 'upload-ds-file',
              'refresh-file-summary'),
    **_routes('instance', 'view',
              'parameters', 'get-instance-health', 'get-instance-sessions',
              'get-config-changes', 'get-config-catalogue',
              'get-temp-tables'),
    **_routes('instance', 'operate', 'drop-temp-tables'),
    **_routes('instance', 'edit', 'set-config-option', 'reload-config'),
}

# Routes that other pages read too: the Dashboard shows the health and the
# scheduler's state, the header the scheduler's state, Scheduler names the
# controls, Results the KPI types of the controls, Files the datasources,
# the datasource editor the tables, the analysis pages a run's trend.
ALSO = {
    'get-instance-health': (('dashboard', 'view'),),
    'scheduler-status': (('dashboard', 'view'), ('runs', 'view'),
                         ('controls', 'view')),
    'get-all-controls': (('scheduler', 'view'),),
    'get-next-fires': (('scheduler', 'view'), ('kpis', 'view')),
    'get-kpi-type-usage': (('runs', 'view'), ('controls', 'view')),
    'get-ds-list': (('files', 'view'),),
    'get-ds-status': (('files', 'view'),),
    'get-datasources': (('datasources', 'view'),),
    'get-control-trend': (('data', 'view'),),
    'get-viewer-settings': (('data', 'view'),),
}


def allows(scopes, area, level):
    """Tell whether scopes {area: level} reach `level` in `area`."""
    held = (scopes or {}).get(area, 'none')
    if held not in LEVELS or level not in LEVELS:
        return False
    return LEVELS.index(held) >= LEVELS.index(level)


def normalize(scopes, free_sql):
    """Check scopes given for a token and get them complete, with `none`
    for an area not given. Raises ValueError naming the first problem.
    """
    if not isinstance(scopes, dict):
        raise ValueError('Scopes must be an object {area: level}.')
    unknown = sorted(set(scopes) - set(AREAS))
    if unknown:
        raise ValueError(f'Unknown scope area: {", ".join(unknown)}.')
    result = {}
    for area, (title, levels) in AREAS.items():
        level = scopes.get(area) or 'none'
        if level not in levels:
            raise ValueError(f'{title} has no level {level!r} '
                             f'({", ".join(levels)}).')
        result[area] = level
    for area, level in NEEDS_FREE_SQL.items():
        if allows(result, area, level) and not free_sql:
            raise ValueError(f'{AREAS[area][0]}: {level.title()} needs Free '
                             f'SQL: its SQL runs as the schema owner.')
    return result


def route_name(path):
    """Get the route name of an /api path (`/api/run-control` → run-control)."""
    return path.rsplit('/api/', 1)[-1].strip('/')


def check_routes(router):
    """Raise RuntimeError for a route of the router without a scope."""
    names = {route_name(route.path) for route in router.routes}
    missing = sorted(names - PUBLIC - MASTER - set(ROUTES))
    if missing:
        raise RuntimeError('API routes without an access scope in '
                           f'rapo/web/api/scopes.py: {", ".join(missing)}')
