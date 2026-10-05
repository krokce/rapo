# Rapo v0.8.5 Change Log

## Annotation
A *Discrepancy analysis* page explains what sets a run's discrepancies apart from its normal records, the email of
a control can be sent on the result of an SQL statement, the Controls page shows when each control runs next,
Results show what started each run and the runs per hour, with a day pill and no filter row, the Scheduler shows the next and last 24 hours with heatmaps, the editor's Run log is the Results table, KPIs can be calculated for a
past run while their SQL is written, *Instance details* shows the health of the server and the database, Results filter by trigger, and a manual run cascades only when ticked. There is no change to Rapo's own
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
   the schedule, a manual start, a catch-up, an iteration, a cascade or a chain pull (*Chain*). Hover it for the
   trigger's name and details, e.g. `Started by: Schedule (scheduled for 2026-09-24 18:15:00)` or `Started by:
   Chain (For CHN_B [1000002993])`. A click filters the runs by that trigger (see 13). A run the run manager did not start (library use, older runs) shows a faint
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
   anything: in the editor's *KPIs* tab, and in a dialog opened by *Calculate KPIs* in the row menu of the editor's
   *Run log* and of *Results* (controls with KPIs).
   - **KPIs tab:** each KPI row shows its value, unit and alarm level, or the error (hover for all of it, click to
     copy), calculated for the run picked in the tab's header (the latest done one by default): every KPI when the
     tab first opens, every KPI again when another run is picked, a KPI as it is added, and a row again with its ▶.
     The value sits on a pale yellow field. A result is dimmed once its statements are edited. The rerun fields are
     labeled *On alarm* and *On new data*; the unit follows the description; a KPI's chip opens its statements.
   - The calculation is the one `RACS_KPI_PKG` makes: the KPI statement gets `:v_processid`, its first column of the
     first row is the value (**0 when there is no row**, said under it), rounded to 4 places and shown with the type's
     decimal places and unit; the alarm statement gets it as `:v_kpi_value`. The alarm level is a chip: 3 red, 2
     orange, 1 blue, none for 0.
   - **Dialog:** one row per KPI, laid out like the KPIs tab: code, description, calculated value (pale yellow) with
     unit and alarm, then what the package **stored** for that run (value and alarm, orange when they differ, status
     and time on hover) and the time the statements took. A row's chevron shows its details: the error of a failing
     statement, notes, a stored `ERROR`'s log, and the statements with their source (as edited, saved, type default)
     and bound values. The dialog is as tall as its rows (up to 90% of the window).
   - From the editor the statements are the ones **as edited**, saved or not; from *Results* the saved ones. Both
     open the same dialog; *Recalculate* (Ctrl+Enter) calculates again.
   - **Run:** any run of the control, the latest done one by default. **Last runs:** the latest N (10, at most 30)
     runs that ended D at once, a table per KPI with the stored values and how often each alarm level fires (on the
     KPI's title line), to tune thresholds.
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

9. **Instance health.** *Instance details* (the plug button of the header) has three tabs with icons:
   *Configuration* (as before, shown first), **Health Rapo server** and **Health Database**.
   - **Each health tab** shows its tiles two per row, the charts filling the dialog, so nothing scrolls unless the
     Sessions or Locks list is open (or a server has many disks). Each is headed by its name and uptime: *Server:
     kosta-notebook (up 6 d 7 h · rapo up 2 h 10 min)*, *Database: mm_usage@localhost:1521/RAAUT (up 5 d 8 h)*.
   - **Span:** small buttons *1h 3h 6h 12h 24h*, remembered by the browser. One hour shows every sample; longer
     spans one point per minute (24 h: per 3 minutes), averaged, but the highest value of locks, lock waits,
     CLOSE_WAIT connections and rapo's processes, so a short peak still shows. A chart starting later says since
     when the server runs.
   - **Server:** CPU, memory, processes and disk of this server's host, each a value and a chart, with rapo's own
     share (the server, its runs, analysis and scan workers) as a second, dashed line: CPU and memory used by rapo,
     rapo's processes and open files. *Disk*: one tile per file system holding the logs, `rapo.ini` or a
     datasource's input or archive directory, titled by its mount point, with its free space and what it holds (e.g.
     *logs · rapo · 72 input · 61 archive dirs*). Symlinks are followed, so `/data_in -> /iris/DATA1/data_in` counts
     on `/iris/DATA1`, and directories on one file system share its tile (its hint names the device and the links).
     The directories are resolved once after the server starts: a datasource added later counts from the next
     restart. A directory missing on this host, or on a mount that does not answer in 2 s, is left out. *Network*: received and sent
     per second over all interfaces but loopback, with errors and drops. *Connections*: the host's established TCP
     connections and those in CLOSE_WAIT (closed by the other side but never by a local program, a leak when it
     grows), TIME_WAIT, and rapo's connections to the database.
   - **Database** (the PDB in a container database): *DB CPU* (% of `cpu_count`, average active sessions),
     *Sessions* (all and rapo's), *Locks* (sessions blocked by another, longest wait), *DB memory* (PGA of
     `pga_aggregate_limit`, SGA) and *Storage* (GB used in the user's default tablespace, and the size of rapo's
     result and temporary tables as the second line; each of the default and temporary tablespaces in GB of what it
     may grow to, autoextend counted, and %; the leftover temporary tables open from there) and
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
      next day and `⏭` today; hover a segment for the day it opens. A click on the day opens a calendar (Monday
      first, later days disabled) whose days carry a dot: teal with runs, red with a run in error. Picking a day opens it. The same pill
      replaces the day buttons of the *Files* page, where the calendar only picks a day (no dots: counting a month of
      the file log is too slow). New route `get-run-calendar`.
    - **Runs per hour.** A heatmap above the table counts the day's runs by the hour they started (or were added, if
      they never started), following the filters. Hover an hour for its runs per control type, errors and warnings; an
      hour with a run in error has a red outline, one with a run flagged with a warning an amber corner. A click
      filters the table to that hour (an *Hour* chip), a second click clears it; another day clears it, too.
    - `get-control-run` also answers `added`.

12. **Scheduler: 24 hours, chips and heatmaps instead of filter fields.**
    - **No filter fields.** *Horizon*, *Control name*, *Event* and *Trigger* are gone. The header search works on the
      Scheduler page (control name; on *History* also a process ID prefix); the *Running* table is never filtered.
      Chips above each tab count its rows by type and trigger (*History* also by event and run status), each filters;
      on *History* the Trigger, Event and Run cells filter, too. Active filters show as chips, with a dot on the tab.
    - **Upcoming** shows the next 24 whole hours (now until the same hour tomorrow) and every run the scheduler causes:
      own fires (*Schedule*), the cascades they trigger (*Cascade*) and the controls each run pulls first
      (*Chain*). A new *Trigger* column names it, with *via* the control it follows; cascades and chain sources show
      the time of that fire, as they start right after it.
    - **History** shows the last 24 whole hours (from the same hour yesterday), up to 5000 events. Older missed fires
      that were never run for their moment are counted by an *Older missed* chip, which lists them with *Run for this
      moment*.
    - **Heatmaps:** a strip of the 24 hours above each table, starting at its window's first hour with the day marked
      at midnight; green for Upcoming (fires per hour, by type and trigger on hover), blue for History (events per hour;
      a red outline where an event failed or a run ended in error, an amber corner where a fire was missed). A click
      filters the table to that hour.
    - **Status bar:** the status card is replaced by a row of chips beside the page title: the state (its dot pulses
      while this server schedules), the scheduling server and its uptime, the heartbeat's age (the heart beats on
      each one; green, amber near the lease timeout, red past it), the slots as a ring gauge with the queued count,
      the next fire, and the last 24 hours' started, missed and failed counts; hover for details (PID, since, next
      maintenance, lease timeout, last fire). The slots open *Running*, the next fire *Upcoming* and each counter
      *History* filtered to it. Stop/Start is a round button at its end. The *In* column of Upcoming is *Next fire*,
      right-aligned and counting down every second.
    - **Running** is a tab of its own (first, with the running + queued counts on it and a spinning icon while
      something runs), so many jobs no longer push Upcoming and History off the page: the table fills the page and
      scrolls inside. It lists *Run from* and *Run to*, and its columns follow History: Type, Queued, Started, PID,
      Control, Run from, Run to, Trigger, State, OS PID.
    - API: `scheduler-upcoming` answers cascades and upstreams (`trigger_type`, `via`, `date_from`, `date_to`) and its
      window ends on a whole hour; `scheduler-events` takes `hours`; new `get-missed-fires`; `scheduler-status` jobs
      carry `date_from`/`date_to`.

13. **Triggers, chains and cascades.**
    - **Results: filter by trigger.** A click on a trigger icon in the *Start* cell, or on a trigger count of the
      day's totals, filters the runs by that trigger (a *Trigger* chip); a second click on the same trigger clears it.
      *Trigger not recorded* can be filtered, too. The filter is kept like the others and followed by the heatmap.
      On the Scheduler page a second click on the trigger filtered by clears it as well.
    - **"Upstream" is now "Chain"** wherever a trigger is named (Results, run log, Scheduler, heatmaps); the
      control a chain pulls is its *chain source*, also in the run log (`Chain source control X ended C`). The
      stored trigger code stays `UPSTREAM`.
    - **Manual runs cascade only when asked.** The *Run* dialog and *Re-run* offer *Cascade into X, Y* as an unticked
      option (as for iterations) when other controls cascade from the control; until now a manual run always
      cascaded. Scheduled and catch-up runs cascade as before. `run-control` takes `cascade` (default `true`, so API
      callers keep the previous behavior); the UI always sends it.
    - **The window of a cascade.** A scheduled cascade gets the *fire time* of the control it follows and counts its
      **own** *Periods back / Number of periods / Period type* back from it; it does not inherit the window of that
      control (a manual run of that control passes its dates instead). The schedule now reads *After X finishes ·
      own window*, the window chip's tooltip and a note under the period fields of the editor's *Scheduler* tab say
      so. Check cascaded controls whose period fields were assumed not to matter.
    - **Controls: *Cascade schedule* attribute** filters the controls that run after another one. The *Control
      attributes* list is grouped (Execution, Scheduling, Run steps in the order a run performs them, Output,
      Issues).
    - **Now on the hour heatmaps.** The heatmaps of Results, Files, a datasource's file log (today only) and the
      Scheduler's Upcoming and History show the present as a line at the current minute under a clock icon and
      *Now HH:MM*. Results and the Scheduler count by the server's clock, Files and the file log by the database's,
      as their hours are. The midnight divider of the Scheduler heatmaps is drawn the same way, in grey, with a calendar
      icon before the day. `get-control-runs` answers `server_time`, `get-ds-file-log` answers `database_time`.
    - **Referenced controls link to their editor:** the control a cascade follows (*After X finishes · own window*)
      and the controls pulling one (*Pulled by X*) in the schedule descriptions (Controls, editor, KPI type), and
      *via X* (Upcoming) and *for X* (Running) on the Scheduler page. A link from one editor to another loads that
      control (asking first about unsaved changes).

14. **Files: chips instead of filter fields, lane locks, file search in the header.**
    - **No filter fields.** *Find file*, *Datasource*, *Lane*, *File status* and *Issues* are gone. The chips of the
      day's totals filter (status, *Duplicate* and the issues); a second click on a chip clears its filter, and a
      chip that filters has an orange ring. Active filters show as chips under the title as before.
    - **Every issue in the header.** *Silent*, *Drop*, *Errors*, *Log name differs* and (on today) *Stalled* are
      counted beside the status chips when any datasource has them; until now only *Silent*, *Drop* and *Stalled*.
    - **Lane chips: the icon locks, the text filters.** A click on a lane's icon locks an idle lane (inserts its
      `LOAD_<lane>` row into `PDI_CORE_STATE`, as a core_load run does, after a confirmation: no core_load run of
      the lane starts until it is removed) or removes the lock of a running one (as before); on hover the icon shows
      a lock or an open lock. A lane locked by hand looks like a running lane. A click on a lane's name shows only
      its datasources; a second click shows all again. One lane at a time, also from the *Lane* column.
      New route `set-lane-lock` (needs `INSERT` on `PDI_CORE_STATE`).
    - **Header search.** *Search datasource name or ID, ?file name, #file ID*: plain text finds datasources by name,
      or digits by the start of their ID; `?FMS-S` finds the files whose name **starts with** the text
      (case-sensitive, 3 characters or more) and `#48910075` the file with that ID, of **any day**, newest first (at
      most 200). The table then shows the datasources of the files found, and a line under the filter chips lists
      them; a file opens its datasource's file log on the file's day.
    - API: `search-files` takes `text` (start of `INPUTFILENAME`, case-sensitive, using its index) or `id`, of any day;
      `date` is gone and `text` no longer matches inside a name.

