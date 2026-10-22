# Rapo v0.8.7 Change Log

## Annotation
New table `rapo_api_token`, column `rapo_scheduler_event.requested_by` and recreated `rapo_config` triggers
(`migrations/v0.8.7/upgrade.sql`); new option `[API] token_cache_seconds`. The upgrade steps are in the [migration instructions](README.md).

1. **API tokens of users.** Signed in with the master token (`[API] token`), its header menu (*Master token*) opens
   *API tokens* (`/tokens`, master only): create a token for a user (name, email, label) valid 1 month, 6 months, 1 year
   or unlimited, with a level per area (Dashboard, Runs, Data, Controls, KPIs, Scheduler, Datasources, Files, Instance:
   None/View/Operate/Edit) and Free SQL, in a table like the rapo.ini one that says what each chosen level allows;
   presets Viewer/Operator/Editor/Full. The token (`rapo_...`) is shown once, with Copy and a curl example; only its
   SHA-256 is stored. Edit, Extend, Regenerate (active tokens; an expired one is extended first), Revoke and Delete
   (revoked or expired) from the row menu; a revoked token opens read only. A token signs
   in to the UI or calls the API; routes beyond its scopes answer 403 (`docs/api/README.md`, *API tokens and scopes*).
   Controls: Edit and KPIs: Edit need Free SQL; without it a Data analysis SQL filter may only be a plain filter of
   the dataset's columns (no subquery, comment or q-quoted literal). A database failure while checking a token answers
   503 and never signs a page out. `status` and `session` name the server's host, OS user and PID only to tokens with
   Instance: View.
1. **The UI follows the token.** Menu items, pages and actions the token may not use are hidden; the control, KPI
   type and datasource editors and the ASN.1 grammars open read only (fields and code do not change; the KPIs of a
   control, the email's folds, file lists, the archive, the file log stay browsable; keys and paste do not reach their
   fields either); the header names the user (scopes, expiry, Sign out) and a banner warns
   14 days before the token expires. A revoked token signs its open pages out within about 30 s, a changed one
   reconnects with its new scopes. Live events go only to the areas a token may view; an analysis session belongs to
   its token; only the token that started a discrepancy analysis (or the master token) may stop it.
1. **Who did it.** Changes made with a user token are recorded under its email (`rapo_config.created_by/updated_by`,
   the versions' *Changed by*), and a manual or catch-up run notes who asked for it (`requested_by`: the Run log's
   trigger icon, Scheduler History). The master token keeps the server's OS user.
1. **Copy a run's process ID.** In Results and in the editor's Run log, a click on a run's process ID (PID column)
   copies it to the clipboard and says so; the number underlines on hover like the other clickable numbers. A click
   on the PID of the selected Run log row keeps it selected.
1. **File log: File ID column.** The file log (`/files-log`, the datasource editor's File log tab) shows each file's
   ID after its status; a click copies it to the clipboard, like a run's process ID.
1. **Files and file log rows like Results.** Rows are as tall as in Results, the lane and status chips have Results'
   size, and the datasource names on Files are written at the size of Results' control names.
   Files shows a grey `0` in an empty count (a status, Duplicates, Read, Written, Rejected), as Incoming did; Runtime,
   Last success and Trend stay empty without files. A count other than zero is bold in its column icon's color (Success
   green, Started blue, Waiting amber, Error orange, Incoming blue-grey, Duplicates purple, ...).
1. **Control editor: no silent overwrites.** A stored rule, case or iteration configuration that cannot be read is
   reported when the control opens and Save/Apply are refused, so the defaults the form falls back to never replace
   it. The schedule is checked on Save: a Weekly or Monthly schedule without days, a Cascade without its trigger
   control, an empty Complex hour/minute/second or an invalid time is refused on the Scheduler tab (a Weekly schedule
   without days was saved as Daily). Changing datasource B clears its output columns, as datasource A did. A new run
   iteration takes the next free ID (IDs no longer repeat after a removed row).
1. **Example menus by keyboard.** The examples of the schedule fields and the *Add KPI* menu now apply the item picked
   with Enter (the menu closed without doing anything).
1. **File log: hidden selections are left alone.** Files selected and then hidden by the status, duplicate, hour or
   search filters stay selected but are no longer recycled, reloaded, deleted or downloaded; the selection bar and the
   confirmation say how many are left alone. The Runtime column is `h:mm:ss`, as on Files.
1. **Failed loads say so.** KPI types, the Scheduler, the Run log dialog, the KPI type and datasource editors, the
   file log, the incoming files list and the ASN.1 grammars show the error with a *Retry* instead of loading forever
   or reading as empty.
1. **Smaller fixes.** The Run dialog shows a picked range as `from - to` and stays open when a run is refused; New and
   Delete KPI type are hidden from tokens without KPIs: Edit; a `?tab=` link to a tab the token may not see opens Main;
   the Scheduler page reloads the control catalogue only when controls change (not each time a fire passes); the
   Dashboard notices a new hour and day by the browser's local clock (it used UTC); the incoming files list keeps the
   kind picked last when an older listing answers late.
