# Rapo v0.8.6 Change Log

## Annotation
A file of the file log can be viewed in the browser, however large, and searched as a whole on the server. Files can
be uploaded into a datasource's input directory from the file log and the datasource editor, and the records a
file loaded are shown below it or on the Data analysis page. There is no change to
Rapo's own schema and no new Python package. The upgrade steps are in the [migration instructions](README.md).

1. **File viewer.** Each file log row whose archived file can be downloaded (`SUCCESS` or `ERROR`, archived file kept,
   found on this server within the datasource's archive, error or duplicate directory) has an eye icon opening the
   file in a viewer, on the Files page's file log and in the editor's *File log* tab.
   - **Reading.** The first 100 lines are shown at once; scrolling to the bottom loads the next ones, *Load 1,000
     more* a thousand. A gzip (recognized by its content, not its name), the first file of a ZIP, or a plain file is
     read decompressed, without unpacking it anywhere: the server keeps nothing between requests and reads each
     page from where the previous one ended (a gzip is decompressed up to that point, which is fast: a jump to line
     5 million of a 300 MB file takes about half a second). The viewer keeps at most 50,000 lines; further, search or
     download the file. The header shows the file's size, compression and encoding (UTF-8, else Latin-1); a binary
     file is not shown. A line longer than 10,000 characters is cut, with a note of the bytes left out.
   - **Look.** Like the SQL boxes: monospace, read-only, the file's own line numbers, in light and dark mode.
   - **Columns.** In a delimited file each column has its own color (eight, repeating), so the values of one column
     are easy to follow; hovering a value names its column (number and the name from line 1). The delimiter (`;`,
     `,`, `|` or tab) is detected from the first lines (respecting quoted values) and shown in the *Delimiter* field,
     marked *auto*. Typing in it sets any delimiter, also of several characters (`||`, `\t` for a tab); digits
     separated by commas (`10,5,8`) are **fixed column widths** in characters (characters after the last width are
     shown as one more, muted column, and hovering names the character positions). Its menu has the usual delimiters,
     *Fixed widths…* (widths that split line 1 as its delimiter does, to edit), *None* and *Detect*. The choice is
     remembered for the datasource in the browser.
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
   editor's *Input files* box open a dialog to choose files, or files are dropped on either place. They go into the
   **first** directory of the saved *Input directory* (in the editor, save changes first).
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
