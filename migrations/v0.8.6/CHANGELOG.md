# Rapo v0.8.6 Change Log

## Annotation
A file of the file log can be viewed in the browser, however large, and searched as a whole on the server. Files can
be uploaded into a datasource's input directory from the file log and the datasource editor, and the records a
file loaded are shown below it or on the Data analysis page. A binary file is shown as ASN.1 (BER, DER, CER): its
tree of tags, named by an uploaded grammar (TAP, RAP, NRTRDE, 3GPP CDRs, a vendor's own), beside its bytes. The
release adds one table (`rapo_viewer_config`) and one Python package (`asn1tools`). The upgrade steps are in the
[migration instructions](README.md).

1. **File viewer.** Each file log row whose archived file can be downloaded (`SUCCESS` or `ERROR`, archived file kept,
   found on this server within the datasource's archive, error or duplicate directory) has an eye icon opening the
   file in a viewer, on the Files page's file log and in the editor's *File log* tab.
   - **Reading.** The first 100 lines are shown at once; scrolling to the bottom loads the next ones, *Load 1,000
     more* a thousand. A gzip (recognized by its content, not its name), the first file of a ZIP, or a plain file is
     read decompressed, without unpacking it anywhere: the server keeps nothing between requests and reads each
     page from where the previous one ended (a gzip is decompressed up to that point, which is fast: a jump to line
     5 million of a 300 MB file takes about half a second; the server keeps a checkpoint every 8 MB of the 8 gzips
     read last, so a jump back into one costs at most 8 MB). The viewer keeps at most 50,000 lines; further, search or
     download the file. The header shows the file's size, compression and encoding (UTF-8, else Latin-1); a binary
     file is not shown. A line longer than 10,000 characters is cut, with a note of the bytes left out.
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
   - New options `[DATASOURCES] view_lines`, `view_max_lines`, `view_line_chars`, `view_grep_seconds`,
     `view_grep_matches`. The viewer is offered wherever downloads are (`file_download`). Each opening and search is
     written to the server log. New routes `view-ds-file` and `grep-ds-file`.
2. **Loaded records.** The rows PDI Core loaded from a file can be shown beside it: a database icon on a file log row
   (when the datasource has tables and the file wrote or rejected records) opens the viewer on them, and the viewer's
   *File* / *Split* / *Database* switch shows the file, both, or the records. *Split* puts the records below the file,
   half each, resizable by dragging the bar; the viewer opens split again next time.
   - **Tables.** The records are read from the datasource's tables (*Retention* tab) by `FILE_ID`, the file's ID in
     the file log. The *Table* select lists them with the rows of this file in each (read by the `FILE_ID` index);
     a table that does not exist or has no `FILE_ID` is listed but can not be chosen. The first table with rows is
     shown. Next to it the rows are checked against the file log's written and rejected counts (orange when the
     tables hold a different number).
   - **Rows.** The rows are a plain table read straight from the database, 200 at a time as you scroll, so every
     row of the file can be reached; nothing is sampled or analysed. *Search all columns* searches all of the file's
     rows in the database (case-insensitive, numbers and dates as text) and shows `N of M rows`. *Columns* chooses and
     orders the columns shown (the same choice as on the Data analysis page for that table). *Open in Data analysis*
     opens the rows (the search included) on the full page (Overview, Columns, Correlations, Missing values,
     Duplicates, Data), at `/analysis/file/<file ID>/<table>`, a link that can be shared.
   - The viewer is as large in every layout.
   - New routes `get-file-tables`, `get-file-records` and `analysis-start-file`. Only tables linked to the file's datasource are ever
     read.
3. **Upload files.** *Upload* on the file log (Files page and the editor's *File log* tab) and *Upload files* in the
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
4. **ASN.1 view.** A binary file (TAP, RAP, NRTRDE, CDR files of the core network) opens in the viewer as ASN.1 when
   its first bytes read as BER; the header's *Text* / *ASN.1* switch changes the view of any file, and a binary file
   that does not start as ASN.1 offers *Decode as ASN.1*.
   - **Record layout.** *Start offset* skips a file header that is no ASN.1; *Record header* skips that many bytes
     before **each** record (Huawei SBC files: 50 and 4); *Filler* picks the padding skipped between records: 00 and
     FF (the default), FF only (needed when a record header may start with 00, as Huawei's), or none. A record's
     header bytes are shown grey in the bytes and belong to it (a click on one selects the record).
   - **Tree.** On the left, the file's TLVs as a tree, `Tag : [20]` as common ASN.1 viewers show them (a folder for a
     constructed node, a page for a primitive one, its value after it). A node's children are read from the file
     when it is opened, 500 at a time (scrolling to the end of a level reads the next ones), so a TAP file of
     100,000 calls or a CDR file of millions of records opens at once. The arrow keys move the selection and open
     or close a node. Bytes between records that are 00 or FF (the padding of block-written files) are skipped;
     bytes that are no TLV show as an orange *Undecodable* node and the reading goes on at the next record, so a
     damaged file is shown as far as it can be. Lengths may be definite or indefinite (CER).
   - **Bytes.** On the right, the **whole file** in hex, 16 bytes a row with the address and the bytes as text, read
     64 KB at a time as you scroll, however large the file. The selected node's bytes are colored: the tag orange,
     the length green, the value blue. A click on a byte selects the deepest node holding it and opens the tree down
     to it.
   - **Tabs** under the bytes: *Hex*, *XML* (the selected node and its children as XML, with tags, offsets, lengths,
     types, values and hex) and *Text* (an indented listing: offset, header and value length, name, tag, type,
     value), each with Copy and Download; at most 5,000 nodes (`asn1_render_nodes`). Below, the selected node's
     details: offset, tag and form, length, field and type, and what its value reads as (by its type with a
     grammar; else every reading that fits: integer, text, TBCD digits as in an IMSI, an address with its TON/NPI, a
     3GPP time stamp, a PLMN, an IP address) with its bytes.
   - **Grammars.** *Grammars…* lists the grammars (search, kind, files, modules or tag map entries, the datasources
     using them, last saved); a row opens it in the grammar editor, its menu duplicates, downloads (the files in one)
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
     files open with them, for everyone.
   - New table `rapo_viewer_config` (grammars and the viewer settings of each datasource), new Python package
     `asn1tools` (MIT; only its ASN.1 parser is used). New options `[DATASOURCES] asn1_page_nodes`,
     `asn1_render_nodes`, `asn1_grammar_max_kb`. New routes `get-ds-file-asn1`, `get-ds-file-asn1-node`,
     `locate-ds-file-asn1`, `render-ds-file-asn1`, `search-ds-file-asn1`, `get-ds-file-bytes`, `get-asn1-grammars`,
     `get-asn1-grammar-types`, `save-asn1-grammar`, `delete-asn1-grammar`, `get-viewer-settings`,
     `save-viewer-settings`. Grammar and settings changes are written to the server log.
5. **Instance limit no longer blocks the queue.** A queued run whose control already runs as many jobs as its
   `instance_limit` on this server is held in the queue and passed over, so other controls take the free slots.
   Before, ten runs of one control with `instance_limit = 1` filled every `control_parallelism` slot while only one of
   them worked. Held runs start in the order they were queued (before, in no particular order) and, like any queued
   run, are not timed out while held (before, a run waiting for its own control could end canceled by its
   `timeout`). The Scheduler's *Running* tab shows them as *Queued · instance limit*, and `scheduler-status` marks
   them with `held: "instance_limit"`. The limit also counts active runs started more than a day ago (they were
   ignored). Runs of the control on another server, or as another control's cascade or chain source, are still waited
   for inside the run's process, holding its slot, as before.
6. **File log page laid out like Results and Files.** The file log of a datasource (`/files-log/<id>`, and the
   datasource editor's *File log* tab) has the day navigator in its title (previous/next day, a date picker, today)
   instead of the day buttons of its filter row, and no filter fields any more: the status and *Duplicate* chips of
   the header toggle their filter (highlighted while on), and *Upload* sits beside them. The page searches with the
   header search, as the Files page does: a file name (any case), `?<start of a file name>` (case-sensitive) or
   `#<file ID>`; a datasource name or ID carried over from the Files page filters nothing. A file ID or name prefix not
   on the day shown is looked up on the other days of the datasource: *Go to its day* (file ID) or a list of the
   files found opens their day with the file picked. The editor's tab keeps a *File name* box (it has no header
   search). The *Not duplicates* filter is gone (`dup=N` in a link is ignored). `search-files` takes an optional
   `source_id`.
