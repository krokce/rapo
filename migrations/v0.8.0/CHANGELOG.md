# Rapo v0.8.0 Change Log

## Annotation
This release moves the scheduler into the web server, gives every control run its own process and its own log
file, and records what the scheduler did and what it missed. The upgrade steps are in the
[migration instructions](README.md).

1. **One process**. The scheduler now runs inside `rapo-server`, started and stopped with it. `rapo-scheduler` is
   deprecated: `rapo-scheduler stop` still kills a standalone daemon left over from an older version, nothing else.
1. **Run manager**. Every run, scheduled or manual, is initiated at once (a `rapo_log` row with status `I`, visible
   and cancellable), queued FIFO under `control_parallelism` and performed in its own process. Scheduled runs can
   therefore be canceled and are stopped at their `timeout`, which before applied only to runs started through the
   API or `launch()`.
1. **Scheduler lease**. Several servers may run against the same database. They share one `rapo_scheduler` row with
   a heartbeat, one of them schedules, the others stand by and take over when the holder stops or dies. Every
   server still serves the API, performs its own runs and cleans its own logs.
1. **Stop and Start from the UI**. The scheduler switch is stored in the database, so it survives a restart and
   applies to every server. It lives on the Scheduler page.
1. **Scheduler event history**. The new table `rapo_scheduler_event` records one row per run request, with its
   trigger (`SCHEDULE`, `MANUAL`, `CATCHUP`, `ITERATION`, `CASCADE`) and its outcome, plus the fires that fell into
   a time when no scheduler was running.
1. **Missed fires**. A fire found too late, or one that fell into scheduler downtime, is recorded as `MISSED`
   instead of being run silently or dropped. The Scheduler page offers "Run for this moment", which runs it for its
   original timestamp.
1. **No dropped fires**. The scheduler computes the next fire times and sleeps until the earliest one, then serves
   every fire since its last pass with that fire's exact time, so a slow pass no longer skips a schedule.
1. **Schedule changes apply without a restart**. A save refreshes the schedules at once, and the holder compares
   the `rapo_config` signature every five seconds, so a change made with direct SQL is picked up too.
1. **Scheduler page** in the UI: state, running and queued runs, upcoming fires and the event history. The schedule
   editor previews the next fires of the schedule being edited, computed by the engine itself.
1. **One log file per control run**. A run process writes to `controls/<control_id>/<process_id>.log`, everything
   else to `rapo-server_YYYYMMDD.log`. Both live in `[LOGGING] directory`, next to `rapo.ini` by default, instead
   of the folder of the started script, which used to put them into `site-packages/uvicorn/logs`.
1. **Run log in the UI**. "Show full log" opens the run details together with the log file, parsed into records
   with level chips, search, copy and download, refreshed live while the run is active.
1. **Log retention**. Every server cleans its own log folder at start and daily. Run logs follow their control's
   `days_retention`, server logs and the logs of deleted controls follow `[LOGGING] retention_days`.
1. **Results one day at a time**. The Results page used to show the last 200 runs with no way to look further back.
   It now shows every run of one day, with prev/next/date-picker/Today navigation, the day in the URL, and a
   summary of the listed runs under the header.
1. **A manual run does the same work as a scheduled one**. It cascades into the controls that follow it, for the
   window that was asked for. Its iterations are offered as an unticked switch, labeled with the dates they would
   run for, so a re-run of one control does not quietly become four.
1. **Swagger is off unless asked for**. `/api/docs` and `/api/openapi.json` described the whole API to anyone able
   to reach the port, because neither can carry the Bearer token. They are served only when `[API] docs` is on.
1. **Instance details** shows what the instance is configured with: the paths of `rapo.ini` and of the logs, the
   version, and every parameter of `rapo.ini` as it is written there, refetched each time it is opened.
