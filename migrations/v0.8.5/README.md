# Rapo v0.8.5 Migration Instructions

Upgrades Rapo from v0.8.4 to v0.8.5. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change**. The release adds the Python package `phik` (which brings `scipy`), installed
by `install.sh` from the package index; on a host without access to it, provide the wheels first (e.g.
`pip download phik==0.12.5 -d wheels` elsewhere, then `.venv/bin/pip install --no-index -f wheels phik==0.12.5`).

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
1. Optionally set the new `[ANALYSIS]` options `discrepancy_quick_rows`, `discrepancy_exact_rows`,
   `discrepancy_parallel` and `discrepancy_timeout_minutes` in
   `rapo.ini` (see `rapo.ini.example`); the defaults apply otherwise.
1. Optionally set the new `[KPI] calculate_timeout` (seconds, default 120) of *Calculate KPIs* in `rapo.ini`.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI.
