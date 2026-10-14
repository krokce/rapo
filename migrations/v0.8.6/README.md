# Rapo v0.8.6 Migration Instructions

Upgrades Rapo from v0.8.5 to v0.8.6. Commands run in the application folder.
What the release contains is in the [change log](CHANGELOG.md).

The release adds three tables, `rapo_viewer_config` (the file viewer's ASN.1 grammars and the settings it opens each
datasource's files with), `rapo_file_summary` (the Dashboard's summary of the PDI Core file log) and
`rapo_health_minute` (the instance health by minute, kept across restarts), and one Python package, `asn1tools` (installed by `./install.sh`). The package `phik` is no longer required; an existing `.venv` keeps
it, which does no harm (`./install.sh --force` recreates it without). `websockets` is downgraded to 16.0, so Python 3.10 is supported again.

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
1. Create the new tables in Rapo's schema (the script can be run again: it skips an existing table).
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
   - `scan_idle_interval` (300): how often the server running the scheduler counts the files waiting while no browser
     is connected (0: only while someone looks).
1. Optionally set `[HEALTH] history_days` (7): the days of instance health kept in `rapo_health_minute` (about 2 MB a
   day per server); 7 or more offers a 7d span.
1. Optionally add the new section `[DASHBOARD]` (see `rapo.ini.example`): `file_summary_days` (90, the days of the
   file log summary kept). With the PDI Core file log, make sure `[SCHEDULER] maintenance_interval` is set (e.g. 3600 or
   86400): the maintenance fills the Dashboard's file summary; without it only the Files section's refresh button
   does. The first maintenance sums the last `file_summary_days` days, one partition each.
1. Start the web server.
    ```bash
    .venv/bin/rapo-server start
    ```
   Reload open browser tabs, so they load the new UI. Rapo now opens on the Dashboard; bookmarks of other pages keep
   working.
1. Upload the ASN.1 grammars your binary files use (TAP, RAP, NRTRDE, 3GPP TS 32.298 or a vendor's): open a binary
   file in the viewer, *Grammars…*. None is shipped with Rapo. A delimiter the viewer remembered per browser before is
   offered for saving (orange save icon in the *Delimiter* field) the next time a file of that datasource is viewed.

## Email files and sheets

`rule_config.email` now holds its attachments as `files` instead of `attachment_name`, `attach` and `sheets`:

```json
"files": [
  {"name": "Losses_{control_date_from:%Y%m%d}", "attach": true,
   "sheets": [
     {"kind": "result", "side": "a", "name": null, "result_types": ["Loss"], "filter": null,
      "fields": [{"column": "msisdn", "label": "MSISDN"}]},
     {"kind": "sql", "name": "Summary", "query": "select ... where rapo_process_id = {process_id}"}]}
]
```

- `name`: the file name with `{variables}` (`.xlsx` added); null = `<NAME>_<run from>[_<run to>]`, `_2`, `_3`... by
  position. `attach`: false = not attached, but counted for `done_with_results` and `{attachment_rows}`.
- A sheet's `kind` is `result` or `sql`. A result sheet has `side` (`main` for ANL/REP, `a`/`b` for REC; REC also
  `result_types`, empty = all the side saves), `filter` and `fields` as before; a Free SQL sheet has `query`. `name`
  null = the default (control name, or the side plus its result types when not all of them; `SQL`, `SQL 2`...).
- `max_records` applies per file; `[EMAIL] max_attachment_mb` to all attached files together.

Nothing has to be done: an older configuration is read as one file with its enabled sheets, by the server and by the
editor, and written in the new form the next time the control is saved. Check controls whose email had sheets turned
off: those sheets are dropped when the control is next saved (the previous version keeps them).
