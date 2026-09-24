# Rapo v0.7.0 Change Log

## Annotation
This is the first release of the fork. It moves the web server from Flask to FastAPI, replaces the UI's polling
with live updates, and brings the UI source into the repository, so that Rapo installs and runs from one folder.
The upgrade steps are in the [migration instructions](README.md).

1. **FastAPI replaces Flask.** The web server runs under uvicorn, with one worker, instead of waitress (production)
   or the flask CLI (development). The routes sit under `/api` on one `APIRouter`, and the Bearer token is checked
   by a single dependency instead of an httpauth decorator. Errors are real HTTP status codes (401, 404, 422, 400)
   instead of canned `Response` objects. The UI is served from the same port. The server is spawned as
   `python -m uvicorn` from the virtual environment's own interpreter, not from whichever script is on `PATH`.
1. **Live updates instead of polling.** A socket.io endpoint at `/api/socket.io`, where the handshake carries the
   token, pushes changes of `rapo_log` and `rapo_config` to the UI. The UI refetches when an event arrives instead
   of on a timer, pauses while its browser tab is hidden and resyncs after a reconnect. Control runs write to the
   database, not to the web server, so the server diffs those tables every two seconds while clients are
   connected. The new index on `rapo_log.updated` keeps that check cheap. Without WebSocket the UI falls back to
   HTTP long-polling.
1. **The UI source is part of the repository.** The Vue/Quasar source, previously `krokce/rapo-ui`, is in
   `rapo-ui/`. Its build writes straight into `rapo/web/ui/`, which is committed and packaged, so installing Rapo
   needs no Node. `RAPO_API_URL` points the development server's `/api` proxy at a running backend.
1. **Console scripts.** `rapo-server` and `rapo-scheduler` are installed into the environment's `bin/`, so starting
   Rapo no longer means writing a script that imports it.
1. **`rapo.ini` lives with the application.** It is read from `$RAPO_CONFIG`, or else from the application folder
   (next to the `rapo` package), instead of `~/.rapo/rapo.ini`. `rapo.ini.example` is the committed template.
1. **Rapo runs from source.** It is no longer installed from PyPI, but from its own folder with a `.venv` inside it.
   Python 3.10 or newer is required (it was 3.7).
1. **Reconciliation algorithm options follow `rapo.ini`.** Opening a reconciliation's Data tab used to write the
   current `rapo.ini` values of `fuzzy_optimization`, `discrepancy_matching`, `normalization_type` and
   `correlation_limit` into the control's `rule_config`, freezing them there. They now stay unset until picked. An
   unset option shows `Default: <value> (rapo.ini)`, and picking *Default* removes the key again. Discrepancy
   matching became a select, so it can be reset too.

## Important Changes

### Database schema
The migration [scripts](upgrade.sql) contain:

* A new index `rapo_log_updated_ix` on `rapo_log (updated)`, used to detect changed control runs.

### Dependencies
* Removed: `flask`, `flask_httpauth`, `waitress`.
* Added: `fastapi`, `uvicorn`, `python-socketio`, `websockets`.
* `python_requires` is `>=3.10`.

### Configuration
* `rapo.ini` moves from `~/.rapo/` to the application folder, or wherever `RAPO_CONFIG` points.
* Without a `[API] token` the module still loads. Every `/api` call then answers 401.

### API
* All routes are under `/api` and need `Authorization: Bearer <token>`.
* Datetimes are naive ISO strings (`2026-09-19T10:05:07`). The UI slices them instead of rebuilding `Date`
  objects, so an absent date shows as empty rather than as 1970.
* New socket.io endpoint `/api/socket.io`, which emits `runs:changed` and `controls:changed`.
* A reverse proxy must allow WebSocket upgrades for `/api/socket.io` (see the migration instructions).

### UI
* The catalogue chip of a cascade names its trigger: *Cascade after &lt;control name&gt;*.
* New cases in the Case config take the next free `case_id`.
* Shared modules replace code that was copied between pages:
  * `api.js`, one fetch helper for the token, parameters, loading bar, FastAPI error details and sign-out on 401;
  * `runActions.js`, the run actions (re-run, cancel, revoke, drop temporary tables, logs, copy SQL) shared by
    Results and the editor;
  * `constants.js`, the control types, colors and run statuses;
  * `utils/format.js` for dates, numbers and the clipboard, `utils/sort.js` (missing values last) and
    `utils/schedule.js`;
  * the `columnFilter` mixin, which replaces search functions pasted into five components.
* Pages read the catalogue and the runs from the Vuex store instead of keeping their own copies, and the columns
  of a datasource are fetched once.
* Editor boxes edit the parent's configuration in place instead of copying it and syncing it back. The two
  comparison criteria boxes are merged into one.
* The header search box is shown according to the route's `meta`.

## Fixes
* The control editor edits a copy of the control, so unsaved edits and clones no longer leak into the catalogue.
* Datasource watchers no longer reset columns and dates while a control is loaded, cloned or switched to another
  version.
* The version select is hidden for clones, since picking a version restored the original's `control_id`.
* The scheduler period validation could never be reached. It runs now.
* A single day picked in range mode sends real dates, and "today" is the local date.
* Error logs and version diffs are escaped before they are shown as HTML.
* A null `schedule_config` no longer breaks the catalogue.
* The examples of the error definition box were fixed.
