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
  `check-control-schema`, `save-kpi-type`, `validate-kpi-sql`, `calculate-kpi`, `validate-sql`,
  `validate-analysis-where`, `download-ds-files`, `check-ds-upload`, `save-asn1-grammar` and `save-viewer-settings`,
  which take a JSON body, `analysis-start`, which takes an optional one, and `upload-ds-file`, whose body is the file.
* **Mutations answer `{"status": 200}`.** `save-control` adds the saved row's `control_id` and `updated_date`.
  Reads answer their payload directly.
* **Errors are real HTTP codes** with FastAPI's `detail`:

  | Code | Meaning                                                                            |
  |------|------------------------------------------------------------------------------------|
  | 401  | Missing or wrong token.                                                             |
  | 400  | The request was understood but could not be performed (bad control, failed save).   |
  | 404  | No such run, control, record or log file.                                           |
  | 413  | An uploaded file over `[DATASOURCES] max_upload_mb`.                                |
  | 409  | Scheduler start refused because the scheduler is disabled for this server in `rapo.ini`, a `save-control` refused because the control changed since `expected_updated_date`, an `analysis-start` refused because all `[ANALYSIS] max_sessions` are in use, or an `upload-ds-file` of a file already in the input directory. |
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
| `cascade`    | bool | `true`  | Also run the controls cascading from it. The UI sends `false` unless ticked. |

With no date at all the window is `now`..`now`. The call goes through the same queue as a scheduled fire: it
returns as soon as the run is initiated - a `rapo_log` row with status `I`, already visible and cancellable - not
when the run is done. The run **cascades** into the controls triggered by it, for the window that was asked for, unless
`cascade=false`.
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