15. **A sort chip brings back the default order.** Once a column header is clicked, a list kept that sort for the
    browser session with no way back to its own order: on Controls the last modified first, a column no header
    offers. Controls, Results, KPI types, Datasources, Files and the file log now show a grey chip after the filter
    chips while a column sort is set (*↑ Name*, its tooltip naming the default); its ✕ restores the default order
    (Results: the latest start first). The orange *Filter* badge still removes only the filters.

16. **Undo single changes in the control editor.** *Unsaved changes* in the editor's footer lists what Apply would
    change; each row now ends with an undo button that puts that value (an option, a column, a KPI, a whole SQL text)
    back to the saved one and leaves the list. Rows the form derives from others (*need_a*/*need_b* from the result
    types of a reconciliation) say what they follow instead; *with_deletion*/*with_drop* revert together. *Discard all
    changes* at the bottom of the dialog returns the form and its KPIs to the saved control, with *Redo* in its
    notification. Leaving the editor with unsaved changes now asks *Keep editing*, *Discard* or **Save**: Save saves
    as the Save button does and goes on to where you were going; a failed check or save (or a control changed
    meanwhile) keeps the editor open.

17. **Fix: a reconciliation marked as changed by opening *Data and logic*.** A REC control whose rule configuration
    has no per-side output limits (saved through the API or a script) showed *Unsaved changes* as soon as the tab
    opened, which disabled Run and Send test: the tab added empty `output_limit_a`/`output_limit_b`. It now copies
    only an older control's single *Output limit* into empty sides, and keeps an explicit limit of 0.

18. **Edit the SQL of a view datasource from the control editor.** When a datasource of *Data and logic* (also A or
    B) is a view of Rapo's own schema, a pencil in its field opens the view's query (the text after `AS`) as stored,
    comments and layout included, in a code editor that completes the columns of the tables it reads and of tables
    typed into it.
    - **Check** creates the view under a scratch name (`RAPO_TEMP_VIEW_<16 hex>`, dropped at once), so it finds
      every error a real compile would, and puts the cursor on the error; when valid it shows the columns added,
      removed and changing type. **Preview** runs the edited query read only and shows its first rows (10 by default,
      up to `[VIEWS] preview_max_rows`). **Format** formats it in Rapo's style, **Revert** brings back the stored text.
    - **Compile** replaces the view (`CREATE OR REPLACE VIEW`), only after a passing Check of the same text, and the
      server checks it again: an invalid view is never compiled. The confirmation names removed or retyped columns,
      the other controls reading the view and the database objects depending on it, since they all see the change.
      A view changed by someone else since it was opened asks to Reload or Overwrite.
    - Only the query is edited: the view's name, its column list (kept when it renames the query's columns, so the
      query must then return as many) and its other clauses stay as they are. A query must be one select/with,
      without `FOR UPDATE` or PL/SQL in a `WITH` clause.
    - **The previous DDL is kept only in the server log** (`rapo-server_<date>.log`, *View X is replaced ... Previous
      DDL*); there is no version history of views.
    - After a compile the editor reads the view's columns again for every side reading it and keeps its choices;
      a date or key field or output column the view no longer has is cleared, and a notice names it and the
      columns gone, which criteria and filters may still use. The result-table schema check runs again.
    - New section `[VIEWS]`: `edit` (default `True`; `False` hides the pencil and refuses the routes),
      `preview_max_rows` (1000), `preview_timeout` (30 s). New routes `get-view`, `check-view`, `preview-view`,
      `compile-view`, `format-view`, `get-object-columns`; `get-datasources?types=true` returns the type of each
      datasource. A scratch view left by an interrupted check is listed and dropped with the temporary tables.
    - Check: the database user needs no new privilege for views of its own schema (`CREATE VIEW` it has).

19. **SQL boxes: line numbers on every line, completion after aliases.** The line numbers of the editor's SQL boxes
    (filters, SQL scripts, KPIs, email, the view dialog) stopped after the first screenful of a long text; they now
    run to the last line. Where a box completes table names (SQL scripts, KPI and email SQL, the view dialog),
    `alias.` now completes the columns of the aliased table (`FROM DEMO_BILLING_USAGE b` … `b.`), also inside
    subqueries and `WITH` parts, and table names match whatever case they are typed in; `OWNER.TABLE.` works too.
    No keywords are offered right after `name.`. Table and column names are completed in upper case, as the
    dictionary names them.