1. **Reliability**. Failures that used to pass as success are reported now, runs that used to hang are settled, and
   a bad configuration value no longer stops the scheduler. See [Fixes](#fixes).
1. **Performance**. `next_fire` no longer walks every second of the day, and the run supervisor reads the few
   values it needs in one query instead of rebuilding a whole `Control` for every running job every two seconds.

## Important Changes

### Database schema
The migration [scripts](upgrade.sql) contain:

* New columns `heartbeat`, `instance_id` and `disabled` of `rapo_scheduler`, holding the lease of the server that
  runs the scheduler and the Stop/Start switch of the UI.
* The new table `rapo_scheduler_event` with its sequence, trigger and indexes.

### Configuration
New options of the `[SCHEDULER]` section:

| Option                 | Default | Meaning                                                              |
|------------------------|---------|----------------------------------------------------------------------|
| `enabled`              | `True`  | Run the scheduler in this server. `False` makes it an API-only server.|
| `event_retention_days` | `90`    | Days scheduler events are kept.                                       |
| `missed_window_hours`  | `24`    | Hours back that missed fires are recorded on startup.                 |
| `lease_timeout`        | `60`    | Seconds without a heartbeat after which a standby server takes over.  |

`control_parallelism` now limits every run, including the ones started from the UI; runs over the limit wait in a
queue.

New options of the `[LOGGING]` section:

| Option           | Default        | Meaning                                                     |
|------------------|----------------|-------------------------------------------------------------|
| `directory`      | `logs`         | Folder of the log files, relative to the folder of `rapo.ini`.|
| `retention_days` | keep           | Days server logs and logs of deleted controls are kept.      |

New option of the `[API]` section:

| Option | Default | Meaning                                                              |
|--------|---------|-----------------------------------------------------------------------|
| `docs` | `False` | Serve the Swagger UI at `/api/docs` and the schema at `/api/openapi.json`.|

A digits-only `token` is read from `rapo.ini` as a number. It is compared as a string now, but a mixed token is
still the better choice.

### API
New routes:

* `scheduler-status`, `scheduler-stop`, `scheduler-start`, `scheduler-upcoming`, `scheduler-events`, `run-missed`,
  `schedule-preview` - the scheduler, its history and its previews.
* `iteration-preview` - the window each enabled iteration of a control would run for, computed by the engine.
* `get-control-run-log` and `download-control-run-log` - the `rapo_log` row with the tail of the run's log file,
  and the file itself.

Changed routes:

* `get-control-runs` took no arguments and returned the last 200 runs as a JSON array. It takes an optional `date`
  (default: the server's today) and returns `{date, today, runs}`, holding every run *started* on that day,
  uncapped. **This changes the response shape for callers outside this repository.**
* `run-control` goes through the same queue as a scheduled fire, so it returns as soon as the run is initiated
  rather than when it is done, and the run cascades. Its iterations are performed only with `iterations=true`.
  A submit that cannot be accepted answers 400 with the reason instead of 500.
* `read-control-logs` takes a `limit` (default 5000, maximum 50000) instead of returning everything.
* `parameters` walks `rapo.ini` itself instead of listing known options, so it no longer drifts from the file. It
  omits the options whose name contains `password`, `token` or `secret`, and unset options are simply absent.
* `info` carries the computed paths `config_path` and `log_directory`.
* `status`, `session` and `get-control-run` answer 404 when their record does not exist, instead of failing with a
  `TypeError` or a 500.
* `cancel-control` also covers runs that have not started yet, and runs owned by another server, which are voided
  for their owner to stop.

Conventions are unchanged: query parameters, a Bearer token on every `/api` call, naive ISO datetimes.

### Behavior
* Every run is performed in its own process. The iterations and the cascade of a run follow it in that same
  process, so `control_parallelism` bounds concurrent chains rather than concurrent runs.
* Stopping the web server kills its running controls and marks them canceled. A child process exits by itself if
  the server disappears. Runs left active by a crashed server are settled at the next start: canceled when a cancel
  had been requested, errors otherwise.
* A run that waits for its instance limit or for the control lock is now subject to its `timeout` as well; it used
  to wait forever, because the limit was measured from the start date it never got.
* Whoever finishes a run releases its `rapo_checkpoint` lock, so a killed process no longer blocks every later run
  of that control until the next maintenance pass.
* Log files written by older versions are left where they were; delete them manually.

### Fixes
* `db.execute` had a `return` inside a `finally`, which discarded the exception a failed COMMIT raises: a run whose
  results were never persisted still reached status `D`.
* `db.parallelize` never read its result queue, so an exception in a reconciliation stage died with its thread and
  the run finished as successful with missing results. It re-raises the first failure under its group's name now.
* `parse_date_to` looped forever on `period_number = 0`. It runs while a run is being submitted, so a single such
  row stopped the scheduler from firing anything at all. Both date parsers reject an unusable configuration value
  by name instead.
* A control process killed by the system left its run active forever, and a cancel no longer found a job to stop.
  The supervisor settles such a run now.
* A cancel arriving while a process was being built could mark the run canceled and let it start anyway.
* The messages of a run were read, changed and written back, so a kill message and the run's own message could
  overwrite each other. They are appended in the database now.
* A canceled run got no `end_date`, a failing prerun hook raised on the return value, and a run whose control had
  been deleted answered 500.
* An unknown section in `rapo.ini` raised on load, and a password like `12a34` was rejected by the float pattern.
* `Server` no longer runs itself from `sys.argv` in its constructor, and a recorded PID is trusted only when it
  names this host and still belongs to a rapo server, so a crashed server neither blocks a start nor makes `stop`
  signal an unrelated process.
* The scheduler reads the configuration signature before the schedules, so a change committed while they load is
  not hidden until the next full reload, and a Start from the UI is recorded where every server sees it.
* Log cleanup keeps the files of runs that are still going.
* Identifiers no longer reach SQL as f-strings, and the legacy SQLAlchemy `select`, `autoload` and `has_table`
  forms are gone.
