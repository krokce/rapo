# Rapo v0.8.6 Migration Instructions

Upgrades Rapo from v0.8.5 to v0.8.6. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

The release adds one table, `rapo_viewer_config` (the file viewer's ASN.1 grammars and the settings it opens each
datasource's files with), and one Python package, `asn1tools` (installed by `./install.sh`). The package `phik` is no
longer required; an existing `.venv` keeps it, which does no harm (`./install.sh --force` recreates it without).

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
1. Create the new table in Rapo's schema (the script can be run again: it skips an existing table).
    ```bash
    sqlplus <user>/<password>@<database> @migrations/v0.8.6/upgrade.sql
    ```
1. Optionally set the new `[DATASOURCES]` options in `rapo.ini` (see `rapo.ini.example`):
   - the file viewer: `view_lines` (100), `view_max_lines` (50000), `view_line_chars` (10000),
     `view_grep_seconds` (20), `view_grep_matches` (500). It is allowed wherever downloads are
     (`file_download`).
   - uploads: `file_upload` (default `False`: set `True` to offer them) and `max_upload_mb` (2048). The user running
     Rapo needs write access to the input directories; a file it creates gets its umask's mode, so the group (e.g.
     the Pentaho server's user) must be able to read and delete it, as with a `dir_mode` of `2775`.
   - the ASN.1 view: `asn1_page_nodes` (500), `asn1_render_nodes` (5000), `asn1_grammar_max_kb` (2048).
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI.
1. Upload the ASN.1 grammars your binary files use (TAP, RAP, NRTRDE, 3GPP TS 32.298 or a vendor's): open a binary
   file in the viewer, *Grammars…*. None is shipped with Rapo. A delimiter the viewer remembered per browser before is
   offered for saving (orange save icon in the *Delimiter* field) the next time a file of that datasource is viewed.
