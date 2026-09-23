// The examples offered by CodeBox's "Example" menu, chosen by where the box is: its field, the control type, the
// email sheet side and, for KPIs, the family of the KPI type. examplesFor() is the only entry point.
//
// Each example is { title, caption, text }. Business tables and columns (ds_calls, charge, msisdn, ...) are
// placeholders; everything else is the real rapo / RACS_KPI_PKG API. The texts respect how the engine runs them:
//   - datasource filters, mismatch criteria and case mappings are raw SQL without {variables};
//   - Preparation/Prerequisite/Completion SQL and email filters get {control_name}, {process_id}, {control_date},
//     {control_date_from} and {control_date_to} (dates take a strftime format, e.g. {control_date:%Y%m%d});
//   - the email's Free SQL is a query (select/with) with the same variables plus the run facts of
//     mailer.build_variables ({status}, {fetched_number}, ...), substituted as text;
//   - KPI statements get only the bind :v_processid, and alarm statements :v_kpi_value, which must be used;
//   - alarm statements are also read by racs_kpi_pkg.get_kpi_thresholds_json with regular expressions, so they
//     keep the shape "case when <condition on :v_kpi_value> then 1..3 ... else 0 end from dual".
// <control_name>, <result_table> and <result_table_b> are placeholders of the examples themselves, filled in by
// examplesFor() when the control is known.

const DATE_FORMAT = "yyyy-mm-dd hh24:mi:ss";
const WINDOW_FROM = `to_date('{control_date_from:%Y-%m-%d %H:%M:%S}', '${DATE_FORMAT}')`;
const WINDOW_TO = `to_date('{control_date_to:%Y-%m-%d %H:%M:%S}', '${DATE_FORMAT}')`;
const CONTROL_DATE = "to_date('{control_date:%Y-%m-%d}', 'yyyy-mm-dd')";
const THRESHOLD_NOTE = "Keep this shape: the dashboard reads its thresholds from it.";

const FILTER = [
  {
    title: "Simple conditions",
    caption: "A WHERE condition on the datasource columns. The date window is applied already.",
    text: "service_id = 1\nand direction in ('MO', 'MT')",
  },
  {
    title: "Exclude test records and empty keys",
    caption: "nvl() keeps the records whose type is not set.",
    text: "msisdn is not null\nand msisdn not like '4369912%'\nand nvl(record_type, 'X') <> 'TEST'",
  },
  {
    title: "Deny list (subselect)",
    caption: "NOT IN returns nothing when the list holds a NULL, hence the is not null.",
    text: "msisdn not in (\n    select msisdn\n    from ref_test_numbers\n    where msisdn is not null\n      and (valid_to is null or valid_to > sysdate)\n)",
  },
  {
    title: "Reference table over a DB link",
    caption: "Only the records of tariffs active in another system.",
    text: "tariff_id in (\n    select tariff_id\n    from ref_tariff@billing\n    where active = 'Y'\n)",
  },
  {
    title: "Business hours on working days",
    caption: "Language-independent day names thanks to NLS_DATE_LANGUAGE.",
    text:
      "to_number(to_char(event_date, 'HH24')) between 8 and 19\n" +
      "and to_char(event_date, 'DY', 'NLS_DATE_LANGUAGE=ENGLISH') not in ('SAT', 'SUN')",
  },
];

const ERROR_DEFINITION = [
  {
    title: "Catch all",
    caption: "Every fetched record is a discrepancy, e.g. when the datasource is already the list of errors.",
    text: "1=1",
  },
  {
    title: "Mismatch, including missing values",
    caption: "decode() treats two NULLs as equal, so a NULL on one side only is a mismatch.",
    text: "decode(charge, calc_charge, 0, 1) = 1",
  },
  {
    title: "Mismatch above a tolerance",
    caption: "Rounding differences up to 0.01 are not discrepancies.",
    text: "abs(nvl(charge, 0) - nvl(calc_charge, 0)) > 0.01",
  },
  {
    title: "Mismatch outside an allow list",
    caption: "Known exceptions are kept out with a subselect.",
    text: "(charge <> calc_charge or calc_charge is null)\nand imsi not in (\n    select imsi\n    from ref_imsi_whitelist\n    where imsi is not null\n)",
  },
  {
    title: "The same in JSON syntax",
    caption: "column, relation, value; is_column compares with another column; connexion joins the conditions.",
    text: '[\n    {"column": "CHARGE", "value": "CALC_CHARGE", "is_column": true},\n    {"connexion": "or", "column": "CALC_CHARGE", "relation": "is", "value": "NULL"}\n]',
  },
];