Answers `{date, today, server_time, runs}`, where `today` is the server's current day, so a caller can tell whether it
is looking at today without a clock of its own, and `server_time` its time (the Results heatmap's *Now* marker). A run that never started is reported on the day it was added. The
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

#### `GET /api/get-run-calendar`
The runs per day of a month (`month=YYYY-MM`, `400` otherwise), for the Results calendar:
`{"YYYY-MM-DD": {"count": n, "errors": e}}` for the days with runs. A run counts on the day it started, or was added
if it never started, as `get-control-runs?date=`; runs of deleted controls are left out, `errors` are runs in `E`.

#### `GET /api/get-control-run`
Details of one run (`process_id`): name, window, timestamps (`added`, `start_date`, `end_date`), status and
counters. `404` when the run does not
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
Names of the tables and views of the Rapo database user's schema. With `types=true`, `[{"name", "type"}]` instead,
`type` `TABLE` or `VIEW` (the editor offers *Edit view SQL* for a view).

#### `GET /api/get-datasource-columns`
`column_name` and `data_type` of one datasource (`datasource_name`), in column order.

#### View datasources
The control editor edits the query of a view of the own schema (its `user_views.text`, the text after `AS`); the
rest of its DDL (column alias list, editioning, clauses) is kept as `dbms_metadata.get_ddl` gives it, and the view is
created without `FORCE`. All routes answer `403` while `[VIEWS] edit` is off, `404` for a name that is not a view of
the own schema.

- `GET /api/get-view?name=`: `{name, status, last_ddl_time, body, editable, reason, aliases, columns, errors,
  dependencies, dependents}`. `editable` is false (with `reason`) when the query is not a plain select/with or the
  DDL cannot be split around it. `aliases` lists the view's column names when its column list renames the query's
  columns (then kept, and the query must return as many), else null. `columns` `[{column_name, data_type}]`,
  `data_type` as in DDL (`VARCHAR2(40)`, `NUMBER(10,2)`); `errors` from `user_errors`; `dependencies` `{name:
  [column]}` of the tables and views it reads (as the dictionary names them, quoted unless plain, `owner.name` for another schema),
  for autocomplete; `dependents` `{controls: [control_name], objects: [{owner, name, type}]}` (controls whose
  `source_name*` is the view, objects of `all_dependencies`).
- `POST /api/check-view` body `{name, body}`: creates the view as `RAPO_TEMP_VIEW_<16 hex>` with the new query,
  reads its columns and drops it. `{valid: true, columns, diff: {added: [name], removed: [name], retyped:
  [{column_name, old, new}]}}`, or `{valid: false, error, error_offset}` (`error_offset`: position in the query,
  when Oracle tells). A query must be one select/with, without `FOR UPDATE` or PL/SQL in a `WITH` clause.
- `POST /api/preview-view` body `{body, rows}`: runs the query read only (`select * from (<query>) fetch first
  :n rows only`), `rows` (default 10) capped at `[VIEWS] preview_max_rows`, stopped after `preview_timeout`.
  `{columns: [{name, type}], rows: [[value]], elapsed, limit, more}`; dates as naive ISO strings, integers beyond
  2^53 as text, RAW as hex. `400` with Oracle's message.
- `POST /api/compile-view` body `{name, body, expected_ddl_time, force, control_name}`: checks the query as
  `check-view` (`400` "The view is not replaced: ..." when invalid), then `CREATE OR REPLACE VIEW`. `409` when the
  view's `last_ddl_time` is not `expected_ddl_time` (as `get-view` gave it) unless `force`. The previous DDL is
  written to the server log (naming `control_name`), the only copy kept. Answers `get-view` of the new view plus
  `diff`.
- `POST /api/format-view` body `{body}`: `{body}` formatted in Rapo's style (`db.formatter`).
- `GET /api/get-object-columns?names=a,owner.b`: `{name as given: [column]}` of the named tables/views (at most 50),
  names without columns left out; the editor asks for the tables typed into a query.

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

**KPIs follow a rename.** With `kpi_config` the KPIs are written under the new name (the web UI has already pointed
their statements to the renamed result tables). Without `kpi_config`, the control's `racs_kpi_config` rows are moved to
the new name, and whole `RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_<old name>` references in their own KPI and alarm
statements are rewritten (any case, quoted or owner-qualified; type defaults are never changed); rows already under
the new name, orphans, are replaced. The answer adds `kpis_moved`, `[{"kpi_type": "RER", "fields":
["kpi_sql_statement"]}]`; a failure answers `400` "Control was saved, but its KPI configuration was not: ...".

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
tables, views and materialized views), and only names Rapo creates (`RAPO_TEMP_<kind>_<process_id>`, current and
legacy kinds, the scratch `RAPO_TEMP_SCHEMA_<16 hex>` of a schema check and the scratch view `RAPO_TEMP_VIEW_<16 hex>`
of a view check, `type` `VIEW`) are recognized:

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
`{status, dropped, kpis_deleted}`, the dropped table names and deleted KPI types. Pass `drop_tables=false` to keep
the tables, as before v0.8.4. With `delete_kpis` (default **true**) its `racs_kpi_config` rows are deleted after it;
`delete_kpis=false` leaves them as orphaned KPIs. A KPI failure answers `400` saying the control *was* deleted. Its run
log, run log files and the stored KPI values (`racs_kpi_runhistory_all`) are not touched. `400` naming them while other controls read its results (chain-rules,
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

#### `GET /api/get-orphan-kpis`
The `racs_kpi_config` rows whose `processname` matches no control (`RACS_KPI_PKG` matches the name exactly, so they
are never calculated): `processname`, `kpi_type`, `has_kpi_sql`/`has_alarm_sql` (own statement, else the type's
default), `stored_runs` and `last_stored` (from `racs_kpi_runhistory_all`), and `case_match`, a control whose name
differs only in case, or `null`.

#### `DELETE /api/delete-orphan-kpis`
Delete the KPI rows of `processname`, one `kpi_type` or all of them. Answers `{"status": 200, "count": N}`. `400`
when a control has that name (its KPIs are edited with it in `save-control`). Stored values are kept.

#### `POST /api/reassign-orphan-kpi`
Move one KPI row (`processname`, `kpi_type`) to an existing control (`control_name`), e.g. one renamed outside the
application. `400` when a control has `processname`, `control_name` does not exist, or it already has the type.

#### `POST /api/calculate-kpi`
Calculate one KPI of one run without storing anything, as `RACS_KPI_PKG.run_rapo_control_kpi_calculation` would.
The body is `{"process_id": 1000003247, "kpi_type": "RER", "kpi_sql_statement": "...", "alarm_sql_statement":
"..."}` with the statements as edited (blank = the type's default), or `{"process_id": ..., "kpi_type": ..., "saved":
true}` for the statements saved for the run's control.

The KPI statement gets `:v_processid` as text; its value is the first column of the first row, **0 when there is no
row** (`no_rows: true`), rounded to 4 places. The alarm statement gets that value as `:v_kpi_value`. A missing
statement (own and default) leaves the value or the alarm level 0, as the package does. The answer:
`{kpi_type, process_id, kpi_value_unit, kpi_decimal_places, kpi_source, alarm_source, kpi_sql, alarm_sql, value,
no_rows, alarm_level, kpi_ms, alarm_ms, error, stage}`; a source is `draft`, `saved`, `default` or `null` (none).

Only one query is executed: it must start with `select`/`with`, and `FOR UPDATE`, PL/SQL in a `WITH` clause and a
second statement are refused. It runs on its own connection in a read-only transaction that is always rolled back,
stopped after `[KPI] calculate_timeout` seconds (120). A function with an autonomous transaction is the one thing
these checks cannot stop. A statement that is refused or fails is answered `200` with `error` and the `stage`
(`kpi`/`alarm`) it failed in; `400` for an unknown run, KPI type or saved KPI.

#### `GET /api/get-kpi-history`
What `RACS_KPI_PKG` stored for one run (`process_id`) in `racs_kpi_runhistory_all`: one row per KPI type with
`processname`, `kpi_type`, `kpi_value`, `alarm_level`, `status`, `created` and the last 4000 characters of
`kpi_sql_log`. `[]` without that table.

#### `GET /api/get-kpi-runs`
The latest runs of one control (`control_name`, `limit` default 50, at most 500), newest first: `process_id`,
`status`, `date_from`, `date_to`, `start_date`, `added`.

#### `POST /api/reingest-kpis`
Calculate, store and post the saved KPIs of one run (`process_id`) by calling
`racs_kpi_pkg.ingest_rapo_control`: environment snapshot, `racs_kpi_runhistory_all`, dashboard post. Answers
`{"status": 200, "kpis": [...]}` with the rows `get-kpi-history` answers afterwards; the package logs its own failures
instead of raising them, so check their `status`. `400` when the run did not end `D`, the control is aliased `TEST...`
or has no KPIs (the package would skip it), or the package fails.

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
at most 20,000: `{date, today, database_time, files, truncated}` (`database_time`: the clock that stamps the file
log), each file with the columns of `pdi_core_file_log` but `log`.

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
Files of any day, newest first, at most 200: those whose `INPUTFILENAME` starts with `text` (3 characters or more,
case-sensitive, so that its index is used), or the file `id`. One of the two is required (`400`); `source_id` keeps
the files of one datasource. Each with `id`,
`sourceid`, `sourcename`, `inputfilename`, `filestatus`, `startloaddate`.

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

#### `POST /api/set-lane-lock`
Pause one lane (`lane`): insert its `LOAD_<lane>` row (`sysdate`, `RUNNING`), as a core_load run does, so no other
run of the lane starts until it is removed (`remove-lane-lock`). `409` when the lane is locked already, `403` without
`INSERT` on `PDI_CORE_STATE`.

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

A sample is held by an **analysis session**: a worker process on the server (kept spawned and connected ahead, so a
session starts at once) that keeps the dataset's cursor open, so that `analysis-extend` fetches the rows that follow.
Sessions are local to the server that started them. One that gets no request for `[ANALYSIS] idle_minutes` is
closed; any request to it then answers 404.

The session **state** is `{status, step, progress, rows, version, sampling, target, exhausted, extendable,
cursor_open, limited, memory_mb, columns, sections, error}`:
- `status`: `starting`, `fetching`, `profiling`, `ready`, `canceled`, `error` (nothing loaded), `lost` (worker
  gone), `expired`.
- `progress`: `{done, total}` of the step, or null. `rows`: rows in the sample. `version` changes whenever the
  sample does; rows and sections are always of the current version.
- `sampling`: how the sample is drawn (see `analysis-start`): `all`, `first`, `sorted` or `bernoulli`; `target` the
  size a Bernoulli sample is drawn for (its rows vary around it).
- `exhausted`: every row of the dataset is loaded. `extendable`: `analysis-extend` can add rows. `cursor_open`: the
  dataset's cursor is still open. `limited`: `rows` (`max_rows` reached) or `memory` (`max_memory_mb` reached), else
  null.
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
fetched dataset's `total` is null, as counting it could scan the whole source. With `random` the sample is drawn by
the dataset's count (`meta.sampling`): `all`, the plain select, when the count is at most `initial_rows`; `bernoulli`
for a larger count, each record kept with the probability `initial_rows / total` (a random value of an unmerged
view), so the records stream without a sort and the sample is read whole; `sorted`, the records in random order
(`order by dbms_random.value`, Oracle sorts the whole dataset before the first row), when the count is not known.
`random=false` reads the first records as the database returns them (`first`). `meta.random` is true for `sorted`
and `bernoulli`; `meta.sql` never has the sampling. The first `initial_rows` are fetched at once, then the columns
and the overview are profiled. 409 when all sessions are in use, 404 for an unknown dataset or a filter that does
not parse, 503 while the server starts or stops.

#### `POST /api/analysis-start-file`
`file_id`, `table`, `random` (default **false**), and the optional pushdown body of `analysis-start`. Starts a session
on the records a file of `PDI_CORE_FILE_LOG` loaded into `table`: `select * from <table> where file_id = <file_id>`,
read as the `FILE_ID` index returns them (load order), no sort. `table` must be one of the tables of the file's
datasource (`PDI_CORE_DS_TABLES`), never any other. `meta` has `kind: "file"`, `file_id`, `sourceid`, `sourcename`,
`file_name`, `records_write`, `records_reject`, `table_name` and the exact `total`. The other `analysis-*` routes
work on its `session_id` as usual. Used by *Open in Data analysis*; the viewer's own pane reads `get-file-records`. 400 for a table that is no table of the datasource or can not be read, 403 without
a readable file log, 404 for a file not in the file log.

#### `GET /api/analysis-status`
`session_id`. Answers the same as `analysis-start`, with the current state.

#### `POST /api/analysis-extend`
`session_id`, optional `rows` (default `extend_rows`). Fetches the next rows into the sample, up to `max_rows`; a
Bernoulli sample is read anew for `target + rows` records instead, and replaces the sample. Answers `{state}`. 400
when the sample can not grow (`state.extendable` false: every row loaded, or the cursor lost).

#### `POST /api/analysis-cancel`
`session_id`. Cancels the step in progress; rows fetched so far are kept. Answers `{state}`.

#### `POST /api/analysis-close`
`session_id`. Ends the session and its process. Answers `{"status": 200}`, also for a session already closed.

#### `GET /api/analysis-rows`
`session_id`, `offset` (0), `limit` (200, at most 5000), optional `sort`, `search`, `filters`. Answers `{version,
total, offset, rows}`: `total` rows match, and `rows` are lists of values in the order of `state.columns`.

#### `GET /api/analysis-profile`
`session_id`, `section`: `overview`, `columns`, `relations` or `breakdown`. Answers `{ready, version, key, data}`. A
section not computed yet answers `ready: false` and is computed; the state lists it (`key`, the section's name)
under `sections` once it is ready.
- `columns`: one object per column: `count`, `missing`, `missing_pct`, `distinct`, `top` (the 8 most frequent
  values), `other_count`, `stats` (numbers: `min`, `max`, `median`, `zeros`, `zeros_pct`, `integral`; date-times:
  `min`, `max`, `date_only`; text: `blank`, `blank_pct`), `histogram` `{counts, edges}` (24 bins, numbers and
  date-times whose values do not fit a few bars), `metadata` (a `rapo_` column), `unusable` (`empty`, `constant`,
  `unique`: text 90% unique, or half unique with no value in 1% of the records, or whole numbers all different in 50
  records or more), `visual` (`top`, `histogram` or null: how the profile shows it) and `group` (`category`,
  `number`, `date` or `text`).
- `overview`: `{rows, columns, duplicate_rows, duplicate_pct, missing_columns, unusable}` without the `rapo_`
  columns; `missing_columns` the names 5% or more missing, `unusable` `[{name, reason, value}]`.
- `relations`: `{pairs}`, at most 5 pairs of columns `{a, b, method, value}` from 0.4 on, each pair once by its
  strongest measure: `pearson` and `spearman` over the numeric columns, `cramers` (Cramér's V) over the columns of 2
  to 50 values; the `rapo_` columns are left out but `rapo_result_type`; measured on the first 200,000 rows.
- `breakdown`: `{rows, types, fields, described, values}`: the counts of `rapo_result_type` (`[{value, count,
  pct}]`), the fields `rapo_discrepancy_description` names (`[{field, count, pct}]` out of the `described` records),
  and the `rapo_result_value` counts when there are several (the top 10).

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
binned the same way on both datasets and counted by Oracle, and a bin's normal count is its fetched count less
its discrepancy count (never below 0). The fetched records are the `fetched_a|b` dataset (the control's current
configuration).

It runs in **two stages**. The *quick look* reads about `[ANALYSIS] discrepancy_quick_rows` (100,000) records of
each dataset: a `SAMPLE BLOCK` of the datasource table (only that share of its blocks is read), or, where Oracle
refuses a sample (a join view, a database link), the first records the select returns; the counts are scaled to the
run's logged totals. It chooses the bins and the pairs, and its report is published at once as preliminary
(`meta.stage = 'quick'`). *Refine* then counts the same bins and pairs in one scan of each dataset: whole up to
`[ANALYSIS] discrepancy_exact_rows` (1,000,000) records, else a row sample (`SAMPLE`, random, every block read) of
about that many, else a Bernoulli sample; with `/*+ PARALLEL(n) */` from `[ANALYSIS] discrepancy_parallel` (4, 0
for none). Its report replaces the preliminary one (`meta.stage = 'final'`). ANL has side `a` only; a CMP's discrepancies are one table, side `a`
analysing its `a_` (or side-A output) columns and side `b` the others. A result column is analysed when it holds a
fetched column (same name, or the output column configuration names it); coalesced columns and `RAPO_*` metadata are
not.

Runs as a job in a process of its own (taken from the spare one, already connected), one at a time per server (others queued, `[ANALYSIS]
discrepancy_timeout_minutes` at most). Answers the job, `{process_id, side, result_type, state, progress, error,
queued, started, finished, has_report, stage, report}`, `state` being `queued`, `running`, `done` or `error`,
`progress` `{step, done, total}`. A `running` job holds the preliminary `report` once the quick look is done. A stop,
a refine failure or a timeout after the quick look ends the job `done` with the preliminary report and
`meta.stopped` or `meta.refine_error`. A job of the same run, side and type is reused (its report too) unless `recompute`; the latest 20 finished
jobs are kept in the server's memory until it stops. State changes are pushed as `discrepancy:progress` (the job
without `report`; `has_report` and `stage` tell when to fetch it). 400 for a report, side `b` of an analysis or an unknown result type, 404 for an unknown run, 503
while the server starts or stops.

The **report**:
- `meta`: the run (as `get-run-dataset-sql`), `side`, `dataset` / `fetched_dataset` (the Data analysis datasets),
  `result_type`, `stage` (`quick` or `final`), `sample_method` / `result_sample_method` (`none`, `block`, `row`,
  `first` or `bernoulli`), `sample_rows` (records read by the quick look), `discrepancies`, `normal`,
  `fetched_total` and `fetched_logged` (at run time), `disc_logged`, `sample` (refine's sampled share, or null),
  `drift` (a whole or random count differs from the logged total), `stale`, `clamped` (columns whose bins hold more
  discrepancies than fetched records), `excluded` (`[{column, reason}]`), `datasets` (`[{side, count}]`),
  `stopped` / `refine_error` (see above).
- `type_split`: REC `[{type, count}]` of the side's discrepancies, else null.
- `attributes`: strongest first, one per binning of a column: `{id, column, source, kind, feature, feature_label,
  ordered, score, bins, special, under, bands}`. `feature` is `value`, `decile` (ranges by the fetched
  deciles), `prefix` (first 3/5/6/8 digits or 2/4/6 characters of an identifier-like column), `length`, `hour`,
  `weekday` or `timeline` (20 equal periods). `score` is Theil's U of being a discrepancy given the bins (0..1,
  the share of the uncertainty removed, less a small-sample bias). Each bin is `{code,
  label, disc, normal, disc_share, normal_share, lift, rate, z, flag, filter}`: `lift` = `disc_share /
  normal_share` (null with `only_disc` when no normal record has it), `rate` the share of the bin's records that are
  discrepancies, `z` a two-proportion z, `flag` `over` (at least 10 discrepancies and 1% of them, lift ≥ 2, z ≥ 4),
  `under` or null (a sampled bin with fewer fetched records than discrepancies is `uncertain` and never `over`; z is
  taken over the records read, a block sample's as if 25 times fewer), and `filter` `{result, fetched}`: a condition selecting the bin's records, usable as
  `analysis-start`'s `where` on the discrepancy and the fetched dataset. `bands` merges adjacent `over` bins of an
  ordered feature (`02:00 – 04:59`).
- `combinations`: up to 8 pairs of bins of two attributes stronger together than alone (over-represented, and a
  discrepancy rate 1.5 times the better of the two bins'): `{id, attributes, parts, disc, normal, disc_share,
  normal_share, lift, rate, z, wracc, filter}`, each part `{attribute, what, label, phrase, codes, lift}` (the bin's
  lift alone). The strongest attribute of up to 6 columns takes part, each reduced to at most 5 groups of its bins
  (bands, a common prefix, the bins with the most discrepancies). Ranked by `wracc`, coverage × (rate − base rate).
- `findings`: what the page leads with: the leading bin (or band, or common prefix) of up to 3 drivers (attributes
  of other columns with a score of 0.02 or more), then up to 2 combinations, `[{id, kind (driver, time for a date
  column, combination), attribute, column, what, label, phrase, codes, filter, disc, normal, disc_share,
  normal_share, lift, rate}]`, a combination also with its `parts`.
- `unrelated`: the columns no binning of which tells the discrepancies apart (a best score under 0.005).
- `magnitude`: REC with all types or `Discrepancy` only, else null: `{total, fields, cut}` from
  `RAPO_DISCREPANCY_DESCRIPTION` of the value discrepancies, per field `{field, records, share, distinct, values
  (top 10 {value, count, share}), numeric, min, median, max, sum, histogram}`; `cut` when more than 2,000 different
  descriptions exist (the most frequent are read; `sum` is then null).

#### `POST /api/stop-discrepancy-analysis`
`process_id`, `side`, optional `result_type`. Stops the job: a queued one ends `error`, a refining one ends `done`
with its preliminary report (`meta.stopped`). 404 when there is none.

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

#### `GET /api/view-ds-file`
Reads lines of a loaded file, for the file viewer of the file log. The file is one `download-ds-files` would send
(same rules and `[DATASOURCES] file_download` switch). A gzip (by its magic bytes) or the first file of a ZIP is read
decompressed. Nothing is kept between requests: each one reads from an uncompressed byte offset, the `next_offset` of
the previous answer (a gzip is decompressed up to it, from the nearest checkpoint the server keeps every 8 MB for the
8 gzips read last).

| Parameter | Type | Default | Meaning                                                                          |
|-----------|------|---------|----------------------------------------------------------------------------------|
| `id`      | int  | -       | File ID of `PDI_CORE_FILE_LOG`. Required.                                         |
| `offset`  | int  | `0`     | Uncompressed byte offset of the first line to read (a line start).                |
| `line`    | int  | `1`     | Number of the line at `offset`, only shown.                                      |
| `lines`   | int  | `[DATASOURCES] view_lines` (100) | Lines to read, at most 5,000.                           |

Answers the file's facts, `id`, `name`, `size` (bytes on disk), `compression` (`gzip`, `zip:<member>` or `plain`),
`encoding` (`utf-8`, or `latin-1` when the first 64 KB are no UTF-8), `binary` (a NUL byte in the first 64 KB: no
lines), `asn1` (a binary file whose first bytes read as BER: the viewer opens it as ASN.1) and `header` (line 1), then `lines` `[{no, offset, text, cut}]`, `next_offset`, `next_line` and `eof`. A line is
cut after `[DATASOURCES] view_line_chars` (10,000) characters; `cut` counts the bytes left out.

`400` when the file can not be shown (the reason is named); `403` with `file_download=False`; `404` for a file ID not
in the file log.

#### `GET /api/grep-ds-file`
Finds the lines of a loaded file containing a text or matching a regular expression (Python's `re`), from a cursor
like `view-ds-file`'s. It reads until `[DATASOURCES] view_grep_matches` (500) lines matched, the file ended, or
`view_grep_seconds` (20) passed; the next request goes on from `next_offset`/`next_line`. A line is matched on the part
shown (`view_line_chars`), on its own (a match across lines is no match).

| Parameter | Type | Default | Meaning                                            |
|-----------|------|---------|-----------------------------------------------------|
| `id`      | int  | -       | File ID. Required.                                  |
| `pattern` | str  | -       | The text or expression. Required.                   |
| `regex`   | bool | `false` | `pattern` is a regular expression.                  |
| `case`    | bool | `false` | Match case.                                         |
| `offset`  | int  | `0`     | Uncompressed byte offset to search from.            |
| `line`    | int  | `1`     | Number of the line at `offset`.                     |

Answers the file's facts (as `view-ds-file`), `matches` `[{no, offset, text, cut, spans}]` (`spans`: `[start, end]` of
each match in `text`), `next_offset`, `next_line`, `eof`, `scanned_bytes`, `scanned_lines` and `stopped` (`matches`,
`time` or `null`). `400` for an invalid expression; otherwise the codes of `view-ds-file`.

#### ASN.1 view
A loaded file read as ASN.1 BER (DER and CER too), for the viewer's ASN.1 view. The file is one `download-ds-files`
would send, decompressed as by `view-ds-file`. From `start_offset` it is a series of records (the *root*), each a TLV
after `record_header` bytes (e.g. 4 in Huawei SBC files); `filler` bytes between them are skipped (`00ff`, the default:
00 and FF; `ff`: FF only, for headers that may start with 00; `none`), bytes that are no TLV become an `undecodable` node and the reading goes on at the next
TLV. Nothing is decoded ahead: a request reads the headers of one page of one node's children; the server notes every
256th child's offset of the files read last, so a later page starts near it. With a `grammar` (an uploaded one, see
`get-asn1-grammars`) and a `top` type (`Module.Type`, guessed from the first TLV when not given) the nodes get their
field names and types; a tag the grammar does not expect leaves the node (and its children) unnamed (`unknown`).

Common parameters: `id` (file ID, required), `start_offset` (`0`: bytes to skip, e.g. a file header), `record_header`
(`0`, at most 1024), `filler`, `grammar` and `top`. A **node** is `{offset, end, record_offset, ordinal, undecodable, cls, number, tag, constructed, indefinite, tag_len,
header_len, length, has_children}` (`length` of the content; `tag` as `[3]`, `[APPLICATION 1]` or `SEQUENCE`;
`record_offset` where a root record starts, its record header, else `offset`), with a
grammar `name`, `alternatives` (the CHOICE alternatives it is), `type`, `state` (sent back to read its children) and
`unknown`, and for a primitive one `preview` (its likeliest reading) or `preview_hex`. Errors as `view-ds-file`.

* `GET /api/get-ds-file-asn1`: a page of nodes, of the root or (`parent`: its offset, `state`: its state) of a
  constructed node. `ordinal` (`0`) the first child, `count` (`[DATASOURCES] asn1_page_nodes`, 500) how many, at most
  5,000. Answers the file's facts (`id`, `name`, `size`, `compression`, `data_size` (uncompressed, null when unknown),
  `start_offset`, `grammar`, `top`), `nodes` and `eof`.
* `GET /api/get-ds-file-asn1-node`: one node by `offset` (and `state`) with `readings` `[{label, value}]` (what its
  value reads as: by its type with a grammar, else every reading that fits, e.g. integer, text, TBCD digits, address,
  3GPP time stamp, IP address), `hex` (its first 4 KB), `type_chain` (the types it is defined as) and, with a tag map,
  `map_path`.
* `GET /api/locate-ds-file-asn1`: the nodes holding the byte at `offset`, `levels` `[{parent, node}]` from the root
  (`parent` null) down to the deepest.
* `GET /api/render-ds-file-asn1`: a node (`offset`, `state`) and its subtree as `format` `xml` or `text` (one line per
  node: offset, header and content length, then the indented name, tag, type and value), at most `[DATASOURCES]
  asn1_render_nodes` (5,000) nodes and 2 MB: `{text, nodes, truncated}`.
* `GET /api/search-ds-file-asn1`: finds nodes from `offset` (`0`) until `[DATASOURCES] view_grep_matches` hits or
  `view_grep_seconds` passed. `field` is a name or tag, or a path of them ending at the node (`servedIMSI`, `[3]`,
  `listOfTrafficVolumes/dataVolumeGPRSUplink`); `value` matches (`match` `contains` or `equals`, any case) a primitive
  node's readings or hex; `hex` (`80 04 0A F9`) finds bytes instead and answers the deepest node holding each. Answers
  `hits` `[{offset, path, preview}]` (+ `match`, the byte offset of a hex hit), `next_offset`, `eof`, `scanned_bytes`
  and `stopped`. 400 without a field, value or valid hex.

#### `GET /api/get-ds-file-bytes`
`id`, `offset` (`0`), `size` (65536, at most 64 KB): uncompressed bytes of a loaded file as `application/octet-stream`
(fewer at its end), for the viewer's hex pane. `X-Rapo-Data-Size` is the uncompressed size when known. Errors as
`view-ds-file`.

#### ASN.1 grammars
Uploaded grammars that name the fields of a file, kept in `rapo_viewer_config`, of two kinds:
* `asn1`: one or more ASN.1 modules. Only parsed (asn1tools), never compiled, so a grammar needs not be complete: a type
  it lacks leaves its fields unnamed. A file of type assignments only, without a module header, is read as a module
  named after the file with IMPLICIT TAGS (`wrapped`).
* `tagmap`: the field definitions of a Pentaho ASN.1 decoder, `props.put("82.4.1","nodeAddress,ia5,4");` lines or
  `82.4.1=nodeAddress,ia5`. A node's path is the tag numbers of its TLVs that are not UNIVERSAL (as the decoder's
  `ObjectParser` builds it); `_ROW` marks the record. Values are decoded as the decoder does by type (`bcdstring`,
  `ebcdstring`, `tbcdstring`, `rbcdstring`, `integer`, `octstring`, `ia5`; another type as hex). No top type.

The kind is detected from the files (all of one kind). Every write is logged to the server log with what it replaces.

* `GET /api/get-asn1-grammars`: `{grammars: [{name, kind, files: [{name, size}], modules, entries, wrapped,
  created_date, updated_date, used_by}]}` (`entries`: of a tag map) (`used_by`: the datasources whose files open with it).
* `GET /api/get-asn1-grammar-types`: `name`; `{name, kind, tops, preferred}` (a tag map has none): the types to decode a file with, as
  `Module.Type`, the first `preferred` of them being the structured types no other type refers to.
* `GET /api/get-asn1-grammar`: `name`; the grammar with its files' texts, `{name, kind, files: [{name, text}],
  modules, entries, wrapped, updated_date, used_by}`, for the editor. 404 for an unknown name.
* `POST /api/save-asn1-grammar`: JSON body `{name, files: [{name, text}], replace, old_name}`. Parsed first: 400 naming
  the file, line and column of an error; 409 for an existing name without `replace`. With `old_name` it edits that
  grammar (404 when gone): a different `name` renames it (409 when taken), and the datasources opening their files
  with it follow the new name, in one transaction; 413 past `[DATASOURCES]
  asn1_grammar_max_kb` (2048). Answers `{status, name, kind, modules, entries, tops, preferred, wrapped}`.
* `POST /api/delete-asn1-grammar`: `name`. 409 while a datasource opens its files with it, 404 for an unknown name.

All answer 503 while `rapo_viewer_config` does not exist (run `migrations/v0.8.6/upgrade.sql`).

#### Viewer settings
* `GET /api/get-viewer-settings`: `sourceid`; `{sourceid, settings}`, `settings` `{layout, asn1: {grammar, top,
  start_offset, record_header, filler}}` (keys left out when not set): what the viewer opens the datasource's files with.
* `POST /api/save-viewer-settings`: JSON body `{sourceid, layout?, asn1?}`; each key given replaces its value (`null`
  removes it), the others are kept. `layout` is the *Delimiter* field's text; `asn1.grammar` must exist (404) and
  `asn1.top` be one of its types (400). Answers `{status, settings}`.

#### `GET /api/get-file-tables`
`file_id`. The tables of the file's datasource (`PDI_CORE_DS_TABLES`, in their order), each with the rows of the
file (`count(*) where file_id = :id`, read by the index): `{file, tables: [{table_name, count, reason}]}`. `file` is
the file log row with `recordsread`, `recordswrite` and `recordsreject`. `count` is null and `reason` says why when a
table does not exist, has no `FILE_ID` column or can not be read. 404 for a file not in the file log.

#### `GET /api/get-file-records`
A page of the records a file loaded into one table of its datasource, read straight from the database (no analysis
session), for the viewer's records pane. The rows are in `ROWID` order, so the pages of one search follow each other.

| Parameter | Type | Default | Meaning                                                                              |
|-----------|------|---------|--------------------------------------------------------------------------------------|
| `file_id` | int  | -       | File ID of `PDI_CORE_FILE_LOG`. Required.                                             |
| `table`   | str  | -       | A table of the file's datasource (`PDI_CORE_DS_TABLES`). Required.                    |
| `search`  | str  | -       | Case-insensitive *contains* over every column as text (dates `YYYY-MM-DD HH24:MI:SS`). |
| `offset`  | int  | `0`     | Rows to skip.                                                                        |
| `limit`   | int  | `200`   | Rows to read, at most 500.                                                           |
| `count`   | bool | `false` | Also count the rows of the search (`total`).                                         |

Answers `{columns: [{name, kind}], rows, offset, total}`: `rows` are lists in column order, `total` is null without
`count`. Text and LOBs are cut to 4,000 characters. 400 for a table that is no table of the datasource or can not be
read, 404 for a file not in the file log.

#### `POST /api/check-ds-upload`
JSON body `{id, names}`: checks files before they are uploaded to datasource `id`. Answers `sourcename`, `directory`
(the first path of the saved `INPUT_DIRECTORY`), `exists`, `writable` (of the directory), `active` (`ISACTIVE` other
than 0), `max_bytes` (`[DATASOURCES] max_upload_mb`) and `files` `[{name, error, exists, matches_mask}]`: `error` why
the name can not be used (a path, a leading dot, control characters, over 255 bytes), `exists` a file of the name
already in the directory, `matches_mask` whether `FILES_MASK` matches it (whole name). `403` with
`[DATASOURCES] file_upload=False` (the default); `404` for an unknown datasource.

#### `PUT /api/upload-ds-file`
Uploads one file into the first input directory of a saved datasource. The body is the file itself
(`application/octet-stream`), streamed to disk. It is written under a temporary name `FILES_MASK` does not match
(`.rapo-upload-<hex>.part`, or in a `.rapo-upload` folder when the mask matches that and subdirectories are not
scanned) and renamed when complete, so PDI Core never picks up a partial file; a file of the name already in the
directory is never overwritten. A canceled or failed upload removes the temporary file. Each upload is written to
the server log. A disabled datasource (`ISACTIVE=0`) takes files too.

| Parameter | Type | Default | Meaning                                      |
|-----------|------|---------|-----------------------------------------------|
| `id`      | int  | -       | Datasource ID. Required.                      |
| `name`    | str  | -       | File name (no path). Required.                |

Answers `{status, path, bytes, matches_mask}`. `400` for a bad name or a missing directory; `403` with
`file_upload=False`; `404` for an unknown datasource; `409` when the file is already in the directory; `413` past
`[DATASOURCES] max_upload_mb` (2048 by default).

```bash
curl -T TAF_20261008.csv.gz -H "Authorization: Bearer $RAPO_TOKEN" \
  "http://rapo-host:7005/api/upload-ds-file?id=152&name=TAF_20261008.csv.gz"
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
  `{event_id, control_name, control_type, job_control_name, trigger_type, process_id, pid, queued, started,
  date_from, date_to}` (`date_from`/`date_to`: the data window of the run performed now).
  `process_id`, `control_name` and `control_type` are those of the run the job process performs now, which is an
  upstream run of a chain, an iteration or a cascade child while those run; `job_control_name` is the control the
  job was submitted for. A `queued` job also has `held`: `instance_limit` while its control already runs as many
  jobs as its `instance_limit` on this server (it is passed over until one ends), else `null`.

#### `POST /api/scheduler-stop` and `POST /api/scheduler-start`
Stop or resume scheduling. The switch is stored in the database, so it survives a restart and applies to every
server against that database. A start resumes from now: fires that fell into the stop are not run. `409` when the
scheduler is disabled for this server in `rapo.ini`.

#### `GET /api/scheduler-upcoming`
The runs the scheduler causes from now on, ordered by time: own fires of the enabled schedules, the cascades they
trigger and the controls each run pulls first (chain-rules), as `get-next-fires` counts them.

| Parameter      | Type | Default | Meaning                                                              |
|----------------|------|---------|-----------------------------------------------------------------------|
| `hours`        | int  | 24      | Whole hours from the start of the current one, 1 .. 744 (24 = now until the same hour tomorrow, exclusive). |
| `control_name` | str  | -       | One control instead of all of them.                                   |

Each fire is `{scheduled_time, control_id, control_name, control_type, control_group, trigger_type, via, date_from,
date_to}`: `trigger_type` is `SCHEDULE`, `CASCADE` (`via` the control it follows) or `UPSTREAM` (`via` the control
that pulls it); cascades and upstreams carry the time of the fire they follow. It is computed from the database, so
any server answers it, even one whose scheduler is stopped.

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
| `hours`        | int  | -       | Events of the last whole hours, the current included, 1 .. 744 (24 = from the same hour yesterday). |
| `limit`        | int  | 500     | Maximum number of rows, 1 .. 5000.             |

Each event carries `event_id`, `control_id`, `control_name`, `control_type`, `trigger_type`, `event_type`,
`scheduled_time`, `event_time`, `start_time`, `process_id`, `message`, `runner`, and the run's `status`,
`date_from`, `date_to`, `start_date` and `end_date` joined from `rapo_log`.

#### `GET /api/get-missed-fires`
`MISSED` events recorded before the last `hours` (default 24, as `scheduler-events`) that were never caught up (no
`CATCHUP` event of the same control and scheduled time), latest first, at most `limit` (500, 1 .. 5000). Rows as
`scheduler-events`.

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
`view_edit` (`[VIEWS] edit`) with `view_preview_max_rows`,
and for the PDI Core datasources `datasources_available`, `datasources_writable`, `datasources_deletable`,
`datasources_log` (the file log is readable), `datasources_file_actions` (files can be recycled, reloaded, deleted),
`datasources_file_download` (files can be downloaded: the file log is readable and `[DATASOURCES] file_download` on),
`datasources_state`, `datasources_state_write` and `datasources_state_delete` (the lane locks of `PDI_CORE_STATE`).

#### `GET /api/get-config-catalogue`
Every option of `rapo.ini` rapo knows (`rapo/options.py`), in sections, for the Configuration tab:
`{general: {version, instance_name, config_path, log_directory}, digest, sections: [{name, description, options}],
unknown}`. Each option has `name`, `written_as` (the name in the file, a deprecated one included), `type` (`bool`,
`int`, `float`, `text`, `choice`, `path`), `default`, `description`, `choices`, `minimum`, `restart` (applies after a
restart only), `secret`, `editable` (no secret, no restart), `set` (written in the file), `value` (as written) and
`loaded` (the value this server uses); a secret's `value`, `loaded` and `default` are `null`. `unknown` lists the
options of the file rapo does not read (`{section, name, value}`). `digest` is the file's SHA-256, for
`set-config-option`.

#### `POST /api/set-config-option`
Body `{section, option, value, reset, digest}`. Writes one option to `rapo.ini` and applies it at once, as
`reload-config` does; `reset: true` removes it, so its default applies (a section left empty goes too). Only that
line changes: comments, order and mode stay; a new option goes to the end of its section, a new section to the end
of the file. The file is first copied to `rapo.ini.bak-<timestamp>` (mode 600, the newest 10 kept). Answers
`{status, digest, applied, restart_required}`. `400` for an unknown option, a secret, an option that applies only
after a restart, or a value not fitting its type, choices or minimum; `409` when the file's checksum is not `digest`
(changed on disk meanwhile). Each change is logged with the old and new value and the backup.

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

#### `GET /api/get-instance-health`
The OS and DB metrics this server sampled in the last `hours` (1 by default), kept in its memory only (a restart
starts them anew): `{enabled, server_time, level, levels, labels, intervals: {os, db}, history_minutes, hours, spans,
step: {os, db}, history_since, thresholds, os: [...], db: [...], footprint, access}`.
- `hours=1` answers the samples (the last `[HEALTH] history_minutes`, default 60); longer spans (up to
  `history_hours`, default 24) the one-minute aggregates, merged into at most 480 points per group. `step` is the
  seconds per point, `spans` the spans this server keeps (of 1, 3, 6, 12, 24), `history_since` its first point. An
  aggregate averages numbers, takes the highest of `locks`, `locks_wait`, `tcp_close_wait`, `processes_rapo`,
  `net_errors` and `net_drops`, and the last value of uptimes, sizes and lists; the last point of a longer span is
  the minute in progress.
- `labels`: `{server, database}`, the host name and `user@host:port/service` (or the `path`) of `[DATABASE]`.
- `os` points (every `os_interval` s) are this server's host and its process tree (the server, its runs, analysis
  and scan workers): `cpu`, `cpu_rapo` (% of all cores), `cpus`, `load`, `memory`, `memory_rapo` (%),
  `memory_rapo_gb`, `memory_total_gb`, `swap`, `processes`, `processes_rapo`, `disk` (used % of the fullest of
  `disks`), `disks` (one per file system holding the log directory, the folder of `rapo.ini` or a datasource's input
  or archive directory, resolved once after the server starts: symlinks followed, the file system found by device
  number, several mount points of one file system as the shortest; a directory missing on this host or not resolved
  in 2 s is left out. `{mount, device, roles: {logs, home, input, archive}` (directories held), `links` (`[[link,
  target]]`, the symlinks leading onto it), `used_percent`, `used_gb`, `free_gb`, `total_gb}`, or `error` when it did
  not answer in 2 s; empty in the first sample), `fds_rapo`, `net_rx_mbs`,
  `net_tx_mbs` (all interfaces but `lo`, `null` at the first sample), `net_errors`, `net_drops` (since the sample
  before), `tcp_established`, `tcp_close_wait`, `tcp_time_wait` (the host's TCP connections), `rapo_db_sockets` (the
  process tree's connections to `[DATABASE] port`), `uptime` and `rapo_uptime` (seconds since the host booted and
  the server started).
