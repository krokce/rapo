# Rapo fork — Release Notes

These are the releases of this fork of [t3eHawk/rapo](https://github.com/t3eHawk/rapo), which it branched from at
v0.6.15. Releases are listed newest first, and each release's changes run from the most to the least impactful.
The full notes and upgrade steps of each release are in `migrations/<version>/` (`CHANGELOG.md`, `README.md`).

---

## v0.8.3 — 2026-09-24

No change to Rapo's own schema. Redeploy `schema/rapo_usage_rule.sql` if you use the `PL` engine.

- **Chain-rules.** A control can use another control's result table (`RAPO_REST_`/`RESA_`/`RESB_<name>`) as a
  datasource. Every run of it first runs that upstream control, and that control's own upstreams, for the
  **puller's own window**. It then reads only the records those runs saved (by `rapo_process_id`).
  - Upstream runs are depth-first and deduplicated. They skip iterations and the cascade and appear as
    `UPSTREAM` in the scheduler history.
  - The whole chain takes one execution slot. Cancelling any run in it cancels the chain, and if an upstream
    fails, the pulling control ends `E`.
  - A save is refused for self-reads, cycles, tables the upstream does not write, and cascades from an
    upstream. A rename updates the dependent controls, and a control that others read cannot be deleted.
- **Data analysis of run results.** Click a Fetched, Discrepancies or error-level number on Results to get
  *Copy SQL* or *Data analysis*. Data analysis is a pandas-profiling style page on a 50k-row sample, which you
  can extend. It runs in its own server process and has:
  - a profile of every column, with alerts;
  - correlations (Pearson, Spearman and Cramér's V);
  - a data grid with filters, search, group-by and Excel/CSV export;
  - scoped profiles ("profile these rows");
  - database-side filters and your own SQL filter;
  - a run trend with one point per day;
  - **Compare**, which ranks columns by PSI and lift against another sample (previous run, other side, fetched
    vs. discrepancies);
  - for REC, a view of each row's counterpart on the other side.

  The view is kept in the URL. New optional `[ANALYSIS]` section; `pandas` and `numpy` are now requirements.
- **Result table schema follows the configuration.** Before, result tables were created by the first run and
  never changed afterwards.
  - The editor checks for drift in the background, unsaved changes included. It offers *Update schema* (add,
    widen, make nullable, keep data) or *Recreate schema* (now drop + create, and only for the drifted tables),
    with row estimates and an exact count on request.
  - Runs heal safe drift themselves and fail with `Recreate schema needed for …` on an incompatible type.
  - A rename takes the tables and their index with it.
  - ANL/REP/CMP now save by column name, not position. A CMP without output columns uses `A_`/`B_` names, which
    fixes collisions.
  - The Controls list has a *Schema drift* chip and filter, a light dictionary-based check of the whole
    catalogue.
  - **Orphaned** tables (an unticked REC side, a former type, a deleted control) are flagged and can only be
    dropped explicitly.
- **Oracle driver `python-oracledb`** replaces `cx_Oracle`, in thick mode, so it needs no compiler and has wheels
  for Python 3.10+. Results are unchanged.
- **`install.sh`** installs or updates in one step: picks a Python 3.10+, creates or updates `.venv`, creates
  `rapo.ini` and checks the Instant Client.
- **Output limit now applies to ANL, REP and CMP.** It used to be stored but ignored, so check controls that
  already have a limit set. Error counts still report every discrepancy.
- **Variables in datasource filters and ANL mismatch criteria.** You can use `{control_name}`, `{process_id}`,
  `{control_date[_from|_to]:fmt}`, on both engines. A lenient renderer leaves unknown braces such as regex `{3}`,
  `{name}` and `{{x}}` as written.
- **Email.** Adds a *Free SQL* sheet (your own query), an *Include* switch for each sheet and a configurable
  attachment file name with variables.
- **SQL boxes.** Each box has curated examples for its context (filters, criteria, hooks, email, KPI/alarm by
  type) and a *Check* button. Check parses the statement with Oracle without running it and flags unknown
  variables, missing case IDs and stray binds. DDL is refused.
- **Editor change tracking.** *Unsaved changes* lists every value Apply would write, with JSON paths and SQL line
  diffs. A new *Manage versions* dialog compares, loads and deletes past versions: one by one, by selection, by
  age or as consecutive duplicates.
- **`rapo.ini` hot reload.** *Instance details* shows what changed on disk and reloads it. `[DATABASE]`, `[API]`,
  `LOGGING.directory` and `SCHEDULER.enabled` still need a restart.
- **Server errors are logged.** Unhandled route errors are written to the server log with their traceback and
  answer 500 with the error type and message. Before, they left no trace.
- **Fixes.**
  - A nested `CASE` in the Case definition no longer takes inner numbers for case IDs (`KeyError: 5`).
  - Logged SQL containing braces no longer crashes a run (`IndexError`) or gets rewritten.
- **Minor.**
  - Every `RAPO_TEMP_` table is created `NOLOGGING`; result tables keep `LOGGING`.
  - The Controls list has a *No KPI* chip and filter.
  - KPI chips are colored by unit.
  - `rapo-ctl.sh` is renamed `rapoctl.sh`, so update any crontab `@reboot` entry.

## v0.8.2 — 2026-09-23

No schema change. Redeploy the `PL` procedure.

- **Email results per control** (ANL, REP, REC).
  - Configured under `rule_config.email`, so it is versioned with the control.
  - To/CC/BCC; send on *done with results*, *done* or *done or error*.
  - Subject and body take variables.
  - Excel attachment with one sheet per result (REC: per side and result type), each with its own filter,
    fields and labels, and proper date and number formats.
  - Row and MB limits; resend from Results and a *Send test* in the editor.
  - Needs `[EMAIL]` in `rapo.ini`, which is off by default.
- **Apply in the control editor.**
  - *Apply* (Ctrl/Cmd+S) saves and keeps the editor open, from a sticky action bar.
  - Only real changes are written, so no empty versions appear.
  - Leaving with unsaved changes asks first, and there is a Run button in the header.
  - **Optimistic locking**: a save over someone else's newer save gets a 409, with Reload or Overwrite.
- **Eight `PL` engine fixes.**
  - Fuzzy clusters sharing a key paired wrongly, and a row without candidates shifted fuzzy positions.
  - Null-key rows were reported as losses, and a non-unique key multiplied rows.
  - An unmatched pair could stall matching, and a `DBMS_SQL` cursor leaked.
  - `max_candidates` and `need_recons` were ignored.
  - Results of `PL` controls may change. It is also faster (n=300: 12s → 7s).
- **KPI types page** (`/kpi-types`) manages the `racs_kpi_type` catalogue. A rename moves the controls' KPIs in
  one transaction, and a type in use cannot be deleted.
- **Results is the home page.**
  - Prev/Next/Today day navigation and clickable totals chips.
  - The side menu collapses to icons.
- **List pages scale to thousands of rows.**
  - Virtual scrolling on Results, Controls and the Scheduler's Upcoming and History tables.
  - Fixed column widths, one shared row menu per table and loading skeletons.
- **SQL autocomplete** in the editor's code boxes: datasource and result columns, Oracle keywords, KPI binds and
  `{variables}`.
- **Consistent look.** Type and status avatar chips everywhere, and the Scheduler tables match Results.

## v0.8.1 — 2026-09-21

Schema: new `rapo_engine_log` table and the `RAPO_USAGE_RULE` procedure.

- **`PL` engine for reconciliation** (`control_engine = 'PL'`). `RAPO_USAGE_RULE` runs the whole s01–s09
  pipeline inside Oracle as a drop-in replacement, with the same config, tables and counters.
  - It streams both sources in key order, one correlation group at a time.
  - A two-pointer band join and a per-row fan-out cap (`max_candidates`, default 100) mean no Cartesian
    product: a group costs `O(n × cap)`, not `n²`.
  - Results are identical to the `DB` engine, and it creates no `rapo_temp_source_*` tables.
  - The engine log is drained live into the run log.
  - `normalization_type = minmax` is rejected. `rank` turns out to be a no-op for match selection on both
    engines.
- **Three reconciliation algorithm fixes** that change the results of existing REC controls:
  - duplicates inside a fuzzy cluster were cross-matched (a regression from upstream `01eb3ec`);
  - the B side's `rapo_discrepancy_id` pointed at itself instead of the A row;
  - unmatched fuzzy (`F`) rows were written nowhere.
- **KPIs tab in the control editor.**
  - Edit `racs_kpi_config` statements per KPI, with "Use type default" (stores NULL) and Check.
  - `save-control` syncs the KPIs, so a rename or clone carries them along.

## v0.8.0 — 2026-09-20

Schema: `rapo_scheduler` lease columns, new `rapo_scheduler_event` table.

- **Scheduler inside the web server.** One process now serves the API, the UI and the scheduler.
  `rapo-scheduler` is deprecated.
- **Run manager.** Every run, scheduled or manual:
  - is initiated at once (`I`, cancellable) and queued FIFO under `control_parallelism`;
  - executes in its own process, with timeouts that also count time spent waiting for a slot or lock;
  - settles by itself if its process dies. Crashed leftovers are settled on the next start and their locks
    released.
- **Scheduler lease for several servers.** A heartbeat row decides which one fires; the others take over after
  `lease_timeout`. Stop/Start is persisted in the DB for all servers.
  - Instances sharing a database no longer touch each other's server row, process or fires.
- **No dropped fires.** Fire times are computed with `next_fire`, and each fire is served with its exact
  timestamp.
  - Late fires and fires during downtime are recorded as `MISSED`, and *Run for this moment* runs one as
    `CATCHUP`.
  - Schedule changes apply without a restart, including direct SQL edits.
- **Scheduler event history** (`rapo_scheduler_event`): one row per run request, with trigger and outcome.
- **Scheduler page**: state, running and queued runs, upcoming fires, history, and a next-fires preview in the
  editor.
- **One log file per run** (`logs/controls/<id>/<pid>.log`), plus a daily server log and retention cleanup.
  - *Show full log* in the UI parses the file into records, with search, download and live refresh.
- **Manual runs behave like scheduled ones.** They cascade for the requested window, and iterations are an
  opt-in switch showing their dates.
- **Results one day at a time.** `get-control-runs?date=` returns `{date, today, runs}`, a **breaking change of
  the response shape**.
- **Reliability fixes.**
  - Failed COMMITs and failed reconciliation stages used to end `D`; they now fail the run.
  - `period_number = 0` hung the scheduler.
  - Cancel races are fixed, and run messages are appended instead of overwritten.
  - A PID is trusted only when it is a rapo server on this host.
- **Security and ops.**
  - Swagger is served only with `[API] docs`.
  - *Instance details* shows the paths and every `rapo.ini` parameter, secrets masked.
  - `rapo-ctl.sh` (renamed `rapoctl.sh` in v0.8.3) supports unattended `@reboot` starts with `--wait`.
- **Distribution.** Runs from source with a `.venv` instead of PyPI; version marked `+fork`; upstream credited in
  README, LICENSE and NOTICE.

## v0.7.0 — 2026-09-19

Schema: index on `rapo_log.updated`. `rapo.ini` moves to the application folder (or `$RAPO_CONFIG`).

- **FastAPI replaces Flask.**
  - uvicorn with one worker; routes under `/api` behind a Bearer token, with real HTTP error codes.
  - The UI is served from the same port.
  - Console scripts `rapo-server` and `rapo-scheduler`.
- **Live updates via socket.io** (`/api/socket.io`). The server diffs `rapo_log` and `rapo_config` and pushes
  changes; the UI refetches on events instead of polling. Reverse proxies must allow WebSocket upgrades.
- **UI source in the repository** (`rapo-ui/`). The built bundle (`rapo/web/ui/`) is committed and packaged, so
  installs need no Node.
- **UI fixes and refactor.**
  - The editor edits a copy, so unsaved edits and clones no longer leak into the catalogue.
  - Datasource watchers no longer reset the form on load.
  - HTML output is escaped.
  - Shared API helper, run actions, schedule parser, sorting and column filters.
- **REC algorithm options follow `rapo.ini`.** Opening a control no longer freezes the current defaults into its
  `rule_config`.