const CASE_NOTE = "The IDs after THEN/ELSE must exist in the Case config above.";
const CASE_DEFINITION = [
  {
    title: "Three classes",
    caption: `Missing value first, since a comparison with NULL is never true. ${CASE_NOTE}`,
    text: "case\n    when calc_charge is null then 3\n    when charge <> calc_charge then 2\n    else 1\nend",
  },
  {
    title: "Severity by amount",
    caption: CASE_NOTE,
    text: "case\n    when abs(charge - calc_charge) >= 100 then 3\n    when abs(charge - calc_charge) >= 10 then 2\n    else 1\nend",
  },
  {
    title: "Overcharge or undercharge",
    caption: CASE_NOTE,
    text: "case\n    when charge > calc_charge then 1\n    when charge < calc_charge then 2\n    else 3\nend",
  },
  {
    title: "By service",
    caption: CASE_NOTE,
    text: "case\n    when service_type = 'VOICE' then 1\n    when service_type in ('SMS', 'MMS') then 2\n    else 3\nend",
  },
];

const LOG_LINE = {
  title: "Log line (using variables)",
  caption: "{control_name}, {process_id} and the dates are replaced before the statement runs.",
  text:
    "insert into log_control_run (message, status, run_date, logged)\n" +
    "values (\n" +
    "    '{control_name} (PID {process_id}) for {control_date_from:%Y-%m-%d} - {control_date_to:%Y-%m-%d}',\n" +
    "    'COMPLETE',\n" +
    `    ${CONTROL_DATE},\n` +
    "    sysdate\n" +
    ")",
};

const PREPARATION = [
  {
    title: "Refresh a materialized view",
    caption: "Complete refresh ('C') of a view the datasource reads from.",
    text: "begin\n    dbms_mview.refresh('MV_ACTIVE_SUBSCRIBERS', 'C');\nend;",
  },
  {
    title: "Rebuild a staging table for the window",
    caption: "DDL runs through execute immediate; the window comes from the control's dates.",
    text:
      "begin\n" +
      "    execute immediate 'truncate table stg_calls';\n" +
      "    insert into stg_calls\n" +
      "    select *\n" +
      "    from ds_calls\n" +
      `    where event_date between ${WINDOW_FROM}\n` +
      `                         and ${WINDOW_TO};\n` +
      "    commit;\n" +
      "end;",
  },
  {
    title: "Gather statistics of the source",
    caption: "Fresh statistics after a large load help the optimizer.",
    text: "begin\n    dbms_stats.gather_table_stats(ownname => user, tabname => 'STG_CALLS');\nend;",
  },
  LOG_LINE,
  {
    title: "Table per control and day (dynamic name)",
    caption: "Drops the table of the same day if it exists, then creates it anew.",
    text:
      "declare\n" +
      "    table_count integer;\n" +
      "begin\n" +
      "    select count(*) into table_count\n" +
      "    from user_tables\n" +
      "    where table_name = upper('tmp_{control_name}_{control_date:%Y%m%d}');\n" +
      "    if table_count > 0 then\n" +
      "        execute immediate 'drop table tmp_{control_name}_{control_date:%Y%m%d} purge';\n" +
      "    end if;\n" +
      "    execute immediate 'create table tmp_{control_name}_{control_date:%Y%m%d} as\n" +
      "        select * from ds_calls where event_date >= trunc(sysdate) - 7';\n" +
      "end;",
  },
];

