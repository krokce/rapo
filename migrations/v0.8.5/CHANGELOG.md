# Rapo v0.8.5 Change Log

## Annotation
A *Discrepancy analysis* page explains what sets a run's discrepancies apart from its normal records, the email of
a control can be sent on the result of an SQL statement, the Controls page shows when each control runs next,
Results show what started each run, and the editor's Run log is the Results table. There is no change to Rapo's own
schema; one Python package is added (`phik`). The upgrade steps are in the [migration instructions](README.md).

1. **Discrepancy analysis.** A new page, *Discrepancy analysis* in the menu of a run's discrepancy number (Results and
   the editor's *Run log*) and a button on *Data analysis* of the discrepancies, answers *what is special about these
   discrepancies*: which values of which columns (a switch, a time band, an IMSI range, an amount range…) are much
   more common among the discrepancies than among the run's **normal records**, the side's fetched records less its
   discrepancies. For every run type with discrepancies (ANL; REC and CMP per side A/B), not REP.
   - **How.** Every column the discrepancies share with the fetched records is binned the same way in both: values
     (up to 1000 distinct texts, 30 numbers; the rest of a value list is *Other*), ranges by the fetched deciles,
     the hour, weekday and period of a date, and for identifier-like columns (unique per record, e.g. IMSI, MSISDN,
     call IDs) their first 3/5/6/8 digits and their length. Empty values are a bin of their own. Oracle counts the
     bins of both datasets over the whole data (one scan each, plus one profile scan of the fetched records); a
     bin's normal count is its fetched count less its discrepancy count. Constant or empty columns, LOBs and columns
     still unique after binning are listed under *Not analysed*.
   - **Scores.** Per binning *Explained*, Theil's U (the share of the uncertainty about a record being a
     discrepancy that the bins remove) and **φK** (phik); per bin the discrepancy and normal shares, the **lift**
     (their ratio), the discrepancy rate and a two-proportion z. A bin is *over-represented* with at least 10
     discrepancies (and 1% of them), a lift of 2 or more and z ≥ 4. Adjacent over-represented hours, ranges or
     periods merge into bands (`02:00 – 04:59`), sibling prefixes into their common prefix (`2940181…`).
   - **Summary tab:** the findings as sentences (*The strongest driver is MSC_ID: MSC07 holds 66% of the
     discrepancies against 9.6% of the normal records (6.8× as often)*), the columns not related to them, notes on a
     sample, a changed control or changed source data; each driver opens its bins or its discrepancies in *Data
     analysis*. Beside it the columns ranked by *Explained* and φK, and for a REC the split by result type.
   - **Attributes tab:** every binning ranked, and the chosen one's butterfly chart (normal records left,
     discrepancies right) with a table of shares, lift and rate; each bin opens its discrepancies or its fetched
     records in *Data analysis*, filtered in the database. **Time bands tab:** a weekday × hour heatmap of the
     discrepancy rate per date column.
   - A REC analyses all its discrepancies or one result type (*All / Loss / Discrepancy / Duplicate*).
   - The analysis runs in the background on the server, one at a time (others wait), with its progress shown; the
     result is kept in the server's memory (the latest 20), so reopening is instant until *Recompute* or a restart.
   - The fetched records are selected with the control's **current** configuration, as in *Data analysis*, and
     counted **now**: a control changed after the run or source data changed since are noted. Above
     `[ANALYSIS] discrepancy_exact_rows` (default 5,000,000) fetched records, they are counted on a random sample of
     about that size and scaled up; `[ANALYSIS] discrepancy_timeout_minutes` (default 20) stops a long analysis. Each
     analysis scans the datasource about three times; check these limits for large datasources.
   - New routes `start-discrepancy-analysis` and `get-discrepancy-analysis`, live event `discrepancy:progress`. New
     Python dependency `phik` (with `scipy`), installed by `install.sh`.

2. **Email: Send when *Evaluate SQL*.** A fourth *Send when* option on the editor's *Email* tab (ANL, REP, REC). The
   email is sent only when the *Evaluate SQL* returns a number above 0, whatever the run's status (Done or Error) or
   its result rows; an Error run's email carries the error and no file, as with *Done or error*.
   - The statement is written like the *Prerequisite SQL*: a select returning one number (first column of the first
     row), with the variables `{control_name}`, `{process_id}`, `{control_date}`, `{control_date_from}` and
     `{control_date_to}` (strict formatting: an unknown variable fails). The editor's *Check* validates it as a
     prerequisite, and its *Example* menu offers ready statements.
   - 0 or a negative number: no email (INFO line in the run log). A failing statement, no row, NULL, a non-numeric
     value or an empty statement: no email and a WARNING line in the run log. The run's status never changes.
   - The value is logged (`Email: Evaluate SQL returned N`) and available as the email variable `{evaluate_value}`
     in the subject, the body and the file name.
   - *Resend* (Results menu) and *Send test* (editor) always send; they still evaluate the statement, and a test's
     body notes when a run would not send (`Evaluate SQL returned 0, so a run would not send this email.`).
   - Stored as `rule_config.email.send_when = "evaluate_sql"` with `rule_config.email.evaluate_sql`. The statement is
     kept, and ignored, when another option is chosen. Save is refused while the option is chosen without a statement.

