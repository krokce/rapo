# Rapo v0.8.6 Change Log

## Annotation
Rapo opens on a new **Dashboard**: what goes on in the instance at a glance and live (today's numbers against last
week, runs, scheduler, files, KPIs and health as donuts, strips and small trends over 24 hours, 7 or 30 days), the instance health keeps a week of history across restarts, and the UI loads faster. A file of the file log can be viewed in the browser, however large, and searched as a whole on the server. Files can
be uploaded into a datasource's input directory from the file log and the datasource editor, and the records a
file loaded are shown below it or on the Data analysis page. A binary file is shown as ASN.1 (BER, DER, CER): its
tree of tags, named by an uploaded grammar (TAP, RAP, NRTRDE, 3GPP CDRs, a vendor's own), beside its bytes. Data
analysis and Discrepancy analysis are redesigned as single pages that lead with what matters and open in under a
second. The release adds three tables (`rapo_viewer_config`, `rapo_file_summary`, `rapo_health_minute`) and one Python
package (`asn1tools`), and drops one (`phik`). The upgrade steps are in the [migration instructions](README.md).

1. **Dashboard.** A new page, first in the side menu, is where Rapo opens (`/`, unknown paths, the sign-in and the
   logo lead to `/dashboard`; Results stays one click away). One scrolling page without a title: a sticky row of links to its sections at
   the top (where the other pages have their title), with the time of the data, the span chips and *Panels* on its
   right; then sections of panels that fill the whole width (the panels of a row grow to fill it, also beside
   a hidden one, and wrap as the window narrows), all charts in the app's colors (the chips' colors, light and dark),
   live: each change refreshes only the panels it touches. The span chips pick the span of the charts: **24h** (by hour), **7d** (default)
   or **30d** (by day), remembered by the browser.
   - **Overview.** Twelve tiles of today in two rows of six (four, three or two per row as the width shrinks), by
     topic, the edge and the week of a tile in the topic's color (red or orange when it needs attention): the runs,
     **run errors** (runs in error today; red with "N controls still failing" while a control's latest run is in
     error, orange with "all recovered" when every one was fixed by a later run), run warnings, KPI alarms (level
     2–3), then the instance: the scheduler's state with a ring of this server's slots (running of all; below, the
     queued runs, the time left to the next fire with its control, `in 23 min · NAME +2`, and to the next
     maintenance, `Maintenance in 41 min`, while this server schedules; the times themselves on hover)
     and health; and the files along their way: **files in input** (waiting in
     the input directories now, with the oldest one's age; red, and linking to the stalled datasources, when any is
     stalled), **files in processing** (files of any day in the file log loading or waiting to be loaded, now:
     how many load and how many wait, the oldest's age on hover), then in pairs **files success** (`SUCCESS` only) and
     files in error, records loaded and **rejected** (the records rejected, with their % of the records read). The counts compare with the same weekday a week
     earlier up to the same time of day (▲/▼, red when worse) and draw the last 7 days as an area across the tile. A click
     opens the page that shows it. The panel is 300 px high, exactly as high as *Instance health*, and its tiles
     stretch to fill it.
   - **Runs.** The runs over time by status (a strip per status, a click opens that status of that day or hour), donuts
     of the runs by status, by type and by trigger, the slowest controls (bars in the control type's color, names in
     full), the records fetched with the discrepancies found as two areas on one scale (a point per day or hour, the
     discrepancy rate on hover; the chart fills the height of its row), and the runs by
     weekday and hour (the full width, the count in each cell, the errors on hover). Every panel of a row is the same height.
   - **Scheduler.** One line with its state, server, heartbeat, slots and the missed fires never caught up (a chip
     opening them on the Scheduler page), then one strip of 48 hours whatever the span: what it did in the last 24
     (started, missed, failed per hour) and what it will start in the next 24, on each side of *Now*, the count written
     in each hour (as in the runs and files over time, when the cells are wide enough).
   - **Files** (with the PDI Core file log). The files over time by status (a strip per status, its total and a
     click per status), *Top datasources* as three donuts over the full width: by records loaded, by number of files
     loaded (`SUCCESS`) and **by loading time** (the `RUNTIME` of their files of every status, `52 min`, `3.4 h`;
     seven each, the rest as *Others*, a datasource in the same color in all three), donuts of the datasources by state (stalled, delivering
     files in the span, silent, disabled; the files waiting beside the title), and *Loading* (records loaded with the
     records rejected in the span as a chip, and the load throughput in records per minute of load time, as two small
     trends side by side filling the height of their row, both of all datasources or the one picked in the panel's head). Days are those of the database clock, as on the Files page.
     There is no *Files by status* donut: the files over time already have a row per status with its total, and a
     click on it opens the same Files page.
   - **KPIs** (with the KPI tables). The highest alarm level of each control per day (or hour), as compact strips over
     the full width: the worst 25 controls, *Show N more controls* for the rest (remembered by the browser). An
     cell is the day (or hour) of the period a run read (`date_from`), and a period run more than once counts by its
     last done run only (as in Data analysis' trend), also in the *KPI alarms* tile and the section's count. An
     alarmed cell (level 1–3) writes the value of the run that reached that level (the latest on a tie), of its most
     important KPI at that level (the KPI type's priority), in at most four characters (`0.35`, `12.4`, `1.2k`, `3.4M`)
     when the cells are wide enough; the exact value, unit, run and the number of its other alarmed KPIs on hover. A
     cell opens the control's KPIs tab with that run picked; a control's name opens its run log.
   - **Health.** The instance health as two rows of six tiles, tall like *Today* (the rapo server's, the database's; the file
     systems as one Disk tile, the fullest, all listed on hover), each with its value, level and a line over the last
     24 hours (24h) or 7 days (7d, 30d); a click opens Instance details on Health.
   - **One type.** Counters, metric labels, row texts and notes have the same size and weight in every panel (tiles,
     donuts, trends, strips, bars, health), larger and darker than before.
   - **Compact.** Shares are donuts of rounded slices, counts over time strips like the hour heatmaps of Results and Files, volumes and
     rates small trends; there are no bar charts over time.
   - **Panels.** Each panel's menu moves it up or down or hides it, and its handle drags it within its section; the
     header's *Panels* menu adds hidden panels back and resets the layout (kept by the browser). A hidden panel's
     data is not read at all.
   - **Clicks** open the page behind a value, filtered: a status slice opens Results with that status, a type or
     trigger slice Results with that filter, a control its editor's run log, a KPI cell its KPIs with the run picked,
     a datasource its file log, the stalled or disabled datasources the Datasources page so
     filtered, a row of the scheduler strip the Scheduler page's history or upcoming fires. Results
     (`status`, `type`, `name`, `trigger`, `warnings`, `hour`), Files (`status`, `lane`, `issue`, `hour`, `dup`),
     Scheduler (`tab`, `event`, `type`, `trigger`, `status`, `missed=1` opening the older missed fires), Controls
     (`type`, `status`, `name`, `attr`, `open=temp|orphan-tables|orphan-kpis` opening that list) and Datasources
     (`issue`, `lane`) take these filters from a link in place of their own, then drop them from the address.
   - **Fast.** One route answers every part, each in its own thread (`get-dashboard`); the present (tiles, runs by
     status) is asked for first; nothing reads a log text over the span, every query uses an index or one partition. What the panels ask for is kept for 3 seconds
     on the server for every open Dashboard, and dropped when a live event changes it. On Dev every part of 30 days
     takes under 0.2 s.
   - **File log summary.** The PDI Core file log takes too many files a day to sum a month of it on every look, so
     its past days are summed once into the new table `rapo_file_summary` (day, hour, datasource, status, duplicate
     flag) by the **scheduler's maintenance**, which sums the last 7 days again on every pass (recycles, reloads and
     deletes change older files) and fills the days missing of `[DASHBOARD] file_summary_days` (90); today, and
     yesterday until it is summed, are read from the file log. Days neither summed nor read live show as gaps, with a
     note; the Files section's refresh button sums the span's days at once (`refresh-file-summary`). Without
     `[SCHEDULER] maintenance_interval` only that button fills the summary. Counts show each file's current status:
     a recycle, reload or delete from Rapo sums the past days of those files again at once and refreshes the open
     Dashboards (a file in error, recycled, no longer counts as in error); status changes made outside Rapo show on
     past days with the next maintenance.
   - **Files waiting history.** With no browser connected, the server running the scheduler still counts the files
     waiting every `[DATASOURCES] scan_idle_interval` seconds (300; 0: only while someone looks, as before), so the
     tile's history has no gaps.
   - New options `[DASHBOARD] file_summary_days`, `[DATASOURCES] scan_idle_interval`; new routes
     `get-dashboard`, `refresh-file-summary`; `datasources:changed` has the kind `summary`.
2. **Instance health kept across restarts.** The one-minute aggregates of the Health tabs are stored in the new
   table `rapo_health_minute` (per server, `[HEALTH] history_days`, default 7, purged hourly) and read back when the
   server starts, so a restart no longer empties the charts; the Health tabs offer a **7d** span (from 7 days kept).
   The minutes also hold the files waiting in the input directories (the Dashboard's *Files in input*). A database
   that cannot store them (the table missing) is noted once in the server log and the history stays in memory.
3. **Faster loading.** The UI's files are sent compressed (gzip, about a quarter of their size: the main bundle 118
   KB instead of 442 KB) and, being named by their content, kept by the browser for good, so a reload asks only for
   the page itself; JSON answers of 1 KB or more are compressed too (downloads and file views are not). Charts are a
   bundle of their own, loaded with the first page that draws one and shared by the Dashboard and the analysis pages
   (the analysis bundle drops from 628 KB to 134 KB). A tab still showing an older build reloads itself when it asks
   for a bundle that is gone.
4. **File viewer.** Each file log row whose archived file can be downloaded (`SUCCESS` or `ERROR`, archived file kept,
   found on this server within the datasource's archive, error or duplicate directory) has an eye icon opening the
   file in a viewer, on the Files page's file log and in the editor's *File log* tab.
   - **Header.** The file's name, its datasource (a link to the datasource editor), its file ID and status, and the
     size, compression and encoding of what is shown; *Copy* copies the archived file's full path, beside *Download*.
     Below, the chips *Text*, *ASN.1* (how the file is read) and *Records* (the rows it loaded, see 5): the ringed
     ones are shown. The viewer opens a datasource's files as last picked in this browser (Text or ASN.1, with or
     without the records), except a binary file that looks like ASN.1, which opens as ASN.1.
   - **Reading.** The first 100 lines are shown at once; scrolling to the bottom loads the next ones, *Load 1,000
     more* (above the lines) a thousand. A gzip (recognized by its content, not its name), the first file of a ZIP, or
     a plain file is read decompressed, without unpacking it anywhere: the server keeps nothing between requests and
     reads each page from where the previous one ended (a gzip is decompressed up to that point, which is fast: a jump
     to line 5 million of a 300 MB file takes about half a second; the server keeps a checkpoint every 8 MB of the 8
     gzips read last, so a jump back into one costs at most 8 MB). The viewer keeps at most 50,000 lines; further,
     search or download the file. The header shows the file's size, compression and encoding (UTF-8, else Latin-1); a
     binary file is not shown. A line longer than 10,000 characters is cut, with a note of the bytes left out.
   - **Look.** Like the SQL boxes: monospace, read-only, the file's own line numbers, in light and dark mode.
   - **Columns.** In a delimited file each column has its own color (eight, repeating), so the values of one column
     are easy to follow; hovering a value names its column (number and the name from line 1). The delimiter (`;`,
     `,`, `|` or tab) is detected from the first lines (respecting quoted values) and shown in the *Delimiter* field,
     marked *auto*. Typing in it sets any delimiter, also of several characters (`||`, `\t` for a tab); digits
     separated by commas (`10,5,8`) are **fixed column widths** in characters (characters after the last width are
     shown as one more, muted column, and hovering names the character positions). Its menu has the usual delimiters,
     *Fixed widths…* (widths that split line 1 as its delimiter does, to edit), *None* and *Detect*. The save icon
     in the field keeps the delimiter for the datasource, for everyone (it was kept per browser before: a delimiter
     only this browser remembers shows an orange save icon, *Saved only in this browser*, and is never saved by
     itself).
   - **Search.** Text in the search field searches the **whole file** on the server, not only the lines loaded: the
     matching lines are listed with their line numbers and the matches highlighted; *Find more* (or scrolling) goes
     on. A search stops after 500 matching lines or 20 seconds of reading and says how far it got; plain text is
     found in about a second per 300 MB of uncompressed data. **Aa** matches case, **.\*** takes the text as a
     regular expression (Python syntax; an invalid one is named under the field). A click on a matching line shows
     the file from that line; *Back to results* returns to the list. Clearing the search shows the file's first
     lines again.
   - **Incoming files.** The files still waiting in a datasource's input directory (not in the file log yet) open in
     the same viewer, from an eye icon on each row of the input file lists (*Matching files*, *All files*, *Clean-up
     files* in the datasource editor and the catalogue, and the Files page's *Incoming* column). The file is read
     where it lies, as it is (plain, gzip or ZIP), as text or ASN.1 with the datasource's saved delimiter and decoding.
     The header shows an *Incoming* chip and the file's modification time instead of a file ID and status; there is
     no *Download* and no *Records*, and *Copy* copies the input path. Only a file whose real path lies in one of the
     datasource's input directories is read (a symbolic link leading out is refused). When PDI Core picks the file up
     while it is open, the lines read stay and a banner says the file is no longer in the input directory.
   - New options `[DATASOURCES] view_lines`, `view_max_lines`, `view_line_chars`, `view_grep_seconds`,
     `view_grep_matches`. The viewer is offered wherever downloads are (`file_download`), for incoming files too.
     Each opening and search is written to the server log. New routes `view-ds-file` and `grep-ds-file`; they and
     the ASN.1 routes take a file ID (`id`) or an incoming file (`source_id` and `path`).
5. **Loaded records.** The rows PDI Core loaded from a file can be shown beside it: a database icon on a file log row
   (when the datasource has tables and the file wrote or rejected records) opens the viewer on them alone, and the
   viewer's *Records* chip (with the file log's written count) shows or hides them: with *Text* or *ASN.1* also on,
   the records are below the file, half each, resizable by dragging the bar (the share is kept); clicking the ringed
   *Text* or *ASN.1* again leaves the records alone.
   - **Tables.** The records are read from the datasource's tables (*Retention* tab) by `FILE_ID`, the file's ID in
     the file log. The *Table* select lists them with the rows of this file in each (read by the `FILE_ID` index);
     a table that does not exist or has no `FILE_ID` is listed but can not be chosen. The first table with rows is
     shown. Next to it the rows are checked against the file log's written and rejected counts (orange when the
     tables hold a different number).
   - **Rows.** The rows are a plain table read straight from the database, 200 at a time as you scroll, so every
     row of the file can be reached; nothing is sampled or analysed. *Search all columns* searches all of the file's
     rows in the database (case-insensitive, numbers and dates as text) and shows `N of M rows`. *Columns* chooses and
     orders the columns shown (the same choice as on the Data analysis page for that table). *Open in Data analysis*
     opens the rows (the search included) on the full page (Summary, Columns, Records), at
     `/analysis/file/<file ID>/<table>`, a link that can be shared.
   - The viewer is as large in every layout.
   - New routes `get-file-tables`, `get-file-records` and `analysis-start-file`. Only tables linked to the file's datasource are ever
     read.
6. **Upload files.** *Upload* on the file log (Files page and the editor's *File log* tab) and *Upload files* in the
   editor's *Input files* box and the input files dialog (*Matching files* / *All files*, Incoming counts on the Files
   page) open a dialog to choose files, or files are dropped on any of these places. They go into the **first**
   directory of the saved *Input directory* (in the editor, save changes first); the input files dialog lists the
   directories again after an upload.
   - Each file is listed with its size; one whose name the file name pattern does not match is flagged in orange
     (PDI Core will not pick it up) but can be uploaded; one already waiting in the directory is left out, as are
     names with a path, a leading dot or control characters, and files over `max_upload_mb`.
   - Files are uploaded one by one with a progress bar; *Cancel* stops the current one. A missing input directory can
     be created from the dialog; a disabled datasource takes files too (the dialog notes that PDI Core picks them up
     once it is in a lane).
   - **Safe for PDI Core.** A file is streamed to disk under a temporary name the file name pattern does not match
     and renamed when complete, so PDI Core never loads a partial file; an existing file is never overwritten, and a
     canceled or failed upload leaves nothing behind. Each upload is written to the server log.
   - New options `[DATASOURCES] file_upload` (**off by default**) and `max_upload_mb` (2048 MB per file). New routes
     `check-ds-upload` and `upload-ds-file`.
7. **ASN.1 view.** A binary file (TAP, RAP, NRTRDE, CDR files of the core network) opens in the viewer as ASN.1 when
   its first bytes read as BER; the header's *Text* / *ASN.1* switch changes the view of any file, and a binary file
   that does not start as ASN.1 offers *Decode as ASN.1*.
   - **Record layout.** *Start offset* skips a file header that is no ASN.1; *Record header* skips that many bytes
     before **each** record (Huawei SBC files: 50 and 4); *Filler* picks the padding skipped between records: 00 and
     FF (the default), FF only (needed when a record header may start with 00, as Huawei's), or none. A record's
     header bytes are shown grey in the bytes and belong to it (a click on one selects the record).
   - **Tree.** On the left, the file's TLVs as a tree, by their tag (`[20]`, `[APPLICATION 4]`) as common ASN.1
     viewers show them (a folder for a constructed node, a page for a primitive one, its value after it). A node's
     children are read from the file when it is opened, 500 at a time (scrolling to the end of a level reads the next
     ones), so a TAP file of 100,000 calls or a CDR file of millions of records opens at once. The arrow keys move the
     selection and open or close a node. Bytes between records that are 00 or FF (the padding of block-written files)
     are skipped; bytes that are no TLV show as an orange *Undecodable* node and the reading goes on at the next
     record, so a damaged file is shown as far as it can be. Lengths may be definite or indefinite (CER).
   - **Bytes.** On the right, the **whole file** in hex, 16 bytes a row with the address and the bytes as text, read
     64 KB at a time as you scroll, however large the file. The selected node's bytes are colored: the tag orange,
     the length green, the value blue. A click on a byte selects the deepest node holding it and opens the tree down
     to it.
   - **Tabs** above the bytes: *Hex*, *XML* (the selected node and its children as XML, with tags, offsets, lengths,
     types, values and hex) and *Text* (an indented listing: offset, header and value length, name, tag, type,
     value), each with Copy and Download; at most 5,000 nodes (`asn1_render_nodes`). Below, the selected node's
     details: offset, tag and form, length, field and type, and what its value reads as (by its type with a
     grammar; else every reading that fits: integer, text, TBCD digits as in an IMSI, an address with its TON/NPI, a
     3GPP time stamp, a PLMN, an IP address) with its bytes.
   - **Grammars.** *Grammars…* lists the grammars (search, kind, files, modules or tag map entries, the datasources
     using them, by name with a link to their editor, last saved); the Datasources page opens the same list from its
     *ASN.1 grammars* chip (with their count) and the datasource editor from its *File viewer* box. A row opens it
     in the grammar editor, its menu duplicates, downloads (the files in one)
     or deletes one no datasource uses. *Add grammar* and editing share one editor: the name, and one tab per file
     whose text is edited in place (ASN.1 highlighting, line numbers, search): **paste** the modules or a tag map into
     a new file, upload files or drop them on the text, rename or remove files. *Save* (Ctrl+S) checks the text first
     (at most `asn1_grammar_max_kb`): an error names the file, line and column and shows that file. Saving under
     another name renames the grammar, and the datasources using it follow. Picking a *Grammar* names the nodes (`servedIMSI [3]`) and
     reads their values by type (`recordType [0] sGWRecord (84)`); the *Type* of the file's records (e.g.
     `GPRSRecord`, `DataInterChange`) is guessed from the first one and can be picked. A grammar needs not be
     complete: a type it lacks (e.g. one imported from a module not uploaded) leaves those fields unnamed, and a
     tag it does not expect is shown in orange. A file of type assignments without a module header (as some copies
     of the GSMA TDs are) is read as one module with IMPLICIT TAGS. No grammar is shipped with Rapo (the GSMA texts
     are not public): upload the ones you use.
   - **Tag maps.** The field definitions of a Pentaho ASN.1 decoder can be uploaded as a grammar as they are (its
     `props.put("82.4.1","nodeAddress,ia5,4");` lines, or `82.4.1=nodeAddress,ia5`): nodes are named by their tag
     path as the decoder builds it (the tag numbers of the TLVs that are not UNIVERSAL), and values decoded as the
     decoder does by type (`bcdstring`, `ebcdstring`, `tbcdstring`, `rbcdstring`, `integer`, `octstring`, `ia5`), so the
     viewer shows what the load job writes.
   - **Full tag.** A node's details show its full tag, the path of tags from its record (`(Full tag: SEQ.1.4.0)`:
     numbers, SEQ/SET for UNIVERSAL ones), and with a tag map its map path when it differs.
   - **Search.** *Field* finds nodes by name or tag, or a path of them (`servedIMSI`, `[20]/[3]`,
     `listOfTrafficVolumes/dataVolumeGPRSUplink`), optionally with a value (contains, or `=` the whole value, in any
     reading or the hex); *Hex* finds bytes (`80 04 0A F9`). Like the text search it reads the whole file on the
     server, 500 hits or 20 seconds at a time, and a hit opens the tree at its node.
   - **Save for datasource** keeps the grammar, type, start offset, record header and filler for the datasource: its
     files open with them, for everyone. The datasource editor's Main tab shows them in a *File viewer* box (read only,
     with the saved delimiter), and the Datasources list marks such a datasource with a grammar badge; a click on it
     shows the datasources using that grammar (a *Grammar* filter).
   - New table `rapo_viewer_config` (grammars and the viewer settings of each datasource), new Python package
     `asn1tools` (MIT; only its ASN.1 parser is used). New options `[DATASOURCES] asn1_page_nodes`,
     `asn1_render_nodes`, `asn1_grammar_max_kb`. New routes `get-ds-file-asn1`, `get-ds-file-asn1-node`,
     `locate-ds-file-asn1`, `render-ds-file-asn1`, `search-ds-file-asn1`, `get-ds-file-bytes`, `get-asn1-grammars`,
     `get-asn1-grammar-types`, `save-asn1-grammar`, `delete-asn1-grammar`, `get-viewer-settings`,
     `save-viewer-settings`. Grammar and settings changes are written to the server log.
