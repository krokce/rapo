# Rapo v0.8.4 Change Log

## Annotation
This release corrects and completes the data analysis of v0.8.3: samples are drawn at random, the counterpart of a
discrepancy shows the record it was matched with, the page switches between a run's datasets, and the editor's run
log opens the same SQL and analysis menu as Results. Deleting a control now drops its result tables, and the list
pages show which filters are active. New Datasources and Files pages edit the PDI Core file loader's datasources and
show, recycle, reload, delete or download the files it loaded. There is no change to Rapo's own schema.
The upgrade steps are in the [migration instructions](README.md).

1. **Datasources page (PDI Core).** A new *Datasources* menu item lists and edits the datasources of the PDI Core
   file loader (`PDI_CORE_DS_CONFIG`) with their tables (`PDI_CORE_DS_TABLES`). It shows where Rapo's database user
   can read them, in its own schema or through synonyms; without write or delete grants it is read-only.
   - **List:** ID, name, input directories, lane (`ISACTIVE`), mask, retention, max files per cycle, subdirectory scan,
     the *Incoming* files (in the input directories, not yet picked up) and the loads of the last 24 hours. The lane
     chip switches the lane at once, with *Undo*; disabled datasources are dimmed and show lane `0`. Badges under the
     directories flag *No tables*, *No retention*, missing or unreadable directories, an invalid mask, *Stalled* and
     *Errors 24h*. The row menu has Edit, Clone, the file lists, *Create input directory*, *Set lane*, and *Delete*
     for a disabled datasource (links go; file log and tables stay).
   - **Editor** (`/edit-datasource/<id>`), like the control editor: tabs *Main*, with the boxes *General*, *Input
     files* (each directory with whether it exists and *Create*; matched, all and clean-up file lists, searchable and
     exportable; the masks tried on the directories in the background and as you type) and *Processing*; *Archive*
     (the directories, and *Explore*: a tree of the saved archive, error and duplicate directories, each folder
     read from this server when opened, with its files' size, date, owner and mode, thousands of files scrolled
     smoothly); *Retention* (linked tables with their partitioning from the dictionary and warnings; a table another
     datasource already retains says so, with a link to it and its key and days, and *Copy* fills them in); and
     *File log*. Old links to `?tab=files` or `?tab=processing` open *Main*. *Clone* starts disabled without
     partition settings; a rename asks first; a save changed meanwhile by others (also by SQL) is refused with
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
     `delete-ds-config`, `count-ds-file-log`, `get-ds-files`, `create-ds-directory`,
     `list-ds-archive`, `get-ds-table-facts` (`partitioned_by` with each datasource's key and days),
     `get-ds-file-log`, `get-ds-file-log-text`; `info` reports `datasources_*`; live event `datasources:changed`.
2. **Files page (PDI Core file log).** A new *Files* menu item: the file log (`PDI_CORE_FILE_LOG`) of one day, like
   Results is for control runs (`/files?date=`).
   - **By datasource:** files, a column per status of the day, duplicates, *Incoming* (today), records read / written /
     rejected, runtime, last success and the change against a week earlier (the table scrolls sideways when wider
     than the page), with *Silent*, *Drop*, *Errors* and *Log name differs* badges. Header totals and status and duplicate chips filter it;
     an hourly heatmap by lane filters by hour; *Find file* searches the day's file names across all datasources.
   - **Lanes** (`PDI_CORE_STATE`): a chip per lane shows whether a core_load run holds it, red when older than
     `lock_stale_minutes`; clicking removes the lock after a confirmation. *Lock all lanes* / *Unlock all lanes* set
     and remove the `LOCK` record. When the table cannot be read, the page says why.
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
     keeps them. *Incoming* opens the datasource's editor with the matching files listed
     (`/edit-datasource/<id>?tab=files&list=match`). **Behavior change:** clicking a status count no longer filters
     the Files page; the status chips of the header still do.
   - API: `get-files-day`, `search-files`, `set-file-status`, `download-ds-files`, `get-pdi-state`, `remove-lane-lock`,
     `set-global-lock`; `info` reports `datasources_file_actions`, `datasources_file_download` and
     `datasources_state*`; `datasources:changed` kinds `state`, `files`.
3. **Results and Controls lists.** The day totals of Results read **ANL** (26), **Done** (164): the label bold, the
   count in brackets; the "25 controls · 190 runs" counts are no longer bold. On Controls, the control name is a link
   to its editor, like the datasource names (the version link under it stays).
4. **Deleting a control drops its result tables.** Before, only the configuration row was deleted, and the
   `RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_<name>` tables stayed behind as orphans. The confirmation now names the
   tables, with *Also drop the result tables* ticked; untick it to keep them. A control with a run in progress can
   no longer be deleted. If a table cannot be dropped, the control is kept and the message says which tables were
   already dropped.
   - **Behavior change for API callers:** `delete-control` drops the tables by default (`drop_tables`, default
     true) and answers the dropped names in `dropped`. Scripts that relied on the tables being kept must pass
     `drop_tables=false`.
5. **Active filters shown on the list pages.** Controls, Results, KPI types, Scheduler, Datasources and Files show an
   orange *Filter* badge while any filter is set, the header search included, and the active filters under it as
   light orange chips, each removable with its ✕. The badge's ✕ removes them all (the sort stays), replacing the
   former *Clear filters* button, which also reset the sort. The count reads "12 of 340 Controls" (Results and
   Scheduler show "12 of 40" in the badge). On Scheduler each tab has its own badge in its filter row, and the tab
   label a dot while it is filtered.
   The filters, the sort and the header search are now **kept for the browser session**: they survive leaving the
   page, a reload and signing in again, until the browser tab is closed. KPI types and Scheduler used to start
   empty on every visit. Each browser tab keeps its own.
6. **Random samples.** A sample was the first records of the dataset as the database returned them, usually in
   the order they were loaded, so it could stand for one partition or one load batch only. A sample is now drawn at
   random by default: the records are read in random order (`order by dbms_random.value`), so the sample is uniform
   at any size, and *Extend* keeps it so. The sample bar has a *Random / First rows* switch; *First rows* is the
   former behavior and is faster on large datasets, since for a random sample Oracle sorts the whole dataset before
   the first row arrives (the progress shows *Shuffling the dataset*). A change starts a new sample, like a
   database filter. The choice is kept in the URL (`rnd=0` for first rows), and a comparison's sample B is drawn
   the same way. *Copy SQL* still copies the plain statement.
   - API: `analysis-start` takes `random` (default true); `meta.random` says which was used.
7. **Counterpart by `RAPO_DISCREPANCY_ID`.** A discrepancy row of a reconciliation carries in `RAPO_DISCREPANCY_ID`
   the key field (`Source key field`) of the record of the other side it was matched with. The counterpart dialog
   now shows that record first, under *Matched record*, from the other side's result table and from its datasource
   for the run's window. The records with the same correlation key are still listed below it. A row without a
   discrepancy ID (a Loss, a fetched record) shows the correlation-key lookup only, as before.
   - API: `analysis-counterpart` answers `pair` `{key_field, value, results, source}`, or null.
8. **Switch dataset on the analysis page.** The page title has a switch between the run's datasets: *Source A*,
   *Source B*, *Discrepancies A*, *Discrepancies B* (what the control type has; none for a report), each with the
   run's count. An empty one is disabled. A switch opens the other dataset of the same run, and Back returns. The
   tab, the sampling, the search, and the Data tab's filters, sort and group-by go along; those on a column the other
   dataset does not have are dropped. A database filter, a profile scope and a comparison are left behind, since
   they belong to one dataset.
   - API: the dataset `meta` (`analysis-start`, `get-run-dataset-sql`) has `datasets`, `[{dataset, kind, side,
     count}]`.
9. **SQL and Data analysis from the editor's run log.** The Fetched, Discrepancies and error-level numbers of the
   run log open the same menu as on Results (click or right-click): *Copy SQL to clipboard* and *Data analysis*.
   The copied SQL is now the server's, as on Results. Before, the editor built the fetched SQL in the browser from
   the form, which left out chain-rule sides and `{variables}` and followed unsaved changes.
10. **Hide all columns.** The Data tab's *Columns* menu has *Hide all* beside *Show all*, and a search box. While
   the search is set, the buttons show or hide the found columns only, so you can hide everything and then show the
   few columns you need. With no column shown, the table says so, and Export is disabled. **Key fields** shows only
   the columns the control's criteria use on this side (a REC's match and mismatch fields, a CMP's match and
   mismatch columns, the columns an ANL's error and case definitions name; formulas included), its date and key
   fields and every `RAPO_` column, and hides the rest. The page's text boxes and drop-down lists now have the
   height of every other form, and its tabs show the icon beside the title.
11. **Fix: "The run trend could not be loaded. 422" on leaving the page.** The analysis page stays alive in the
   background, and its run trend reloaded with the parameters of the next page's route as you left it. The trend
   and the SQL filter now follow the page's own dataset.
12. **"Checking schema…" in the control editor.** The editor compares the result tables with the datasource when a
   control is opened, after a change of its datasource or output columns, and after Apply, Update schema, Recreate
   schema or dropping an orphan. Over large or complex views this can take a while, and until it answered the footer
   showed nothing, as if the schema matched while the *Schema drift* badge of the Controls list said otherwise. The
   footer now shows *Checking schema…* with a spinner until the answer comes. A re-check after a run keeps the
   notice it has meanwhile.
13. **Nullability is no schema drift.** A result-table column that is `NOT NULL` while the datasource's is
   nullable, or an old column that is `NOT NULL` but no longer filled, no longer shows *Schema drift* on the
   Controls list, *Schema changes* in the editor, or counts toward Update schema. Each run already makes such
   columns nullable before it saves, so results are always written. Drift now means only a missing or too narrow
   column (Update schema) or an incompatible type (Recreate schema). The schema dialog lists *Nullable* columns
   only with *Show all columns*. The bulk check also no longer differed from the editor on primary-key columns,
   whose `NOT NULL` a result table does not copy.
14. **Page names on the editors and the file log.** The control, KPI type and datasource editors and a datasource's
   file log are titled *Edit control* / *New control*, *Edit KPI type*, *Edit datasource* and *Files log*, followed
   by the type chip and name, smaller.
15. **Scheduler tables reach the bottom of the window.** *Upcoming* and *History* now use the whole height below
   the tabs, as the Files page does, and scroll inside the table from there.
16. **Fix: the Scheduler's running list named the wrong control.** A run's upstream runs (chain-rules), iterations and
   cascade run in the same job process, one after the other. The list showed the run ID of the one running now, but
   always the name of the control the job was started for, so e.g. the ANL upstream of a reconciliation never
   appeared. It now shows the control of the run in progress with its type chip, and *for <control>* when that run
   belongs to another control's job. `scheduler-status` reports `control_type` and `job_control_name` too.
