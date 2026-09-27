# Rapo v0.8.4 Change Log

## Annotation
This release corrects and completes the data analysis of v0.8.3: samples are drawn at random, the counterpart of a
discrepancy shows the record it was matched with, the page switches between a run's datasets, and the editor's run
log opens the same SQL and analysis menu as Results. Deleting a control now drops its result tables, and the list
pages show which filters are active. A new Datasources page edits the datasources of the PDI Core file-loading
framework and shows the files incoming for them, and a Files page shows the files PDI Core loaded per day and
datasource, with lane locks, and recycles, reloads or deletes files. There is no change to Rapo's own schema.
The upgrade steps are in the [migration instructions](README.md).

1. **Datasources page (PDI Core).** A new *Datasources* menu item, below Files and above Scheduler, lists the
   datasources of PDI Core (`PDI_CORE_DS_CONFIG`) and edits them, with their tables (`PDI_CORE_DS_TABLES`). It shows
   only where Rapo's database user can read these tables, in its own schema or through synonyms; without write or
   delete grants the page is read-only, or offers no deletion.
   - **List:** ID, name, input directories, `ISACTIVE`, mask, retention days, max files per cycle and subdirectory
     scan, plus the *Incoming* files (in the input directories, not yet picked up into the file log) and the loads of
     the last 24 hours (`PDI_CORE_FILE_LOG`). The `ISACTIVE` chip switches the scheduler lane at once (Disabled, the
     lanes in use, any other 1-9), with *Undo* in the notice; disabled datasources are dimmed. Badges flag *No
     tables*, *No retention*, a missing or unreadable input directory, a missing archive directory, an invalid mask,
     *Stalled* (active, and the oldest incoming file is older than `stalled_minutes`) and *Errors 24h*, under the
     input directories; each filters the list. The lane chip shows the lane number in bold, `0` for a disabled
     datasource. Header chips count the lanes and the incoming files like the day totals of Results, e.g. **Scheduler
     5** (145). The row menu has Edit, Clone, *Show matched files waiting*, *All files waiting in Input*, *Show
     clean-up files*, *Create input directory* and *Set lane*; *Delete* only for a disabled datasource (its tables'
     links go, its file log and tables stay).
   - **Editor** (`/edit-datasource/<id>`): tabs *Main*, *Input files*, *Processing*, *Archive*, *Retention* and
     *File log*, with Save / Apply / Cancel, unsaved-change guard and Ctrl+S like the control editor. Every field
     explains itself from the PDI Core documentation.
     - *Input files*: each input directory (`|`-separated) with whether it exists on this server and a *Create*
       button; *Matching files*, *All files* and *Clean-up files* lists (name, subdirectory, size, dates, age,
       owner, mode, flags: too young for PDI, deleted by the PDI clean-up, why a file is not picked up), searchable,
       sortable and exportable as CSV. The masks are tried on the directories as you type ("Matches 3 of 5 files").
     - *Retention*: the linked tables, picked from the schema or typed, with the partition key picked from the
       table's DATE columns and the days to retain and create in advance. Each row shows what the dictionary says
       (not found, partitioned by which column, how many partitions, from when to when) and warns when the key is
       not the partitioning column, or another datasource partitions the same table.
     - *File log*: the files loaded on one day, with status, sizes, times and record counts; a row opens the log
       text PDI Core wrote.
   - **Clone** starts disabled, named `<NAME>_COPY`, with the tables linked but without partition settings, which
     only one datasource of a table should have.
   - **Renaming** asks first, since PDI Core finds its transformation by the name, and offers to link the table of
     the new name instead of the old one.
   - **Concurrent changes:** a save is refused when the datasource or its tables changed since the editor loaded
     them (also by SQL), with *Reload* or *Overwrite*. The page follows changes by others live.
   - Every save, lane change and deletion through Rapo is written to the server log; no version history is kept.
   - **Incoming files are read from this server's file system**, so the input directories must be local or mounted
     as PDI Core sees them. They are counted for the active datasources in the background, only while the UI is
     open, every `scan_interval` seconds, each directory once and each file name once per distinct mask, by a small
     child process of the server, so that a slow or hung network file system never holds up the web UI (a child not
     answering in time is killed and started anew). Opening a datasource does not touch the file system: whether its
     directories exist comes from the last count (checked in the background, 5 s at most each, when not counted), and
     the masks are tried on the directories only when the *Input files* tab is opened. A file listing reads for
     `list_budget_seconds` (10) at most. A mask must match the whole file name (as in PDI Core); Java-only regular
     expression syntax is reported as an invalid mask.
   - New `rapo.ini` section `[DATASOURCES]`, all optional: `scan_interval` (60), `scan_max_entries` (200000),
     `scan_budget_seconds` (20), `list_max_files` (10000), `list_budget_seconds` (10), `clean_max_bytes` (1024),
     `dir_mode` (2775, octal, the mode of created directories), `stalled_minutes` (60).
   - API: `get-ds-list`, `get-ds-status`, `get-ds-config`, `save-ds-config`, `set-ds-active`, `delete-ds-config`,
     `count-ds-file-log`, `get-ds-files`, `create-ds-directory`, `get-ds-table-facts`,
     `get-ds-file-log`, `get-ds-file-log-text`; `info` reports `datasources_*`; live event `datasources:changed`.
