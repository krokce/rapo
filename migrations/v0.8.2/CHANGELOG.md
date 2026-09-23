# Rapo v0.8.2 Change Log

## Annotation
This release sends control results per email, lets the control editor save without closing, adds a page to manage
KPI types, and reworks the web UI around a Results home page that stays fast with thousands of rows. It also fixes
eight defects in the PL-SQL reconciliation engine. There is no schema change. The upgrade steps are in the
[migration instructions](README.md).

1. **Email results per control.** An analysis, report or reconciliation control can mail its results when a run
   finishes. It is switched on with **Send email** in the editor's Main tab, which opens a new **Email** tab. The
   configuration is stored under the `email` key of `rapo_config.rule_config`, so it is versioned with the rest of
   the control. Comparison controls keep `rule_config` as a list and have no email.
   - **Recipients.** To, CC and BCC lists.
   - **Send when.** *Done, with results* (the default) sends only when the attachment would have rows. *Done,
     always* sends for every successful run. *Done or error* also sends when a run fails, with its error.
   - **Subject and body with variables.** The body is plain text. Variables such as `{control_name}` or
     `{control_date_from:%Y-%m-%d}` are the ones Preparation SQL uses, plus run facts: `{status}`, the fetched,
     success and error counts, and `{attachment_rows}`. An unknown one is left as written. A run summary can be
     appended below the body.
   - **Excel attachment.** The run's rows from `rapo_rest_<name>`, or for a reconciliation one sheet per side from
     `rapo_resa_<name>` / `rapo_resb_<name>`, with its own choice of Loss, Discrepancy and Match. Each sheet has a
     name, a SQL filter like the datasource filters, and an ordered choice of fields with optional header labels.
   - **Excel formatting.** The header is bold and frozen, with an autofilter. Dates show as `dd.mm.yyyy`, or
     `dd.mm.yyyy hh:mm:ss` when a column carries times. Integers have no decimals and other numbers two. Integers
     longer than 15 digits are written as text, so Excel does not round them.
   - **File name.** `<CONTROL>_<yyyy-mm-dd>.xlsx`, or `<CONTROL>_<from>_<to>.xlsx` when the run window spans
     several days.
   - **Limits.** A per-control *Max records*, capped by `[EMAIL] max_attachment_rows` and `max_attachment_mb` in
     `rapo.ini`. Above a limit the email still goes out, without the file and with a note saying why.
   - **Logging.** Each step is written to the run's own log (Show full log). A failed send never changes the
     run's status.
   - **Resend and test.** **Send email** in the Results row menu sends a finished run's email again with the
     current configuration. **Send test** in the Email tab sends the last finished run to one address, marked
     `[TEST]`.
   - **In the Controls list,** controls that send email show an **Email** chip, and *Email* is a Control
     attributes filter.
1. **Apply in the control editor.**
   - **Buttons.** **Apply** (or Ctrl+S / Cmd+S) saves and keeps the editor open. **Save** saves and returns to
     the list, as before. Both sit in a bar pinned to the bottom of the window, on every tab.
   - **Only changes are saved.** A form without changes is not written, so no new version appears in the
     control's history. The bar shows *Unsaved changes* while there are any.
   - **Leaving with unsaved changes** asks first: Cancel, the side menu, the browser's back and closing the tab.
   - **A Run button in the editor header.** After Apply, you can run the control with the new filters, or send a
     test email, without leaving. While there are unsaved changes, Run, Re-run and Send test are disabled, since
     a run always uses the saved configuration.
   - **No more silent overwrites.** If someone else saved the control after you opened it, your save is refused.
     You then choose between reloading their version and overwriting it.
1. **KPI types page.** The RACS KPI catalogue (`racs_kpi_type`) is now managed from the UI at **KPI types**.
   - You can create, edit and delete types. Renaming a type moves the controls' KPIs along with it in one
     transaction.
   - A type still used by controls cannot be deleted. The type editor lists those controls.
   - The page appears only where the RACS KPI tables are deployed.
1. **Results is the home page.** The day's runs open by default.
   - Prev, Next and Today buttons step through days. The page title names the day, and the day's totals are
     clickable type and status chips.
   - The side menu leads with Results, highlights the current page, and collapses to icons (remembered per
     browser).
1. **Lists stay fast.** Results, Controls and the Scheduler's Upcoming and History tables render only the visible
   rows, so thousands of runs or controls scroll smoothly. Pages show loading placeholders instead of empty forms.
1. **SQL autocomplete in the control editor.**
   - The filter, criteria, Preparation, Prerequisite, Completion and KPI SQL boxes complete the columns of the
     control's datasources and result tables.
   - They also complete Oracle keywords, the KPI bind variables (`:v_processid`, `:v_kpi_value`) and the
     `{control_name}`-style variables.
1. **Consistent look.** Control types have icons and show as the same chips everywhere. The Scheduler tables show
   each fire's run window and follow the column order of Results.

## Fixes

These concern the `PL` engine only. The procedure must be redeployed (see the migration instructions), and
controls using it can give different, now correct, results.

1. **Fuzzy clusters sharing a key were paired wrongly.** Positions inside `F` clusters were numbered over the whole
   correlation-key group instead of per cluster, so a group with several clusters paired rows across them.
1. **A row with no candidate could shift the fuzzy positions** of the real `F` rows of its group.
1. **Rows with a null key were reported as losses.** Their select used the widened time window, and the A side's
   formula for side B.
1. **A non-unique key field multiplied rows.** The procedure joined the raw datasource without the source filter
   and the window.
1. **An unmatched fuzzy pair could stall matching.** The conflict-type filter of `s06` was missing.
1. **A DBMS_SQL cursor leaked** when parsing a source failed.
1. **`rule_config.max_candidates` was ignored.** It never reached the procedure.
1. **Reconciled output ignored `need_recons`,** so `result_number` differed from the `DB` engine for the same
   control.

The engine is also faster: the n=300 stress fixture dropped from 12 s to 7 s.