8. **Instance limit no longer blocks the queue.** A queued run whose control already runs as many jobs as its
   `instance_limit` on this server is held in the queue and passed over, so other controls take the free slots.
   Before, ten runs of one control with `instance_limit = 1` filled every `control_parallelism` slot while only one of
   them worked. Held runs start in the order they were queued (before, in no particular order) and, like any queued
   run, are not timed out while held (before, a run waiting for its own control could end canceled by its
   `timeout`). The Scheduler's *Running* tab shows them as *Queued · instance limit*, and `scheduler-status` marks
   them with `held: "instance_limit"`. The limit also counts active runs started more than a day ago (they were
   ignored). Runs of the control on another server, or as another control's cascade or chain source, are still waited
   for inside the run's process, holding its slot, as before.
9. **File log page laid out like Results and Files.** The file log of a datasource (`/files-log/<id>`, and the
   datasource editor's *File log* tab) has the day navigator in its title (previous/next day, a date picker, today)
   instead of the day buttons of its filter row, and no filter fields any more: the status and *Duplicate* chips of
   the header toggle their filter (highlighted while on), and *Upload* sits beside them. The page searches with the
   header search, as the Files page does: a file name (any case), `?<start of a file name>` (case-sensitive) or
   `#<file ID>`; a datasource name or ID carried over from the Files page filters nothing. A file ID or name prefix not
   on the day shown is looked up on the other days of the datasource: *Go to its day* (file ID) or a list of the
   files found opens their day with the file picked. The editor's tab keeps a *File name* box (it has no header
   search). The *Not duplicates* filter is gone (`dup=N` in a link is ignored). `search-files` takes an optional
   `source_id`.