- `db` points (every `db_interval` s) are the database rapo is connected to (the PDB in a container database):
  `cpu_count`, `pga_limit_gb`, `db_cpu` (% of `cpu_count`, last minute), `db_cpu_cores`, `aas` (average active
  sessions), `sessions`, `sessions_active`, `sessions_rapo`, `sessions_rapo_active` (sessions with module `rapo`),
  `locks` (sessions blocked by another), `locks_wait` (longest wait, s), `sga_gb`, `pga_gb`, `pga_percent`,
  `storage` (used % of the fullest of `tablespaces`, the user's default and temporary ones, autoextend counted, each
  `{name, used_percent, used_gb, size_gb, default}`), `storage_gb` (used GB of the default tablespace),
  `rapo_gb` and `rapo_segments` (`RAPO_RES*`/`RAPO_TEMP_*` segments, read every `footprint_interval` s),
  `io_read_mbs`, `io_write_mbs` (physical reads and writes of all files), `redo_mbs`, `commits` (per second, last
  minute), `db_uptime` (seconds since the instance started, by the database's clock), `errors`.
  Each point has `t`, a naive ISO time of the server.
- `levels` is `{rule: null|"warn"|"crit"}` for `cpu` (average of the last 3 points), `memory`, `disk`, `db_cpu`,
  `db_memory` (`pga_percent`), `storage`, `locks`, `locks_wait` and `close_wait` (`tcp_close_wait`); `level` the worst of them; `thresholds`
  `{rule: [warn, crit]}`, `null` for none.
- `access` is `{source: {grant, error, probed}}` per DB view read: `sysmetric` (`V_$CON_SYSMETRIC`), `parameter`
  (`V_$PARAMETER`), `session` (`V_$SESSION`), `sgainfo`, `pgastat`, `tablespace` (`DBA_TABLESPACE_USAGE_METRICS`),
  `instance` (`V_$INSTANCE`).
  A source with an `error` is not read; it is probed again every 10 minutes and on `reload-config`.

`history=false` answers only `enabled`, `server_time`, `level` and `levels` (the UI's header button).

#### `GET /api/get-instance-sessions`
`kind=sessions` (default): the user sessions of the database, blocked first, then active, by wait; `kind=locks`: the
blocked sessions and those blocking them. `{rows, truncated}`, at most 500 rows of `sid`, `serial`, `username`,
`module`, `action`, `status`, `machine`, `program`, `event`, `sql_id`, `blocking_session`, `logon_time`,
`wait_seconds` (the current wait, or the time since the last call of an idle session), `is_rapo` (module `rapo`) and
`control_id` (the control a run performs, its name being the action). `400` without access to `V$SESSION`.

Rapo's connections carry module `rapo`, and a run process's connections the control it performs as action, so they
can be told apart in any DBA tool.

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
| `health:level`     | `{level}`: the worst level of the instance health changed (`null`, `warn`, `crit`) |
| `health:sample`    | `{group, point, minute, levels, level}`: a new `os` or `db` sample of `get-instance-health`, and `minute` the aggregate of the minute it closed (else `null`), sent only to clients that joined the room with `health:join` (and left with `health:leave`) |
| `datasources:changed` | `{kind}`: `config` when `pdi_core_ds_config` or `pdi_core_ds_tables` changed, by anyone; `status` when a count of the waiting files differs from the one before; `state` when a lane lock of `pdi_core_state` changed; `files` when today's file log got files or finished loads |

`resync` means the changed rows could not be named - a deletion, or more than 500 changes at once - and everything
should be refetched. The events say *what*
changed, never the new values - fetch them with the routes above (`health:sample` is the exception: it carries the
point). This is how the UI stays current without
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
