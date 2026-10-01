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
  `check-control-schema`, `save-kpi-type`, `validate-kpi-sql`, `validate-sql`, `validate-analysis-where` and
  `download-ds-files`, which take a JSON body, and `analysis-start`, which takes an optional one.
* **Mutations answer `{"status": 200}`.** `save-control` adds the saved row's `control_id` and `updated_date`.
  Reads answer their payload directly.
* **Errors are real HTTP codes** with FastAPI's `detail`:

  | Code | Meaning                                                                            |
  |------|------------------------------------------------------------------------------------|
  | 401  | Missing or wrong token.                                                             |
  | 400  | The request was understood but could not be performed (bad control, failed save).   |
  | 404  | No such run, control, record or log file.                                           |
  | 409  | Scheduler start refused because the scheduler is disabled for this server in `rapo.ini`, a `save-control` refused because the control changed since `expected_updated_date`, or an `analysis-start` refused because all `[ANALYSIS] max_sessions` are in use. |
  | 422  | A parameter is missing or of the wrong type (FastAPI validation).                   |
  | 500  | An unexpected error in the route. `detail` is `<ErrorType>: <message>`, and the traceback is written to the server log (`rapo-server_YYYYMMDD.log`). |
  | 503  | The run manager is not running, so no run can be accepted (likewise analysis sessions and jobs while the server starts or stops). |

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
Every run **started** on one day, newest first, or the runs of one control over the last days.

| Parameter      | Type | Default            | Meaning                                                        |
|----------------|------|--------------------|-----------------------------------------------------------------|
| `date`         | date | the server's today | Day to report.                                                  |
| `control_name` | str  | -                  | One control's runs instead (the editor's *Run log*); `date` is then ignored and answered as null. |
| `days`         | int  | 7                  | With `control_name`: how many days back from now, 1 .. 366.     |

Answers `{date, today, runs}`, where `today` is the server's current day, so a caller can tell whether it is
looking at today without a clock of its own. A run that never started is reported on the day it was added. The
list is not capped.

Every run carries `control_name`, `control_id`, `control_type`, `process_id`, `added`, `start_date`, `end_date`,
`date_from`, `date_to`,
`status`, the A/B counters (`fetched_number_a`/`_b`, `success_number_a`/`_b`, `error_number_a`/`_b`,
`error_level_a`/`_b`, the A column holding the single value of a one-sided control), `text_log`, `text_error`,
`has_warning`, `prerequisite_value`, `duration_minutes`, and what started it from `rapo_scheduler_event`:
`trigger_type` (`SCHEDULE`, `MANUAL`, `CATCHUP`, `ITERATION`, `CASCADE`, `UPSTREAM`), `trigger_message` (e.g. `For
CHN_B [1000002993]` on an upstream run) and `scheduled_time`, all null for a run the run manager did not start.
`has_warning` is `1` when the run's messages hold a
`Warning: ` line (a key field that is not unique, `correlation_limit` reached, approximate matching over
`max_candidates`, an `output_limit` that cut the saved rows), else `0`; the text is in `get-control-run-log`.

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
Past configurations of a control (`control_id`) from `rapo_config_bak`, newest first. `rapo_config_bak` has no key
(two saves within a second share their `audit_date`), so each version carries its ROWID as `version_id`.

#### `DELETE /api/delete-control-versions`
Deletes past versions of one control (`control_id`) from `rapo_config_bak`, either the listed ones (`version_id`,
repeated: `?control_id=28&version_id=AAA...&version_id=AAB...`), or all older than `older_than_days` (by the
database clock, which stamps `audit_date`) apart from the newest `keep` (default 0). A `version_id` of another
control deletes nothing. Answers `{"status": 200, "count": N}`. With `dry_run=true` nothing is deleted, and the answer
also lists the `version_ids` that would be (`count` is their number). `422` without `version_id` or
`older_than_days`, `400` for a malformed `version_id`. The UI sends at most 100 `version_id`s per request.

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

The answer is `{"status": 200, "control_id": 94, "updated_date": "2026-09-23T11:43:56", "renamed_dependents": []}`:
the row as saved, read back from the database. `updated_date` is stamped by the database trigger, with the
database's clock. `renamed_dependents` names the controls whose datasources followed a rename (see below).

**Optimistic lock.** Send the `updated_date` you read the control with as `expected_updated_date` (a body key
beside the columns). If the row has been saved since, nothing is written and the answer is `409` with
`"The control was changed by <user> at <dd.mm.yyyy hh24:mi:ss>."`. Without the key the last writer wins, as
before. The web UI always sends it, and its Overwrite choice repeats the save without it.