const PREREQUISITE_NOTE = "The control runs only when the number is not 0.";
const PREREQUISITE = [
  {
    title: "Source has data for the window",
    caption: PREREQUISITE_NOTE,
    text: `select count(*)\nfrom ds_calls\nwhere event_date between ${WINDOW_FROM}\n                     and ${WINDOW_TO}\n  and rownum = 1`,
  },
  {
    title: "Load of the day is finished",
    caption: PREREQUISITE_NOTE,
    text: `select count(*)\nfrom etl_load_log\nwhere table_name = 'DS_CALLS'\n  and load_date = ${CONTROL_DATE}\n  and status = 'DONE'`,
  },
  {
    title: "Partition of the day exists",
    caption: `A partition named after the control date, e.g. P20260923. ${PREREQUISITE_NOTE}`,
    text: "select count(*)\nfrom user_tab_partitions\nwhere table_name = 'DS_CALLS'\n  and partition_name = 'P{control_date:%Y%m%d}'",
  },
  {
    title: "Upstream control finished for the same window",
    caption: `Waits for another rapo control to end with status D. ${PREREQUISITE_NOTE}`,
    text:
      "select count(*)\n" +
      "from rapo_log l\n" +
      "join rapo_config c on c.control_id = l.control_id\n" +
      "where c.control_name = 'UPSTREAM_CONTROL'\n" +
      "  and l.status = 'D'\n" +
      `  and l.date_from = ${WINDOW_FROM}`,
  },
  {
    title: "Working days only",
    caption: PREREQUISITE_NOTE,
    text:
      "select case\n" +
      `    when to_char(${CONTROL_DATE}, 'DY', 'NLS_DATE_LANGUAGE=ENGLISH') in ('SAT', 'SUN') then 0\n` +
      "    else 1\n" +
      "end\nfrom dual",
  },
];

const COMPLETION = [
  {
    title: "Run the next control",
    caption: "Sends a run request to rapo for the same window.",
    text:
      "begin\n" +
      "    racs_kpi_pkg.run_rapo_control(\n" +
      "        'NEXT_CONTROL',\n" +
      `        ${WINDOW_FROM},\n` +
      `        ${WINDOW_TO}\n` +
      "    );\n" +
      "end;",
  },
  {
    title: "Archive the results of this run (dynamic table name)",
    caption: "{control_name} builds the result table name, {process_id} picks this run.",
    text:
      "begin\n" +
      "    insert into hist_{control_name}\n" +
      "    select *\n" +
      "    from <result_table>\n" +
      "    where rapo_process_id = {process_id};\n" +
      "    commit;\n" +
      "end;",
  },
  {
    title: "Post an alarm when there are discrepancies",
    caption: "Reads the counts of this run from rapo_log.",
    text:
      "begin\n" +
      "    for run in (select error_number from rapo_log where process_id = {process_id} and error_number > 0) loop\n" +
      "        racs_kpi_pkg.post_alarm_to_dash(\n" +
      "            in_alarm_object => '{control_name}',\n" +
      `            in_alarm_date => ${CONTROL_DATE},\n` +
      "            in_alarm_level => 2,\n" +
      "            in_alarm_description => run.error_number || ' discrepancies found'\n" +
      "        );\n" +
      "    end loop;\n" +
      "end;",
  },
  LOG_LINE,
  {
    title: "Drop the table per control and day",
    caption: "Cleans up the table created by the Preparation example.",
    text: "begin\n    execute immediate 'drop table tmp_{control_name}_{control_date:%Y%m%d} purge';\nexception\n    when others then null;\nend;",
  },
];

// Email sheets are already limited to this run (rapo_process_id) and, for REC, to the chosen result types.
const EMAIL_FILTER = [
  {
    title: "Amount above a threshold",
    caption: "Mail only the discrepancies worth a look.",
    text: "abs(nvl(charge, 0) - nvl(calc_charge, 0)) > 10",
  },
  {
    title: "Discrepancy on a given field",
    caption: "A reconciliation lists the differing fields in rapo_discrepancy_description as FIELD|value.",
    text: "rapo_discrepancy_description like '%CHARGE|%'",
    types: ["REC"],
  },
  {
    title: "Only new since the previous runs (using variables)",
    caption: "{process_id} is this run; earlier runs of the control are in the same table.",
    text:
      "msisdn not in (\n" +
      "    select msisdn\n" +
      "    from <result_table>\n" +
      "    where rapo_process_id < {process_id}\n" +
      "      and msisdn is not null\n" +
      ")",
  },
  {
    title: "Exclude an allow list",
    caption: "Known exceptions are not mailed.",
    text: "msisdn not in (\n    select msisdn\n    from ref_test_numbers\n    where msisdn is not null\n)",
  },
  {
    title: "Losses and duplicates only",
    caption: "For analysis and report controls, whose results carry the case type.",
    text: "rapo_result_type in ('Loss', 'Duplicate')",
    types: ["ANL", "REP"],
  },
];

