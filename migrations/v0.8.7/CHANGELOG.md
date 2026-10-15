# Rapo v0.8.7 Change Log

## Annotation
No schema change. The upgrade steps are in the [migration instructions](README.md).

1. **Copy a run's process ID.** In Results and in the editor's Run log, a click on a run's process ID (PID column)
   copies it to the clipboard and says so; the number underlines on hover like the other clickable numbers. A click
   on the PID of the selected Run log row keeps it selected.
1. **File log: File ID column.** The file log (`/files-log`, the datasource editor's File log tab) shows each file's
   ID after its status; a click copies it to the clipboard, like a run's process ID.
1. **Files and file log rows like Results.** Rows are as tall as in Results, the lane and status chips have Results'
   size, and the datasource names on Files are written at the size of Results' control names.
   Files shows a grey `0` in an empty count (a status, Duplicates, Read, Written, Rejected), as Incoming did; Runtime,
   Last success and Trend stay empty without files.
