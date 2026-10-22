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