// The email's Free SQL sheet: a whole query, whose column names (quoted aliases keep their case) become the headers.
const EMAIL_SQL = [
  {
    title: "This run's results, chosen columns",
    caption: "Quoted aliases become the headers of the sheet.",
    text:
      "select msisdn as \"MSISDN\",\n" +
      "       charge as \"Charge\",\n" +
      "       rapo_result_type as \"Result\"\n" +
      "from <result_table>\n" +
      "where rapo_process_id = {process_id}\n" +
      "order by charge desc",
  },
  {
    title: "Count per result type",
    caption: "A small summary sheet next to the detail.",
    text:
      "select rapo_result_type as \"Result type\",\n" +
      "       count(*) as \"Records\"\n" +
      "from <result_table>\n" +
      "where rapo_process_id = {process_id}\n" +
      "group by rapo_result_type\n" +
      "order by 2 desc",
  },
  {
    title: "Losses of both sides in one sheet",
    caption: "Sides A and B are separate result tables; a SIDE column tells them apart.",
    text:
      "select 'A' as side, msisdn, charge\n" +
      "from <result_table>\n" +
      "where rapo_process_id = {process_id}\n" +
      "  and rapo_result_type = 'Loss'\n" +
      "union all\n" +
      "select 'B' as side, msisdn, charge\n" +
      "from <result_table_b>\n" +
      "where rapo_process_id = {process_id}\n" +
      "  and rapo_result_type = 'Loss'",
    types: ["REC"],
  },
  {
    title: "Discrepancies per differing fields",
    caption: "rapo_discrepancy_description lists them as FIELD|value; — the values are dropped to group.",
    text:
      "select regexp_replace(rapo_discrepancy_description, '\\|[^;]*', '') as \"Differing fields\",\n" +
      "       count(*) as \"Records\"\n" +
      "from <result_table>\n" +
      "where rapo_process_id = {process_id}\n" +
      "  and rapo_result_type = 'Discrepancy'\n" +
      "group by regexp_replace(rapo_discrepancy_description, '\\|[^;]*', '')\n" +
      "order by 2 desc",
    types: ["REC"],
  },
  {
    title: "Source rows of the run's window",
    caption: "Dates are substituted as text, so they are quoted and converted.",
    text: "select *\n" + "from ds_calls\n" + `where call_date >= ${WINDOW_FROM}\n` + `  and call_date <= ${WINDOW_TO}`,
  },
  {
    title: "Trend of the last 10 runs",
    caption: "Result counts of this control's runs up to this one, from rapo_log.",
    text:
      "select *\n" +
      "from (\n" +
      "    select l.process_id as \"Process ID\",\n" +
      "           l.date_from as \"Run from\",\n" +
      "           l.status as \"Status\",\n" +
      "           (select count(*) from <result_table> r where r.rapo_process_id = l.process_id) as \"Results\"\n" +
      "    from rapo_log l\n" +
      "    join rapo_config c on c.control_id = l.control_id\n" +
      "    where c.control_name = '{control_name}'\n" +
      "      and l.process_id <= {process_id}\n" +
      "    order by l.process_id desc\n" +
      ")\n" +
      "where rownum <= 10",
  },
];

