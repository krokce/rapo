# Rapo v0.8.3 Change Log

## Annotation
This release makes the Output limit work for analysis, report and comparison controls, and gives every SQL box of
the editors curated examples and a Check button. There is no schema change.
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
