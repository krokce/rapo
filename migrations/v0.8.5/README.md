# Rapo v0.8.5 Migration Instructions

Upgrades Rapo from v0.8.4 to v0.8.5. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change**. The release adds the Python package `phik` (which brings `scipy`), installed
by `install.sh` from the package index; on a host without access to it, provide the wheels first (e.g.
`pip download phik==0.12.5 -d wheels` elsewhere, then `.venv/bin/pip install --no-index -f wheels phik==0.12.5`).

The `v0.8.4` tag was made before the last changes described in the
[v0.8.4 notes](../v0.8.4/CHANGELOG.md) (among them dark mode, the temporary tables chip, run warnings, control groups
and a new version of the `PL` engine's procedure); this release contains them. If you installed the `v0.8.4` tag
itself, step 3 applies to you.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.5
    ./install.sh
    ```
1. If you use the `PL` engine and installed the `v0.8.4` tag (or an earlier version), redeploy its procedure as the
   Rapo schema owner, so that its runs warn about a key field that is not unique. After the upgrade, look at
   *Results* for runs with the warning icon: a reconciliation flagged *Key field ... is not unique* has repeated
   results; choose a unique key field for it.
    ```bash
    sqlplus <user>/<password>@<database> @schema/rapo_usage_rule.sql
    ```
1. Optionally set the new `[ANALYSIS]` options `discrepancy_quick_rows`, `discrepancy_exact_rows`,
   `discrepancy_parallel` and `discrepancy_timeout_minutes` in
   `rapo.ini` (see `rapo.ini.example`); the defaults apply otherwise.
1. Optionally set the new `[VIEWS]` options of the view editor in `rapo.ini`: `edit` (default `True`; `False` hides
   it), `preview_max_rows` (1000) and `preview_timeout` (30 s). For views of its own schema the database user needs
   no new privilege.
1. Optionally set the new `[KPI] calculate_timeout` (seconds, default 120) of *Calculate KPIs* in `rapo.ini`.
1. Optionally set the new `[HEALTH]` options of the instance health (sampling intervals, history, warning levels) in
   `rapo.ini` (see `rapo.ini.example`). For its database metrics a DBA grants the database user (as `SYS`, in the
   PDB of a container database):
    ```sql
    grant select on v_$con_sysmetric to <user>;
    grant select on v_$parameter to <user>;
    grant select on v_$session to <user>;
    grant select on v_$sgainfo to <user>;
    grant select on v_$pgastat to <user>;
    grant select on dba_tablespace_usage_metrics to <user>;
    grant select on v_$instance to <user>;
    ```
   Each view not granted only shows *No access* on its tile. None of them needs the Diagnostics Pack.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI.
