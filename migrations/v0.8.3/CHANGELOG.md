# Rapo v0.8.3 Change Log

## Annotation
This release makes the Output limit work for analysis, report and comparison controls. There is no schema change.
The upgrade steps are in the [migration instructions](README.md).

1. **Output limit for ANL, REP and CMP.** The *Output limit* in the editor's Main tab was stored but ignored for
   these types, so every discrepancy was written to `rapo_rest_<name>`. A run now writes at most that many records.
   Empty or 0 means no limit. The run's error count still reports every discrepancy found, and the run log says
   when the output was cut (`Output limited to N of M records`). Which records are kept is not defined, as with
   the reconciliation limits. Controls that already have a limit set will start applying it with this release.