2. **Files page (PDI Core file log).** A new *Files* menu item, just above Datasources: the file log
   (`PDI_CORE_FILE_LOG`) of one day, like Results is for control runs (`/files?date=YYYY-MM-DD`, Prev / Next / Today).
   - **By datasource:** lane, ID, name, the files, a column per file status the day has (Success, Error, Recycle,
     Reload, Waiting, ...), *Duplicates* (on days with any), *Incoming* (today only: the files in the input
     directories not yet picked up into the file log, unlike its WAITING status), records read / written / rejected,
     the summed runtime, the last SUCCESS, the throughput (median k records written per second of its SUCCESS files,
     the quartiles in the tooltip) and the change against the same weekday a week earlier (for today, up to the same
     time of day). Numbers are right-aligned in a monospace font. Badges under the name: *Silent* (active, no file,
     but files a week earlier), *Drop* (less than half), *Errors*, and *Log name differs* (the file log gives the
     SOURCEID another name than the configuration, so its files may belong to another datasource).
   - **Header:** the day's totals (files, duplicates, records, runtime) and a chip per file status plus
     **Duplicate** (n), e.g. **Success** (56,696), each filtering the datasources with such files.
   - **Heatmap** of the files per hour (the database's clock) above the filters, one row per lane and a total, an
     ERROR hour outlined in red. It follows the filters; clicking an hour filters the table by it.
   - **Filters:** datasource, lane, file status (only the statuses of the day), issues, hour and duplicates, kept for
     the browser session like the other pages' filters. **Find file** searches the file names of the day across all
     datasources (3 characters or more) and opens the file in its datasource's log, marked.
   - **Lanes:** a chip per lane shows whether a core_load run holds it (`PDI_CORE_STATE`, `LOAD_<lane>`), *Active since*
     in its tooltip, red when older than `[DATASOURCES] lock_stale_minutes` (30). Clicking it removes the lock after a
     confirmation, which warns when the lock is recent. *Lock all lanes* inserts the `LOCK` record (no core_load run
     starts while it exists, a banner says since when); *Unlock all lanes* removes it. `PDI_CORE_STATE` is read in
     Rapo's schema or through a synonym; when it cannot be read, the page says why (e.g. the grant behind a synonym is
     missing), and a synonym or grant added later is found within a minute, without a restart.
   - **A datasource's files** (`/files-log/<id>`), laid out like Results: title and day, the day's totals and status
     and duplicate chips, the same hourly heatmap (a row per status), the file name, status and duplicate filters,
     and the files, dates styled like the Start of Results, sortable by every column (the sort kept with the
     filters). Files can be selected (one by one or all shown); then **Recycle**, **Reload** and **Delete** appear.
     Rapo only sets the status; PDI Core does the work: RECYCLE deletes the records and loads the archived file
     again, RELOAD loads it again keeping the records, DELETE deletes the records **and the archived file** (a
     warning says so). RECYCLE takes SUCCESS and ERROR files, RELOAD SUCCESS files, both only when the archived file
     is kept (`OUTFILEDELETED = 0`); DELETE takes files of any status; other files are left alone and counted in the
     notice.
   - The File log of the datasource editor is the same table, more compact: status chips like Results, records in a
     monospace font, a *Duplicate* filter; the server moved to the file's details. Its search and filters are kept
     for the browser session and across days.
   - The pages follow new files, lane locks and incoming files live.
   - API: `get-files-day`, `search-files`, `set-file-status`, `get-pdi-state`, `remove-lane-lock`, `set-global-lock`;
     `info` reports `datasources_file_actions`, `datasources_state`, `datasources_state_write`,
     `datasources_state_delete`; `datasources:changed` has the kinds `state` and `files`.
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
5. **Active filters shown on the list pages.** Controls, Results, KPI types and Scheduler show an orange *Filter*
   badge while any filter is set, the header search included, and a small line of the active filters under it, each
   removable with its ✕. The badge's ✕ removes them all (the sort stays), replacing the former *Clear filters*
   button, which also reset the sort. The count reads "12 of 340 Controls" (Results and Scheduler show "12 of 40" in
   the badge). On Scheduler each tab has its own badge in its filter row, and the tab label a dot while it is
   filtered.
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
   few columns you need. With no column shown, the table says so, and Export is disabled.
11. **Fix: "The run trend could not be loaded. 422" on leaving the page.** The analysis page stays alive in the
   background, and its run trend reloaded with the parameters of the next page's route as you left it. The trend
   and the SQL filter now follow the page's own dataset.
