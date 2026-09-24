# Rapo v0.8.3 Change Log

## Annotation
This release makes the Output limit work for analysis, report and comparison controls, gives every SQL box of
the editors curated examples and a Check button, lets an email attach a sheet from a query of your own, and keeps
the result tables in line with the control's configuration. There is no change to Rapo's own schema.
The upgrade steps are in the [migration instructions](README.md).

1. **Output limit for ANL, REP and CMP.** The *Output limit* in the editor's Main tab was stored but ignored for
   these types, so every discrepancy was written to `rapo_rest_<name>`. A run now writes at most that many records.
   Empty or 0 means no limit. The run's error count still reports every discrepancy found, and the run log says
   when the output was cut (`Output limited to N of M records`). Which records are kept is not defined, as with
   the reconciliation limits. Controls that already have a limit set will start applying it with this release.

2. **Examples by context.** The *Example* menu of every SQL box offers up to five examples written for that box:
   datasource filters, mismatch criteria, case mappings, Preparation/Prerequisite/Completion SQL (with the
   `{control_name}`, `{process_id}` and date variables and dynamic table names), email sheet filters, and KPI and
   alarm statements. KPI examples follow the KPI type (monetary, points, discrepancies, trend, records, error
   level) and the control type (`RAPO_RESA_`/`RAPO_RESB_` for REC, `RAPO_REST_` otherwise); the other families are
   under *More*. They use the real `racs_kpi_pkg` functions (`get_rapo_discrepancy`, `get_rapo_control_trend`,
   `get_rapo_repeating_discrepancies`, `get_kpi_multiplier`). Picking an example over your own text asks first.
   The email filter no longer shows the datasource filter examples, and the default KPI example that called a
   function that does not exist is gone.
3. **Check on every SQL box.** A *Check* button parses the statement with Oracle against the unsaved editor
   (datasource, name, case IDs) without running it, and reports errors, unknown `{variables}`, case IDs missing
   from the Case config, and colons that would be read as bind variables. DDL such as `truncate` is refused rather
   than parsed, because Oracle's parser would execute it. An alarm check also shows the thresholds the dashboard
   will draw from the statement, and warns when `get_kpi_thresholds_json` would misread it.