For analysis, report and reconciliation controls, `rule_config` may carry an `email` object, the email
configuration of the control. See [Email](#email).

**Rename.** When `control_name` changes, the result tables (`rapo_rest_`/`rapo_resa_`/`rapo_resb_<name>`) and
their `rapo_process_id` index are renamed with it. When a table of the new name already exists, the control is
still saved, the tables stay under the old name, and the answer is `400` with
`"Control was saved, but its result tables, or the datasources reading them, were not renamed: ..."`. The controls
reading the result tables (chain-rules, below) get their `source_name*` renamed in the same save, each as a new
version.

**Chain-rules.** A datasource named `rapo_rest_`/`rapo_resa_`/`rapo_resb_<name>` of an existing control (a plain
name, not owner-qualified, linked or with `{variables}`) makes the control read that control's results: each run
first runs it for the same period and reads only its records, with no date window and no time-shift widening
(so a reconciliation pair straddling midnight shows its other record as a Loss on the neighbouring day's run). Nothing is written and the answer is `400` when the
control would read its own result table, read a table the other control does not write (e.g. `rapo_resb_` of a
reconciliation with `need_b = 'N'`), close a cycle (`"Controls would read each other's results in a cycle: A -> B
-> A."`), be cascaded (`trigger_id`) from a control it runs first, or when a control reading this one's results
would read a table it no longer writes.

### Result table schema

The result tables are created by the first run from the datasource columns (or the configured output columns).
These routes compare them with what the configuration would create now, and bring them in line.

**Which tables a control writes.** An analysis, report or comparison writes `rapo_rest_<name>`. A reconciliation
writes `rapo_resa_<name>` only when it saves side A (`need_a = 'Y'`, i.e. an A output is ticked under
*Discrepancies*) and `rapo_resb_<name>` only when it saves side B (`need_b = 'Y'`). Only those tables are
checked, updated and created. Another existing result table of the control's name is **orphaned**: no run writes
it any more, e.g. side B after its output was unticked, or `rapo_rest_<name>` after the type changed to REC.
Orphans are never changed by an update or a recreate; they are only dropped explicitly (`drop-orphaned-table`).
Result tables whose name matches no control at all (a deleted control, or one renamed outside the application)
are listed by `get-schema-drift` as `unowned`.

#### `POST /api/check-control-schema`
Compare the result tables of a saved control with the schema of a configuration. The body is the control object
as `save-control` takes it, possibly with unsaved changes; its `control_id` names the saved control. Nothing is
changed.

```json
{"control_name": "MY_CONTROL", "control_type": "REC", "renamed_from": null, "source_changed": ["A"],
 "rebuilt_each_run": false, "active_run": false,
 "orphans": [{"table": "rapo_resb_my_control", "target": "rapo_resb_my_control", "rows": 820,
              "rows_analyzed": "2026-09-21T22:00:04", "oldest": "2026-09-02T06:00:11"}],
 "tables": [{"table": "rapo_resa_my_control", "target": "rapo_resa_my_control", "exists": true,
             "rows": 1315, "rows_analyzed": "2026-09-21T22:00:04", "oldest": "2026-09-21T14:37:45",
             "columns": [{"name": "amount", "status": "widened", "current": "NUMBER(8,2)",
                          "expected": "NUMBER(12,4)", "ddl": "MODIFY (amount NUMBER(12,4))"}]}]}
```

- `tables`: the tables runs of this configuration write (see above), compared column by column.
- `orphans`: the existing tables of the control that runs of this configuration no longer write, with the same
  `rows`/`rows_analyzed`/`oldest` as a table. They are listed even when `rebuilt_each_run`.
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
  change `update-control-schema` makes (mixed-case and reserved column names quoted), or `null`. Only `added`/`widened` changes and `incompatible` columns are
  drift; a `ddl` of `nullable`/`not_output` (`MODIFY ... NULL`) is not, since every run applies it before it saves.
- A datasource that cannot be read is reported as `error` (top level), a table whose expected schema cannot be
  built (e.g. an output column missing in the datasource) as `error` of that table. Both answer `200`.

`400` when the body has no saved `control_id`.

#### `GET /api/get-schema-drift`
The drift and orphaned tables of every control at once, keyed by `control_id`, and the result tables of no
control:

```json
{"controls": {"94": {"level": "update", "changes": 1, "incompatible": 0,
                     "tables": ["RAPO_RESA_RAPO_FIX_REC"], "reason": null,
                     "orphans": [{"table": "RAPO_RESB_RAPO_FIX_REC", "rows": 1488,
                                  "rows_analyzed": "2026-09-21T22:00:04",
                                  "reason": "no discrepancies of side B are written"}]}},
 "unowned": [{"table": "RAPO_RESA_OLD_CONTROL", "rows": 1315, "rows_analyzed": "2026-09-21T22:00:04"}]}
```

`level` is `ok`, `update` (added or widened columns; nullability never counts), `recreate` (incompatible columns), `error` (the
configuration names a column its datasource lacks, or the exact check below failed, see `reason`), `missing` (no
written table exists yet), `source_missing` (a datasource does not exist, named in `reason`), `not_checked`, or
`rebuilt` (the control drops its tables on every run, so only its `orphans` are reported).
`orphans` are the control's tables its saved configuration no longer writes, with the optimizer statistics
(`rows`/`rows_analyzed`, `null` without them) and why nothing writes them. `unowned` carries the same statistics.
Nothing is counted and no table is read here, so a few hundred result tables cost one dictionary query.

Unlike `check-control-schema`, which creates each expected table empty to learn Oracle's types, this starts from
the dictionary (one pass over `all_tab_columns`), so it is cheap enough for the whole catalogue. The result tables
are copies of datasource columns, but the dictionary type of a view column that is an expression is not always the
one a CTAS creates (e.g. a length in bytes where the CTAS keeps characters). So each table the dictionary flags as
`update` or `recreate` is confirmed by the exact check of `check-control-schema`, and only its answer is reported.
The confirmation is reused until the dictionary rows or the configuration it came from change, so a refresh costs
no DDL. A datasource that is a synonym is checked as the table or view it names. Where only Oracle can type a
column, a CMP output column that coalesces A and B, a datasource name with `{variables}`, and a datasource over a
database link (also through a synonym) are `not_checked` with the `reason`.

#### `GET /api/count-control-table-rows`
Count the rows of one result table (`table`) exactly: one of a saved control (`name`), its orphans included, or,
without `name`, one of no control. A full scan, so it is meant to be asked for explicitly. Answers
`{"table": "RAPO_RESA_MY_CONTROL", "rows": 1315, "counted": "2026-09-24T08:21:05"}`, `rows` being `null` when the
table does not exist. `400` when `table` is not a result table of the control, or, without `name`, belongs to a
control.

#### `POST /api/update-control-schema`
Apply the safe changes of `check-control-schema` to the existing result tables of a saved control (`name`):
add missing columns, widen narrow ones, make NOT NULL columns nullable. Nothing is dropped and no data is
changed. Answers `{"status": 200, "incompatible": ["rapo_rest_my_control.name"]}`, the columns left for
`recreate-control-schema`. A run makes the same changes itself before it saves, and fails with
`Recreate schema needed for <table>: ...` when an incompatible column is left.

#### `POST /api/recreate-control-schema`
Drop result tables of a saved control (`name`) and create them at once with the schema of its saved configuration:
those named in `tables` (comma-separated, e.g. `tables=rapo_resb_my_control` to recreate only the side that drifted),
by default all it writes. Past results of those tables are deleted; the others and any orphans are not touched.
`400` when a named table is not one the control writes.

#### `POST /api/drop-orphaned-table`
Drop one result table (`table`) that no run writes any more: an orphan of a control according to its **saved**
configuration, or a table of no control. Past results are deleted. `400` when the table is still written by its
control, is not a result table (`RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_`), or does not exist. `400` with the reason when a table cannot be created, e.g. a missing
datasource.

#### `GET /api/get-temp-tables`
The temporary tables runs left behind. A run drops its `RAPO_TEMP_*` tables only when it ends `D` without debug
mode, so failed, canceled and debug runs keep them. Only objects of the connected schema are read (`user_objects`,
tables and materialized views), and only names Rapo creates (`RAPO_TEMP_<kind>_<process_id>`, current and legacy
kinds, and the scratch `RAPO_TEMP_SCHEMA_<16 hex>` of a schema check) are recognized:

```json
{"runs": [{"process_id": 1000003094, "control_id": 45, "control_name": "TESST", "status": "E",
           "started": "2026-09-29T07:41:12", "debug": false, "in_log": true,
           "tables": ["RAPO_TEMP_SOURCE_B_1000003094"], "mb": 0.1}],
 "scratch": [{"table": "RAPO_TEMP_SCHEMA_ABCDEF0123456789", "type": "TABLE", "created": "2026-09-29T05:55:54", "mb": 0.0}],
 "unknown": [{"table": "RAPO_TEMP_ZZZ_1", "type": "TABLE", "created": "2026-09-29T05:59:54", "mb": 0.0}],
 "total_tables": 3, "total_mb": 0.1}
```

`runs` are newest first; a run in progress (`I`, `W`, `S`, `P`, `F`, or voided) is left out. `debug` marks a run
started in debug mode, `in_log` false a process ID no longer in `rapo_log`. `scratch` lists schema-check tables older
than an hour. `unknown` lists other `RAPO_TEMP_*` objects, which are never dropped by the API (check them manually).
`mb` includes index and LOB segments; `created` is the database clock.

#### `POST /api/drop-temp-tables`
Drop temporary tables, body `{"process_ids": [1000003094], "tables": ["RAPO_TEMP_SCHEMA_ABCDEF0123456789"]}`:
the recognized tables of those runs, and scratch tables (`tables` accepts nothing else). The server re-reads the
dictionary and drops only what it recognizes itself, by its exact name (`DROP MATERIALIZED VIEW` for a
materialized view, else `DROP TABLE ... PURGE`). Answers `{dropped: [table], skipped: [{process_id, reason}],
failed: [{table, error}]}`: a run in progress or without temporary tables is skipped, and one failure never stops
the others. `400` when a name in `tables` is not a listed scratch table (nothing is dropped then), `422` for a body
that is not lists of integers and names.

#### `DELETE /api/delete-control`
Delete a control (`control_id`) from `rapo_config`. With `drop_tables` (default **true**) its result tables are
dropped first: every `RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_<name>` that exists, orphans included. Answers
`{status, dropped}`, the dropped table names. Pass `drop_tables=false` to keep them, as before v0.8.4. Its run log,
run log files and KPI rows are not touched. `400` naming them while other controls read its results (chain-rules,
see `save-control`), `400` while the control has a run in progress, and `400` when a table cannot be dropped: the
control is then kept, and the message names the tables already dropped.

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

### Datasources

The datasources of the PDI Core (Pentaho) file-loading framework: `pdi_core_ds_config`, one row per datasource
(input directories, file mask, scheduler lane `isactive`, archive directories, ...), `pdi_core_ds_tables`, the tables
it loads and their partition retention, and `pdi_core_file_log`, one row per loaded file. They belong to that
framework, not to Rapo, and are found in Rapo's own schema or through a private or public synonym. Where they can
not be read every route answers `404`, and `GET /api/info` reports `datasources_available: false`; where the user
may not change them, the writing routes answer `403` (`datasources_writable`, `datasources_deletable`). What the user
may do is checked with statements that change nothing; a failed check is repeated after a minute, the others every ten
minutes, so a synonym or grant added later is found without a restart.

The input directories are read from **this server's** file system. A mask is matched against the whole file name
(`re.fullmatch`, like Java's `matches()` in PDI Core); subdirectories are read only with `input_scan_subdirs = 1`;
`input_directory` may list several paths separated by `|`.

#### `GET /api/get-ds-list`
Every datasource: its `pdi_core_ds_config` columns, plus `tables` (the linked table names), `table_count` and
`retention_count` (tables with a partition key).

#### `GET /api/get-ds-status`
The files waiting for every active datasource (`isactive` other than 0) as last counted, by `id` (as text) under
`datasources`: `waiting`, `bytes`,
`oldest` (epoch seconds) and `oldest_at`, `young` (modified in the last 60 s, which PDI Core skips), `clean` and
`pdi_clean` (clean-up files under `[DATASOURCES] clean_max_bytes` / under 10 bytes), `missing` and `unreadable`
input directories, `missing_other` (archive, error, duplicate directory), `mask_error`, `clean_mask_error`,
`capped` (a directory had more than `scan_max_entries` files), `stale` (not counted in the last scan, its budget
ran out), `stalled` (active, and the oldest waiting file is older than `stalled_minutes`) and `log`, the loads of the
last 24 hours (`last_load`, `files`, `records`, `rejected`, `errors`, `duplicates`) or `null`. Also `scanned_at`,
`scanned_epoch`, `database_time`, `duration`, `interval`, `stalled_minutes`.

The count runs in the background every `[DATASOURCES] scan_interval` seconds, only while UI clients are connected,
in a child process of the server that reads the directories; one not answering within the budget and 30 seconds is
killed and started anew, and the datasources it did not read keep their counts, marked `stale`.
Before the first one the answer is `{"pending": true, "datasources": {}}` and a count starts.

#### `GET /api/get-ds-config`
One datasource (`id`) with `links`, its tables (`table_name`, `partition_key`, `partition_days_to_retain`,
`partition_days_in_advance`), and `directories`: `{field, path, exists, writable}` for every input path and the
archive, error and duplicate directory, as the background count last read them, without touching the file system;
`null` when one of them was not read (a disabled datasource, a path just saved). `404` when there is none.

#### `GET /api/check-ds-directories`
The `directories` of a datasource (`id`), checked now on the file system, each within 5 seconds, after which its
`exists` and `writable` are `null`.

#### `POST /api/save-ds-config`
Create or update a datasource and replace its tables. The body is `{"datasource": {...}, "expected": {...}}`: the
datasource with its `links` (no `id` creates one; the ID comes from `PDI_CORE_DS_CONFIG_SEQ`), and the datasource as
the caller loaded it. When `expected` is passed and the row or its tables differ from it now, nothing is written:
`409`. Answers `{"status": 200, "datasource": {...}}`, read back like `get-ds-config`.

`400` with the reason when a value is not valid: `sourcename` letters, digits and underscores, at most 50 characters
(it is also `pdi_core_file_log.sourcename`) and unique; directories absolute, without `..`; masks valid regular
expressions; numbers whole and within their column; `isactive` 0-9; flags 0 or 1; `files_dup_handling` one of
`PREVENT`, `PREVENTX`, `REPLACE`, `LOAD`; a table listed once, and days to retain (1 or more) exactly when it has a
partition key. A table need not exist.

Every write is logged in the server log.

#### `POST /api/set-ds-active`
Move a datasource (`id`) to another scheduler lane: `value` is the new `isactive`, 0 disables it. With `expected`,
the lane the caller saw, a datasource moved by someone else meanwhile is not moved: `409`.

#### `DELETE /api/delete-ds-config`
Delete a datasource (`id`) and its `pdi_core_ds_tables` rows. Its file log and the tables it loads stay. `400` while
it is active (`isactive` other than 0).

#### `GET /api/count-ds-file-log`
`{"rows": n}`, the `pdi_core_file_log` rows of a datasource (`id`); `null` without the file log.

#### `GET /api/get-ds-files`
The files in the saved input directories of a datasource (`id`). `kind` is `match` (the files `files_mask` picks
up, the default), `clean` (matching `input_clean_files_mask` and smaller than `[DATASOURCES] clean_max_bytes`) or
`all` (every file, subdirectories included, with the `reason` it is or is not picked up). `files_mask`,
`clean_mask` and `subdirs` replace the saved values, to try the editor's.

Answers `files` (oldest first, at most `list_max_files`: `name`, `directory`, `subdir`, `path`, `size`, `modified`,
`age`, `owner`, `group`, `mode`, `matches`, `clean`, `pdi_deletes`, `young`, `reason`), `directories`
(`{path, exists, readable, capped, error}`), `total`, `matched`, `clean`, `truncated`, `mask_error`,
`clean_mask_error`, `subdirs` and the limits used. A listing reads for `[DATASOURCES] list_budget_seconds` at most;
what it did not read makes it `truncated`.

#### `GET /api/check-ds-mask`
Check a file mask (`mask`, a regular expression) and try it on sample file names (`names`, repeated), each matched
whole (`re.fullmatch`, like Java's `matches()` in PDI Core). Needs no saved datasource. Answers `error` (null when the
mask compiles) and `names` (`{name, matches}`).

#### `POST /api/create-ds-directory`
Create a missing directory (`path`) of a saved datasource (`id`), with its missing parents, each with the mode of
`[DATASOURCES] dir_mode` (umask ignored). Only a directory the saved datasource names: `400` otherwise, or when it
exists or can not be created. Answers `{"status": 200, "created": [...]}`.

#### `GET /api/list-ds-archive`
One level of a saved datasource's (`id`) `field` directory (`archive_directory`, `error_directory` or
`duplicate_directory`), or of its subdirectory `path` (relative, e.g. a day `YYYYMMDD`; `400` when it leads outside).
Answers `root`, `path`, `exists`, `readable`, `error`, `dirs` (`{name, path, modified}`, newest name first), `files`
(`{name, path, size, modified, owner, group, mode}`, by name) and `truncated`, stopped at `[DATASOURCES]
list_max_files` entries or `list_budget_seconds`. `path` of an entry is what to pass to list it.

#### `GET /api/get-ds-table-facts`
What the dictionary says about tables (`tables`, repeated) of Rapo's schema, by name: `exists`, `num_rows`,
`partitioned`, `partitioning_type`, `interval`, `partition_keys`, `partition_count`, `first_partition` and
`last_partition` (their high values), and `partitioned_by`, the datasources (`{id, sourcename, partition_key,
partition_days_to_retain, partition_days_in_advance}`) configuring a partition key for the table.

#### `GET /api/get-ds-file-log`
The files a datasource (`id`) loaded on one day (`date`, `YYYY-MM-DD`, default the database's today), newest first,
at most 20,000: `{date, today, files, truncated}`, each file with the columns of `pdi_core_file_log` but `log`.

#### `GET /api/get-ds-file-log-text`
`{"log": "..."}`, the log text PDI Core wrote for one file (`file_id`).

#### `GET /api/get-files-day`
The file log of one day (`date`, `YYYY-MM-DD`, default the database's today) as aggregates, every query bounded to
the day's partitions: `cells` (`{sourceid, hour, status, files, read, written, rejected, duplicates, runtime}`,
runtime in seconds summed, one per datasource, hour
0-23 and status), `perf` by datasource id (`n`, `min`, `p25`, `median`, `p75`, `max` of the k records written per
second of its SUCCESS files with a runtime, and `last_success`), `week_before` (files by datasource id on the same
weekday a week earlier, for today up to the same time of day), `names` (the SOURCENAME the log gives each id),
`date`, `today`, `database_time`.

#### `GET /api/search-files`
The files of one day (`date`) whose name contains `text` (3 characters or more, case-insensitive), newest first, at
most 200: `id`, `sourceid`, `sourcename`, `inputfilename`, `filestatus`, `startloaddate`.

#### `POST /api/set-file-status`
Ask PDI Core to recycle, reload or delete loaded files. The body is `{"ids": [...], "status": "RECYCLE"|"RELOAD"|
"DELETE"}`, at most 5000 ids. `RECYCLE` changes a `SUCCESS` or `ERROR` file, `RELOAD` a `SUCCESS` file, both only with
`OUTFILEDELETED = 0`; `DELETE` a file of any status but `DELETE`; PDI Core does the rest (DELETE also deletes the archived file). Answers `{"status": 200, "requested", "changed",
"skipped": [{id, status, reason}]}`. `403` without `UPDATE` on the file log.

#### `GET /api/get-pdi-state`
The lane locks of `PDI_CORE_STATE`: `lanes` (`{lane: since}` of the `LOAD_<lane>` rows), `lock` (since when the `LOCK`
row stops every lane, or `null`), `other` rows, `database_time`, `lock_stale_minutes`, and `available`; when it is
`false`, `error` says why (e.g. `ORA-00942` for a synonym without the grant behind it).

#### `POST /api/remove-lane-lock`
Delete the `LOAD_<lane>` row (`lane`) when its `DATETIME` still is `since`, as the caller saw it; `409` when it was
taken anew or is gone.

#### `POST /api/set-global-lock`
`on=true` inserts the `LOCK` row (`sysdate`, `RUNNING`) unless it exists, `on=false` deletes it. `403` without the
grants on `PDI_CORE_STATE`.

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

### Data analysis

The records behind a number of a run can be copied as SQL, or loaded into a sample that is profiled and browsed.
A **dataset** names the number it stands for:

| `dataset`   | Records                                                                                              |
|-------------|------------------------------------------------------------------------------------------------------|
| `fetched_a` | What the run read from datasource A (or the only datasource): the engine's select for the run's window, built from the control's **current** configuration. A REP's is its result table. |
| `fetched_b` | The same for datasource B (REC, CMP).                                                                |
| `result_a`  | The run's rows of `RAPO_RESA_<name>` (REC, without the `Match` rows) or `RAPO_REST_<name>` (other types). |
| `result_b`  | The run's rows of `RAPO_RESB_<name>` (REC, without `Match`) or `RAPO_REST_<name>`.                   |

A sample is held by an **analysis session**: a worker process on the server that keeps the dataset's cursor open,
so that `analysis-extend` fetches the rows that follow. Sessions are local to the server that started them. One
that gets no request for `[ANALYSIS] idle_minutes` is closed; any request to it then answers 404.

The session **state** is `{status, step, progress, rows, version, exhausted, cursor_open, limited, memory_mb,
columns, sections, error}`:
- `status`: `starting`, `fetching`, `profiling`, `ready`, `canceled`, `error` (nothing loaded), `lost` (worker
  gone), `expired`.
- `progress`: `{done, total}` of the step, or null. `rows`: rows in the sample. `version` changes whenever the
  sample does; rows and sections are always of the current version.
- `exhausted`: every row of the dataset is loaded. `cursor_open`: the sample can be extended. `limited`: `rows`
  (`max_rows` reached) or `memory` (`max_memory_mb` reached), else null.
- `columns`: `[{name, kind, db_type}]` in the dataset's order, `kind` being `numeric`, `datetime` or `text`.
- `sections`: the profile sections ready for this version.

Changes of the state are pushed as the `analysis:progress` event (see Live events).

**Viewer filters** (`filters`, a JSON list) are `{column, op, value}`: `eq`, `ne` (a value, null for missing),
`in` (a list), `contains`, `starts` (case-insensitive text), `range` (`{min, max, max_inclusive}`, either bound
null), `null`, `notnull`, and `{op: "duplicated"}` without a column (rows repeated in the sample). `sort` is a JSON
list of `{column, desc}`, and `search` a case-insensitive text looked for in every column.

#### `GET /api/get-run-dataset-sql`
`process_id`, `dataset`. Answers `{sql, meta}`: the dataset's SQL, formatted, and its description (control, run
window and status, `table_name`, `total` rows - exact for a result dataset, the run's count for a fetched one -
`stale`, true when the control was saved after the run started, and `datasets`, the run's other datasets
`[{dataset, kind, side, count}]` with the counts of its run log; empty for a report; `key_fields`, the lower-case
identifiers of the control's criteria on the dataset's side: REC correlation and discrepancy fields, CMP match and
mismatch columns, ANL error and case definitions, plus the date and key fields). 404 when the run, the dataset or the result
table does not exist.

#### `POST /api/analysis-start`
`process_id`, `dataset`, `random` (default true), and an optional JSON body `{filters, search, where}` applied by the database: the filters
and the search become literal predicates over the dataset's select, and `where` is a condition of your own over its
columns. The statement is parsed by Oracle first, so a wrong filter answers 404 with Oracle's message. Starts a
session and answers `{session_id, meta, state, options}`, `options` being the `[ANALYSIS]` limits in effect. `meta`
also holds `sql`, the statement the sample is drawn with (formatted), and `pushdown`; with a database filter, a
fetched dataset's `total` is null, as counting it could scan the whole source. With `random` the records are read
in random order (`order by dbms_random.value` around the statement, so Oracle sorts the whole dataset before the
first row), and the sample is uniform at any size, extensions included; `random=false` reads the first records as
the database returns them. `meta.random` says which; `meta.sql` never has the random order. The first
`initial_rows` are fetched at once, then the columns and the overview are profiled. 409 when all sessions are in use, 404 for an unknown
dataset or a filter that does not parse, 503 while the server starts or stops.

#### `GET /api/analysis-status`
`session_id`. Answers the same as `analysis-start`, with the current state.

#### `POST /api/analysis-extend`
`session_id`, optional `rows` (default `extend_rows`). Fetches the next rows into the sample, up to `max_rows`.
Answers `{state}`. 400 when the dataset has no more rows or its cursor was lost.

#### `POST /api/analysis-cancel`
`session_id`. Cancels the step in progress; rows fetched so far are kept. Answers `{state}`.

#### `POST /api/analysis-close`
`session_id`. Ends the session and its process. Answers `{"status": 200}`, also for a session already closed.

#### `GET /api/analysis-rows`
`session_id`, `offset` (0), `limit` (200, at most 5000), optional `sort`, `search`, `filters`. Answers `{version,
total, offset, rows}`: `total` rows match, and `rows` are lists of values in the order of `state.columns`.

#### `GET /api/analysis-profile`
`session_id`, `section`: `overview`, `columns`, `missing`, `duplicates`, `correlations` or `breakdown`, and optional
`filters` and `search`, which make the section describe only the rows they leave. Answers `{ready, version, key,
data}`. A section not computed yet answers `ready: false` and is computed; the state lists its `key` under
`sections` once it is ready (the section name, or `<section>@<hash>` for filtered rows). `correlations` holds
`pearson`, `spearman` and `cramers` (`{columns, matrix}`), the strongest `pairs` and `alerts`; it is measured on the
first 200,000 rows (`sampled`). `breakdown` counts the values of `rapo_result_type`, `rapo_result_value` and
`rapo_discrepancy_description` where the dataset has them. `columns` is one object per column (`count`, `missing`, `distinct`, `top` values, `stats`, `histogram`
`{counts, edges}`, and per kind `smallest`/`largest`, `hours`/`weekdays`, text lengths), each with its `alerts`.

#### `GET /api/analysis-groups`
`session_id`, `by` (a JSON list of `{column, bucket}`, `bucket` being `hour`, `day`, `month` or `year` for a
date-time column), optional `aggregates` (a JSON list of `{column, fn}`, `fn` one of `sum`, `mean`, `min`, `max`,
`nunique`), `filters`, `search`, `sort` (a JSON `{column, desc}`, `column` being `count`, a grouping column or
`fn(column)`; by default the largest groups first) and `limit` (1000, at most 5000). Answers `{version, by,
aggregates, rows, total_groups, total_rows}`, each row being `{keys, ends, count, values}`; `ends` gives, by key
position, the end of a date bucket (exclusive).

#### `POST /api/validate-analysis-where`
`process_id`, `dataset`, JSON body `{where}`. Parses the dataset's select with that condition without running it,
and answers like `validate-sql`.

#### `GET /api/get-analysis-targets`
`process_id`, `dataset`. Answers the datasets it is usually compared with, `[{key, label, process_id, dataset}]`:
`source` (the other kind of the same side of the run: fetched for discrepancies and back; none for a REP),
`previous` (the same dataset of the previous done run) and `other_side` (REC, and CMP fetched datasets).

#### `GET /api/get-control-done-runs`
`control_name`, `limit` (50, at most 500). Answers the latest done runs of a control, newest first, with their
window and counts but without their logs, for picking one to compare with.

#### `GET /api/analysis-compare-mapping`
`session_id`, `other_id` (two sessions of this server). Answers `{pairs, unmatched_a, unmatched_b}`: the columns
paired by name (case-insensitive; `rapo_process_id` and `rapo_discrepancy_id` left out) and, for the two sides of
one reconciliation, by its correlation and discrepancy fields (`source` is `criteria` or `name`).

#### `POST /api/analysis-compare`
`session_id` (A), `other_id` (B), JSON body `{pairs: [{a, b}]}`. Compares the two samples column by column; no
rows leave the workers. A numeric or date-time pair is binned on 20 common ranges, anything else by the 30 values
most frequent in either sample, plus the missing and the other values. Answers `{rows_a, rows_b, version_a,
version_b, columns}`, most divergent first, each `{a, b, kind, mode (bins or values), psi, level (stable, moderate,
major, or unique for a key-like column, which is not ranked), missing_pct, distinct, stats {mean, median, min, max:
[a, b]}, labels, shares_a, shares_b, lifts}`. `shares_*` are percentages of the rows per label, then missing, then
other; each lift is `{index, label, missing, other, count_a, count_b, share_a, share_b, lift}`, lift being
`share_a / share_b` (null when B has none).

#### `POST /api/analysis-counterpart`
`session_id` of a REC dataset, JSON body `{row}` (the row's values in the order of `state.columns`). Evaluates the
row's correlation key with the control's own expressions and answers `{side, other_side, keys: [{expression,
value}], pair, results, source}`: the other side's rows of the run's result table and of its datasource for the run's
window, each `{columns, rows, more, error}` (at most 100 rows, `more` when there are others). `pair` is the record
the row was matched with, when the row has a `RAPO_DISCREPANCY_ID` (which holds that record's key field):
`{key_field, value, results, source}`, looked up by `cast(<key_field> as varchar2(4000)) = value`, or with an `error`
when the other side has no key field. It is null for a row without one (a Loss, a fetched record). 400 for other
types.

#### `GET /api/get-control-trend`
`process_id`, `dataset`, `limit` (30, 2 to 200). Answers `{side, process_id, runs}`: the latest `limit` periods of
the run's control in date order, each `{process_id, date_from, date_to, start_date, status, fetched, discrepancies,
error_level}` of the dataset's side, from the run log only. A period is the days of `date_from` and `date_to`, and
is shown by its last done run (the highest `process_id`), since a day is often run more than once; the period of
the run itself is shown by that run.

#### `GET /api/analysis-export`
`session_id`, `format` (`xlsx` or `csv`), optional `sort`, `search`, `filters`, `columns` (a JSON list of names, in
the order wanted). Downloads the matching rows. Excel is cut at 1,048,575 rows, and the header `X-Rapo-Cut` then
holds that limit.

#### `POST /api/start-discrepancy-analysis`
`process_id`, `side` (`a` or `b`), optional `result_type` (REC only: `Loss`, `Discrepancy` or `Duplicate`; all of
them by default), `recompute` (default false). Explains what sets the discrepancies of one side of a run apart from
its **normal records**, the side's fetched records less the discrepancies. Nothing is joined: every attribute is
binned the same way on both datasets and counted by Oracle over the whole data, and a bin's normal count is its
fetched count less its discrepancy count (never below 0). The datasource is scanned about four times (profile,
bins, pairs of bins, examples). The fetched records are the `fetched_a|b` dataset (the
control's current configuration); above `[ANALYSIS] discrepancy_exact_rows` they are counted on a random sample
scaled back up, the discrepancies always whole. ANL has side `a` only; a CMP's discrepancies are one table, side `a`
analysing its `a_` (or side-A output) columns and side `b` the others. A result column is analysed when it holds a
fetched column (same name, or the output column configuration names it); coalesced columns and `RAPO_*` metadata are
not.

Runs as a job in a process of its own, one at a time per server (others queued, `[ANALYSIS]
discrepancy_timeout_minutes` at most). Answers the job, `{process_id, side, result_type, state, progress, error,
queued, started, finished, report}`, `state` being `queued`, `running`, `done` or `error`, `progress` `{step, done,
total}`. A job of the same run, side and type is reused (its report too) unless `recompute`; the latest 20 finished
jobs are kept in the server's memory until it stops. State changes are pushed as `discrepancy:progress` (the job
without `report`). 400 for a report, side `b` of an analysis or an unknown result type, 404 for an unknown run, 503
while the server starts or stops.

The **report** (`state` = `done`):
- `meta`: the run (as `get-run-dataset-sql`), `side`, `dataset` / `fetched_dataset` (the Data analysis datasets),
  `result_type`, `discrepancies`, `normal`, `fetched_total` (counted now) and `fetched_logged` (at run time),
  `sample` (the sampled share, or null), `drift` (the two totals differ), `stale`, `clamped` (columns whose bins
  hold more discrepancies than fetched records), `excluded` (`[{column, reason}]`), `datasets` (`[{side, count}]`).
- `type_split`: REC `[{type, count}]` of the side's discrepancies, else null.
- `attributes`: strongest first, one per binning of a column: `{id, column, source, kind, feature, feature_label,
  ordered, score, phik, bins, special, under, bands}`. `feature` is `value`, `decile` (ranges by the fetched
  deciles), `prefix` (first 3/5/6/8 digits or 2/4/6 characters of an identifier-like column), `length`, `hour`,
  `weekday` or `timeline` (20 equal periods). `score` is Theil's U of being a discrepancy given the bins (0..1,
  the share of the uncertainty removed, less a small-sample bias), `phik` the phik correlation. Each bin is `{code,
  label, disc, normal, disc_share, normal_share, lift, rate, z, flag, filter}`: `lift` = `disc_share /
  normal_share` (null with `only_disc` when no normal record has it), `rate` the share of the bin's records that are
  discrepancies, `z` a two-proportion z, `flag` `over` (at least 10 discrepancies and 1% of them, lift ≥ 2, z ≥ 4),
  `under` or null, and `filter` `{result, fetched}`: a condition selecting the bin's records, usable as
  `analysis-start`'s `where` on the discrepancy and the fetched dataset. `bands` merges adjacent `over` bins of an
  ordered feature (`02:00 – 04:59`).
- `heatmaps`: per date column `{column, cells}`, each cell `{weekday (0 = Monday), hour, disc, normal, rate,
  lift}`.
- `combinations`: up to 8 pairs of bins of two attributes stronger together than alone (over-represented, and a
  discrepancy rate 1.5 times the better of the two bins'): `{id, attributes, parts, disc, normal, disc_share,
  normal_share, lift, rate, z, wracc, filter}`, each part `{attribute, what, label, phrase, codes, lift}` (the bin's
  lift alone). The strongest attribute of up to 6 columns takes part, each reduced to at most 5 groups of its bins
  (bands, a common prefix, the bins with the most discrepancies). Ranked by `wracc`, coverage × (rate − base rate).
- `findings`: what the history and the examples follow, `[{id, kind (driver|combination), attribute, label, codes,
  filter, disc_share, normal_share}]`.
- `history`: null without a previous run, else `{runs, findings, error?}`: `runs` the previous finished runs of the
  control (up to `[ANALYSIS] discrepancy_history_runs`) whose results are still in the result table, plus this one,
  oldest first, `[{process_id, date_from, date_to, total}]`; per finding `{finding, label, attribute, counts, shares,
  status, since, before}`, `shares` its share of each run's discrepancies, `status` `new` (it stands out from
  `since`; before, under a quarter of its share now), `growing`, `chronic` or `single`, `before` the average share
  in the previous runs.
- `magnitude`: REC with all types or `Discrepancy` only, else null: `{total, fields, cut}` from
  `RAPO_DISCREPANCY_DESCRIPTION` of the value discrepancies, per field `{field, records, share, distinct, values
  (top 10 {value, count, share}), numeric, min, median, max, histogram}`; `cut` when more than 2,000 different
  descriptions exist (the most frequent are read).
- `excerpts`: per finding (up to 4) `{finding, label, columns, result, fetched}`: up to 10 discrepancies and 10
  fetched records of its bins, rows as lists in `columns` order (`result_error`/`fetched_error` when one could not
  be read).
- `story`: `[{kind, text, attribute?, codes?, finding?}]`, the findings in sentences: `headline`, `types`,
  `driver`, `time`, `combination`, `history`, `magnitude`, `unrelated`, `none`, `note`; a driver names its
  attribute `id` and bin codes, a combination or history sentence its finding.

#### `GET /api/get-discrepancy-analysis`
`process_id`, `side`, optional `result_type`. Answers the job as `start-discrepancy-analysis` does; 404 when none
was started on this server since it started.

### PDI Core files

#### `POST /api/download-ds-files`
JSON body `{ids}`: at most 500 file IDs of `PDI_CORE_FILE_LOG`. Downloads the files from where PDI Core kept them
(`OUTPUTFULLFILENAME`), read from **this server's** file system. A file is sent only when its status is `SUCCESS` or
`ERROR`, its archived file is kept (`OUTFILEDELETED = 0`), and its real path (symlinks resolved) lies within the
`ARCHIVE_DIRECTORY`, `ERROR_DIRECTORY` or `DUPLICATE_DIRECTORY` of its datasource. One file is sent as it is
(`application/octet-stream`); several as one ZIP `<SOURCENAME>_<YYYYMMDD>.zip`, written while it is sent, with a
`MISSING.txt` naming the files left out and why. The header `X-Rapo-Skipped` counts the files left out. Each download
is written to the server log.

`400` when no file can be sent (the reasons are named), or the files are more than `[DATASOURCES]
max_download_mb` (500 MB by default) together; `403` with `[DATASOURCES] file_download=False`; `404` without a
readable file log.

```bash
curl -X POST -H "Authorization: Bearer $RAPO_TOKEN" -H "Content-Type: application/json" \
  -d '{"ids": [101, 102]}' -o files.zip http://rapo-host:7005/api/download-ds-files
```

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
  `{event_id, control_name, control_type, job_control_name, trigger_type, process_id, pid, queued, started}`.
  `process_id`, `control_name` and `control_type` are those of the run the job process performs now, which is an
  upstream run of a chain, an iteration or a cascade child while those run; `job_control_name` is the control the
  job was submitted for.

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

#### `GET /api/get-next-fires`
The next runs of every control, for the Controls page. A scheduled fire runs the control, then cascades into the
active controls whose `trigger_id` it is (one level: a cascaded run does not cascade), and every run first pulls
the controls whose results it reads (chain-rules), whatever their status.

| Parameter | Type | Default | Meaning                                |
|-----------|------|---------|-----------------------------------------|
| `count`   | int  | 5       | Runs per control, 1 .. 20.              |

Answers `{server_time, scheduler_state, scheduler_active, controls}`. `controls` maps every control ID to
`{fires: [{time, source, via, date_from, date_to}]}`, sorted by time: `source` is `schedule`, `cascade` (`via` the
control it follows) or `chain` (`via` the control that pulls it), and `date_from`/`date_to` the run's data window
(the puller's window for a chain run, null for an invalid period). A control whose `schedule_config` cannot be read
has `invalid: true`. `scheduler_active` is false while the scheduler is stopped, or off here with no other server
holding it; the runs are then still listed. Computed from the database, so any server answers it.

#### `GET /api/scheduler-events`
The run request history, latest first.

| Parameter      | Type | Default | Meaning                                       |
|----------------|------|---------|------------------------------------------------|
| `control_name` | str  | -       | Filter by control.                             |
| `event_type`   | str  | -       | `FIRED`, `STARTED`, `MISSED`, `FAILED`, `CANCELED`. |
| `trigger_type` | str  | -       | `SCHEDULE`, `MANUAL`, `CATCHUP`, `ITERATION`, `CASCADE`, `UPSTREAM`. |
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
`config_path` (the `rapo.ini` actually loaded) and `log_directory`. Also what the UI may offer: `kpi_available`,
and for the PDI Core datasources `datasources_available`, `datasources_writable`, `datasources_deletable`,
`datasources_log` (the file log is readable), `datasources_file_actions` (files can be recycled, reloaded, deleted),
`datasources_file_download` (files can be downloaded: the file log is readable and `[DATASOURCES] file_download` on),
`datasources_state`, `datasources_state_write` and `datasources_state_delete` (the lane locks of `PDI_CORE_STATE`).

#### `GET /api/parameters`
The loaded `rapo.ini` as it is written, one object per section. Options whose name contains `password`, `token` or
`secret` are left out, and options that are not in the file are simply absent - defaults applied in code are not
shown here.

#### `GET /api/get-config-changes`
The differences between the loaded `rapo.ini` and the file on disk: `{"changes": [...]}`, one object per option with
`section`, `option`, `change` (`added`, `removed` or `changed`), `restart` (the change applies only after a restart:
`[DATABASE]`, `[API]`, `[LOGGING] directory`, `[SCHEDULER] enabled`, and a removed pepperoni `[LOGGING]` option),
`secret`, and the `loaded` and `file` values, both `null` for a secret. `400` when the file is missing or can not be
parsed.

#### `POST /api/reload-config`
Applies the changes of `rapo.ini` that need no restart to this server:
`{"status": 200, "applied": [...], "restart_required": [...]}`, as `get-config-changes` describes them. Options that
need a restart keep their loaded value and stay listed by `get-config-changes`. `400` when the file is missing or can
not be parsed, and then nothing is applied. It only affects the server that answers; runs read the file anew anyway.

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
| `analysis:progress` | `{session_id, state}` - see Data analysis         |
| `discrepancy:progress` | A discrepancy analysis job without its `report` - see `start-discrepancy-analysis` |
| `datasources:changed` | `{kind}`: `config` when `pdi_core_ds_config` or `pdi_core_ds_tables` changed, by anyone; `status` when a count of the waiting files differs from the one before; `state` when a lane lock of `pdi_core_state` changed; `files` when today's file log got files or finished loads |

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
control triggered by another control, `UPSTREAM` a control run first because another reads its results (the
`message` is `For <control> [<process_id>]`).

**Scheduler states** (`scheduler-status.state`): `running` this server holds the lease and schedules, `standby`
another server does, `stopped` scheduling is switched off in the database for every server, `off` the scheduler is
disabled for this server in `rapo.ini`, `starting` no server holds the lease yet.
