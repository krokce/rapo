# Rapo v0.8.3 Migration Instructions

Upgrades Rapo from v0.8.2 to v0.8.3. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change**.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.3
    .venv/bin/pip install --no-build-isolation -e .
    ```
1. Before starting, check the controls that have an output limit, since it now applies to their results.
    ```sql
    select control_name, control_type, output_limit from rapo_config
     where output_limit is not null and control_type != 'REC';
    ```
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```

## Result table schema

Nothing to do on upgrade. The first run of each control after it compares its result tables with its
configuration and adds or widens columns that drifted (the run log shows each `ALTER TABLE`). A table with an
incompatible column, e.g. a datasource column changed from text to number, fails the run until its schema is
recreated from the editor or the Controls list. To see a control's state without running it, open it in the
editor: the bottom bar shows *Schema changes* or *Schema needs recreate* when its tables differ. To see all
controls at once, filter the Controls list by *Schema drift* (Control attributes): amber chips can be fixed with
*Update schema*, red ones need *Recreate schema* or a configuration fix.

## Email: Free SQL sheet and file name

Existing email configurations keep working unchanged. Three keys are new in the `email` object of `rule_config`:

```json
{"email": {
  "attachment_name": "Losses_{control_date_from:%Y%m%d}",
  "sheets": {
    "main": {"enabled": true, "name": "Discrepancies"},
    "sql": {"enabled": true, "name": "Summary",
            "query": "select rapo_result_type as \"Result type\", count(*) as \"Records\" from rapo_rest_my_control where rapo_process_id = {process_id} group by rapo_result_type"}
  }
}}
```

- `attachment_name`: the file name, with `{variables}`. `.xlsx` is added when missing, and `\ / : * ? " < > |`
  become `_`. Empty or `null` keeps `<NAME>_<from>[_<to>].xlsx`.
- `sheets.main.enabled` (ANL, REP): whether the result sheet is in the file, as `a`/`b` already have. A missing
  key means included.
- `sheets.sql`: one sheet from a query of your own, placed last. Only `select`/`with` queries run; anything else,
  or a query that fails, is skipped with a line in the run log. Its `{variables}` are replaced as text, so dates
  are quoted (`to_date('{control_date_from:%Y-%m-%d}', 'yyyy-mm-dd')`). The headers are the column names as
  Oracle returns them, so a quoted alias keeps its case. Its rows count toward `max_records` and the size limit,
  and toward *Done, with results* only when no other sheet is in the file.