1. **Dark theme and contrast.** The Group by table, the share bars, the run trend chart, the code editors' focus ring
   and active line, the empty/error notices and the run log's level colors follow the theme (some stayed light-theme
   colors in dark mode); the version bubbles of the Run log and Results keep readable numbers in dark mode. Comparison
   (CMP) control names are written in a darker lime that reads on white (the chip keeps its color). The counts in the
   Dashboard's heat strips pick white or dark text by the cell's actual color, so light hues (Waiting, Missed) stay
   readable.
1. **Keyboard access.** Tab reaches and Enter opens: the rows of KPI types, API tokens, a KPI type's Controls tab and
   the ASN.1 grammars; the editable `rapo.ini` values of Instance details (the pencil shows on focus); the trigger,
   history (⟲) and warning marks of Results, the Run log and the Scheduler; the email's Evaluate SQL and sheet folds
   (announced as expanded or not); the control editor's *Manage versions*, *Get all columns*, schema notice and
   *Unsaved changes*. The ASN.1 tree and the file viewer's text show a focus ring; the viewer's Aa/.*/= toggles say
   whether they are on; the schedule fields' example buttons are named *Examples*. The reason a Stop scheduler or Save
   token button is disabled now shows on hover. The schedule column and the version line of Controls are no longer
   extra Tab stops.
1. **Page titles.** The browser tab names the page (`Results · RAPO - <instance>`), so tabs and history tell pages
   apart.
1. **KPI type editor like the others.** The KPI type editor has the sticky Save / Apply / Cancel bar of the control
   and datasource editors, an *Unsaved changes* marker, Ctrl+S for Apply, and asks before leaving with unsaved changes
   (it discarded them without asking); Save without changes writes nothing. Apply of a new or renamed type moves to its
   own address.
1. **Datasource editor: Save on leaving.** Leaving the datasource editor with unsaved changes now offers Keep editing,
   Discard or Save, as the control editor does (it offered only Discard). A renamed datasource is saved with Save,
   whose dialog says what else to rename.
1. **One chip style.** The attribute chips of Controls (group, scheduler inactive, hooks, engine, SQL, email, case,
   iterations, chain, systems, schema drift, datasource missing) and its header chips (orphaned tables and KPIs,
   temporary tables, schema check failed), the attribute chips of a KPI type's Controls tab, the issue chips of Files
   and Datasources, the run log's level filters and Scheduler's *Older missed* are grey chips with a colored icon, like
   every type and status chip (they were colored chips, some hard to read). The run log's levels, the incoming files
   list's Matching/All/Clean-up, Instance health's time span and the KPI calculation's This run/Last runs are chips
   ringed when picked (they were button groups).
1. **Dashboard type.** Every panel takes its font sizes from one scale (`--rapo-dash-*` beside `.dash-value`,
   `.dash-label`, `.dash-text`, `.dash-note`).
1. **Narrower windows.** Page titles wrap their facts and chips onto a second row instead of overflowing; the
   *New control* / *New KPI type* buttons and the filters of Controls and KPI types take a full or half row on narrow
   windows; the page margin is not doubled on small screens; the file viewer opens full screen on a phone and cuts its
   header facts before the buttons; a control's KPI rows wrap; the Run dialog and the orphaned KPI menu fit the
   screen.
1. **Consistency.** The column of the control's name is called *Control* in Results, the Run log and the orphaned KPIs
   (it was *Processname*/*Process name*); a process ID on the Scheduler's Running and History tabs copies on click, as
   in Results; the log text of a file in the file log is in the monospace font.
1. **Discrepancy analysis tells thin evidence apart.** With too few discrepancies for any finding (a pattern needs at
   least 10 in one bin), the summary says so instead of "No column sets these discrepancies apart", and the
   *Explained* bars are grey whenever no finding backs them (they were red at e.g. 88% under a summary denying any
   cause). The report carries `meta.min_support`.
1. **Compact page chrome.** Page titles are 34px (were 60px), so tables start about 100px higher; buttons are written
   as labelled (no capitals); *New control*, *New KPI type*, *New datasource* and *New token* are normal buttons beside
   the title; the control editor's tab bar is blue-grey like the other pages' (it took the control type's color) and
   all editor tabs sit left; *File processing* is titled *Files*, like its menu entry.
1. **Quieter destructive actions.** The control editor shows *Recreate schema* only while the result tables differ
   from the configuration (the Controls row menu always has it); *Lock all lanes* on Files is a flat button; *Run* is
   flat-colored.
1. **One meaning per color.** Canceled runs and scheduler events are brown (purple means duplicate); the Files issue
   *Errors* is deep orange like the ERROR status and *Silent* amber; the Dashboard calls datasources without files in
   the span *Idle* (Files' *Silent* is the issue of missing files a week later); recycled, reloaded and deleted files
   have the same distinct greys on the Files page and the Dashboard; the Dashboard's datasource colors avoid status
   hues; *Slowest controls* bars are one neutral color; correlation strengths are shades of teal (were red/orange).
1. **Control editor: Main tab in boxes.** General (name, alias, group, version, description), Execution (type, engine,
   parallelism, instance limit, timeout) and Hooks and results, with a short hint under each field instead of hover
   tooltips; required fields are marked `*`; the control name is upper-cased also when pasted. A link to another tab
   of the control already open (`?tab=`) now switches to it.
1. **Data analysis:** the columns not profiled are listed one per line in a grid (were one long paragraph). The
   Dashboard's *As of* time is darker.
