# Rapo v0.8.6 Change Log

## Annotation
A file of the file log can be viewed in the browser, however large, and searched as a whole on the server. Files can
be uploaded into a datasource's input directory from the file log and the datasource editor. There is no change to
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
     `,`, `|` or tab) is detected from the first lines (respecting quoted values); *Columns* overrides it or turns
     the colors off.
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
2. **Upload files.** *Upload* on the file log (Files page and the editor's *File log* tab) and *Upload files* in the
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
