# Rapo v0.8.6 Migration Instructions

Upgrades Rapo from v0.8.5 to v0.8.6. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

There is **no database schema change** and no new Python package.

1. Wait until all your Rapo controls are completed or cancel them. Stop the web server.
    ```bash
    .venv/bin/rapo-server stop
    ```
1. Update the source in the application folder and reinstall it.
    ```bash
    git fetch
    git checkout v0.8.6
    ./install.sh
    ```
1. Optionally set the new `[DATASOURCES]` options in `rapo.ini` (see `rapo.ini.example`):
   - the file viewer: `view_lines` (100), `view_max_lines` (50000), `view_line_chars` (10000),
     `view_grep_seconds` (20), `view_grep_matches` (500). It is allowed wherever downloads are
     (`file_download`).
   - uploads: `file_upload` (default `False`: set `True` to offer them) and `max_upload_mb` (2048). The user running
     Rapo needs write access to the input directories; a file it creates gets its umask's mode, so the group (e.g.
     the Pentaho server's user) must be able to read and delete it, as with a `dir_mode` of `2775`.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI.
