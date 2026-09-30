# Rapo v0.8.4 Change Log

## Annotation
This release adds two pages for the PDI Core file loader: *Datasources* edits its datasources and *Files* shows,
recycles, reloads, deletes or downloads the files it loaded. Deleting a control now drops its result tables (API
callers: see item 3), leftover temporary tables can be reviewed and dropped, the web UI has a dark mode, comparison
criteria get the formula mode of reconciliations, and the data analysis draws random samples, shows the exact
counterpart of a discrepancy and switches between a run's datasets. The list pages show and keep their active
filters. A reconciliation whose key field is not unique no longer fails on the `DB` engine, and runs with incomplete
or unreliable results are flagged with a warning. The UI was also reviewed: the editors load on first visit,
keyboard and screen-reader access, one global stylesheet and shared code. There is no change to Rapo's own schema;
the `PL` engine's procedure must be redeployed. The upgrade steps are in the [migration instructions](README.md).

1. **Datasources page (PDI Core).** A new *Datasources* menu item lists and edits the datasources of the PDI Core
   file loader (`PDI_CORE_DS_CONFIG`) with their tables (`PDI_CORE_DS_TABLES`). It shows where Rapo's database user
   can read them, in its own schema or through synonyms; without write or delete grants it is read-only.
   - **List:** ID, name, input directories, lane (`ISACTIVE`), mask, retention, max files per cycle, subdirectory scan
     and the loads of the last 24 hours. The lane chip switches the lane at once, with *Undo*; disabled datasources
     are dimmed and show lane `0`. Badges under the directories flag *No tables*, *No retention*, missing or unreadable
     directories, an invalid mask, *Stalled* and *Errors 24h*; the header counts the datasources per lane and per
     issue (whatever the filters; a click filters by it; issues with no datasource are hidden). The incoming files are
     counted on the Files page (*Incoming*), not here. The row menu has Edit, Clone, the file lists, *Create input
     directory*, *Set lane*, and *Delete* for a disabled datasource (links go; file log and tables stay).
   - **Editor** (`/edit-datasource/<id>`), like the control editor: tabs *Main*, with the boxes *General*, *Input
     files* (each directory with whether it exists; matched, all and clean-up file lists, searchable and exportable;
     the masks tried on the directories in the background and as you type) and *Processing*; *Retention*, with the
     boxes *Files* (archive, error and duplicate directories, days kept), *Tables* (linked tables with their
     partitioning from the dictionary and warnings; a table another datasource already retains says so, with a link to
     it and its key and days, and *Copy* fills them in) and *Explore* (a tree of the saved archive, error and
     duplicate directories, each folder read from this server when opened, with its files' size, date, owner and mode,
     thousands of files scrolled smoothly); *File log*; and last *Need attention*, shown only when the saved
     datasource has issues: missing directories with *Create*, read-only or unreadable ones, an invalid pattern,
     *Stalled*, errors in the last 24 hours, no tables or no retention, each with a way to fix or look at it (the same
     issues as the list's badges; a red folder icon on Main or Retention opens it). Fields have plain labels (*File
     name pattern*, *Scheduler lane*, *Keep files gzipped*, ...) with an icon and a tooltip naming what they do,
     Yes/No drop-downs instead of switches, and fixed widths: directories and patterns 600 px (as is *Source name*,
     with *Scheduler lane* and *ID* above it), so adding or removing a directory never resizes the rows. *Check regex*
     next to each pattern checks it with the server's regular expressions and tries it on sample file names, also
     before the first save; *Matching files*, *All files* and *Clean-up files* are at the bottom of *Input files*. Old
     links to `?tab=files` or `?tab=processing` open *Main*, `?tab=archive` *Retention*. *Clone* starts disabled
     without partition settings; a rename asks first; a save changed meanwhile by others (also by SQL) is refused with
     *Reload* or *Overwrite*.
   - **Files are read from this server's file system** (local or mounted as PDI Core sees them): the incoming files of
     the active datasources are counted every `scan_interval` seconds while the UI is open, by a small child process,
     so a slow or hung network file system never holds up the UI. Opening a datasource does not touch the file
     system; listings stop after `list_budget_seconds`. A mask must match the whole file name, as in PDI Core.
   - New optional `rapo.ini` section `[DATASOURCES]`: `scan_interval` (60), `scan_max_entries` (200000),
     `scan_budget_seconds` (20), `list_max_files` (10000), `list_budget_seconds` (10), `clean_max_bytes` (1024),
     `dir_mode` (2775), `stalled_minutes` (60), `lock_stale_minutes` (30), `file_download` (True),
     `max_download_mb` (500).
   - API: `get-ds-list`, `get-ds-status`, `get-ds-config`, `check-ds-directories`, `save-ds-config`, `set-ds-active`,
     `delete-ds-config`, `count-ds-file-log`, `get-ds-files`, `check-ds-mask`, `create-ds-directory`,
     `list-ds-archive`, `get-ds-table-facts` (`partitioned_by` with each datasource's key and days),
     `get-ds-file-log`, `get-ds-file-log-text`; `info` reports `datasources_*`; live event `datasources:changed`.

2. **Files page (PDI Core file log).** A new *Files* menu item: the file log (`PDI_CORE_FILE_LOG`) of one day, like
   Results is for control runs (`/files?date=`).
   - **By datasource:** the status columns, the workflow read back from its end: *Success*, *Started*, *Waiting*
     (always shown) and *Incoming* (today only), then *Error*, *Recycle*, *Reload*, *Duplicates* and the rarer
     statuses (only when the day has such files); then records read / written / rejected, runtime, last success and
     *Trend* (the day's files against a week earlier); every header explains its column on mouse-over. There is no
     *Files* column: the datasource's name opens all its files of the day (the table scrolls sideways when wider
     than the page), with *Silent*, *Drop*, *Errors* and *Log name differs* badges. Header totals and status and duplicate chips filter it;
     an hourly heatmap by lane filters by hour; *Find file* searches the day's file names across all datasources.
   - **Issue chips in the header:** after the status chips, *Silent* and *Drop* with the number of the day's
     datasources that have them and, on today, *Stalled* (the Datasources page's issue, as it is now; also shown under
     the datasource names and offered by the *Issues* filter). Counted whatever the filters; a click filters by it, so
     the count is the rows it gives; an issue with no datasource is hidden. On another day *Stalled* is not shown and
     its filter is dropped. The other datasource issues are counted on the Datasources page.
   - **Lanes** (`PDI_CORE_STATE`): a chip per lane shows whether a core_load run holds it, red when older than
     `lock_stale_minutes`; clicking a held lane removes the lock after a confirmation, clicking an idle one filters the
     page by that lane. *Lock all lanes* / *Unlock all lanes* set and remove the `LOCK` record. When the table cannot be read, the page says why.
   - **A datasource's files** (`/files-log/<id>`), laid out like Results, with the heatmap, filters and sorting by any
     column. Selected files can be **Recycled** (SUCCESS or ERROR), **Reloaded** (SUCCESS) or **Deleted** (any
     status): Rapo sets the status and PDI Core does the work. Recycle and Reload need the archived file; Delete also
     deletes it, which the confirmation warns about. The editor's File log is the same table, with the same selection
     and actions.
   - **Download** of selected files (SUCCESS or ERROR whose archived file is kept): the file PDI Core kept
     (`OUTPUTFULLFILENAME`), one file as it is, several as one ZIP `<SOURCENAME>_<YYYYMMDD>.zip` with a `MISSING.txt`
     naming the files left out and why. Files are read from this server's file system and only within the archive,
     error or duplicate directory of their datasource; at most 500 files and `max_download_mb` at once. Each download
     is written to the server log. New `[DATASOURCES]` options `file_download` (True; False hides the button) and
     `max_download_mb` (500; the download is held in the browser's memory before it is saved).
   - **The counts open the files behind them.** On the Files page, a datasource's *Files*, status and *Duplicates*
     numbers (and its name) open its file log filtered to exactly those files: the status clicked, or the page's
     status filter, its hour and, for Duplicates, only duplicates (`/files-log/<id>?status=&hour=&dup=`). Such a link
     replaces the file log's kept filters; the file log's filters are written back into its URL, so a reload or Back
     keeps them. *Incoming* opens the datasource's matching input files in a dialog
     on the Files page (the list the Datasources page opens), without leaving the page. **Behavior change:** clicking a status count no longer filters
     the Files page; the status chips of the header still do.
   - API: `get-files-day`, `search-files`, `set-file-status`, `download-ds-files`, `get-pdi-state`, `remove-lane-lock`,
     `set-global-lock`; `info` reports `datasources_file_actions`, `datasources_file_download` and
     `datasources_state*`; `datasources:changed` kinds `state`, `files`.

3. **Deleting a control drops its result tables.** Before, only the configuration row was deleted, and the
   `RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_<name>` tables stayed behind as orphans. The confirmation now names the
   tables, with *Also drop the result tables* ticked; untick it to keep them. A control with a run in progress can
   no longer be deleted. If a table cannot be dropped, the control is kept and the message says which tables were
   already dropped.
   - **Behavior change for API callers:** `delete-control` drops the tables by default (`drop_tables`, default
     true) and answers the dropped names in `dropped`. Scripts that relied on the tables being kept must pass
     `drop_tables=false`.

4. **Temporary tables on the Controls page.** A run drops its `RAPO_TEMP_*` tables only when it ends *Done*
   without debug mode, so failed, canceled and debug runs left them behind for good. The Controls header shows
   *N temporary tables · X MB* beside the orphaned tables; it opens a list by run (control, status, start, tables,
   size) with *Drop* per run and *Drop all* (debug runs only with *Include debug runs*), plus leftover scratch tables
   of schema checks. Runs in progress are never listed or dropped. Only tables and materialized views of the own
   schema named as Rapo creates them (current and legacy kinds) are recognized and dropped, each by its exact name;
   other `RAPO_TEMP_*` objects are listed under *Not recognized* for manual handling.
   - Removed: *Drop temporary tables* from the run menus of Results and the control editor, and *Show error log*
     from Results (*Show full log* shows the error).
   - **API:** `get-temp-tables` and `drop-temp-tables` are new; `delete-control-temporary-tables` is removed.

5. **Fix: reconciliation failed with ORA-30926 when its key field is not unique (DB engine).** Rapo does not
   require `source_key_field_a|b` to be unique, but a key value shared by rows of a square (fuzzy) cluster made the
   `match_duplicates` step fail with *ORA-30926: unable to get a stable set of rows in the source tables*. The `DB`
   engine now completes. Both engines still identify rows by the key, so such rows get their results **repeated**
   (a key shared by k rows gives up to k² result rows, with possibly different verdicts, and the two engines differ
   for them): the run now says so (item 6). **Check** the controls flagged with it and choose a unique key field; on
   a table, a key field name that is not one of its columns makes Rapo use `ROWID` (as it already does for sources
   without the column).

6. **Run warnings.** A run whose results are incomplete or unreliable now ends *Done* with a warning: a line
   `Warning: ...` in the run's messages (*Run details → Messages* of the run log dialog) and a WARNING in its log.
   - **Key field not unique:** `Key field TAG of source A (VIDS_AVSTX_LX) is not unique: N values are shared by M of
     T rows ...`, checked on the fetched rows (`DB`) or the rows of the window (`PL`); keys taken from `ROWID` are
     not checked.
   - **`correlation_limit` reached:** the remaining rows were left uncorrelated and are reported as losses. The `PL`
     engine logged this before; the `DB` engine now warns too.
   - **Approximate matching:** a `PL` key group had more rows within reach than `max_candidates` (logged before).
   - **Output limit reached:** `output_limit` (or `output_limit_a|b` of a reconciliation) cut the saved rows:
     *Output limit of 1000 reached: 1000 of 5230 issues of side A written*. Before, a reconciliation cut them
     silently and the other types logged an INFO.
   - **Results** shows an amber warning icon beside the status of a flagged run, which opens its run log dialog, and
     a *Warnings (N)* chip in the day totals that filters the flagged runs.
   - **API:** `get-control-runs` rows carry `has_warning`.
   - The `PL` engine's procedure `RAPO_USAGE_RULE` changed: redeploy it (see the migration instructions).

7. **Engine on the Controls page.** Reconciliation controls show a *DB engine* or *PL engine* chip among their
   attributes; clicking it, or picking it under *Control attributes*, filters by engine. Other types always run on
   the `DB` engine and show none.

8. **Dark mode.** A button in the header cycles the theme: *Automatic* (follows the operating system, the default),
   *Light* and *Dark*. The choice is kept by the browser (`rapo_theme`). The pages, dialogs, tables, chips, the
   analysis charts and the SQL editors have dark variants; the colors of both themes are the `--rapo-*` variables of
   `src/styles/app.sass`, so a component needs no rules of its own. The light theme looks as before.

9. **Formula mode in comparison (CMP) criteria.** Each *Match criteria* and *Mismatch criteria* row has a *Formula*
   Yes/No, as in reconciliations: with *Yes*, Field A and Field B are SQL expressions instead of column names, the
   fetched source A as `a.` and source B as `b.`, e.g. `'0' || substr(a.MSISDN, 3)` = `b.MSISDN` or `round(a.AMOUNT)`
   ≠ `b.AMOUNT`. The run uses them as written in the join (match) and the `!=` conditions (mismatch), so an invalid
   expression fails the run with Oracle's message. Switching *Yes* on turns the chosen columns into `a.<column>` /
   `b.<column>`. Both boxes are now full width, one below the other, like the reconciliation ones.
   - `rule_config` and `error_definition` items take an optional `"formula_mode": true` (missing = false); existing
     controls run unchanged. The comparison SQL now names the fetched tables `a` and `b`.
   - Switching *Formula* off, in CMP and REC criteria alike, turns a formula that is only `a.<column>` / `b.<column>`
     back into that column; any other formula is cleared, as before.

10. **Random samples.** A sample was the first records of the dataset as the database returned them, usually in
   the order they were loaded, so it could stand for one partition or one load batch only. A sample is now drawn at
   random by default: the records are read in random order (`order by dbms_random.value`), so the sample is uniform
   at any size, and *Extend* keeps it so. The sample bar has a *Random / First rows* switch; *First rows* is the
   former behavior and is faster on large datasets, since for a random sample Oracle sorts the whole dataset before
   the first row arrives (the progress shows *Shuffling the dataset*). A change starts a new sample, like a
   database filter. The choice is kept in the URL (`rnd=0` for first rows), and a comparison's sample B is drawn
   the same way. *Copy SQL* still copies the plain statement.
   - API: `analysis-start` takes `random` (default true); `meta.random` says which was used.

11. **Counterpart by `RAPO_DISCREPANCY_ID`.** A discrepancy row of a reconciliation carries in `RAPO_DISCREPANCY_ID`
   the key field (`Source key field`) of the record of the other side it was matched with. The counterpart dialog
   now shows that record first, under *Matched record*, from the other side's result table and from its datasource
   for the run's window. The records with the same correlation key are still listed below it. A row without a
   discrepancy ID (a Loss, a fetched record) shows the correlation-key lookup only, as before.
   - API: `analysis-counterpart` answers `pair` `{key_field, value, results, source}`, or null.

12. **Nullability is no schema drift.** A result-table column that is `NOT NULL` while the datasource's is
   nullable, or an old column that is `NOT NULL` but no longer filled, no longer shows *Schema drift* on the
   Controls list, *Schema changes* in the editor, or counts toward Update schema. Each run already makes such
   columns nullable before it saves, so results are always written. Drift now means only a missing or too narrow
   column (Update schema) or an incompatible type (Recreate schema). The schema dialog lists *Nullable* columns
   only with *Show all columns*. The bulk check also no longer differed from the editor on primary-key columns,
   whose `NOT NULL` a result table does not copy, nor on invisible datasource columns: the dictionary lists them,
   but runs never copy them, so the Controls list showed e.g. *1 column change(s) for Update schema* for good while
   the editor showed nothing. A slow `get-schema-drift` answer can no longer overwrite a newer one either.
   - **The list and the editor agree.** The list's check reads column types from the dictionary, but a view column
     that is an expression can be typed there differently from the table a run creates (e.g. `VARCHAR2(803)` in
     bytes while a run creates fewer characters), so a control was flagged although the editor offered nothing to
     update. Every table the list flags is now confirmed by the editor's exact check before it is shown; the
     confirmation is reused until the datasource, the result table or the control changes.
   - **Datasource missing.** A control whose datasource does not exist showed no badge at all; it now shows a red
     *Datasource missing* badge (with the name in its tooltip) and can be filtered by it under *Control attributes*.
     API: `get-schema-drift` level `source_missing`.
   - Datasources that are synonyms are now checked as the table or view they name, instead of being skipped.

13. **Fix: reconciliation results after a schema update (since v0.8.3).** *Update schema* and the schema update of a
   run add a column at the end of the result table, after `RAPO_PROCESS_ID`. A reconciliation (REC, both engines)
   saved its A/B results by position with `RAPO_PROCESS_ID` last, so the new column and `RAPO_PROCESS_ID` got each
   other's values. The run failed, e.g. with `ORA-01438: value larger than specified precision allowed for this
   column` for a short `NUMBER`, or, for a plain `NUMBER` column, saved its rows with that column's value (often
   NULL) as `RAPO_PROCESS_ID`, so they were missing from the run's results. A table column the run no longer fills
   failed the save too. REC now matches the columns by name, as ANL, CMP and REP already did.
   - The `ALTER TABLE` of *Update schema* and of a run wrote column names lowercase and unquoted, which failed with
     `ORA-00904` for a mixed-case or reserved name (`"Amount"`, `SIZE`, `LEVEL`). Such names are now quoted.
   - **Check:** the REC result tables with columns after `RAPO_PROCESS_ID` were exposed. Runs that ended *Done*
     since those columns were added may have saved rows under a wrong process ID; re-run them after the upgrade:
     ```sql
     select c.table_name, c.column_name
     from user_tab_columns c
     join user_tab_columns p on p.table_name = c.table_name and p.column_name = 'RAPO_PROCESS_ID'
     where regexp_like(c.table_name, '^RAPO_RES[AB]_') and c.column_id > p.column_id;
     ```

14. **Fix: the Scheduler's running list named the wrong control.** A run's upstream runs (chain-rules), iterations and
   cascade run in the same job process, one after the other. The list showed the run ID of the one running now, but
   always the name of the control the job was started for, so e.g. the ANL upstream of a reconciliation never
   appeared. It now shows the control of the run in progress with its type chip, and *for <control>* when that run
   belongs to another control's job. `scheduler-status` reports `control_type` and `job_control_name` too.

15. **Fix: iterations and cascade skipped when the postrun hook fails.** A failing
   `rapo_postrun_control_hook` (e.g. an invalid `RACS_KPI_PKG`) ended the run's job process right after the
   run was *Done*, so its iterations and cascade never ran, and the error was lost with the process. The error is
   now written to the run log and the run is flagged `Warning: Postrun hook failed: ORA-...` (it stays *Done*);
   iterations and cascade go on. Likewise an unexpected failure of one run of a job, or of one iteration or
   cascaded control, is logged and no longer skips the ones after it.

16. **Active filters shown on the list pages.** While any filter is set (the header search included), Controls,
   Results, KPI types, Scheduler, Datasources, Files and the file log show a row of small chips under the title: first
   an orange *Filter* badge, then the active filters as light orange chips, each removable with its ✕. The badge's
   ✕ removes them all (the sort stays), replacing the former *Clear filters* button, which also reset the sort. The
   count reads "12 of 340 Controls" (Results, Files, the file log and Scheduler show "12 of 40" in the badge). On
   Scheduler each tab has its own row under its filter fields, and the tab label a dot while it is filtered.
   The filters, the sort and the header search are now **kept for the browser session**: they survive leaving the
   page, a reload and signing in again, until the browser tab is closed. KPI types and Scheduler used to start
   empty on every visit. Each browser tab keeps its own.

17. **Switch dataset on the analysis page.** The page title has a switch between the run's datasets: *Source A*,
   *Source B*, *Discrepancies A*, *Discrepancies B* (what the control type has; none for a report), each with the
   run's count. An empty one is disabled. A switch opens the other dataset of the same run, and Back returns. The
   tab, the sampling, the search, and the Data tab's filters, sort and group-by go along; those on a column the other
   dataset does not have are dropped. A database filter, a profile scope and a comparison are left behind, since
   they belong to one dataset.
   - API: the dataset `meta` (`analysis-start`, `get-run-dataset-sql`) has `datasets`, `[{dataset, kind, side,
     count}]`.

18. **Lazy-loaded editors.** The control, datasource and KPI type editors and the file log page are separate chunks
   loaded on first visit, so CodeMirror and the editor boxes are no longer part of the first page load (the vendor
   bundle drops from about 870 KB to 440 KB).

19. **Accessibility.** Every icon-only button has an accessible name, sortable column headers report `aria-sort`, and
   the Group by toggle reports its state. Clickable elements that were not buttons (sortable headers, run numbers on
   Results and in the editor's run log, analysis rows and cards, heatmap cells, the archive tree, code variables) can
   be reached with Tab and activated with Enter or Space, and every focused element shows a teal ring. The token
   box's show/hide icon works again (it used a Material icon name). Muted grey and teal text, and white text on
   amber/orange chips, are darker to be readable; the heatmap's error cells have a corner mark and the trend's
   current run a dark outline, so neither depends on color alone. Column names in analysis chart tooltips are escaped.

20. **Icons, headers and analysis states.** The remaining Material icons (menu, close, add, search, clock) are Font
   Awesome 5 like the rest of the UI and the Material icon font is no longer loaded. The Controls and KPI types titles
   follow the same header layout as the other list pages,.
   Empty states in the analysis panels share one look; a failed run trend, a failed page of rows or a section that
   cannot be computed now says so with a *Retry* button instead of showing a skeleton or "No rows match the filters"
   forever. The SQL filter and Copy SQL buttons are hidden, not disabled, until their data exists.

21. **SQL and Data analysis from the editor's run log.** The Fetched, Discrepancies and error-level numbers of the
   run log open the same menu as on Results (click or right-click): *Copy SQL to clipboard* and *Data analysis*.
   The copied SQL is now the server's, as on Results. Before, the editor built the fetched SQL in the browser from
   the form, which left out chain-rule sides and `{variables}` and followed unsaved changes.

22. **Hide all columns.** The Data tab's *Columns* menu has *Hide all* beside *Show all*, and a search box. While
   the search is set, the buttons show or hide the found columns only, so you can hide everything and then show the
   few columns you need. With no column shown, the table says so, and Export is disabled. **Key fields** shows only
   the columns the control's criteria use on this side (a REC's match and mismatch fields, a CMP's match and
   mismatch columns, the columns an ANL's error and case definitions name; formulas included), its date and key
   fields and every `RAPO_` column, and hides the rest. The page's text boxes and drop-down lists now have the
   height of every other form, and its tabs show the icon beside the title.

23. **"Checking schema…" in the control editor.** The editor compares the result tables with the datasource when a
   control is opened, after a change of its datasource or output columns, and after Apply, Update schema, Recreate
   schema or dropping an orphan. Over large or complex views this can take a while, and until it answered the footer
   showed nothing, as if the schema matched while the *Schema drift* badge of the Controls list said otherwise. The
   footer now shows *Checking schema…* with a spinner until the answer comes. A re-check after a run keeps the
   notice it has meanwhile.

24. **Fix: "The run trend could not be loaded. 422" on leaving the page.** The analysis page stays alive in the
   background, and its run trend reloaded with the parameters of the next page's route as you left it. The trend
   and the SQL filter now follow the page's own dataset.

25. **Shared code and lists.** The copies of small helpers are gone: one `formatBytes`, one download-a-file and one
   copy-and-notify routine, one run-start call for the Run dialog and Re-run, one day-navigation helper for Results,
   Files and the file log, the KPI statement check shared by the KPI editor and the control's KPI box, one alert-label
   table and one base ECharts option for the analysis charts. Confirmations all use the same Quasar dialog (the
   separate Yes/No dialog is removed); *Recreate schema* and *Delete KPI type* now name the control or type in its
   title and have a red action button. The KPI types page is a virtual-scroll list with a sticky header, like Controls,
   and stays fast with thousands of rows.

26. **Results and Controls lists.** The day totals of Results read **ANL** (26), **Done** (164): the label bold, the
   count in brackets; the "25 controls · 190 runs" counts are no longer bold. On Controls, the control name is a link
   to its editor, like the datasource names (the version link under it stays). The Controls header also counts the
   controls flagged *Datasource missing*, *Schema drift* and *No KPI* in the whole list (whatever the filters), as
   chips like the Results totals; a click filters the list by that attribute. On the Files page the day's figures
   (files, read, written, rejected, runtime) are now a line under the status chips, both right-aligned by the title;
   Results does the same, with its type, status and *Warnings* chips above a line of the day's figures:
   "14 controls · 72 runs · 1 failing · 173k fetched · 0:02:46 runtime". *Failing* (red, only when there are any)
   counts the controls whose latest run of the day ended in error and names them in its tooltip; *fetched* sums
   sides A and B of all runs (the exact number in its tooltip); *runtime* sums the runs' runtimes and names the
   longest run.

27. **Page names on the editors and the file log.** The control, KPI type and datasource editors and a datasource's
   file log are titled *Edit control* / *New control*, *Edit KPI type*, *Edit datasource* and *Files log*, followed
   by the type chip and name, smaller. A control opened from a KPI type's *Controls* tab shows its *KPIs* tab, and
   one opened from the Scheduler (*Upcoming*, *History*) its *Scheduler* tab (`/edit-control/<id>?tab=kpi|scheduler`;
   any tab the control shows can be named).

28. **Scheduler tables reach the bottom of the window.** *Upcoming* and *History* now use the whole height below
   the tabs, as the Files page does, and scroll inside the table from there. The *Scheduler* menu item moves up,
   after *KPI types*, spaced from it and from *Files*; the header's clock button still opens the page too.

29. **Control groups.** The control editor's *Main* tab has a *Control group* field (`RAPO_CONFIG.CONTROL_GROUP`)
   beside the name and alias: type to pick one of the groups already in use, or type a new one. Spaces around it are
   removed, an empty field clears the group, and a group typed in another case takes the existing spelling ("tests"
   becomes "Tests"). The Controls page has a *Control group* filter next to *Control name* listing the groups in use
   and *No group*, and each control with a group shows it as a chip under its description; clicking the chip filters
   by that group. No schema change: the column already existed and is kept in the control's versions.
   The *System* / *System A* / *System B* fields (`SOURCE_TYPE_A|B`) work the same way, offering the systems in use
   on either side. The Controls page's *System* filter offers those systems as you type: a system picked (or typed
   in full) matches controls whose system A or B is exactly it; other text matches as a substring, ignoring case, as
   before.

30. **Datasources layout and one mono font.** Paths, patterns, code (the SQL editors, the run and file logs,
   Instance details) and the numbers of tables and number inputs now use **Roboto Mono**, bundled with the UI next
   to Roboto (the app font), so every browser shows the same fixed-width font instead of the system's `monospace`;
   numbers in text, chips, titles and tooltips, and dates, keep the page font. Table numbers are 12px, and the
   *Fetched* and *Discr.* columns of Results are wider, so 10-digit process IDs and counts in the millions fit.
   - **Datasources page:** clicking an input directory opens the datasource's *All files* list. The *Files mask*
     column is gone: the mask is shown in light blue under the input directories, above the issue chips, in the
     column now named *Input files* (a longer one ends in an ellipsis, the whole mask in its tooltip). New *Zipped*
     and *Parallel* columns before *Subdirs* show an icon where the flag is set. *Last 24h* is now *Files 24h*: only
     the number of files loaded, sorted by it; the last load time and the other counts are in its tooltip.
   - **Datasource editor:** *Source name* sits in one row with the lane and the ID. *Scan subdirectories* and *Max
     files per cycle* move from *Input files* to *Processing*, which now has two rows: scan, files per cycle, load
     in parallel; then gzipped, duplicate handling, rejected records. On *Retention* the archive, error and
     duplicate directories share one row. The *Check file name pattern* dialog is wider (1100px) and keeps sample
     names on one line.

31. **Cleanup and shared styles.** Unused exports, props and empty style blocks are removed and a few typos and
   misnamed methods fixed ("Mis-match" is now "Mismatch"; the analysis header reads "Fetched" instead of "Source").
   The classes the list pages duplicated (`.sortable`, `.text-mono`, `.day-btn`, `.name-filter`, `.row-inactive`,
   the sticky editor action bar and others) now live in `src/styles/app.sass`, and the brand colors are
   `--rapo-*` CSS variables used by the component styles.

32. **Header tooltips.** Every column header of every table (the list pages, the editors' tables and run log, the
   dialogs and the data analysis tables) explains its field on mouse-over, e.g. *PV* on Results is the value the
   Prerequisite SQL returned, *Err. lvl A [%]* the discrepancies of A as a percentage of the records fetched. All
   table headers are now compact (28px), as on Results: Controls, KPI types, Datasources and the dialogs had 48px.
