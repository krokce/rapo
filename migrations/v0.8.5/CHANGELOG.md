# Rapo v0.8.5 Change Log

## Annotation
A *Discrepancy analysis* page explains what sets a run's discrepancies apart from its normal records, the email of
a control can be sent on the result of an SQL statement, the Controls page shows when each control runs next,
Results show what started each run and the runs per hour, with a day pill and no filter row, the editor's Run log is the Results table, KPIs can be calculated for a
past run while their SQL is written, and *Instance details* shows the health of the server and the database. There is no change to Rapo's own
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
   - **Combinations tab:** pairs of bins of two attributes that together set the discrepancies apart more than
     either alone (*Together, MSC = MSC07 and EVENT_TIME (hour of day) 02:00 – 04:59 hold 64% of the discrepancies
     against 0.84% of the normal records (76× as often), more than either alone (6.8×, 5.6×)*).
   - **Differences tab** (REC value discrepancies): by field, how much the values differ, read from
     RAPO_DISCREPANCY_DESCRIPTION (*AMOUNT differs in 100% of the 86 value discrepancies, always by -7*).
   - **Records tab:** up to 10 discrepancies and 10 fetched records of each of the strongest findings, the
     finding's columns first.
   - A REC analyses all its discrepancies or one result type (*All / Loss / Discrepancy / Duplicate*).
   - **Fast on large datasources: two stages.** A *quick look* reads about `[ANALYSIS] discrepancy_quick_rows`
     (default 100,000) records of each dataset, a block sample of the table (only that share of its blocks is
     read), and shows its results at once, marked *Preliminary*. Where Oracle can not sample (a join view, a
     database link) it reads the first records instead, noted as not random. *Refining* then counts the same bins
     and pairs in a single scan of each dataset, every record up to `[ANALYSIS] discrepancy_exact_rows` (default
     1,000,000), else a random row sample of about that size, with a parallel hint of `[ANALYSIS]
     discrepancy_parallel` (default 4, 0 for none), and replaces the preliminary results. *Stop refining* keeps
     the preliminary ones and frees the database, as does a failure or the timeout.
   - A block sample of a table whose records are stored in time or key order is uneven, so the quick look flags
     only strong differences, and never a bin where it read fewer fetched records than there are discrepancies.
     Heatmaps and example records come from the quick look.
   - The analysis runs in the background on the server, one at a time (others wait), with its progress shown; the
     result is kept in the server's memory (the latest 20), so reopening is instant until *Recompute* or a restart.
   - The fetched records are selected with the control's **current** configuration, as in *Data analysis*, and
     counted **now**: a control changed after the run or source data changed since are noted.
     `[ANALYSIS] discrepancy_timeout_minutes` (default 20) stops a long analysis.
   - New routes `start-discrepancy-analysis`, `get-discrepancy-analysis` and `stop-discrepancy-analysis`, live
     event `discrepancy:progress`. New Python dependency `phik` (with `scipy`), installed by `install.sh`.

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

6. **Calculate KPIs.** KPI and alarm statements can be tried on a past run before they are saved, without storing
   anything: *Calculate KPIs* in the header of the editor's *KPIs* tab (all KPIs), a ▶ button on each KPI row (that
   KPI), and *Calculate KPIs* in the row menu of the editor's *Run log* and of *Results* (controls with KPIs).
   - The calculation is the one `RACS_KPI_PKG` makes: the KPI statement gets `:v_processid`, its first column of the
     first row is the value (**0 when there is no row**, said under it), rounded to 4 places and shown with the type's
     decimal places and unit; the alarm statement gets it as `:v_kpi_value`. The alarm level is a chip: 3 red, 2
     orange, 1 blue, none for 0.
   - Next to it, what the package **stored** for that run (value, alarm, status, time), highlighted when it differs;
     a stored `ERROR` shows the end of its log. Per KPI: where each statement came from (as edited, saved, type
     default), the time each took, the statements with their bound values, and the error of a failing one.
   - From the editor the statements are the ones **as edited**, saved or not; from *Results* the saved ones. Both
     open the same dialog; *Recalculate* (Ctrl+Enter) calculates again.
   - **Run:** any run of the control, the latest done one by default. **Last runs:** the latest N (10, at most 30)
     runs that ended D at once, a table per KPI with the stored values and how often each alarm level fires, to tune
     thresholds.
   - **Re-ingest** (one run that ended D, saved statements, no unsaved changes) stores the KPIs for real: it calls
     `racs_kpi_pkg.ingest_rapo_control` after a confirmation, which overwrites the run's stored KPIs and posts the run
     to the dashboard, as after a run. Refused for a control aliased `TEST...`, as the package would skip it.
   - **Safety:** only one query runs: it must start with `select`/`with`; `FOR UPDATE`, PL/SQL in a `WITH` clause and
     a second statement are refused. It runs in a read-only transaction that is rolled back, and is stopped after
     `[KPI] calculate_timeout` seconds (new option, 120). A function with an autonomous transaction that writes is
     the one thing these checks can not stop, so KPI statements calling functions should be read before they run.
   - New routes `calculate-kpi`, `get-kpi-history`, `get-kpi-runs` and `reingest-kpis` (see the API reference).