// KPI statements of one control: one number for the run :v_processid. By family, see kpiFamily().
const KPI = {
  monetary: [
    {
      title: "Value of losses and discrepancies",
      caption: "get_rapo_discrepancy: the whole field for Loss/Duplicate, the difference for a Discrepancy.",
      text:
        "select nvl(sum(\n" +
        "    racs_kpi_pkg.get_rapo_discrepancy(rapo_result_type, rapo_discrepancy_description, 'CHARGE', charge)\n" +
        "), 0)\n" +
        "from <result_table>\n" +
        "where rapo_process_id = :v_processid",
      types: ["REC"],
    },
    {
      title: "Undercharge only (loss)",
      caption: "Only positive differences: charged less than it should be.",
      text:
        "select nvl(sum(greatest(\n" +
        "    racs_kpi_pkg.get_rapo_discrepancy(rapo_result_type, rapo_discrepancy_description, 'CHARGE', charge), 0\n" +
        ")), 0)\n" +
        "from <result_table>\n" +
        "where rapo_process_id = :v_processid",
      types: ["REC"],
    },
    {
      title: "Overcharge only (unjustified gain)",
      caption: "Only negative differences, as a positive amount.",
      text:
        "select nvl(sum(abs(least(\n" +
        "    racs_kpi_pkg.get_rapo_discrepancy(rapo_result_type, rapo_discrepancy_description, 'CHARGE', charge), 0\n" +
        "))), 0)\n" +
        "from <result_table>\n" +
        "where rapo_process_id = :v_processid",
      types: ["REC"],
    },
    {
      title: "Value of the differences",
      caption: "The charged amount against the expected one, both directions.",
      text: "select nvl(sum(abs(charge - calc_charge)), 0)\nfrom <result_table>\nwhere rapo_process_id = :v_processid",
      types: ["ANL", "REP", "CMP"],
    },
    {
      title: "Undercharge only (loss)",
      caption: "Only where less was charged than expected.",
      text: "select nvl(sum(calc_charge - charge), 0)\nfrom <result_table>\nwhere rapo_process_id = :v_processid\n  and calc_charge > charge",
      types: ["ANL", "REP", "CMP"],
    },
    {
      title: "Overcharge only (unjustified gain)",
      caption: "Only where more was charged than expected.",
      text: "select nvl(sum(charge - calc_charge), 0)\nfrom <result_table>\nwhere rapo_process_id = :v_processid\n  and charge > calc_charge",
      types: ["ANL", "REP", "CMP"],
    },
    {
      title: "Rated with a tariff table",
      caption: "The partner's own rate, or the average rate when it has none.",
      text:
        "select nvl(sum(case\n" +
        "    when a.call_type = 'MOC' then (a.call_duration / 60) * coalesce(r.rate_per_min, d.rate_per_min)\n" +
        "    when a.call_type = 'MOSMS' then coalesce(r.rate_per_sms, d.rate_per_sms)\n" +
        "end), 0)\n" +
        "from <result_table> a\n" +
        "left join ref_rate r on r.provider_id = a.provider_id\n" +
        "cross join (select * from ref_rate where provider_id = 'AVG') d\n" +
        "where a.rapo_process_id = :v_processid\n" +
        "  and a.rapo_result_type = 'Loss'",
    },
    {
      title: "Value on side B",
      caption: "A reconciliation keeps side B in its own result table.",
      text:
        "select nvl(sum(\n" +
        "    racs_kpi_pkg.get_rapo_discrepancy(rapo_result_type, rapo_discrepancy_description, 'CHARGE', charge)\n" +
        "), 0)\n" +
        "from <result_table_b>\n" +
        "where rapo_process_id = :v_processid",
      types: ["REC"],
    },
  ],
  points: [
    {
      title: "Points per call type",
      caption: "get_kpi_multiplier reads the factor from RACS_KPI_MULTIPLIER, 1 when it is missing.",
      text:
        "select nvl(sum(case\n" +
        "    when call_type = 'MOC' then ceil(call_duration / 60) * racs_kpi_pkg.get_kpi_multiplier('MOC_POINTS')\n" +
        "    when call_type = 'MOSMS' then racs_kpi_pkg.get_kpi_multiplier('SMS_POINTS')\n" +
        "end), 0)\n" +
        "from <result_table>\n" +
        "where rapo_process_id = :v_processid",
    },
    {
      title: "Monetary value of the points",
      caption: "Points converted with a second multiplier.",
      text:
        "select nvl(sum(points), 0) * racs_kpi_pkg.get_kpi_multiplier('EUR_PER_POINT')\n" +
        "from <result_table>\n" +
        "where rapo_process_id = :v_processid",
    },
    {
      title: "Records with points",
      caption: "How many results carry points at all.",
      text: "select count(*)\nfrom <result_table>\nwhere rapo_process_id = :v_processid\n  and points > 0",
    },
  ],
  discrepancies: [
    {
      title: "Discrepancy records",
      caption: "One result type; Loss, Duplicate, Error... work the same way.",
      text: "select count(*)\nfrom <result_table>\nwhere rapo_process_id = :v_processid\n  and rapo_result_type = 'Discrepancy'",
    },
    {
      title: "Distinct subscribers affected",
      caption: "Counts keys instead of records.",
      text: "select count(distinct msisdn)\nfrom <result_table>\nwhere rapo_process_id = :v_processid",
    },
    {
      title: "Repeating discrepancies",
      caption: "Discrepancies equal (on MSISDN and IMSI) to one of the last 3 runs; side 'A', 'B' or 'ANB'.",
      text: "select racs_kpi_pkg.get_rapo_repeating_discrepancies(:v_processid, 'MSISDN,IMSI', 3, 'A')\nfrom dual",
    },
    {
      title: "Discrepancies older than 7 days",
      caption: "Relative to the end of the run's window, from rapo_log.",
      text:
        "select count(*)\n" +
        "from <result_table> r\n" +
        "join rapo_log l on l.process_id = r.rapo_process_id\n" +
        "where r.rapo_process_id = :v_processid\n" +
        "  and r.event_date < l.date_to - 7",
    },
    {
      title: "Duplicate records",
      caption: "Records the control found more than once.",
      text: "select count(*)\nfrom <result_table>\nwhere rapo_process_id = :v_processid\n  and rapo_result_type = 'Duplicate'",
    },
  ],
  trend: [
    {
      title: "Trend of fetched records (A)",
      caption: "Deviation in % from the trend of previous runs. Also FETCHED_B, SUCCESS_A/B, ERROR_NUMBER_A/B, ERROR_LEVEL_A/B.",
      text: "select racs_kpi_pkg.get_rapo_control_trend(:v_processid, 'FETCHED_A')\nfrom dual",
    },
    {
      title: "Trend of the error level (A)",
      caption: "Deviation in % of the error level from its trend.",
      text: "select racs_kpi_pkg.get_rapo_control_trend(:v_processid, 'ERROR_LEVEL_A')\nfrom dual",
    },
    {
      title: "Trend of discrepancies (B)",
      caption: "Deviation in % of the discrepancy count on side B.",
      text: "select racs_kpi_pkg.get_rapo_control_trend(:v_processid, 'ERROR_NUMBER_B')\nfrom dual",
    },
  ],
  volume: [
    {
      title: "Zero records on either side",
      caption: "100 when a side fetched nothing, otherwise 0. fetched_number is the single side of ANL/REP/CMP.",
      text:
        "select case\n" +
        "    when coalesce(fetched_number_a, fetched_number, 0) = 0 then 100\n" +
        "    when control_type = 'REC' and nvl(fetched_number_b, 0) = 0 then 100\n" +
        "    else 0\n" +
        "end\n" +
        "from rapo_log l\n" +
        "join rapo_config c on c.control_id = l.control_id\n" +
        "where l.process_id = :v_processid",
    },
    {
      title: "Ratio of A to B records in %",
      caption: "0 when both sides fetched the same number of records.",
      text:
        "select case\n" +
        "    when nvl(fetched_number_b, 0) = 0 then 100\n" +
        "    else least((fetched_number_a / fetched_number_b - 1) * 100, 100)\n" +
        "end\n" +
        "from rapo_log\n" +
        "where process_id = :v_processid",
    },
    {
      title: "Fetched records",
      caption: "Side A of a reconciliation, or the only side of the other types.",
      text: "select coalesce(fetched_number_a, fetched_number)\nfrom rapo_log\nwhere process_id = :v_processid",
    },
  ],
  errorLevel: [
    {
      title: "Error level (A)",
      caption: "Share of discrepancies in %, as rapo computed it for the run.",
      text: "select coalesce(error_level_a, error_level)\nfrom rapo_log\nwhere process_id = :v_processid",
    },
    {
      title: "Error level (B)",
      caption: "Side B of a reconciliation.",
      text: "select nvl(error_level_b, 0)\nfrom rapo_log\nwhere process_id = :v_processid",
    },
    {
      title: "Discrepancy records (A)",
      caption: "The count behind the error level.",
      text: "select coalesce(error_number_a, error_number)\nfrom rapo_log\nwhere process_id = :v_processid",
    },
  ],
  general: [
    {
      title: "Count of result records",
      caption: "All results of the run.",
      text: "select count(*)\nfrom <result_table>\nwhere rapo_process_id = :v_processid",
    },
    {
      title: "Sum of a result column",
      caption: "nvl() makes a run without results count as 0.",
      text: "select nvl(sum(charge), 0)\nfrom <result_table>\nwhere rapo_process_id = :v_processid",
    },
  ],
};

