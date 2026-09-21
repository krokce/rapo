# Rapo v0.8.1 Migration Instructions

Upgrades Rapo from v0.8.0 to v0.8.1. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

This release adds `PL`, a third control engine that runs REC (reconciliation) controls inside Oracle through
the `RAPO_USAGE_RULE` procedure instead of the Python `s01..s09` pipeline. Existing controls are untouched:
they keep `control_engine = 'DB'` and behave exactly as before.

The upgrade adds one table, `rapo_engine_log`. It is a transport buffer, not a log: the procedure appends its
progress there and the control process drains it into the run's own log file and deletes the rows, so it
should normally be empty.

It also corrects three defects in the reconciliation SQL, which **changes the results of existing REC
controls**. Re-baseline any comparison you keep against previous runs:

- duplicates inside a fuzzy (`F`) correlation cluster were cross-matched instead of paired positionally;
- `rapo_discrepancy_id` on the B side pointed at the B row itself rather than its A counterpart;
- unmatched `F` rows were written to neither the issue nor the reconciled output.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.1
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-build-isolation -e .
    ```
1. Apply the database upgrade and deploy the procedure, as the Rapo schema owner.
    ```bash
    sqlplus <user>/<password>@<database> @migrations/v0.8.1/upgrade.sql
    sqlplus <user>/<password>@<database> @schema/rapo_usage_rule.sql
    ```
   `RAPO_USAGE_RULE` is declared `AUTHID CURRENT_USER`, because it creates and drops temporary tables and
   privileges held through a role are disabled in a definer's-rights unit. The schema owner therefore needs
   `CREATE TABLE`, directly or through a role.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```

## Using the new engine

Set a REC control's engine to `PL` in the control editor, or directly:

```sql
update rapo_config set control_engine = 'PL' where control_name = '<name>';
```

The engine is a drop-in replacement: the control's sources, filters, `rule_config`, output tables and
`rapo_log` counters are unchanged, and results land in `rapo_resa_<name>` / `rapo_resb_<name>` as before.

Two differences to know about:

- `normalization_type = "minmax"` is **rejected**. It normalizes over the entire candidate set, which a
  streaming engine never holds; the run fails with a message naming the option. The other values
  (`none`/`default`, `rank`, `z_norm`, `srd`) behave identically to the `DB` engine.
- The procedure fetches from the datasources itself, so it never creates `rapo_temp_source_a/_b_<pid>`.

## Verifying a control after switching it

The two engines are meant to be interchangeable, so the check is a differential one: clone the control, set
the clone to `PL`, run both for the same window and diff the results.

```sql
select tag, rapo_result_type, rapo_discrepancy_id, rapo_discrepancy_description
  from rapo_resa_<name>      where rapo_process_id = <db_pid>
minus
select tag, rapo_result_type, rapo_discrepancy_id, rapo_discrepancy_description
  from rapo_resa_<name>_pl   where rapo_process_id = <pl_pid>;
```

Run it in both directions, on both sides, and compare `fetched_number_a/b`, `error_number_a/b` and
`success_number_a/b` in `rapo_log`. Anything other than zero rows and identical counters is a defect in one
of the engines — the run log of the `PL` run carries the generated SQL, which is usually where to start.

The fixtures used to validate the engine are in the (gitignored) `test/` folder: a 15-case option matrix, a
multi-field discrepancy fixture and an ~86k-row scale fixture.
