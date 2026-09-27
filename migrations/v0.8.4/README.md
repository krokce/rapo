# Rapo v0.8.4 Migration Instructions

Upgrades Rapo from v0.8.3 to v0.8.4. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change**, and the `PL` engine's procedure is unchanged.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.4
    ./install.sh
    ```
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI.
