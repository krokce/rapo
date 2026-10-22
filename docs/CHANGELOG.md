# Rapo fork — Release Notes

These are the releases of this fork of [t3eHawk/rapo](https://github.com/t3eHawk/rapo), which it branched from at
v0.6.15. Releases are listed newest first, and each release's changes run from the most to the least impactful.
The full notes and upgrade steps of each release are in `migrations/<version>/` (`CHANGELOG.md`, `README.md`).

---

## v0.8.7 — unreleased

New table `rapo_api_token`, column `rapo_scheduler_event.requested_by`, recreated `rapo_config` triggers
(`migrations/v0.8.7/upgrade.sql`); new option `[API] token_cache_seconds`.

- **API tokens**: the master token manages per-user tokens (*Master token* menu → *API tokens*): user, expiry, area × level scopes with descriptions, Free SQL; shown once, stored hashed; 403 beyond the scopes.
- The UI hides what a token may not use (read-only editors and grammars, expiry banner, user menu); revoked tokens are signed out, a database failure never signs out.
- User menu: access per area, expiry and Free SQL at a glance; *Reset my token* gives a user token a new secret with the same scopes and expiry.
- Without Free SQL, Data analysis filters are plain filters of the dataset's columns (no subquery, comment or q-quoted literal).
- Changes and manual runs are attributed to the token's user (`updated_by`, versions, `requested_by`).
- Results and the Run log: a click on a run's process ID copies it to the clipboard.
- File log: a File ID column; a click copies the ID.
- Files and the file log: rows, chips and datasource names sized like Results; Files shows 0 for empty counts and other counts bold in their status color.
- Control editor: an unreadable stored configuration blocks Save; the schedule is checked on Save (Weekly without days was saved as Daily); changing datasource B clears its output columns.
- File log: files hidden by the filters are no longer acted on; Runtime as `h:mm:ss`.
- Failed loads show the error with Retry (KPI types, Scheduler, Run log, KPI type and datasource editors, file log, grammars).
- Keyboard Enter works in the schedule and KPI example menus; smaller fixes to the Run dialog, KPI type permissions and Scheduler refetching.
- Dark theme and contrast: remaining light-only colors follow the theme; CMP names readable on white; heat-strip counts pick their text color by contrast.
- Keyboard: clickable rows, marks, folds and editor icons are reachable by Tab and Enter; focus rings in the ASN.1 tree and file viewer; disabled-button reasons show on hover.
- The browser tab names the page.
- KPI type editor: Save/Apply/Cancel bar, Ctrl+S, unsaved-changes guard; the datasource editor offers Save when leaving with changes.
- One chip style: attribute, issue and level chips are grey chips with a colored icon; choices are ringed chips instead of button groups.
- Narrower windows: titles, filters and the file viewer wrap or fit; Dashboard panels share one type scale.
- *Control* instead of *Processname*; Scheduler process IDs copy on click.
- Discrepancy analysis: thin evidence (under 10 discrepancies per bin) is said so, and unbacked scores are grey.
- Compact page titles, unshouted buttons, *New …* beside the title, one tab-bar color; Files is titled *Files*.
- Control editor Main tab in three boxes with field hints; Recreate schema only on drift; quieter Lock all lanes.
- Colors keep one meaning: canceled brown, file errors deep orange, Dashboard *Idle* datasources, neutral rankings.
- *Filter* menus replace the filter-field rows of Controls, KPI types and Datasources.
- New control checklist; a type change that clears fields asks first and can be undone.
- Files: lane chips filter, a separate lock button locks; Discrepancy analysis can be stopped at any stage, with grey/amber/red end banners.
- No overlapping table columns down to 1024 px.
- Keyboard: hour heatmaps are one Tab stop with arrow keys; the ASN.1 tree has tree roles and Home/End/Page keys; split bars move by keys and touch.
- Datasource editor: Undo per unsaved change, Discard all.

## v0.8.6 — 2026-10-14

New tables `rapo_viewer_config`, `rapo_file_summary` and `rapo_health_minute` (`migrations/v0.8.6/upgrade.sql`) and
Python package `asn1tools` (`phik` no longer needed); new `[DATASOURCES]` options (uploads are off until
`file_upload=True`), `[HEALTH] history_days` and section `[DASHBOARD]`; set `[SCHEDULER] maintenance_interval` for the
Dashboard's file summary.

- **Dashboard**, the new start page (`/`, sign-in, logo), live and full width: 12 tiles of today against the same
  weekday last week (run errors, scheduler slots with the next fire and maintenance, files in input and processing,
  records rejected...); over 24h / 7d / 30d runs by status, type and trigger, slowest controls, fetched vs
  discrepancies, weekday × hour, the scheduler's last and next 24 hours, files over time by status, top datasources,
  loading and throughput, KPI alarms per control (a cell opens the run in its Run log) and health tiles. Panels hidden
  and moved per browser; clicks open the list pages filtered. Route `get-dashboard`; past file log days summed into
  `rapo_file_summary` by the maintenance or *Refresh* (`refresh-file-summary`). Options `[DASHBOARD]
  file_summary_days`, `[DATASOURCES] scan_idle_interval`.
- **File viewer** (eye icon on a file log row or an incoming file): gzip, ZIP or plain files of any size read a few
  lines at a time with their line numbers, delimited columns colored (any delimiter or fixed widths, saved per
  datasource); search of the whole file on the server (text or regex). Options `[DATASOURCES] view_*`; routes
  `view-ds-file`, `grep-ds-file`.
- **ASN.1 view** of binary files (BER, DER, CER): a tree of tags read node by node beside a hex dump, XML/Text of a
  subtree, typed value readings; **grammars** (TAP, RAP, NRTRDE, 3GPP 32.298, a vendor's; none shipped) and Pentaho
  **tag maps** uploaded and edited in place, saved per datasource with the record layout (start offset, record header,
  filler); search by field path, value or hex bytes. Options `[DATASOURCES] asn1_*`; routes `*-ds-file-asn1`,
  `get-ds-file-bytes`, `*-asn1-grammar*`, `*-viewer-settings`.
- **Loaded records** of a file (database icon, or the viewer's *Records* chip): the rows PDI Core loaded into each
  table of the datasource, paged and searched in the database, alone or below the file; *Open in Data analysis*
  (`/analysis/file/:fileId/:table`). Routes `get-file-tables`, `get-file-records`, `analysis-start-file`.
- **Upload files** into a datasource's first input directory (file log, editor, input files dialog, or drop), with
  progress and a pattern check, never overwriting and renamed when complete. `[DATASOURCES] file_upload` (off),
  `max_upload_mb`; routes `check-ds-upload`, `upload-ds-file`.
- **Data analysis and Discrepancy analysis redesigned** as single scrolling pages with an *On this page* list (old
  `?tab=` links work): Summary with a 30-day trend, Result types, compact column cards (one visual each, date
  histograms in whole units of the run's window), Records; findings as cards and Attributes opening in place to a
  butterfly of their bins. Faster (a spare connected process, Bernoulli samples without sorting). Removed: Compare
  (`get-analysis-targets`, `get-control-done-runs`, `analysis-compare*`), Missing values, Duplicates, correlation
  heatmap, Time bands, example records, φK.
- **Superseded runs folded** under the later run of the same period in Results and the Run log (*Ver* bubble unpacks
  them); stored KPI values in colored boxes (a *KPIs* column in Results sorting by alarm, a column per KPI in the Run
  log); a superseded run or a control name in Results opens the Run log on the run; *Calculate KPIs* flags stored
  values that differ; columns drop as the width shrinks; no *PV* column (a badge on the status chip, as warnings).
  `get-control-runs`: `superseded_by`, `kpis`, `kpi_types`.
- **Email: several files with several sheets each**: result sheets (REC: side and result types per sheet) and Free
  SQL sheets, named and filtered each; *Attach* and a row limit per file, the size limit over all; files without rows
  left out. Old configurations read as one file and saved as `files` on the next save.
- **Run log by periods:** the latest 14 periods with all their runs, older ones loading as the table scrolls; no *Days
  back* (`get-control-runs`: `periods`, `before_*`, `through_*`, `all` instead of `days`).
- **Instance limit no longer blocks the queue:** a run whose control already runs `instance_limit` jobs is held
  (*Queued · instance limit*) while other controls take the free slots, in queue order and without timing out.
- **File log page** like Results/Files: day navigator in the title, status/*Duplicate* chips as filters, *Upload*
  beside them; the search takes a file name, `?prefix` or `#file ID` and finds other days (`search-files`).
- **Instance health kept across restarts** in `rapo_health_minute` (`[HEALTH] history_days`, 7); a 7d span.
- **Faster loading:** UI bundles gzipped and cached for good, JSON answers gzipped, ECharts its own bundle.
- **Python 3.10 installs again:** `websockets` pinned to 16.0 (17.1 needs Python 3.11; broken since v0.8.3).
- **Next maintenance** chip on the Scheduler page (lease holder only); `scheduler-status` adds `maintenance_interval`.
- **Scheduler's Running tab:** a control's name opens its editor on the *Scheduler* tab.

## v0.8.5 — 2026-10-05

No change to Rapo's own schema; new Python dependency `phik` (installed by `install.sh`). From the `v0.8.4` tag: redeploy
the `PL` engine's `RAPO_USAGE_RULE` (the tag predates the last changes of the v0.8.4 notes, which this release contains).

- **Discrepancy analysis page** (run number menu, Data analysis button): what sets a run's discrepancies apart from
  its normal records (fetched less discrepancies), per side, for ANL/REC/CMP. Every column binned (values, deciles,
  hour/weekday/period, identifier prefixes and length), counted by Oracle over the whole data; ranked by Theil's U
  and φK, per-bin lift, rate and z; pairs of bins stronger together, REC value differences and example records.
  Findings as sentences, butterfly charts, weekday × hour heatmaps; every bin opens its records in Data analysis. REC
  per result type. Preliminary results at once from a block sample, then refined in one (parallel) scan; options
  `[ANALYSIS] discrepancy_*`. New routes `start-|get-|stop-discrepancy-analysis`.
- **Instance health** (*Instance details* → *Health Rapo server* / *Health Database*, charts filling the dialog):
  server (CPU, memory, a disk per file system (symlinks followed) of the logs, rapo and datasource input/archive directories, network,
  TCP connections, processes) and database (CPU, PGA/SGA, storage in GB, I/O, sessions, locks), each under its name and
  uptimes, each a value and a live chart over 1–24 h (span remembered) with rapo's own share; warning levels color
  the tiles and put a dot on the header button; Sessions/Locks list the sessions and blockers (a run's control by
  name). Rapo's DB sessions now carry module `rapo` (action = control). Optional grants on seven `V$`/`DBA_` views,
  `[HEALTH]` options. New routes `get-instance-health|sessions`.
- **Configuration tab:** every `rapo.ini` option with its value, default and description, a General box (version,
  paths), filter; options that need no restart are changed in place (pencil on hover), written to their line of
  `rapo.ini` after a `rapo.ini.bak-*` backup and applied at once. New routes `get-config-catalogue`,
  `set-config-option`.
- **Edit a view datasource's SQL** (pencil in the editor's datasource field when it is a view): the query with
  autocomplete, Check on a scratch view (column diff), Preview of the first rows (read only), Format, and Compile
  (`CREATE OR REPLACE VIEW`, never while invalid; confirms naming other controls and objects using the view; 409 on a
  concurrent change). The previous DDL goes to the server log only. The editor then rereads the view's columns,
  keeping its choices. `[VIEWS] edit|preview_max_rows|preview_timeout`; routes `get-|check-|preview-|compile-|
  format-view`, `get-object-columns`, `get-datasources?types=true`.
- **Calculate KPIs** (editor KPIs tab, Run log and Results run menu): runs the KPI and alarm SQL as edited (or
  saved) for a past run without storing it, as RACS_KPI_PKG would (0 without a row, alarm 3/2/1 chips), beside the
  stored value, one row per KPI with details on demand; the KPIs tab shows each KPI's value (pale yellow), alarm
  or error in its row for the run picked there; *Last runs* backtests up to 30 runs; *Re-ingest* stores a run's
  KPIs with the package. Read-only single queries, `[KPI] calculate_timeout`. New routes `calculate-kpi`, `get-kpi-history|runs`, `reingest-kpis`.
- **Orphaned KPIs** (Controls header chip): KPIs configured for a name no control has, assigned to a control or
  deleted. Deleting a control deletes its KPIs (ticked option, `delete_kpis`); stored values are kept.
- **KPIs follow a rename or clone:** the editor rewrites `RAPO_REST|RESA|RESB_<name>` in the control's KPI statements
  live as the name changes (banner with Undo); an API rename without `kpi_config` moves and rewrites them too.
- **Email *Send when: Evaluate SQL*:** sent only when a Prerequisite-style SQL returns a number above 0, whatever the
  run status or result rows; its value is `{evaluate_value}`. A failing or non-numeric statement sends nothing and
  warns in the run log; *Resend* and *Send test* always send.
- **Controls *Scheduler* column:** when each control runs next (own schedule, cascade or chain pull) and
  in how long, the schedule in words (*Weekdays at 08:15*), a frequency-colored avatar, a strip of where the runs
  fall and the data window. Sorted by the next run, hover for the next 5 runs, click for the Scheduler
  tab. Type, Name and Scheduler fit their content; Description takes the rest. New route `get-next-fires`.
- **Results page:** filter row and *Run control* button removed (chips filter); a runs-per-hour heatmap (runs per type
  on hover, errors outlined red, warnings an amber corner, click filters the hour); a day pill `‹ day › ⏭` in the
  title (also on Files) whose day opens a calendar with activity/error dots (Files: a plain date picker); the header search finds process IDs (prefix) and offers *Go to its day* for another day's
  run; the name magnifier filters by the exact control and clears on a second click. `get-control-run` answers `added`.
- **Scheduler page:** a status bar of live chips beside the title (state, server, heartbeat, slots gauge, next fire,
  24 h counters) linking to the tabs instead of the status card; filter fields removed (header search, count chips that filter); Upcoming = next 24 hours incl.
  cascades and chain sources (*Trigger* column, *via*), History = last 24 hours plus an *Older missed* chip; a green/blue
  24-hour heatmap above each (failed/error outlined, missed marked, click filters the hour); Running is a tab of its own (counts on the tab, scrolls inside) with the run
  window in History's column order. `scheduler-upcoming` cascades/upstreams, `scheduler-events?hours=`, new
  `get-missed-fires`.
- **Results trigger icon:** a small icon after the start time shows what started the run (schedule, manual,
  catch-up, iteration, cascade, chain); hover for details. The day's totals count the runs per trigger. A click on
  either filters by the trigger (again: clears); Scheduler trigger clicks toggle too.
- **Manual runs cascade only when ticked:** *Run* and *Re-run* offer *Cascade into X* (off); `run-control` takes
  `cascade` (default `true` for API callers). Scheduled/catch-up runs unchanged.
- **"Upstream" renamed "Chain"** in the UI and run log (stored code stays `UPSTREAM`). A scheduled cascade's window
  is its own periods counted back from the fire time of the control it follows (*After X finishes · own window*,
  explained in the editor). Controls: *Cascade schedule* attribute; the attribute list is grouped.
- **Now marker** on the hour heatmaps (Results, Files, file log on today; Scheduler Upcoming/History): a line at the
  current minute under a clock icon and *Now HH:MM*, by the server's or the database's clock as the hours are; the
  Scheduler's midnight divider is drawn alike, in grey, with a calendar icon.
- **Files page:** filter fields removed (chips filter, toggling); every issue kind is a header chip; a lane chip's
  icon locks or unlocks the lane (new route `set-lane-lock`), its text shows only that lane. The header search takes
  a datasource name or ID, `?<file name start>` (case-sensitive) or `#<file ID>`, files of any day, newest first;
  `search-files` takes `text` (prefix) or `id`, no longer `date`.
- **Links to referenced controls** in schedule descriptions (*After X finishes*, *Pulled by X*) and the Scheduler's
  *via X* / *for X*; an editor-to-editor link reloads the form (unsaved changes asked first).
- **Editor Run log = Results table:** same columns, menus, number menus and totals (chips not filters); sortable,
  day separators, fills the tab. `get-control-runs` takes `control_name`/`days`.
- **Editor unsaved changes:** undo one change per row in the *Unsaved changes* dialog, *Discard all changes* (with
  Redo), and *Save* when leaving the editor with unsaved changes.
- **SQL boxes:** line numbers no longer stop after the first screenful; `alias.` completes the aliased table's
  columns (subqueries and `WITH` included), names match in any case and complete in upper case.
- **Sort chip:** a grey chip under the title while a list is sorted by a column; its ✕ restores the default order
  (Controls: last modified first).
- **Fix:** opening *Data and logic* of a reconciliation saved without per-side output limits no longer marks the
  editor as changed.

---

## v0.8.4 — 2026-09-28

No change to Rapo's own schema; redeploy the `PL` engine's `RAPO_USAGE_RULE`. PDI Core pages need grants on its tables.

- **Datasources page** for the PDI Core file loader (`PDI_CORE_DS_CONFIG`/`_TABLES`): list with 24h loads,
  lane switch and issue badges (counted in the header); editor with input-file lists, *Check regex*,
  retention tables, a directory explorer, the file log and a *Need attention* tab; clone, delete, 409 on concurrent
  changes. New `[DATASOURCES]` options.
- **Files page**: one day of the PDI Core file log by datasource, an hourly heatmap, file search and lane locks,
  *Silent* / *Drop* / *Stalled* chips with counts; per datasource the files to Recycle, Reload, Delete or
  **Download** (one file or a ZIP). Counts open exactly those files and no longer filter the page; *Incoming* opens the
  input files in a dialog. Status columns from *Success* back to *Incoming*, then *Error*/*Recycle*/*Reload*/*Duplicates* when present; header tooltips.
- **Deleting a control drops its result tables** (orphans included) unless unticked; not while a run is active.
  API callers: `delete-control` drops by default, pass `drop_tables=false` to keep them.
- **Temporary tables** left by failed, canceled and debug runs: a Controls header chip lists them by run, with
  *Drop* and *Drop all*; only recognized Rapo temp objects are dropped. The run menus lose *Drop temporary tables*
  and *Show error log*; API: `get-temp-tables`/`drop-temp-tables` replace `delete-control-temporary-tables`.
- **Fix: ORA-30926 in a DB-engine reconciliation** whose key field is not unique. Such rows still get repeated
  results in both engines, so the run is now flagged with a warning: check it and pick a unique key (or `ROWID`).
- **Fix: iterations and cascade skipped** when the postrun hook (KPI ingest) failed: the error is logged and flags
  the run with a warning instead of ending the job.
- **Run warnings:** a key field that is not unique, `correlation_limit` reached, approximate PL matching and an
  output limit that cut the saved rows add a `Warning:` run message; Results shows an icon and a *Warnings* filter
  chip (API: `has_warning` in `get-control-runs`).
- **Engine chip on Controls:** reconciliations show *DB engine* / *PL engine*, filterable as an attribute.
- **Control groups:** a *Control group* field in the editor (pick a group in use or type a new one), a group filter
  and a clickable group chip on Controls. *System A/B* pick from the systems in use too; the *System* filter suggests them.
- **One mono font:** paths, code and table numbers use the bundled Roboto Mono. Datasources: a directory opens
  its files, the mask moves under the directories (*Input files*; no *Files mask* column), *Zipped*/*Parallel* columns, *Files 24h* is a count; the editor
  puts the source name beside lane and ID, the scan options under *Processing*, the archive directories in one row.
- **Dark mode:** a header button cycles Automatic (follows the system, default) / Light / Dark, remembered by the
  browser; pages, dialogs, charts and SQL editors have dark variants, the light theme is unchanged.
- **Formula mode in CMP criteria:** *Match* and *Mismatch* rows take SQL expressions over `a.`/`b.`, as in REC
  (`"formula_mode": true`); the two boxes are stacked. Switching *Formula* off (CMP and REC) keeps a plain
  `a.<column>` as that column.
- **Random analysis samples** by default (`order by dbms_random.value`); *First rows* keeps the faster old mode.
- **Counterpart by `RAPO_DISCREPANCY_ID`:** a REC discrepancy shows first the exact record it was matched with.
- **Fix: reconciliation saves after a schema update** (since v0.8.3): a column added after `RAPO_PROCESS_ID`
  swapped values with it (`ORA-01438`, or rows saved under a wrong process ID); REC matches columns by name.
  Schema updates quote mixed-case and reserved column names.
- **Nullability is no schema drift:** only missing, too narrow or incompatible columns count. The Controls list
  confirms what it flags with the editor's exact check, so invisible columns and view expressions typed differently
  in the dictionary no longer show a drift the editor does not. Synonym datasources are checked.
- **Datasource missing** badge and filter on Controls for a control whose datasource does not exist
  (`get-schema-drift` level `source_missing`).
- **Fix:** the Scheduler's running list names the control of the run in progress (upstream, iteration, cascade).
- **Active filters** on every list page as a badge and removable chips; filters, sort and search are kept for the
  browser session; a grey sort chip restores the default order (Controls: last modified first).
- **Analysis:** a dataset switch between Source A/B and Discrepancies A/B of a run; *Hide all*, *Key fields* and a
  search in the *Columns* menu; the editor's run log opens *Copy SQL* and *Data analysis* with the server's SQL.
- **UI load time:** the editors and the file log page load on first visit, halving the vendor bundle of the first
  load.
- **Table headers:** every column header explains its field on mouse-over, and all are compact (28px) as on Results.
- **UI accessibility:** names on icon-only buttons, keyboard access (Tab, Enter, Space, focus ring) to sortable
  headers, run numbers and analysis rows, `aria-sort`, and darker muted text and chip colors for contrast.
- **UI icons and states:** Material icons replaced by Font Awesome (the Material font is gone), one look for empty
  analysis panels, and *Retry* states for a failed run trend, page of rows or analysis section.
- **"Checking schema…"** in the editor footer while the result tables are compared.
- **Fix:** leaving the analysis page no longer reports "The run trend could not be loaded. 422".
- **UI consistency:** shared helpers instead of copies (file download, copy, run start, day navigation, chart
  options), one confirmation dialog style, the KPI types page as a virtual-scroll list like Controls, and the
  styles the pages duplicated moved into one global stylesheet with `--rapo-*` color variables, with dead code and
  typos removed.
- **Controls header counts** of *Datasource missing*, *Schema drift* and *No KPI* controls, each filtering the list.
- Smaller: Results totals read **ANL** (26) and gain failing controls, records fetched and runtime
  under the chips (as on Files), Controls names link to the editor, editor pages are titled, a control opened from
  a KPI type or the Scheduler shows its *KPIs* / *Scheduler* tab, Scheduler tables fill the window, the *Scheduler*
  menu item follows *KPI types*.

## v0.8.3 — 2026-09-24

No change to Rapo's own schema. Redeploy `schema/rapo_usage_rule.sql` if you use the `PL` engine.

- **Chain-rules.** A control can use another control's result table (`RAPO_REST_`/`RESA_`/`RESB_<name>`) as a
  datasource. Every run of it first runs that upstream control, and that control's own upstreams, for the
  **puller's own window**. It then reads only the records those runs saved (by `rapo_process_id`).
  - Upstream runs are depth-first and deduplicated. They skip iterations and the cascade and appear as
    `UPSTREAM` in the scheduler history.
  - The whole chain takes one execution slot. Cancelling any run in it cancels the chain, and if an upstream
    fails, the pulling control ends `E`.
  - A save is refused for self-reads, cycles, tables the upstream does not write, and cascades from an
    upstream. A rename updates the dependent controls, and a control that others read cannot be deleted.
- **Data analysis of run results.** Click a Fetched, Discrepancies or error-level number on Results to get
  *Copy SQL* or *Data analysis*. Data analysis is a pandas-profiling style page on a 50k-row sample, which you
  can extend. It runs in its own server process and has:
  - a profile of every column, with alerts;
  - correlations (Pearson, Spearman and Cramér's V);
  - a data grid with filters, search, group-by and Excel/CSV export;
  - scoped profiles ("profile these rows");
  - database-side filters and your own SQL filter;
  - a run trend with one point per day;
  - **Compare**, which ranks columns by PSI and lift against another sample (previous run, other side, fetched
    vs. discrepancies);
  - for REC, a view of each row's counterpart on the other side.

  The view is kept in the URL. New optional `[ANALYSIS]` section; `pandas` and `numpy` are now requirements.
- **Result table schema follows the configuration.** Before, result tables were created by the first run and
  never changed afterwards.
  - The editor checks for drift in the background, unsaved changes included. It offers *Update schema* (add,
    widen, make nullable, keep data) or *Recreate schema* (now drop + create, and only for the drifted tables),
    with row estimates and an exact count on request.
  - Runs heal safe drift themselves and fail with `Recreate schema needed for …` on an incompatible type.
  - A rename takes the tables and their index with it.
  - ANL/REP/CMP now save by column name, not position. A CMP without output columns uses `A_`/`B_` names, which
    fixes collisions.
  - The Controls list has a *Schema drift* chip and filter, a light dictionary-based check of the whole
    catalogue.
  - **Orphaned** tables (an unticked REC side, a former type, a deleted control) are flagged and can only be
    dropped explicitly.
- **Oracle driver `python-oracledb`** replaces `cx_Oracle`, in thick mode, so it needs no compiler and has wheels
  for Python 3.10+. Results are unchanged.
- **`install.sh`** installs or updates in one step: picks a Python 3.10+, creates or updates `.venv`, creates
  `rapo.ini` and checks the Instant Client.
- **Output limit now applies to ANL, REP and CMP.** It used to be stored but ignored, so check controls that
  already have a limit set. Error counts still report every discrepancy.
- **Variables in datasource filters and ANL mismatch criteria.** You can use `{control_name}`, `{process_id}`,
  `{control_date[_from|_to]:fmt}`, on both engines. A lenient renderer leaves unknown braces such as regex `{3}`,
  `{name}` and `{{x}}` as written.
- **Email.** Adds a *Free SQL* sheet (your own query), an *Include* switch for each sheet and a configurable
  attachment file name with variables.
- **SQL boxes.** Each box has curated examples for its context (filters, criteria, hooks, email, KPI/alarm by
  type) and a *Check* button. Check parses the statement with Oracle without running it and flags unknown
  variables, missing case IDs and stray binds. DDL is refused.
- **Editor change tracking.** *Unsaved changes* lists every value Apply would write, with JSON paths and SQL line
  diffs. A new *Manage versions* dialog compares, loads and deletes past versions: one by one, by selection, by
  age or as consecutive duplicates.
- **`rapo.ini` hot reload.** *Instance details* shows what changed on disk and reloads it. `[DATABASE]`, `[API]`,
  `LOGGING.directory` and `SCHEDULER.enabled` still need a restart.
- **Server errors are logged.** Unhandled route errors are written to the server log with their traceback and
  answer 500 with the error type and message. Before, they left no trace.
- **Fixes.**
  - A nested `CASE` in the Case definition no longer takes inner numbers for case IDs (`KeyError: 5`).
  - Logged SQL containing braces no longer crashes a run (`IndexError`) or gets rewritten.
- **Minor.**
  - Every `RAPO_TEMP_` table is created `NOLOGGING`; result tables keep `LOGGING`.
  - The Controls list has a *No KPI* chip and filter.
  - KPI chips are colored by unit.
  - `rapo-ctl.sh` is renamed `rapoctl.sh`, so update any crontab `@reboot` entry.

## v0.8.2 — 2026-09-23

No schema change. Redeploy the `PL` procedure.

- **Email results per control** (ANL, REP, REC).
  - Configured under `rule_config.email`, so it is versioned with the control.
  - To/CC/BCC; send on *done with results*, *done* or *done or error*.
  - Subject and body take variables.
  - Excel attachment with one sheet per result (REC: per side and result type), each with its own filter,
    fields and labels, and proper date and number formats.
  - Row and MB limits; resend from Results and a *Send test* in the editor.
  - Needs `[EMAIL]` in `rapo.ini`, which is off by default.
- **Apply in the control editor.**
  - *Apply* (Ctrl/Cmd+S) saves and keeps the editor open, from a sticky action bar.
  - Only real changes are written, so no empty versions appear.
  - Leaving with unsaved changes asks first, and there is a Run button in the header.
  - **Optimistic locking**: a save over someone else's newer save gets a 409, with Reload or Overwrite.
- **Eight `PL` engine fixes.**
  - Fuzzy clusters sharing a key paired wrongly, and a row without candidates shifted fuzzy positions.
  - Null-key rows were reported as losses, and a non-unique key multiplied rows.
  - An unmatched pair could stall matching, and a `DBMS_SQL` cursor leaked.
  - `max_candidates` and `need_recons` were ignored.
  - Results of `PL` controls may change. It is also faster (n=300: 12s → 7s).
- **KPI types page** (`/kpi-types`) manages the `racs_kpi_type` catalogue. A rename moves the controls' KPIs in
  one transaction, and a type in use cannot be deleted.
- **Results is the home page.**
  - Prev/Next/Today day navigation and clickable totals chips.
  - The side menu collapses to icons.
- **List pages scale to thousands of rows.**
  - Virtual scrolling on Results, Controls and the Scheduler's Upcoming and History tables.
  - Fixed column widths, one shared row menu per table and loading skeletons.
- **SQL autocomplete** in the editor's code boxes: datasource and result columns, Oracle keywords, KPI binds and
  `{variables}`.
- **Consistent look.** Type and status avatar chips everywhere, and the Scheduler tables match Results.

## v0.8.1 — 2026-09-21

Schema: new `rapo_engine_log` table and the `RAPO_USAGE_RULE` procedure.

- **`PL` engine for reconciliation** (`control_engine = 'PL'`). `RAPO_USAGE_RULE` runs the whole s01–s09
  pipeline inside Oracle as a drop-in replacement, with the same config, tables and counters.
  - It streams both sources in key order, one correlation group at a time.
  - A two-pointer band join and a per-row fan-out cap (`max_candidates`, default 100) mean no Cartesian
    product: a group costs `O(n × cap)`, not `n²`.
  - Results are identical to the `DB` engine, and it creates no `rapo_temp_source_*` tables.
  - The engine log is drained live into the run log.
  - `normalization_type = minmax` is rejected. `rank` turns out to be a no-op for match selection on both
    engines.
- **Three reconciliation algorithm fixes** that change the results of existing REC controls:
  - duplicates inside a fuzzy cluster were cross-matched (a regression from upstream `01eb3ec`);
  - the B side's `rapo_discrepancy_id` pointed at itself instead of the A row;
  - unmatched fuzzy (`F`) rows were written nowhere.
- **KPIs tab in the control editor.**
  - Edit `racs_kpi_config` statements per KPI, with "Use type default" (stores NULL) and Check.
  - `save-control` syncs the KPIs, so a rename or clone carries them along.

## v0.8.0 — 2026-09-20

Schema: `rapo_scheduler` lease columns, new `rapo_scheduler_event` table.

- **Scheduler inside the web server.** One process now serves the API, the UI and the scheduler.
  `rapo-scheduler` is deprecated.
- **Run manager.** Every run, scheduled or manual:
  - is initiated at once (`I`, cancellable) and queued FIFO under `control_parallelism`;
  - executes in its own process, with timeouts that also count time spent waiting for a slot or lock;
  - settles by itself if its process dies. Crashed leftovers are settled on the next start and their locks
    released.
- **Scheduler lease for several servers.** A heartbeat row decides which one fires; the others take over after
  `lease_timeout`. Stop/Start is persisted in the DB for all servers.
  - Instances sharing a database no longer touch each other's server row, process or fires.
- **No dropped fires.** Fire times are computed with `next_fire`, and each fire is served with its exact
  timestamp.
  - Late fires and fires during downtime are recorded as `MISSED`, and *Run for this moment* runs one as
    `CATCHUP`.
  - Schedule changes apply without a restart, including direct SQL edits.
- **Scheduler event history** (`rapo_scheduler_event`): one row per run request, with trigger and outcome.
- **Scheduler page**: state, running and queued runs, upcoming fires, history, and a next-fires preview in the
  editor.
- **One log file per run** (`logs/controls/<id>/<pid>.log`), plus a daily server log and retention cleanup.
  - *Show full log* in the UI parses the file into records, with search, download and live refresh.
- **Manual runs behave like scheduled ones.** They cascade for the requested window, and iterations are an
  opt-in switch showing their dates.
- **Results one day at a time.** `get-control-runs?date=` returns `{date, today, runs}`, a **breaking change of
  the response shape**.
- **Reliability fixes.**
  - Failed COMMITs and failed reconciliation stages used to end `D`; they now fail the run.
  - `period_number = 0` hung the scheduler.
  - Cancel races are fixed, and run messages are appended instead of overwritten.
  - A PID is trusted only when it is a rapo server on this host.
- **Security and ops.**
  - Swagger is served only with `[API] docs`.
  - *Instance details* shows the paths and every `rapo.ini` parameter, secrets masked.
  - `rapo-ctl.sh` (renamed `rapoctl.sh` in v0.8.3) supports unattended `@reboot` starts with `--wait`.
- **Distribution.** Version marked `+fork`; PyPI metadata dropped; upstream credited in
  README, LICENSE and NOTICE.

## v0.7.0 — 2026-09-19

Schema: index on `rapo_log.updated`. `rapo.ini` moves to the application folder (or `$RAPO_CONFIG`). Runs from source
in a `.venv` instead of PyPI; Python >= 3.10.

- **FastAPI replaces Flask.**
  - uvicorn with one worker; routes under `/api` behind a Bearer token, with real HTTP error codes.
  - The UI is served from the same port.
  - Console scripts `rapo-server` and `rapo-scheduler`.
- **Live updates via socket.io** (`/api/socket.io`). The server diffs `rapo_log` and `rapo_config` and pushes
  changes; the UI refetches on events instead of polling. Reverse proxies must allow WebSocket upgrades.
- **UI source in the repository** (`rapo-ui/`). The built bundle (`rapo/web/ui/`) is committed and packaged, so
  installs need no Node.
- **UI fixes and refactor.**
  - The editor edits a copy, so unsaved edits and clones no longer leak into the catalogue.
  - Datasource watchers no longer reset the form on load.
  - HTML output is escaped.
  - Shared API helper, run actions, schedule parser, sorting and column filters.
- **REC algorithm options follow `rapo.ini`.** Opening a control no longer freezes the current defaults into its
  `rule_config`.