7. **Orphaned KPIs, and KPIs deleted with their control.** `RACS_KPI_PKG` finds a control's KPIs by its exact
   name, so KPIs configured for a name no control has are never calculated.
   - The Controls page header shows *N orphaned KPIs* next to *orphaned result tables*. Its dialog lists each one:
     process name, KPI type, own or default statements, how many runs have stored values (and the latest), and why
     (no control of that name, or *differs only in case from control X*).
   - **Assign to control** moves a KPI to an existing control (the one differing only in case is offered first), for
     a control renamed outside the application; refused when that control already has the KPI type. **Delete**
     removes one KPI, **Delete all** every KPI of the name. Values stored for past runs are always kept.
   - **Deleting a control** now offers *Also delete its KPIs ...*, ticked, next to *Also drop the result tables*.
     Unticked, they are left as orphaned KPIs, as before. `delete-control` takes `delete_kpis` (default true).
   - New routes `get-orphan-kpis`, `delete-orphan-kpis` and `reassign-orphan-kpi`.

8. **KPIs follow a rename or clone.** KPI statements that read the control's own result table
   (`RAPO_REST_`/`RAPO_RESA_`/`RAPO_RESB_<name>`) keep reading it after the control is renamed or cloned.
   - In the editor, while the *Control name* changes (and at once on a clone, which still read the source control's
     tables), the KPI and alarm statements of the control's KPIs are rewritten to the new name. Only whole names
     change, in any case, quoted or owner-qualified (`RAPO_REST_X2` is left alone for `X`); type defaults and other
     controls' KPIs are never changed.
   - A banner on the *KPIs* tab (and a dot on the tab) says which statements now follow the name; **Undo** points them
     back and stops following the name until the control is loaded again. The unsaved-changes list shows the KPI
     changes as usual.
   - A rename saved through the API without `kpi_config` now moves the KPIs to the new name and rewrites the same
     references; before, they were left behind as orphaned KPIs. `save-control` answers `kpis_moved`.

