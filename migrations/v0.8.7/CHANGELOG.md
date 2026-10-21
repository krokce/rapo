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
