# Rapo v0.8.7 Migration Instructions

Upgrades Rapo from v0.8.6 to v0.8.7. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md). The release has no schema change.

1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.7
    ./install.sh
    ```
1. Restart the web server.
    ```bash
    .venv/bin/rapo-server stop && .venv/bin/rapo-server start
    ```