9. **Instance health.** *Instance details* (the plug button of the header) has two tabs: *Configuration* (as before,
   shown first) and a new **Health** tab.
   - **Two columns**, the server left and the database right, with matching metrics side by side. Each is headed
     by its name and uptime: *Server: kosta-notebook (up 6 d 7 h · rapo up 2 h 10 min)*, *Database:
     mm_usage@localhost:1521/RAAUT (up 5 d 8 h)*.
   - **Span:** small buttons *1h 3h 6h 12h 24h*, remembered by the browser. One hour shows every sample; longer
     spans one point per minute (24 h: per 3 minutes), averaged, but the highest value of locks, lock waits,
     CLOSE_WAIT connections and rapo's processes, so a short peak still shows. A chart starting later says since
     when the server runs.
   - **Server:** CPU, memory, processes and disk of this server's host, each a value and a chart, with rapo's own
     share (the server, its runs, analysis and scan workers) as a second, dashed line: CPU and memory used by rapo,
     rapo's processes and open files, free space where the logs and `rapo.ini` are. *Network*: received and sent
     per second over all interfaces but loopback, with errors and drops. *Connections*: the host's established TCP
     connections and those in CLOSE_WAIT (closed by the other side but never by a local program, a leak when it
     grows), TIME_WAIT, and rapo's connections to the database.
   - **Database** (the PDB in a container database): *DB CPU* (% of `cpu_count`, average active sessions),
     *Sessions* (all and rapo's), *Locks* (sessions blocked by another, longest wait), *DB memory* (PGA of
     `pga_aggregate_limit`, SGA) and *Storage* (used % of the user's default and temporary tablespaces, autoextend
     counted, and the size of rapo's result and temporary tables; the leftover temporary tables open from there) and
     *DB I/O* (physical reads and writes per second, redo and commits).
   - **Sessions and Locks** open a list of the sessions, or of the blocked ones and their blockers: user, module,
     action, status, wait event and time, blocker, SQL ID, machine. A rapo run's action is its control, which opens in
     the editor. Read-only: nothing is killed from here.
   - **Warning levels:** a tile turns amber or red at its warning or critical level (CPU 80/95% averaged over 30 s,
     memory 85/95%, disk 85/95%, DB CPU 80/95%, PGA 85/95%, tablespace 85/95%, any blocked session / a lock wait of
     60 s, 50 connections in CLOSE_WAIT), and the plug button gets an amber or red dot naming the tiles in its tooltip. The dashed line of a chart is
     its warning level.
   - The server samples in the background, the OS every 10 s and the database every 30 s (a few cheap queries of
     views free of the Diagnostics Pack), and keeps the samples of the last hour and one-minute aggregates of the
     last 24 hours in memory only (a few MB): a restart starts the charts anew.
     The open tab receives each new sample live; nothing polls.
   - **Database sessions of rapo are tagged:** every connection sets module `rapo`, and the connections of a run its
     control's name as action (`V$SESSION.MODULE`/`ACTION`), so they are told apart in any DBA tool too.
   - The database metrics need SELECT on `V_$CON_SYSMETRIC`, `V_$PARAMETER`, `V_$SESSION`, `V_$SGAINFO`,
     `V_$PGASTAT`, `DBA_TABLESPACE_USAGE_METRICS` and `V_$INSTANCE` (see the [migration instructions](README.md)). A tile whose view
     can not be read shows *No access* and the grant it needs; the others work. Views granted later are found
     within 10 minutes, or at once with *Reload* of `rapo.ini`.
   - **Layout:** the six server charts first (two per row), then the six database charts.
   - New `[HEALTH]` options: `enabled`, `os_interval`, `db_interval`, `footprint_interval`, `history_minutes`,
     `history_hours`, and
     `<rule>_warn`/`<rule>_crit` for the levels, all applied by a reload. New routes `get-instance-health` and
     `get-instance-sessions`, live events `health:sample` and `health:level`.

10. **Configuration tab: every option, editable in place.** *Instance details* → *Configuration* lists every
    `rapo.ini` option rapo reads, in sections and in a logical order, not only those written in the file.
    - A *General* box first: version, instance name, and the configuration file and log folder in use.
    - One line per option: its name, its value in `rapo.ini` (blue), or its default (grey) when the file does not
      set it, the default, and what it does; sections are separated by lines. A legend explains the colors and
      symbols. A filter and *Only set in rapo.ini* narrow the list; options the file sets that rapo does not read
      carry a red dot; changes on disk not applied yet stay highlighted.
    - **Change in place:** hovering a value that applies without a restart shows a pencil; clicking it opens a small
      editor (a switch, a number, a choice or a text), with *Save* and *Reset to default*. The option's line in
      `rapo.ini` is rewritten (comments and the rest of the file kept) and applied at once on this server, as
      *Reload* does. Before each change the file is copied to `rapo.ini.bak-<timestamp>` next to it (readable by its
      owner only; the newest 10 are kept, and they are ignored by git). A file changed on disk meanwhile is shown
      again instead of being overwritten.
    - Options that apply only after a restart (`[DATABASE]`, `[API]`, `[LOGGING] directory`, `[SCHEDULER]
      enabled`) carry an orange dot and are changed in the file on the server; secrets (passwords, the API token)
      show only whether they are set.
    - The defaults shown are the ones rapo uses: they now come from one catalogue in the code, `rapo/options.py`.
      Nothing changes in behavior.
    - The change applies to the server answering; another server on the same database has its own `rapo.ini`.
    - New routes `get-config-catalogue` and `set-config-option`.

11. **Results: a cleaner page, a day pill and runs per hour.**
    - **No filter row.** The *Run control* button and the *Control type*, *Control name* and *Run status* fields are
      gone. Filter by type, status or warnings with the chips of the day's totals or of the table; start a run from
      the row menu (*Re-run*, *Run*), the Controls page or the editor. Active filters show as chips under the title
      as before.
    - **Name filter.** The magnifier before a control name filters by exactly that control (no longer a part of the
      name); it is teal while it filters, and a second click clears it. It is shown also while the header search is
      used.
    - **Process ID search.** The header search (*Search control name or process ID*) also finds runs whose process ID
      starts with the digits typed. A process ID not run on the day shown offers *Go to its day*, which opens the day
      it ran on with the search kept; a process ID with no run says so.
    - **Day pill.** The day in the title is a pill with the weekday: `‹` the previous day, and on an earlier day `›` the
      next day and `⏭` today; hover a segment for the day it opens. The same pill replaces the day buttons of the
      *Files* page.
    - **Runs per hour.** A heatmap above the table counts the day's runs by the hour they started (or were added, if
      they never started), following the filters. Hover an hour for its runs per control type, errors and warnings; an
      hour with a run in error has a red outline, one with a run flagged with a warning an amber corner. A click
      filters the table to that hour (an *Hour* chip), a second click clears it; another day clears it, too.
    - `get-control-run` also answers `added`.