// A type default applies to every control of the type, so it can't name one control's result table. Only the
// statements that find their data by :v_processid alone are offered.
const DEFAULT_KPI = {
  discrepancies: [KPI.discrepancies[2]],
  trend: KPI.trend,
  volume: KPI.volume,
  errorLevel: KPI.errorLevel,
  general: [
    {
      title: "Records of the run",
      caption: "Fetched records from rapo_log, whatever the result table.",
      text: "select coalesce(fetched_number_a, fetched_number)\nfrom rapo_log\nwhere process_id = :v_processid",
    },
  ],
};

const ALARM = {
  monetary: [
    {
      title: "Three levels by amount",
      caption: THRESHOLD_NOTE,
      text: "select\ncase\n    when :v_kpi_value > 1000 then 3\n    when :v_kpi_value > 500 then 2\n    when :v_kpi_value > 100 then 1\n    else 0\nend\nfrom dual",
    },
    {
      title: "Single threshold",
      caption: THRESHOLD_NOTE,
      text: "select\ncase\n    when :v_kpi_value >= 800 then 3\n    else 0\nend\nfrom dual",
    },
  ],
  percent: [
    {
      title: "Deviation of 50% either way",
      caption: `abs() covers both directions. ${THRESHOLD_NOTE}`,
      text: "select\ncase\n    when abs(:v_kpi_value) >= 50 then 1\n    else 0\nend\nfrom dual",
    },
    {
      title: "Escalating deviation",
      caption: THRESHOLD_NOTE,
      text: "select\ncase\n    when abs(:v_kpi_value) >= 80 then 3\n    when abs(:v_kpi_value) >= 50 then 2\n    when abs(:v_kpi_value) >= 20 then 1\n    else 0\nend\nfrom dual",
    },
  ],
  zero: [
    {
      title: "Any value is an alarm",
      caption: `For 0/100 flags such as zero records. ${THRESHOLD_NOTE}`,
      text: "select\ncase\n    when :v_kpi_value > 0 then 2\n    else 0\nend\nfrom dual",
    },
  ],
  errorLevel: [
    {
      title: "Error level in %",
      caption: THRESHOLD_NOTE,
      text: "select\ncase\n    when :v_kpi_value >= 5 then 3\n    when :v_kpi_value >= 1 then 1\n    else 0\nend\nfrom dual",
    },
  ],
  count: [
    {
      title: "Any record is an alarm",
      caption: THRESHOLD_NOTE,
      text: "select\ncase\n    when :v_kpi_value > 0 then 1\n    else 0\nend\nfrom dual",
    },
    {
      title: "Three levels by count",
      caption: THRESHOLD_NOTE,
      text: "select\ncase\n    when :v_kpi_value > 100 then 3\n    when :v_kpi_value > 10 then 2\n    when :v_kpi_value > 0 then 1\n    else 0\nend\nfrom dual",
    },
  ],
};