4. **Email: Free SQL sheet, Include per sheet and file name.** The Email tab has a *Free SQL* card: a query of your
   own becomes the last sheet of the attachment, with its own name, *Example* menu and *Check*. The result sheet of
   analysis and report controls now has an *Include* switch, like the A and B sheets of a reconciliation, so a
   file can hold only the Free SQL sheet. The attachment's *File name* can be set, with variables. Rows of the Free
   SQL sheet count toward *Done, with results* only when it is the only sheet. The Free SQL and the sheet filters
   list every variable they accept under the box (click to insert) and complete them after `{`, including the run
   facts such as `{status}` and `{fetched_number}`. Details in the [migration instructions](README.md#email-free-sql-sheet-and-file-name).
5. **Variables in datasource filters and mismatch criteria.** The datasource filters of every control type (both
   sides of a reconciliation, for the DB and the PL-SQL engine) and the mismatch criteria of analysis controls
   accept `{control_name}`, `{process_id}`, `{control_date}`, `{control_date_from}` and `{control_date_to}`,
   e.g. `partition_day = '{control_date:%Y%m%d}'`, listed under the box as chips and completed after `{`. Only
   those names are replaced: any other brace, such as the `{3}` of a regular expression, an unknown `{name}` or a
   doubled `{{control_date}}` (how a literal one is written), stays exactly as written, so existing filters are
   unchanged. *Check* reports an unknown variable as a warning.
6. **Braces in logged SQL.** A run whose logged SQL held a brace, e.g. a filter with `regexp_like(x, '^\d{3}$')`,
   failed with `IndexError: Replacement index 3 out of range`, because the log line was formatted as a template;
   and `{thread}` or `{{x}}` in it were rewritten in the log. Log lines are now written exactly as they are.
7. **Result table schema follows the configuration.** The result tables (`RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_`)
   used to be created by the first run and never changed, so a new datasource column, a changed output column or
   a table altered by hand made later runs fail or lose columns, and the only fix was dropping the history. Now:
   - The editor compares the tables with the configuration in the background, including unsaved changes, and
     shows *Schema changes* or *Schema needs recreate* in the bottom bar next to *Unsaved changes*. Clicking it
     lists every table with the columns that differ (added, widened, nullable, no longer output, incompatible),
     the current and expected types, and how many rows a recreate would delete: the estimate of the optimizer
     statistics, or an exact count on *Get exact count*, since counting scans the whole table. Only differences
     that affect runs are reported: a result column wider than its datasource column (e.g. after the datasource
     column was narrowed) still holds every value, so it is not shown and not changed.
   - *Update schema* adds the missing columns, widens narrow ones and makes NOT NULL columns nullable, keeping
     all results. *Recreate schema* drops the tables and creates them at once (it used to only drop them). Both
     save unsaved changes first. A changed datasource or an incompatible type change (e.g. text to number)
     highlights *Recreate schema*. Both buttons moved from the Main tab to the bottom bar; *Recreate schema* shows
     the tables and their rows first. The *Recreate schema*
     of the Controls list creates the tables at once too.
   - A run makes the same safe changes itself before it saves, so a column added to a datasource no longer breaks
     it. An incompatible column fails the run with `Recreate schema needed for <table>: <column> <type> -> <type>`.
   - Renaming a control renames its result tables and their index, so the history stays with it.
   - Analysis, report and comparison controls now save their results by column name, as reconciliations already
     did, instead of by position. A comparison without output columns names its result columns `A_<column>` and
     `B_<column>` in the working tables too; before, it failed when both datasources had a column of the same
     name.
   - The Controls list shows a *Schema drift* chip on each control whose result tables need an update (amber) or a
     recreate (red), with the tables and the number of columns in its tooltip, and *Schema drift* in the
     attribute filter. It is a light check of the whole catalogue from the Oracle dictionary, refreshed as
     controls are saved and run. A control that cannot be checked (e.g. invalid output columns) gets a red chip
     with the reason, a result table without `RAPO_PROCESS_ID` (e.g. a copy made by hand) is listed without its
     oldest run, and if the check fails as a whole the header says *Schema check failed*, with the reason.
     Comparison output columns that combine A and B, datasource names with variables, and remote datasources are
     checked only in the editor.

   - A reconciliation writes the A and B tables only for the sides whose output is ticked under *Discrepancies*,
     so only those are checked, updated and (re)created. A result table no run writes any more is shown as
     *Orphaned*: the table of a side whose output was unticked, or of the control's former type. The editor
     marks it in the bottom bar and offers *Drop table* per orphan, with its rows; neither *Update schema* nor
     *Recreate schema* ever drops one. The Controls list shows them in the *Schema drift* chip, and a header chip
     counts **every** orphaned table: those of a control (with a link to it and the reason) and those of no
     control (deleted, or renamed outside the application), with their rows, to review and drop.
   - *Recreate schema* recreates only the tables that drifted, e.g. side B of a reconciliation whose B datasource
     changed, keeping side A and its results; when none drifted, it recreates all the control writes. Each table
     in the schema details also has its own *Recreate table*. The *Recreate schema* of the Controls list still
     recreates all of them.

   Controls that drop their tables on every run (*Keep past results: No, drop on each run*) are not checked for
   drift; their orphaned tables are still shown.

8. **Controls without KPIs and KPI chips.**
   - The Controls list shows a red *No KPI* chip on each control with no KPI configured. The Control attributes
     filter gains *No KPI* and *Post-run hook*, the counterpart of *No Post-run hook*. KPIs are calculated only
     when the post-run hook is on. On an instance without the KPI tables, neither the chip nor the filter
     appears.
   - KPI codes show as chips with a calculator icon, colored by the KPI type's unit: the same unit always has the
     same color, and a type without a unit is grey. They appear in the KPI types list, the KPI type editor's
     title, and the control editor's KPIs tab (the rows, the *Add KPI* menu and the statement tabs).
   - The type chips in the Results table are the same size as the status chips.
9. **What Apply will change.** In the control editor, clicking *Unsaved changes* in the footer lists every value
   that Apply would write, compared with the saved control, each marked added, removed or changed. Values inside the JSON configurations are shown by
   their path (e.g. `rule_config.email.to`, `schedule_config.hour`), SQL and other multi-line texts as a line
   diff, and KPIs as added, removed or changed statements. *Apply* in the list saves them. A new or cloned control,
   which has nothing saved to compare with, has no list. After picking a past version, the list shows only its
   configuration: the version's audit columns and stamps (`updated_by`, `created_date`, ...) are neither listed nor
   saved back, and a version equal to the saved control makes no unsaved change.
10. **rapo.ini reload.** *Instance details* shows the options of `rapo.ini` changed on disk since the server read
    it: the old and the new value, added options in green and removed ones struck through (secrets only as
    changed, never their values). *Reload* applies them without a restart. `[DATABASE]`, `[API]`,
    `[LOGGING] directory` and `[SCHEDULER] enabled` are read only at startup, so they stay marked *restart
    required* until the next restart. Runs already read `rapo.ini` afresh, since each runs in its own process.
    The dialog is wider, and the browser tab names the instance (`RAPO - AUT Dev`).
11. **Manage versions.** The tag icon of the editor's *Version* box opens the control's past versions (who changed
    them and when). Tick one to compare it with the saved control, or two to compare them, shown like *Unsaved
    changes*; a version loaded in the editor starts ticked, and the header checkbox selects them all. *Load* puts a
    version into the editor, as the Version box does. Versions can be deleted one by one, as a selection, all older
    than a number of days while keeping the newest few (30 days and 5 by default), or as *duplicates*: a version
    equal to the one just before it, so that only the oldest of each run of equal versions stays and a return to an
    earlier configuration is kept. The versions a removal would delete are marked in red (for the age boxes as soon
    as they are changed), and every removal is confirmed with its count. Canceling it leaves those versions ticked,
    to be looked at or deleted as a selection. Only that control's versions are touched.
12. **Server errors are logged.** An unexpected error in a web API call used to leave no trace: the server answered
    500 and its traceback was discarded with the web server's own output. The traceback is now written to the
    server log (`rapo-server_YYYYMMDD.log`), and the answer carries the error type and message.
13. **Nested CASE in the Case definition.** Every number after `THEN` or `ELSE` was taken for a case ID, so a
    CASE nested in a condition, e.g. `when days < case when x is null then 5 else 10 end then 1`, failed the run
    with `KeyError: 5`. Only the results of the definition itself are case IDs now: the outer CASE's branches and
    those of a CASE that is a whole branch of it. A CASE inside a `WHEN` condition or a function call keeps its
    values, and numbers in comments and quoted text are ignored. A case ID missing from the Case config fails the
    run with a message naming it, and *Check* counts case IDs the same way.
    A case added in the editor's Case config now starts with the value `Case <ID>` (e.g. `Case 4`) instead of an
    empty one.
14. **`rapoctl.sh`.** The control script `rapo-ctl.sh` is renamed `rapoctl.sh`, so the shell completes it after
    `./rapo` without stopping at `rapo-`. Its log is `rapoctl.log`. A crontab `@reboot` entry needs the new name
    (see the [migration instructions](README.md)).
15. **Oracle driver `python-oracledb`.** Rapo uses `oracledb`, the successor of `cx_Oracle`, instead of
    `cx_Oracle`. `cx_Oracle` has no ready-made package for Python 3.11 or newer, so installing it compiled it and
    needed `gcc` and the Python development headers (`python3.12-devel`); `oracledb` installs without either. It runs in
    the same (thick) mode as before, so the Oracle Instant Client is still needed, found as before through `[DATABASE]
    client_path` or the library path. Results are unchanged.
16. **`install.sh`.** One command installs Rapo, or updates it after checking out a new version: it creates the
    virtual environment with a Python 3.10+ of your choice (offered from the ones installed, or `--python
    python3.12`), installs the requirements and Rapo, creates `rapo.ini` from the example when there is none, and
    checks that the Oracle Instant Client can be loaded, warning when a start from cron would not find it. An
    existing environment is updated in place; `--force` recreates it, and is refused while Rapo runs from it. See
    the README's Installation.
17. **NOLOGGING for every temporary table.** A run created only some of its `RAPO_TEMP_` tables with `NOLOGGING`
    (four reconciliation stages and the PL engine's tables). Now every one of them is: the fetched sources, the
    analysis and comparison working tables and all reconciliation stages. This cuts redo only on a database that is
    not in `FORCE LOGGING` mode (e.g. with Data Guard, Oracle logs them anyway). The result tables (`RAPO_REST_`/
    `RAPO_RESA_`/`RAPO_RESB_`) keep `LOGGING`, as they must be recoverable. Results are unchanged.
