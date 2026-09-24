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
     controls are saved and run. Comparison output columns that combine A and B, datasource names with
     variables, and remote datasources are checked only in the editor.

   - A reconciliation writes the A and B tables only for the sides whose output is ticked under *Discrepancies*,
     so only those are checked, updated and (re)created. A result table no run writes any more is shown as
     *Orphaned*: the table of a side whose output was unticked, or of the control's former type. The editor
     marks it in the bottom bar and offers *Drop table* per orphan, with its rows; *Update schema* never drops
     anything, and *Recreate schema* drops orphans too. The Controls list shows them in the *Schema drift* chip,
     and a header chip lists the result tables of **no** control (deleted, or renamed outside the application)
     with their rows, to review and drop.

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