const KPI_FAMILIES = {
  monetary: { label: "Monetary", alarm: ["monetary"] },
  points: { label: "Points", alarm: ["monetary"] },
  discrepancies: { label: "Discrepancies", alarm: ["count"] },
  trend: { label: "Trend", alarm: ["percent"] },
  volume: { label: "Records", alarm: ["zero", "percent"] },
  errorLevel: { label: "Error level", alarm: ["errorLevel"] },
  general: { label: "General", alarm: ["count", "monetary"] },
};

// The family of a KPI type, from the convention of its code (RACS_KPI_TYPE): MVA/MVB/MVAL... are monetary,
// ER*/DUP/CER discrepancy counts, TR*/ELAT trends, DZ*/DS* record volumes, EL* error levels.
export function kpiFamily(code) {
  const value = (code || "").toUpperCase();
  if (/^MV/.test(value)) return "monetary";
  if (/^MP/.test(value)) return "points";
  if (/^(TR|ELAT)/.test(value)) return "trend";
  if (/^(ER|DUP|CER)/.test(value)) return "discrepancies";
  if (/^(DZ|DS)/.test(value)) return "volume";
  if (/^EL/.test(value)) return "errorLevel";
  return "general";
}

function forType(items, controlType) {
  return items.filter((item) => !item.types || !controlType || item.types.includes(controlType));
}

