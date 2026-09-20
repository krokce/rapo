# Rapo v0.8.0 Migration Instructions
This short document describes how to upgrade Rapo from v0.7.0 to v0.8.0. Commands run in the application folder
(the Rapo source checkout, see the [v0.7.0 instructions](../v0.7.0/README.md)). What the release contains is in the
[change log](CHANGELOG.md).

The scheduler now runs inside the web server, so there is only one process to run: `rapo-server`.
`rapo-scheduler` is deprecated. It only stops a standalone scheduler left over from an older version.

1. Wait until all your Rapo controls are completed or cancel them. Stop the scheduler and the web server.
    ```bash
    .venv/bin/rapo-scheduler stop
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it. Without Git, replace the folder's content with the
   v0.8.0 source (keep `rapo.ini`, `.venv` and `logs`) and run only the two install commands.
    ```bash
    git fetch
    git checkout v0.8.0
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-build-isolation -e .
    ```
1. Execute migration SQL [scripts](upgrade.sql) in database, which include:
    1. New columns `heartbeat`, `instance_id` and `disabled` of `rapo_scheduler`. They hold the lease of the server
       running the scheduler and the Stop/Start switch of the UI.
    1. New table `rapo_scheduler_event` with its sequence, trigger and indexes. It records every control run
       request (scheduled, manual, catch-up, iteration and cascade) and every scheduled fire missed while no
       scheduler was running.
1. Optionally add the new options to the `[SCHEDULER]` section of `rapo.ini` (see `rapo.ini.example`):
    * `enabled` (default `True`): run the scheduler in this server. Set to `False` for an API-only server.
    * `event_retention_days` (default `90`): days scheduler events are kept.
    * `missed_window_hours` (default `24`): hours back that missed fires are recorded on startup.
    * `lease_timeout` (default `60`): seconds without a heartbeat after which a standby server takes over.

   `control_parallelism` now limits all runs, including those started from the UI. Runs over the limit wait in a
   queue.
1. Optionally set the log options in the `[LOGGING]` section:
    * `directory` (default `logs` next to `rapo.ini`): folder of the log files. It holds `rapo-server_YYYYMMDD.log`
      (server, scheduler and run manager, one file per day) and `controls/<control_id>/<process_id>.log` (one file
      per control run, shown in the UI under "Show full log").
    * `retention_days` (default: keep): days server logs and logs of deleted controls are kept. Run logs are kept
      as long as their control's `days_retention`. Every server cleans its own log folder at start and daily.

   Log files of older versions were written to a `logs` folder next to the started script (e.g.
   `site-packages/uvicorn/logs`); delete them manually.
1. Optionally set `docs` in the `[API]` section. `/api/docs` and `/api/openapi.json` cannot carry the Bearer token,
   so they describe the whole API to anyone able to reach the port. They are now served only with `docs=True`, and
   answer 404 otherwise.

   Check as well that `token` is not made of digits only: such a token is read from `rapo.ini` as a number. It is
   compared as a string now, but a mixed token is still the better choice.
1. Start the web server. It starts the scheduler too.
    ```bash
    .venv/bin/rapo-server start
    ```
   `rapo-server start dev` runs without the scheduler unless started with `rapo-server start dev --scheduler`.
1. Remove `rapo-scheduler` from any service or startup scripts.

Behavior changes:
* Every run, scheduled or manual, is performed in its own process, so scheduled runs can now be canceled and are
  stopped at their `timeout`, like manual ones. Iterations and cascades of a scheduled run follow it in the same
  process.
* Stopping the web server kills its running controls, which are marked as canceled. Runs left active by a crashed
  server are settled when it starts again: canceled when a cancel had been requested, errors otherwise. The
  `rapo_checkpoint` lock of such a run is released, so it no longer blocks the next run of that control.
* Scheduled fires are no longer skipped when the scheduler is busy. Fires that fell into scheduler downtime are
  recorded as missed and can be run for their original moment from the Scheduler page.
* The scheduler can be stopped and started from the UI (Scheduler page). The state is kept in the database, so it
  survives restarts and applies to all servers. The "Instance details" dialog shows only the configuration of the
  instance; the scheduler state is in the header clock, which links to the Scheduler page.
* A run started by hand now cascades into the controls that follow it, for the window that was asked for, the way
  a scheduled run does. Its iterations stay opt-in: the run dialog and the re-run confirmation offer them as an
  unticked switch labeled with the dates they would run for.
* A run waiting for its `instance_limit` or for the control lock is now canceled at its `timeout`. It used to wait
  forever, since the limit was measured from a start date it never got.
* The Results page shows one day of runs instead of the last 200, navigated with prev/next/picker/Today and kept in
  `/results?date=YYYY-MM-DD`.

For callers of the API outside this repository:
* `get-control-runs` took no arguments and returned the last 200 runs as an array. It takes an optional `date`
  (default: the server's today) and returns `{date, today, runs}` with every run started on that day, uncapped.
* `run-control` goes through the same queue as a scheduled fire: it returns once the run is initiated, not once it
  is done, and the run cascades into the controls that follow it. Add `iterations=true` for its iterations. A
  submit that cannot be accepted answers 400 with the reason instead of 500.
* `read-control-logs` takes a `limit` (default 5000, maximum 50000) instead of returning everything.
* `parameters` is read from `rapo.ini` as it is written, without the options whose name contains `password`,
  `token` or `secret`; unset options are absent. The computed paths `config_path` and `log_directory` moved to
  `info`.
* `status`, `session` and `get-control-run` answer 404 when their record does not exist, instead of 500.
* New routes: `scheduler-status`, `scheduler-stop`, `scheduler-start`, `scheduler-upcoming`, `scheduler-events`,
  `run-missed`, `schedule-preview`, `iteration-preview`, `get-control-run-log`, `download-control-run-log`.
