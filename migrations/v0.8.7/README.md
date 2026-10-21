# Rapo v0.8.7 Migration Instructions

Upgrades Rapo from v0.8.6 to v0.8.7. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

The release adds the table `rapo_api_token` (the API tokens of users) and the column
`rapo_scheduler_event.requested_by`, and recreates the `rapo_config` triggers so that they record the token's user.

1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.7
    ./install.sh
    ```
1. Upgrade Rapo's schema (the script can be run again).
    ```bash
    sqlplus <user>/<password>@<database> @migrations/v0.8.7/upgrade.sql
    ```
1. Optionally set `[API] token_cache_seconds` (30) in `rapo.ini` (see `rapo.ini.example`).
1. Restart the web server.
    ```bash
    .venv/bin/rapo-server stop && .venv/bin/rapo-server start
    ```
