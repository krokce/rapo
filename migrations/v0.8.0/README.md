# Rapo v0.8.0 Migration Instructions
This short document describes how to upgrade Rapo from v0.7.0 to v0.8.0. Commands run in the application folder
(the Rapo source checkout, see the [v0.7.0 instructions](../v0.7.0/README.md)).

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
  server are marked as errors when it starts again.
* Scheduled fires are no longer skipped when the scheduler is busy. Fires that fell into scheduler downtime are
  recorded as missed and can be run for their original moment from the Scheduler page.
* The scheduler can be stopped and started from the UI (Instance details dialog or Scheduler page). The state is
  kept in the database, so it survives restarts and applies to all servers.