10. **Data analysis and Discrepancy analysis redesigned.** Both pages are one scrolling page instead of tabs, with an
   *On this page* list on the right (in a row under the header on narrow screens) that marks the section being read
   and jumps to a section; the section is kept in the link (`#records`, `#attributes`), and older links with `?tab=`
   open the matching section. The run's datasets (and sides) are avatar chips with their counts, the one shown ringed;
   the buttons are the app's outlined ones; filters show as the orange filter chips of the list pages.
   - **Data analysis** shows *Summary*, *Result types* (discrepancies), *Columns* and *Records*.
     - *Summary*: chips for the records loaded (all, a random sample, or the first ones; with *Load … more* or *Sample
       …*), the columns, and only when there are any: duplicate records (a click shows them), columns 5% or more
       missing, columns not profiled, *Config changed*. Below them the three strongest **related columns** (Pearson,
       Spearman or Cramér's V, 0.4 or more); a click shows the records grouped by both. Then a compact trend of the
       last 30 days.
     - *Result types*: one bar in the result type colors, chips per type, and the fields the value discrepancies
       differ in (from RAPO_DISCREPANCY_DESCRIPTION, *DURATION_SEC (239 of 239)*), each opening its records; case
       values when there are several.
     - *Columns*: a compact card per column, the columns that split the records first (few values, then numbers,
       dates, other text), each with its number of values, missing (grey, orange from 5%), blank and zero shares as
       chips, and **one** visual: its most frequent values as bars, or a histogram of its numbers or dates, never a
       chart of one bar. A date histogram counts **whole clock hours, days or months**: one bar per hour up to 2
       days (a daily control's 24 hours, ticks 00 06 12 18 24), per day up to 62 days, per month beyond, and when
       most of a column's values lie in the run's window (`date_from` – `date_to`) its bars cover exactly that
       window (*Run window 2026-10-09 · by hour*), records outside it (e.g. a reconciliation's time shift) as faded
       bars at the ends; other date columns are bucketed over their own range the same way. A bar shows its hour
       (day, month) and opens its records. Constant, empty and (nearly) unique columns are only named in one line; the RAPO_ columns
       are left out (Result types shows them, Records has them).
     - *Records* is the last section, one window tall: a click on any value, bar, chip or bin of the page filters it
       and scrolls there. Its tools are the same (search, Columns, Group by, Export, the REC counterpart); *Filter in
       the database* moves its filters into the database (the whole page then describes the matching records).
     - **Removed:** the Missing values tab (bar chart and nullity matrix), the Duplicates tab (the top-50 table; the
       duplicate records stay one click away), the correlation heatmap and its method switch, the **Compare** tab
       (with another sample, the previous run, the other side or any run), the alerts list, the column types list,
       the memory figure, each column's details (quantiles, moments, extremes, hour and weekday charts), the
       *Random / First rows* switch, *Profile these rows*, the trend's 10/30/90 days switch and the column order in
       the Columns menu (show and hide stay). Routes `get-analysis-targets`, `get-control-done-runs`,
       `analysis-compare-mapping` and `analysis-compare` are gone; `analysis-profile` has the sections `overview`,
       `columns`, `relations` and `breakdown` and no `filters`/`search`.
   - **Discrepancy analysis** shows *Summary*, *Attributes* and *Differences* (REC value discrepancies).
     - *Summary*: chips for the discrepancies and their share of the fetched records, the result types (a click
       analyses one; *All* returns) and the notes (*Preliminary*, *Sampled N%*, *Config changed*, *Source changed*,
       *Counts clamped*, explained on hover) in place of banners and sentences; a 30-day trend of the discrepancies
       and their rate (a click opens that run's analysis); then the **findings as cards**, the strongest one wider:
       up to three drivers and two combinations, each with the share of the discrepancies against the share of the
       normal records on one scale, its lift, and *Records*, which opens Data analysis on those discrepancies at
       their records (*Back* returns to the same place). A click on a card opens its attribute. The columns not
       related are named in one line.
     - *Attributes*: one row per column by its best binning, strongest first, with its *Explained* bar (Theil's U)
       and its over-represented bins. The *Time* binning is whole hours, days or months of the run's window (or of
       the column's range), with *Before* / *From* bins for records outside it, instead of 20 equal periods between
       the first and last record; it is left out for a one-day window (the *Hour of day* binning is the same), as is
       *Weekday* for values of one day; a click opens it in place: chips for its other binnings and the shares of its
       largest 12 bins as a butterfly (normal records left, discrepancies right), each bin opening its discrepancies
       or its fetched records. The columns not related are folded at the end.
     - *Differences*: one row per field with the range, median and sum of the differences and a histogram.
     - **Removed:** the story sentences, the Time bands heatmap, the Records tab of example records (and the queries
       that read them), the Combinations and Not analysed tabs (now cards and a footnote), and **φK**: the report has no
       `story`, `excerpts`, `heatmaps` or `phik`; `findings` carry `kind`, `column`, `what`, `phrase`, counts, `lift`
       and `rate`; `unrelated` lists the columns not related; `magnitude` fields have `sum`.
   - **Faster.** A spare analysis process is kept spawned and connected to the database, so a session or a
     discrepancy analysis starts without the 1–2 s a new process needs (it is replaced after `reload-config`). A
     random sample of a dataset larger than `initial_rows` no longer has the database sort the whole dataset first:
     each record is kept with the probability that gives the sample's size, so the records stream at once (*Sample
     …* reads a bigger one); a dataset that fits is read as it is, without any sort. Only when its count is not
     known (a fetched dataset filtered in the database) is it still shuffled. The column profile computes less, the
     charts of the cards are drawn without a chart library, and the analysis bundle is 20% smaller. On Dev a
     discrepancy analysis of 6,000 records takes 0.6 s instead of 3–4 s.
   - The menu of a run's discrepancies number lists *Discrepancy analysis* first.
   - The Python package `phik` (with `scipy`, `matplotlib`, `joblib`) is no longer required.
11. **Scheduler's Running tab links its controls.** The name of a running or queued control opens its editor on the
    *Scheduler* tab, as on the *Upcoming* and *History* tabs.
12. **Superseded runs folded, KPIs in the Run log.** A run is *superseded* when a later run of the same control and
    period (the days of its *Run from* and *Run to*) ended Done: a re-run, or the fix of a failed run. In Results and
    the editor's Run log a new *Ver* column shows the number of runs of the period as a bubble, darker the more there
    are; a click on it unpacks the earlier versions (hidden otherwise), faded, each with its version number outlined
    (the oldest 1), and a click on the *Ver* header unpacks or folds every period (remembered by the browser). A
    superseded run whose newer run is on another day stays in place with a ⟲ mark, which opens that run's day on
    Results. A later run in error or still running supersedes nothing. The Run log is sorted by the period by default,
    leaves out side B for ANL and REP, and has a column per KPI stored for the runs (`RACS_KPI_RUNHISTORY_ALL`): the
    value, compact (exact on hover), on its alarm level's color; a click calculates the KPIs of that run.
    **Columns follow the width:** both tables show Type, Processname, *Run from* and *Run to* when they fit, and only
    as the window narrows put the period in one *Period* column with narrower numbers, then drop Type, and (the Run
    log only) Processname; the name column takes the width left, so rows have no empty gap, and Results no longer
    scrolls sideways at common widths. `get-control-runs` answers
    `superseded_by`/`superseded_on` per run and, for one control, `kpis` per run and `kpi_types`.
13. **Next maintenance on the Scheduler page.** A chip after the next fire shows the time left to the scheduler's
    next maintenance (database clean-up, the file log summary, the controls' retention, old scheduler events), the
    time and interval on hover; also on the Dashboard's scheduler tile. Only the server holding the lease maintains, so
    the chip shows there only; `scheduler-status` no longer reports a `next_maintenance` after the scheduler was
    stopped or the lease moved (it reported one that never came), and adds `maintenance_interval`.
14. **Python 3.10 installs again.** `websockets` is pinned to 16.0 instead of 17.1, which needs Python 3.11, so
    `pip install -r requirements.txt` failed on Python 3.10 since v0.8.3. `./install.sh` downgrades it in an existing
    `.venv`; nothing else changes (only uvicorn uses it, for the socket.io connection).
