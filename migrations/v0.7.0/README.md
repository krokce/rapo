# Rapo v0.7.0 Migration Instructions
This short document describes how to upgrade Rapo from v0.6.15 to v0.7.0:

1. Wait until all your Rapo controls are completed or cancel them. Stop the scheduler and the web server.
    ```bash
    rapo-scheduler stop
    rapo-server stop
    ```
1. Replace the pip module with the Rapo source. Rapo is no longer published on PyPI: it runs from its own folder
   (the application folder) with a virtual environment inside it.
    ```bash
    pip uninstall rapo
    git clone <rapo-repository-url> rapo
    cd rapo
    git checkout v0.7.0
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-build-isolation -e .
    ```
   `<rapo-repository-url>` is the Git repository Rapo is distributed from. Without Git access, copy the source of
   the release into the application folder instead of cloning it; the later updates then replace that folder's
   content the same way.

   The requirements bring new dependencies `python-socketio` and `websockets` used for live UI updates. The built UI
   is part of the source, so Node is not needed. The commands `rapo-server` and `rapo-scheduler` are now in
   `.venv/bin/`; update any service or startup scripts accordingly.
1. Move the configuration file from `~/.rapo/rapo.ini` to the application folder, or point the `RAPO_CONFIG`
   environment variable to it. Compare it with `rapo.ini.example` for the available options.
    ```bash
    mv ~/.rapo/rapo.ini rapo.ini
    ```
1. Execute migration SQL [scripts](upgrade.sql) in database, which include:
    1. Index on `rapo_log.updated`, used by the web server to detect changed control runs and push them to the UI.
1. If the web server is behind a reverse proxy, allow WebSocket upgrades for `/api/socket.io`, e.g. for nginx:
    ```nginx
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    ```
   Without it the UI still works over HTTP long-polling.
1. Start the scheduler and the web server.
    ```bash
    .venv/bin/rapo-scheduler start
    .venv/bin/rapo-server start
    ```

## What this release contains
* **FastAPI** replaces Flask. The web server runs under uvicorn (one worker), the routes sit under `/api` and are
  guarded by a Bearer token, errors are real HTTP codes, and the UI is served from the same port.
* **Live updates instead of polling.** A socket.io endpoint at `/api/socket.io` pushes the changes of `rapo_log`
  and `rapo_config` to the UI, which refetches on them rather than on a timer.
* **The UI source is part of the repository** (`rapo-ui/`), and its build output (`rapo/web/ui/`) is committed and
  packaged, so installing Rapo needs no Node.
* **`rapo.ini` lives in the application folder** instead of `~/.rapo/`, or wherever `RAPO_CONFIG` points.
* **UI fixes and cleanup.** The editor edits a copy of the control, so unsaved edits and clones no longer leak into
  the catalogue; datasource watchers no longer reset columns and dates while a control is loaded, cloned or
  switched to another version; a single day picked in range mode sends real dates; error logs and version diffs are
  escaped before they are shown as HTML; a null `schedule_config` no longer breaks the catalogue.
* **Shared UI modules.** One API helper (token, parameters, loading bar, error details, sign-out on 401), one set
  of run actions, one schedule parser, one sort, one column filter, and pages reading the store instead of keeping
  their own copies.
* **Reconciliation algorithm options follow `rapo.ini`.** Opening a reconciliation no longer copies the current
  `fuzzy_optimization`, `discrepancy_matching`, `normalization_type` and `correlation_limit` into its `rule_config`;
  an unset option shows the value it falls back to, and Default removes the key again.