3. **Controls: *Scheduler* column.** Replaces *Periods back / Schedule* on the Controls page and on a KPI
   type's *Controls* tab.
   - Line 1 is the next run, `Today 14:20`, `Tomorrow 08:15`, `Thu 02.10 08:15` or `01.11 18:15`, followed by the
     time left (`(in 2h 5m)`, updated every 30 s). It is the earliest run of any kind: the control's own schedule, a
     cascade after the control it is triggered by, or a chain pull by a control reading its results (marked `≈`,
     since it starts once that run gets there). Otherwise the line reads *Inactive*, *Not scheduled*, *No run ahead*
     (a cascade whose trigger does not run) or *Invalid schedule*.
   - Line 2 describes the schedule in words, e.g. *Every day at 08:15*, *Weekdays at 08:15*, *Twice a month (1st,
     2nd) at 08:15:01*, *Every hour at :05:12*, *Every 15 min, 08:00–18:45*, *After CHN_B finishes* or *Pulled by
     CHN_C*. Line 3 carries a chip with the data window (*1 day back*, *7 days, 1 back*).
   - The round avatar is colored by how often the control runs (several times a day, daily, weekly, monthly, month
     and week days, cascade, chain, not scheduled). Its icon shows what starts the next run: a clock, a cascade
     tree, a chain link, or a pause sign while the scheduler is stopped (the times are then greyed). Line 3 shows
     a strip of where the runs fall (the hours of a day, the days of a week or the days of a month), the same width
     for every schedule, next to the data window chip.
   - Hovering a row lists its next 5 runs with their data windows. A click on the avatar or the next run opens the
     control's *Scheduler* tab.
   - A click on the header sorts by the next run (controls without one last). A sort kept from the old column
     becomes this one.
   - The *Type*, *Name* and *Scheduler* columns are as wide as their content (the longest control name, the widest
     schedule in words, up to 360 and 400px), and *Description* takes the rest of the page.
   - The next runs refresh on every configuration or scheduler change, and when the earliest one is due.
   - The editor's *Scheduler* tab shows the same description, strip and window live under the schedule fields.
   - New route `GET /api/get-next-fires` (see the API reference).

4. **Results: trigger icon.** The *Start* cell shows a small icon after the start time for what started the run:
   the schedule, a manual start, a catch-up, an iteration, a cascade or a chain pull (upstream). Hover it for the
   trigger's name and details, e.g. `Started by: Schedule (scheduled for 2026-09-24 18:15:00)` or `Started by:
   Upstream (For CHN_B [1000002993])`. A run the run manager did not start (library use, older runs) shows a faint
   question mark, *Trigger not recorded*. The *Start* column is 18px wider, taken from the *Processname* column.
   `get-control-runs` answers `trigger_type`, `trigger_message` and `scheduled_time` for each run.
   - The day's totals under the header chips count the runs by trigger, each an icon with its number (hover it for
     the trigger's name), not recorded last.

5. **Editor: *Run log* as on Results.** The *Run log* tab shows the runs of the last *Days back* days in the Results
   table: the same formatting, trigger icon, warning flag, number menus (*Copy SQL*, *Data analysis*) and row menu
   (*Re-run*, *Run*, *Revoke run*, *Cancel run*, *Show full log*, *Send email*).
   - The same columns as Results. The row menu has no *Edit control* (you are in it); the end of a run is in *Show
     full log*.
   - Sortable by every column (newest first by default, kept for the browser session); a line separates the days
     while sorted by *Start* or *PID*.
   - Above it, the totals of those runs as on Results: status and warning chips, runs by trigger, records fetched and
     runtime. They are not filters.
   - *Re-run* and *Run* are disabled while the form has unsaved changes. The *#*, *Added* and *End* columns are
     gone.
   - The table fills the tab down to the *Save* bar and scrolls inside.
   - `get-control-runs` takes `control_name` and `days` for this, and answers `added` and `end_date` for every run.
