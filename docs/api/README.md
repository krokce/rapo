# Rapo Web API

The Rapo server (`rapo-server`) serves a REST API and the web UI on the same port. Everything below is what the UI
itself is built on; it is a published interface and may be called from reports, dashboards, schedulers or scripts
outside this repository.

* [Connection](#connection)
* [Conventions](#conventions)
* [Reference](#reference)
  * [Runs](#runs)
  * [Run logs](#run-logs)
  * [Reads](#reads)
  * [Configuration](#configuration)
  * [Scheduler](#scheduler)
  * [Service](#service)
* [Live events](#live-events)
* [Value reference](#value-reference)

## Connection

The address comes from the `[API]` section of `rapo.ini` (`host` and `port`, `127.0.0.1:8080` by default). Every
route lives under `/api` and requires the `token` of that section as a Bearer token:

```bash
curl -H "Authorization: Bearer $RAPO_TOKEN" http://rapo-host:7005/api/scheduler-status
```

A request without a valid token is answered with `401 Unauthorized Access`, whatever the route. `GET /api/help`
returns a short HTML page and is the cheapest way to check that a token works - it is what the UI validates
against.

Swagger is **off by default**. Neither `/api/docs` nor `/api/openapi.json` can carry the Bearer token, so they
would describe the whole API to anyone able to reach the port; they are served only with `docs=True` in the `[API]`
section and answer 404 otherwise. Redoc is disabled.

## Conventions

* **Parameters are query parameters**, including on `POST` and `DELETE`. The single exception is `save-control`,
  which takes a JSON body.
* **Mutations answer `{"status": 200}`.** Reads answer their payload directly.
* **Errors are real HTTP codes** with FastAPI's `detail`:

  | Code | Meaning                                                                            |
  |------|------------------------------------------------------------------------------------|
  | 401  | Missing or wrong token.                                                             |
  | 400  | The request was understood but could not be performed (bad control, failed save).   |
  | 404  | No such run, control, record or log file.                                           |
  | 409  | Scheduler start refused because the scheduler is disabled for this server in `rapo.ini`. |
  | 422  | A parameter is missing or of the wrong type (FastAPI validation).                   |
  | 503  | The run manager is not running, so no run can be accepted.                          |

* **Datetimes are naive ISO wall-clock strings** in the server's local time, e.g. `2026-09-19T10:05:07`. There is
  no timezone suffix and none is accepted. Dates are `YYYY-MM-DD`.
* **Numbers are numbers**: Oracle `NUMBER` columns arrive as JSON numbers, not strings.
* A run is identified by its **`process_id`**, a control by its **`control_name`** or **`control_id`**.

## Reference

### Runs

#### `POST /api/run-control`
Initiate a control run and queue it for execution.

| Parameter    | Type | Default | Meaning                                                       |
|--------------|------|---------|----------------------------------------------------------------|
| `name`       | str  | -       | Control name. Required.                                         |
| `date`       | str  | -       | Single day or moment of the run window.                         |
| `date_from`  | str  | -       | Start of the run window.                                        |
| `date_to`    | str  | -       | End of the run window.                                          |
| `debug_mode` | bool | `false` | Keep the temporary tables of the run.                           |
| `iterations` | bool | `false` | Also run the enabled iterations of the control.                 |

With no date at all the window is `now`..`now`. The call goes through the same queue as a scheduled fire: it
returns as soon as the run is initiated - a `rapo_log` row with status `I`, already visible and cancellable - not
when the run is done. The run **cascades** into the controls triggered by it, for the window that was asked for.
Its iterations are performed only with `iterations=true`.

`400` when the control is unknown or cannot be initiated, `503` when the run manager is not running.

```bash
curl -X POST -H "Authorization: Bearer $RAPO_TOKEN" \
  "http://rapo-host:7005/api/run-control?name=MY_CONTROL&date_from=2026-09-01&date_to=2026-09-02"
```

#### `POST /api/cancel-control`
Cancel an active run. `id` is the `process_id`. A run of this server is stopped directly; a run of another server
is voided for its owner to stop. Runs in status `I`, `W`, `S`, `P` and `F` can be canceled.

#### `DELETE /api/revoke-control-run`
Revoke a finished run (`id` = `process_id`): its results are deleted and the run is marked `X`.

#### `DELETE /api/delete-control-temporary-tables`
Delete the temporary tables of one run (`id` = `process_id`), e.g. after a run in debug mode.

#### `DELETE /api/delete-control-output-tables`
Delete the result tables of a control (`name`). Irreversible.

#### `GET /api/iteration-preview`
The runs the iterations of a manual run would perform: `name` and either `date` or `date_from`/`date_to`, the same
window that would be passed to `run-control`. Returns one object per **enabled** iteration with `iteration_id`,
`iteration_description`, `date_from` and `date_to`.

The windows are computed by the engine, so what this route offers is what a run performs. Use it instead of
repeating the period arithmetic.

### Run logs

#### `GET /api/get-control-run-log`
The `rapo_log` row of a run together with the tail of its log file.

| Parameter    | Type | Default | Meaning                                              |
|--------------|------|---------|-------------------------------------------------------|
| `process_id` | int  | -       | Run to read. Required.                                 |
| `max_bytes`  | int  | 2 MB    | Tail size, 1 .. 50 MB.                                 |

Answers `{run, log}`. `run` is the log row plus `control_name` and `control_type`. `log` is
`{path, exists, size, modified, truncated, text, host, runner}`: `runner` is the server that performed the run and
`host` the server answering, which are not the same when several servers share a database - log files are local to
the server that wrote them. The text starts at a line boundary. `404` when there is no such run.

#### `GET /api/download-control-run-log`
The log file of a run (`process_id`) as `text/plain`, named `<control_name>_<process_id>.log`. `404` when the run
or its file does not exist.

### Reads

#### `GET /api/get-control-runs`
Every run **started** on one day, newest first.

| Parameter | Type | Default           | Meaning        |
|-----------|------|-------------------|-----------------|
| `date`    | date | the server's today | Day to report. |

Answers `{date, today, runs}`, where `today` is the server's current day, so a caller can tell whether it is
looking at today without a clock of its own. A run that never started is reported on the day it was added. The
list is not capped.

Every run carries `control_name`, `control_id`, `control_type`, `process_id`, `start_date`, `date_from`, `date_to`,
`status`, the A/B counters (`fetched_number_a`/`_b`, `success_number_a`/`_b`, `error_number_a`/`_b`,
`error_level_a`/`_b`, the A column holding the single value of a one-sided control), `text_log`, `text_error`,
`prerequisite_value` and `duration_minutes`.

> Until v0.8.0 this route took no parameters and returned the last 200 runs as a plain array.

#### `GET /api/get-control-run`
Details of one run (`process_id`): name, window, timestamps, status and counters. `404` when the run does not
exist or its control has been deleted.

#### `GET /api/get-running-controls`
The `rapo_log` rows of every run currently in status `I`, `W`, `S`, `P` or `F`, on any server.

#### `GET /api/read-control-logs`
Run logs of one control.

| Parameter      | Type | Default | Meaning                                    |
|----------------|------|---------|---------------------------------------------|
| `control_name` | str  | -       | Control to read. Without it, `[]`.          |
| `days`         | int  | 31      | How far back to look.                       |
| `limit`        | int  | 5000    | Maximum number of rows, 1 .. 50000.         |

Rows are whole `rapo_log` records, newest first. They carry the text of their run, so a frequently run control
holds a lot of data - keep the limit in mind.

#### `GET /api/get-all-controls`
Every row of `rapo_config`, most recently updated first. This is the whole control definition, the same object
`save-control` takes back.

#### `GET /api/get-control-versions`
Past configurations of a control (`control_id`) from `rapo_config_bak`, newest first.

#### `GET /api/get-datasources`
Names of the tables and views visible to the Rapo database user.

#### `GET /api/get-datasource-columns`
`column_name` and `data_type` of one datasource (`datasource_name`), in column order.

### Configuration

#### `POST /api/save-control`
Create or update a control. The body is the control object as JSON, the shape `get-all-controls` returns. Keys
that are not columns of `rapo_config` are ignored. With `control_id` the row is updated, without it a row is
inserted. `updated_date` is set by the server.

Saving reloads the schedules at once, so a new or changed schedule applies without a restart. `400` with the
reason when the row cannot be written.

#### `DELETE /api/delete-control`
Delete a control (`control_id`) from `rapo_config`. Its result tables and logs are not touched.

### Scheduler

#### `GET /api/scheduler-status`
The state of the scheduler, of its lease and of the run manager of **this** server:

* `state` - `running`, `standby`, `stopped`, `starting` or `off` (see [Value reference](#value-reference));
* `enabled`, `disabled`, `leader`, `instance_id`, `lease_timeout`;
* `holder` - `{instance_id, server, username, pid, start_date, stop_date, heartbeat, alive}` of the server that
  currently holds the lease;
* `scheduled_controls`, `last_fire`, `next_maintenance`;
* `server_time` - the server's clock, which the UI uses to show relative times;
* `runner` - `{runner, active, capacity, queued, running}`, where `queued` and `running` list
  `{event_id, control_name, trigger_type, process_id, pid, queued, started}`.

#### `POST /api/scheduler-stop` and `POST /api/scheduler-start`
Stop or resume scheduling. The switch is stored in the database, so it survives a restart and applies to every
server against that database. A start resumes from now: fires that fell into the stop are not run. `409` when the
scheduler is disabled for this server in `rapo.ini`.

#### `GET /api/scheduler-upcoming`
Future fires of all enabled schedules, ordered by time.

| Parameter      | Type | Default | Meaning                             |
|----------------|------|---------|--------------------------------------|
| `hours`        | int  | 24      | How far ahead to look, 1 .. 744.     |
| `control_name` | str  | -       | One control instead of all of them.  |

Each fire is `{scheduled_time, control_id, control_name, control_type, control_group}`. It is computed from the
database, so any server answers it, even one whose scheduler is stopped.

#### `GET /api/scheduler-events`
The run request history, latest first.

| Parameter      | Type | Default | Meaning                                       |
|----------------|------|---------|------------------------------------------------|
| `control_name` | str  | -       | Filter by control.                             |
| `event_type`   | str  | -       | `FIRED`, `STARTED`, `MISSED`, `FAILED`, `CANCELED`. |
| `trigger_type` | str  | -       | `SCHEDULE`, `MANUAL`, `CATCHUP`, `ITERATION`, `CASCADE`. |
| `date_from`    | date | -       | Events from this day on.                       |
| `date_to`      | date | -       | Events up to and including this day.           |
| `limit`        | int  | 500     | Maximum number of rows, 1 .. 5000.             |

Each event carries `event_id`, `control_id`, `control_name`, `control_type`, `trigger_type`, `event_type`,
`scheduled_time`, `event_time`, `start_time`, `process_id`, `message`, `runner`, and the run's `status`,
`date_from`, `date_to`, `start_date` and `end_date` joined from `rapo_log`.

#### `POST /api/run-missed`
Run a missed fire (`event_id`) for its original moment, as a `CATCHUP` run with its iterations and its cascade. The
event must be a `MISSED` one, otherwise `400`.

#### `GET /api/schedule-preview`
The next fires of a schedule configuration, without saving it.

| Parameter         | Type | Default | Meaning                                    |
|-------------------|------|---------|---------------------------------------------|
| `schedule_config` | str  | -       | The `schedule_config` JSON. Required.       |
| `count`           | int  | 5       | How many fires, 1 .. 100.                   |

Answers a list of datetimes, `[]` for a schedule that never fires. `422` when the configuration cannot be parsed.

### Service

#### `GET /api/version`
`{"version": "0.8.0"}`.

#### `GET /api/info`
What this instance is: `instance_name`, `schema_name`, `database_server`, `database_name`, and the computed paths
`config_path` (the `rapo.ini` actually loaded) and `log_directory`.

#### `GET /api/parameters`
The loaded `rapo.ini` as it is written, one object per section. Options whose name contains `password`, `token` or
`secret` are left out, and options that are not in the file are simply absent - defaults applied in code are not
shown here.

#### `GET /api/status`
The `rapo_scheduler` record: `server`, `username`, `pid`, `start_date`, `stop_date`, `status`. `404` before a
scheduler has ever run.

#### `GET /api/session`
The `rapo_web_api` record of the server that started last: `server`, `username`, `pid`, `url`, `debug`, `start_date`,
`stop_date`, `status`. `404` when no server has recorded itself yet.

#### `GET /api/help`
A short HTML help page. Cheap, always available with a valid token, and therefore what the UI uses to validate
one.

## Live events

The server is a socket.io application wrapping the API, with the endpoint at `/api/socket.io`. The token goes in
the handshake, not in a header:

```js
io("http://rapo-host:7005", { path: "/api/socket.io", auth: { token } });
```

Control runs write to the database, not to the server process, so a watcher compares a signature of `rapo_log`,
`rapo_config` and `rapo_scheduler_event` every two seconds while clients are connected, and emits:

| Event               | Payload                                          |
|---------------------|--------------------------------------------------|
| `runs:changed`      | `{resync, process_ids, control_names}`            |
| `controls:changed`  | `{resync, control_ids}`                           |
| `scheduler:changed` | `{event_ids}`                                     |

`resync` means the changed rows could not be named - a deletion, or more than 500 changes at once - and everything
should be refetched. The events say *what*
changed, never the new values - fetch them with the routes above. This is how the UI stays current without
polling, and it is the recommended way for any other client to do the same.

## Value reference

**Control types** (`rapo_ref_types`): `ANL` analysis, `REC` reconciliation, `CMP` comparison, `REP` report.

**Run statuses** (`rapo_log.status`), in lifecycle order:

| Status | Meaning                                                               |
|--------|------------------------------------------------------------------------|
| `I`    | Initiated: the run exists and is queued for an execution slot.          |
| `W`    | Waiting for its instance limit or for the lock of its control.          |
| `S`    | Started: preparation SQL and prerequisite.                              |
| `P`    | In progress: fetching, executing, saving.                               |
| `F`    | Finishing.                                                              |
| `D`    | Done.                                                                   |
| `E`    | Error; the traceback is in `text_error`.                                |
| `C`    | Canceled, by a user, a timeout or a server shutdown.                    |
| `X`    | Revoked: the run was undone and its results deleted.                    |
| *null* | Voided: a cancel has been requested and is being performed.             |

`I`, `W`, `S`, `P` and `F` are the active statuses, the ones `cancel-control` accepts.

**Scheduler event types** (`rapo_scheduler_event.event_type`): `FIRED` queued, `STARTED` process spawned, `MISSED`
fire not run, `FAILED` could not be initiated or spawned, `CANCELED` stopped before it started. The outcome of a
started run is not repeated here; it is the `rapo_log` row linked by `process_id`.

**Trigger types** (`rapo_scheduler_event.trigger_type`): `SCHEDULE` a scheduled fire, `MANUAL` a run asked for
through `run-control`, `CATCHUP` a missed fire run afterwards, `ITERATION` an iteration of another run, `CASCADE` a
control triggered by another control.

**Scheduler states** (`scheduler-status.state`): `running` this server holds the lease and schedules, `standby`
another server does, `stopped` scheduling is switched off in the database for every server, `off` the scheduler is
disabled for this server in `rapo.ini`, `starting` no server holds the lease yet.
