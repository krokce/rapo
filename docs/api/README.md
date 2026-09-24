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
  * [KPIs](#kpis)
  * [Email](#email)
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

* **Parameters are query parameters**, including on `POST` and `DELETE`. The exceptions are `save-control`,
  `check-control-schema`, `save-kpi-type`, `validate-kpi-sql` and `validate-sql`, which take a JSON body.
* **Mutations answer `{"status": 200}`.** `save-control` adds the saved row's `control_id` and `updated_date`.
  Reads answer their payload directly.
* **Errors are real HTTP codes** with FastAPI's `detail`:

  | Code | Meaning                                                                            |
  |------|------------------------------------------------------------------------------------|
  | 401  | Missing or wrong token.                                                             |
  | 400  | The request was understood but could not be performed (bad control, failed save).   |
  | 404  | No such run, control, record or log file.                                           |
  | 409  | Scheduler start refused because the scheduler is disabled for this server in `rapo.ini`, or a `save-control` refused because the control changed since `expected_updated_date`. |
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
Delete the result tables of a control (`name`). Irreversible. The next run creates them again. To drop and create
them at once, use [`recreate-control-schema`](#post-apirecreate-control-schema).

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

The answer is `{"status": 200, "control_id": 94, "updated_date": "2026-09-23T11:43:56"}`: the row as saved, read
back from the database. `updated_date` is stamped by the database trigger, with the database's clock.

**Optimistic lock.** Send the `updated_date` you read the control with as `expected_updated_date` (a body key
beside the columns). If the row has been saved since, nothing is written and the answer is `409` with
`"The control was changed by <user> at <dd.mm.yyyy hh24:mi:ss>."`. Without the key the last writer wins, as
before. The web UI always sends it, and its Overwrite choice repeats the save without it.

For analysis, report and reconciliation controls, `rule_config` may carry an `email` object, the email
configuration of the control. See [Email](#email).

**Rename.** When `control_name` changes, the result tables (`rapo_rest_`/`rapo_resa_`/`rapo_resb_<name>`) and
their `rapo_process_id` index are renamed with it. When a table of the new name already exists, the control is
still saved, the tables stay under the old name, and the answer is `400` with
`"Control was saved, but its result tables were not renamed: ..."`.

### Result table schema

The result tables are created by the first run from the datasource columns (or the configured output columns).
These routes compare them with what the configuration would create now, and bring them in line.

#### `POST /api/check-control-schema`
Compare the result tables of a saved control with the schema of a configuration. The body is the control object
as `save-control` takes it, possibly with unsaved changes; its `control_id` names the saved control. Nothing is
changed.

```json
{"control_name": "MY_CONTROL", "renamed_from": null, "source_changed": ["A"],
 "rebuilt_each_run": false, "active_run": false,
 "tables": [{"table": "rapo_resa_my_control", "target": "rapo_resa_my_control", "exists": true,
             "rows": 1315, "rows_analyzed": "2026-09-21T22:00:04", "oldest": "2026-09-21T14:37:45",
             "columns": [{"name": "amount", "status": "widened", "current": "NUMBER(8,2)",
                          "expected": "NUMBER(12,4)", "ddl": "MODIFY (amount NUMBER(12,4))"}]}]}
```

- `source_changed`: the datasources that differ from the saved ones (`source`, `A`, `B`).
- `renamed_from`: the saved name when `control_name` changed. `table` is then the existing table under the old
  name and `target` its name after the save.
- `rebuilt_each_run`: the control drops its tables on every run (`with_drop`), so there is nothing to compare and
  `tables` is empty.
- `active_run`: a run of the control is in status `I`/`W`/`S`/`P`/`F`.
- `rows` / `rows_analyzed`: the row estimate of the optimizer statistics (`user_tables.num_rows`) and when they
  were gathered, `null` without statistics. It is never counted here, since a `count(*)` scans the whole table;
  see [`count-control-table-rows`](#get-apicount-control-table-rows).
- `oldest`: the `added` time of the oldest run in the table (read from the `rapo_process_id` index).
- `status` of a column: `ok` (the table column holds every value of the datasource column, so a column wider
  than the datasource, e.g. `VARCHAR2(20)` for a datasource `VARCHAR2(15)`, is `ok` and never narrowed);
  `added` (missing in the table); `widened` (too narrow for the datasource);
  `nullable` (NOT NULL only in the table); `not_output` (no longer filled, kept with its history);
  `incompatible` (the type cannot be converted in a table with data, e.g. `VARCHAR2` → `NUMBER`). `ddl` is the
  change `update-control-schema` makes, or `null`.
- A datasource that cannot be read is reported as `error` (top level), a table whose expected schema cannot be
  built (e.g. an output column missing in the datasource) as `error` of that table. Both answer `200`.

`400` when the body has no saved `control_id`.

#### `GET /api/get-schema-drift`
The drift of every control's result tables at once, keyed by `control_id`:

```json
{"94": {"level": "update", "changes": 1, "incompatible": 0,
        "tables": ["RAPO_RESB_RAPO_FIX_REC"], "reason": null}}
```

`level` is `ok`, `update` (changes `update-control-schema` makes), `recreate` (incompatible columns), `error` (the
configuration names a column its datasource lacks, see `reason`), `missing` (no result table yet) or
`not_checked`. Controls that drop their tables on every run are left out.

Unlike `check-control-schema`, which creates each expected table empty to learn Oracle's types, this reads the
dictionary only (one pass over `all_tab_columns`), so it is cheap enough for the whole catalogue. The result
tables are copies of plain datasource columns, so the answer is the same, except where only Oracle can type a
column: a CMP output column that coalesces A and B, a datasource name with `{variables}`, and a datasource over a
database link are `not_checked` with the `reason`.

#### `GET /api/count-control-table-rows`
Count the rows of one result table (`table`) of a saved control (`name`) exactly. A full scan, so it is meant
to be asked for explicitly. Answers `{"table": "RAPO_RESA_MY_CONTROL", "rows": 1315, "counted":
"2026-09-24T08:21:05"}`, `rows` being `null` when the table does not exist. `400` when `table` is not a result
table of the control.

#### `POST /api/update-control-schema`
Apply the safe changes of `check-control-schema` to the existing result tables of a saved control (`name`):
add missing columns, widen narrow ones, make NOT NULL columns nullable. Nothing is dropped and no data is
changed. Answers `{"status": 200, "incompatible": ["rapo_rest_my_control.name"]}`, the columns left for
`recreate-control-schema`. A run makes the same changes itself before it saves, and fails with
`Recreate schema needed for <table>: ...` when an incompatible column is left.

#### `POST /api/recreate-control-schema`
Drop the result tables of a saved control (`name`) and create them at once with the schema of its saved
configuration. Past results are deleted. `400` with the reason when a table cannot be created, e.g. a missing
datasource.

#### `DELETE /api/delete-control`
Delete a control (`control_id`) from `rapo_config`. Its result tables and logs are not touched.

#### `POST /api/validate-sql`
Parse one statement of the control editor with Oracle without executing it, the way the engine will run it. The
body is JSON:

| Key            | Meaning                                                                                  |
|----------------|------------------------------------------------------------------------------------------|
| `kind`         | `filter`, `error_sql`, `case_definition`, `prerequisite`, `preparation`, `completion`, `email_filter` or `email_sql`. |
| `statement`    | The text as it is in the box.                                                            |
| `source_name`  | The datasource a `filter`, `error_sql` or `case_definition` is checked against.          |
| `control_name`, `control_type` | Name the result table of an `email_filter` and the value of `{control_name}`. |
| `side`         | `a` or `b`: the result table of an `email_filter` of a REC control.                      |

A `filter` or `error_sql` gets sample values for its `{variables}` the way a run renders them: only a known
`{name}` or `{name:format}` is replaced, every other brace stays as written, and an unknown `{name}` is reported
as a `warning`.

An `email_sql` is the Free SQL sheet of an email. It must be a query (`select`/`with`), its `{variables}` are
replaced with sample values, and it needs no saved control. The answer lists its `columns`, and carries a
`warning` when it uses neither `{process_id}` nor a `{control_date...}` variable, since it is then not limited to
the run being mailed.
| `case_ids`     | The IDs of the Case config, for a warning when `case_definition` returns another one.    |

A filter and the mismatch criteria are parsed as `select * from <source_name> where (<statement>)`, a case
mapping as `select <statement> from <source_name>`, and an email filter against `RAPO_REST_`/`RAPO_RESA_`/
`RAPO_RESB_<name>` (only its variables are checked while that table does not exist). JSON mismatch criteria are
checked as JSON and their columns against the datasource. `{variables}` are replaced with sample values first
(today, `process_id` 0), so a wrong or unknown one is reported.

Oracle's parse compiles queries, DML and PL/SQL blocks but **executes DDL**, so Preparation and Completion SQL are
parsed only when they start with `select`, `with`, `insert`, `update`, `delete`, `merge`, `begin` or `declare`,
and a Prerequisite only when it is a query. Anything else is refused with an error, not run.

The answer is `{"valid", "error"|"columns", "warning", "message", "statement"}`, where `statement` is what was
parsed. Always `200`.

### KPIs

KPI values are calculated after a run by the Oracle package `RACS_KPI_PKG`, which reads two tables of that
deployment: `racs_kpi_type`, the catalogue of KPI types with their default statements, and `racs_kpi_config`, one
row per KPI of one control, linked to it by `rapo_config.control_name = racs_kpi_config.processname`. The tables
are optional: where they are not deployed, the reads answer `[]` and `GET /api/info` reports
`kpi_available: false`.

A statement left NULL in `racs_kpi_config` means the type's default is used, and a KPI whose statement is NULL on
both sides is not calculated at all.

#### `GET /api/get-kpi-types`
Every row of `racs_kpi_type`, most important first (`kpi_priority`, then `kpi_type`).

#### `GET /api/get-control-kpis`
The `racs_kpi_config` rows of one control (`control_name`), in type priority order.

#### `GET /api/get-kpi-type-usage`
One row per (KPI type, control) of `racs_kpi_config` as `kpi_type`, `processname` and `control_id`. The control
is outer-joined, so a row naming a control that does not exist any more is reported without an id. This is what
makes a KPI type undeletable.

#### `POST /api/save-kpi-type`
Create, update or rename a KPI type. The body is the row as JSON, the shape `get-kpi-types` returns; a blank text
value is stored as NULL, which is what "this type ships no default" means. `kpi_type` is stored upper case.

`kpi_type` is the primary key, so an edit that changes it is a **rename**: pass the old code as
`previous_kpi_type` and the row is inserted under the new code, the `racs_kpi_config` rows of the controls are
moved over and the old row is deleted, all in one transaction. Without `previous_kpi_type` the row is inserted.

`400` with the reason when the code is empty, longer than 20 characters, already taken, when the unit takes more
than 10 bytes, or when the write fails.

#### `DELETE /api/delete-kpi-type`
Delete a KPI type (`kpi_type`) from `racs_kpi_type`. `400` naming the controls when any of them still configures
it - `racs_kpi_config` references the code and nothing is deleted for you.

#### `POST /api/validate-kpi-sql`
Parse a KPI or alarm statement without executing it. The body is `{"statement": "...", "kind": "kpi"|"alarm"}`
(`kind` defaults to `kpi`) and the answer is `{"valid": true, "columns": [...]}` or
`{"valid": false, "error": "..."}`, with a `warning` when the statement parses but would not produce one numeric
value, or does not use its bind (`:v_processid`, or `:v_kpi_value` for an alarm), which RACS_KPI_PKG fails to
bind. Only a query is parsed. Always `200`: this is an opinion, not a verdict.

An alarm also gets `thresholds`, `[{"condition": "KPI>1000", "alarm": "3"}, ...]`: what
`racs_kpi_pkg.get_kpi_thresholds_json` will read from it for the dashboard, computed by a port of its regular
expressions. The `warning` says when that reading goes wrong (a level outside 1-3, a condition that is not a plain
comparison on `:v_kpi_value`). The shape it understands is
`case when <condition> then 1..3 ... else 0 end from dual`.

### Email

A control of type `ANL`, `REP` or `REC` can mail its results when a run finishes. The configuration is the
`email` key of its `rule_config` (written through `save-control`), and the SMTP server is the `[EMAIL]` section of
`rapo.ini`, whose `enabled` switch turns email off for the whole instance. The shape of the object and the
meaning of each key are in the [v0.8.2 migration instructions](../../migrations/v0.8.2/README.md#setting-up-an-email),
and the Free SQL sheet, the per-sheet `enabled` of ANL/REP and the file name in the
[v0.8.3 ones](../../migrations/v0.8.3/README.md#email-free-sql-sheet-and-file-name).

After a run, the control's own process sends the email and logs each step in the run log. The two routes below
send outside of a run, in the server process. Both answer `{"status": 200}` once the SMTP server has accepted the
message, and `400` with the reason otherwise: email disabled in `rapo.ini` or for the control, no recipients, an
SMTP error.

#### `POST /api/send-control-email`
Send the email of a finished run (`process_id`) again, with the control's **current** configuration. The run
must have status `D` (otherwise `400`), and its rows must still be in the result table. The *Send when*
condition is not applied: the email is sent even when the run has no rows.

#### `POST /api/send-test-email`
Send the email of a control's (`control_name`) last run with status `D` to one address (`to`) instead of its
recipients, with `[TEST]` before the subject. `400` when the control has no such run.

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