// One menu: the items of the context's own group, the other groups under "More".
function grouped(groups, labels, own, controlType) {
  const items = forType(groups[own] || [], controlType);
  const more = Object.keys(groups)
    .filter((key) => key !== own)
    .map((key) => ({ group: labels[key] || key, items: forType(groups[key], controlType) }))
    .filter((group) => group.items.length);
  return { items, more };
}

function alarmGroups(family) {
  const keys = KPI_FAMILIES[family].alarm;
  const labels = { monetary: "Amounts", percent: "Deviation in %", zero: "Flags", errorLevel: "Error level", count: "Counts" };
  const items = keys.flatMap((key) => ALARM[key]);
  const more = Object.keys(ALARM)
    .filter((key) => !keys.includes(key))
    .map((key) => ({ group: labels[key], items: ALARM[key] }));
  return { items, more };
}

function familyLabels() {
  return Object.fromEntries(Object.entries(KPI_FAMILIES).map(([key, family]) => [key, family.label]));
}

function resultTable(controlName, controlType, side) {
  const name = (controlName || "<control_name>").toUpperCase();
  if (controlType === "REC") return `RAPO_RES${side === "b" ? "B" : "A"}_${name}`;
  return `RAPO_REST_${name}`;
}

function fill(example, context) {
  const { controlName, controlType, side } = context;
  let text = example.text
    .replaceAll("<result_table_b>", resultTable(controlName, controlType, "b"))
    .replaceAll("<result_table>", resultTable(controlName, controlType, side));
  if (controlName) text = text.replaceAll("<control_name>", controlName);
  return { ...example, text };
}

function filled(menu, context) {
  return {
    items: menu.items.map((item) => fill(item, context)),
    more: menu.more.map((group) => ({ ...group, items: group.items.map((item) => fill(item, context)) })),
  };
}

/**
 * Get the examples of one CodeBox.
 *
 * @param {object} context
 * @param {string} context.field - filter, error_definition, case_definition, preparation, prerequisite,
 *   completion, email_filter, email_sql, kpi_sql, alarm_sql, default_kpi_sql or default_alarm_sql.
 * @param {string} [context.controlType] - ANL, REC, CMP or REP; picks the result table and type-bound examples.
 * @param {string} [context.controlName] - fills <control_name> and the result table names.
 * @param {string} [context.kpiType] - the KPI type code, whose family comes first.
 * @param {string} [context.side] - a or b, the side of an email sheet.
 * @returns {{items: object[], more: {group: string, items: object[]}[]}}
 */
export function examplesFor(context) {
  const { field, controlType, kpiType } = context;
  const plain = (items) => filled({ items: forType(items, controlType), more: [] }, context);
  const family = kpiFamily(kpiType);
  switch (field) {
    case "filter":
      return plain(FILTER);
    case "error_definition":
      return plain(ERROR_DEFINITION);
    case "case_definition":
      return plain(CASE_DEFINITION);
    case "preparation":
      return plain(PREPARATION);
    case "prerequisite":
      return plain(PREREQUISITE);
    case "completion":
      return plain(COMPLETION);
    case "email_filter":
      return plain(EMAIL_FILTER);
    case "email_sql":
      return plain(EMAIL_SQL);
    case "kpi_sql":
      return filled(grouped(KPI, familyLabels(), family, controlType), context);
    case "default_kpi_sql":
      return filled(grouped(DEFAULT_KPI, familyLabels(), DEFAULT_KPI[family] ? family : "general", null), context);
    case "alarm_sql":
    case "default_alarm_sql":
      return alarmGroups(family);
    default:
      return { items: [], more: [] };
  }
}

// Every example, for tests: [{ field, group, title, text }].
export function allExamples() {
  const lists = { filter: FILTER, error_definition: ERROR_DEFINITION, case_definition: CASE_DEFINITION };
  Object.assign(lists, { preparation: PREPARATION, prerequisite: PREREQUISITE, completion: COMPLETION, email_filter: EMAIL_FILTER, email_sql: EMAIL_SQL });
  const rows = [];
  Object.entries(lists).forEach(([field, items]) => items.forEach((item) => rows.push({ field, group: null, ...item })));
  Object.entries(KPI).forEach(([group, items]) => items.forEach((item) => rows.push({ field: "kpi_sql", group, ...item })));
  Object.entries(ALARM).forEach(([group, items]) => items.forEach((item) => rows.push({ field: "alarm_sql", group, ...item })));
  return rows;
}
