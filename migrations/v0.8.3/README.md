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
