create or replace PROCEDURE RAPO_USAGE_RULE (json_input IN CLOB)
    -- Invoker's rights: the procedure creates tables, and a CREATE TABLE held only through a role is disabled in a definer's-rights unit.
    AUTHID CURRENT_USER
AS
    /*
     RAPO_USAGE_RULE - Oracle-side execution engine for Rapo REC controls.

     Replaces stages s01..s09 of rapo/algorithms/reconciliation for a control whose rapo_config.control_engine is 'PL'. Scheduling, the
     rapo_log row, the hooks and the save into rapo_res* stay Rapo's job, so the two engines are interchangeable.

     Both sources are streamed in correlation-key order and ONE key group is held at a time. Inside a group, candidates are found with a
     two-pointer band join and capped per row by rule_config.max_candidates (default 100), so a group of n rows costs O(n * max_candidates)
     pairs and O(n * max_candidates^2) ranking. Clusters larger than the cap make the matching approximate; that is logged as a WARNING.

     Stage map:
       build_pairs       s01       candidate pairs, discrepancy flags, time gap
       assign_clusters   s01       sessionise pairs into clusters by time_shift
       classify_pairs    s01       cluster cardinalities -> O / F / A / B / M
       compute_*         s01       distance, time-gap rank, discrepancy rank
       organise_rows     s02       project the verdict onto each source row
       match_duplicates  s03-s05   pair square (F) clusters positionally
       match_conflicts   s06-s07   mutual-best-choice fixpoint for A/B/M
       emit_row          s08-s09   Match / Discrepancy / Loss / Duplicate
       materialise       s08-s09   write the temp tables Rapo then saves

     Correlation types, decided per cluster in classify_pairs:
       O  1 A x 1 B          one-to-one, matched immediately
       F  n A x n B, n>1     square "fuzzy" cluster, paired positionally
       A  1 A x n B          duplicates on the A side
       B  n A x 1 B          duplicates on the B side
       M  n A x m B, n<>m    many-to-many
     A row spanning clusters of several types takes the first of O>F>A>B>M.

     Contract:
       - The JSON CLOB is the only input; rapo_config is never read here. Rapo resolves the [ALGORITHM] fallbacks before serialising.
       - Rapo owns the rapo_log row: this only UPDATEs it, never inserts, and never sets rapo_log.updated (see report_progress).
       - Output is rapo_temp_error_{a,b}_<pid> and rapo_temp_stage_{a,b}_<pid>, which Rapo's _save path copies into rapo_res{a,b}_<name>.
       - Errors are re-raised so Rapo's _escape() records them.
       - Progress goes to rapo_engine_log, which the control process drains into the run's log file while the run is still going.
       - time_shift_* is the CANDIDATE reach; time_tolerance_* only FLAGS an already matched pair. They are not interchangeable.
       - A discrepancy field out of tolerance labels a matched pair, it never stops a match.
       - normalization_type 'minmax' is rejected: it normalises over the whole candidate set and has no streaming equivalent.

     See docs/rapo_usage_rule_payload.md for the payload and docs/rapo_usage_rule_review.md for the review of the original version.
    */

    -- Failures use raise_application_error with a -20001..-20005 code, so the reason survives into rapo_log.text_error.

    -- collections -----------------------------------------------------------------------------------------------------------------------
    TYPE t_num_tab IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
    TYPE t_str_tab IS TABLE OF VARCHAR2(4000) INDEX BY PLS_INTEGER;
    TYPE t_int_tab IS TABLE OF PLS_INTEGER INDEX BY PLS_INTEGER;

    -- One entry per correlation_config field. expr_* is ready-to-embed SQL: qualified with the a./b. alias, or verbatim in formula mode.
    TYPE t_corr IS RECORD (
        expr_a      VARCHAR2(4000),
        expr_b      VARCHAR2(4000),
        allow_null  BOOLEAN                  -- true: keep NULL-key rows (as Loss)
    );
    TYPE t_corr_tab IS TABLE OF t_corr INDEX BY PLS_INTEGER;

    -- One entry per discrepancy_config field. label_* is what appears in rapo_discrepancy_description.
    TYPE t_disc IS RECORD (
        expr_a    VARCHAR2(4000),
        expr_b    VARCHAR2(4000),
        tol_from  NUMBER,                    -- inclusive band; asymmetric is allowed
        tol_to    NUMBER,
        pct       BOOLEAN,                   -- compare a relative difference instead
        label_a   VARCHAR2(4000),
        label_b   VARCHAR2(4000)
    );
    TYPE t_disc_tab IS TABLE OF t_disc INDEX BY PLS_INTEGER;

    -- One fetched source row. Only the key, the date and the compared values; every other column is joined back from the datasource at the end.
    TYPE t_row IS RECORD (
        row_id        VARCHAR2(4000),        -- key field, or rowid when it is not one
        keys          t_str_tab,             -- canonical text of each correlation key
        dt            DATE,
        disc          t_num_tab,             -- coalesce(field, 0) per discrepancy field
        corr_type     VARCHAR2(1),           -- O/F/A/B/M, NULL when it has no candidate
        matched       BOOLEAN,               -- the s02 correlation_indicator
        matched_pair  PLS_INTEGER,           -- pair it was matched with (s08 branch 1)
        best_pair     PLS_INTEGER            -- nearest candidate (s08 branch 2)
    );
    TYPE t_row_tab IS TABLE OF t_row INDEX BY PLS_INTEGER;

    -- One candidate pair, i.e. one row of what s01 would put in t01_mod. ai/bi index into grp_a/grp_b of the group being resolved.
    TYPE t_pair IS RECORD (
        ai          PLS_INTEGER,
        bi          PLS_INTEGER,
        dt          DATE,                    -- greatest of the two dates, for clustering
        tsv         NUMBER,                  -- time gap a-b in seconds (signed)
        cluster_id  PLS_INTEGER,
        time_flag   BOOLEAN,                 -- gap outside time_tolerance
        flags       t_str_tab,               -- 'Y' per discrepancy field out of band
        vals        t_num_tab,               -- signed difference per discrepancy field
        dsum        NUMBER,                  -- sum of abs(vals): the discrepancy-rank key, summed once
        dist_a      NUMBER,                  -- summed normalised distance, A's view
        dist_b      NUMBER,                  -- ... and B's, which can differ
        trank_a     PLS_INTEGER,             -- rank by absolute time gap
        trank_b     PLS_INTEGER,
        drank_a     PLS_INTEGER,             -- rank by summed absolute difference
        drank_b     PLS_INTEGER,
        rank_a      PLS_INTEGER,             -- position over the full tie-break chain
        rank_b      PLS_INTEGER,
        corr_type   VARCHAR2(1),
        matched     BOOLEAN
    );
    TYPE t_pair_tab IS TABLE OF t_pair INDEX BY PLS_INTEGER;

    -- payload, all set by parse_payload ---------------------------------------------------------------------------------------------------
    v_process_id      NUMBER;                -- the rapo_log row Rapo already created
    v_control_name    VARCHAR2(128);         -- for log messages only
    v_date_from       DATE;                  -- the UNSHIFTED window; output is re-filtered to it, so shift padding
    v_date_to         DATE;                  -- correlates but never reaches a result
    v_debug_mode      BOOLEAN;               -- keep the verdict tables for inspection
    v_parallelism     NUMBER;                -- 0 emits no hint

    v_source_a        VARCHAR2(128);
    v_source_b        VARCHAR2(128);
    v_filter_a        CLOB;                  -- raw predicate, ANDed in parentheses
    v_filter_b        CLOB;
    v_date_field_a    VARCHAR2(128);
    v_date_field_b    VARCHAR2(128);
    v_key_field_a     VARCHAR2(128);
    v_key_field_b     VARCHAR2(128);
    v_key_rowid_a     BOOLEAN;               -- key is not a real column: use rowid, the same fallback _parse_select makes
    v_key_rowid_b     BOOLEAN;
    v_upstream_a      NUMBER;                -- a chain-rule side: the upstream run whose rows are read, instead of the window
    v_upstream_b      NUMBER;

    v_shift_from      NUMBER;                -- candidate reach, seconds
    v_shift_to        NUMBER;
    v_tol_from        NUMBER;                -- flag threshold, seconds (NOT a join)
    v_tol_to          NUMBER;
    v_allow_dups      BOOLEAN;               -- true drops Duplicate rows entirely
    v_fuzzy           BOOLEAN;               -- pair F clusters positionally
    v_norm            VARCHAR2(30);          -- distance formula; minmax is rejected
    v_disc_matching   BOOLEAN;               -- an unmatched duplicate WITH a discrepancy becomes Loss, not Duplicate, and Loss survives
                                             -- allow_duplicates filtering
    v_corr_limit      NUMBER;                -- 0 unlimited, -1 "size it from the fetched counts", else a literal cap
    v_max_candidates  NUMBER;                -- per-row fan-out cap; past this many rows in reach, a row keeps only the nearest in time
    capped_groups     NUMBER := 0;           -- how many groups hit that limit
    v_need_a          BOOLEAN;               -- process this side at all
    v_need_b          BOOLEAN;
    v_need_issues_a   BOOLEAN;
    v_need_issues_b   BOOLEAN;
    v_need_recons_a   BOOLEAN;               -- gates the stage table, as prepare_save gates s09
    v_need_recons_b   BOOLEAN;

    v_corr            t_corr_tab;
    v_disc            t_disc_tab;
    n_corr            PLS_INTEGER := 0;
    n_disc            PLS_INTEGER := 0;

    -- cursors ---------------------------------------------------------------------------------------------------------------------------
    -- DBMS_SQL rather than a ref cursor, because the select list is built at run time and its width depends on how many fields are configured.
    c_a               NUMBER;
    c_b               NUMBER;
    v_sql_a           CLOB;                  -- CLOB: real filters exceed VARCHAR2
    v_sql_b           CLOB;
    col_date_pos      PLS_INTEGER;           -- column layout: 1 row_id, 2..1+n_corr keys, then the date, then the discrepancy values
    col_disc_pos      PLS_INTEGER;

    cur_str           VARCHAR2(4000);        -- define_column only needs a value of the right type; never read
    cur_date          DATE;
    cur_num           NUMBER;

    row_a             t_row;                 -- the merge front: the next unconsumed row of each side
    row_b             t_row;
    have_a            BOOLEAN := FALSE;
    have_b            BOOLEAN := FALSE;

    grp_a             t_row_tab;             -- the key group being resolved and its candidate pairs: the whole memory footprint of the run
    grp_b             t_row_tab;
    pairs             t_pair_tab;

    fetched_a         NUMBER := 0;
    fetched_b         NUMBER := 0;

    vq_a_id           t_str_tab;
    vq_a_type         t_str_tab;
    vq_a_did          t_str_tab;
    vq_a_desc         t_str_tab;
    vq_b_id           t_str_tab;
    vq_b_type         t_str_tab;
    vq_b_did          t_str_tab;
    vq_b_desc         t_str_tab;

    -- verdict_* are ours and dropped at the end; error_* and stage_* are what Rapo reflects by name and saves, then drops in its own _finish.
    v_tmp_verdict_a   VARCHAR2(128);
    v_tmp_verdict_b   VARCHAR2(128);
    v_tmp_error_a     VARCHAR2(128);
    v_tmp_error_b     VARCHAR2(128);
    v_tmp_stage_a     VARCHAR2(128);
    v_tmp_stage_b     VARCHAR2(128);

    log_record_number PLS_INTEGER := 0;      -- orders the lines within one run
    groups_done       NUMBER := 0;
    last_reported     NUMBER := 0;           -- fetched total at the last report

    FLUSH_LIMIT  CONSTANT PLS_INTEGER := 5000;                          -- rows buffered before a FORALL insert
    EPOCH        CONSTANT DATE := to_date('1970-01-01', 'YYYY-MM-DD');  -- s02's numeric_value is in seconds since this
    REPORT_EVERY CONSTANT NUMBER := 50000;                              -- progress interval, counted over BOTH sides together

    ---------------------------------------------------------------------------------------------------------------------------- logging
    -- Autonomous transaction, so a line is visible to the control process at once without committing the work in flight.
    PROCEDURE log_line (log_level VARCHAR2, message CLOB) IS
        PRAGMA AUTONOMOUS_TRANSACTION;
    BEGIN
        log_record_number := log_record_number + 1;
        INSERT INTO rapo_engine_log (process_id, record_number, logged, log_level, message)
        VALUES (v_process_id, log_record_number, sysdate, log_level, message);
        COMMIT;
    EXCEPTION WHEN OTHERS THEN
        ROLLBACK;   -- logging must never be the reason a run fails
    END log_line;

    PROCEDURE log_info (message CLOB) IS
    BEGIN
        log_line('INFO', message);
    END log_info;

    PROCEDURE log_debug (message CLOB) IS
    BEGIN
        log_line('DEBUG', message);
    END log_debug;

    -- Publishes the running counts. Deliberately does NOT touch rapo_log.updated: rapo stamps that with the application clock, and a sysdate
    -- here would drag the column backwards and hide the run from the live-event watcher. The control process bumps it as it drains the log.
    PROCEDURE report_progress IS
        PRAGMA AUTONOMOUS_TRANSACTION;
    BEGIN
        UPDATE rapo_log SET fetched_number_a = fetched_a, fetched_number_b = fetched_b WHERE process_id = v_process_id;
        COMMIT;
        last_reported := fetched_a + fetched_b;
    EXCEPTION WHEN OTHERS THEN
        ROLLBACK;
    END report_progress;

    ------------------------------------------------------------------------------------------------------------------------------ utils
    -- Read a JSON boolean. JSON_VALUE ... RETURNING BOOLEAN is PL/SQL-only on 19c and cannot express a default for an absent key.
    FUNCTION jb (path VARCHAR2, default_value BOOLEAN) RETURN BOOLEAN IS
        v VARCHAR2(10);
    BEGIN
        v := json_value(json_input, path);
        IF v IS NULL THEN RETURN default_value; END IF;
        RETURN lower(v) = 'true';
    END jb;

    -- Read a JSON number, or the default when the key is absent or not one.
    FUNCTION jn (path VARCHAR2, default_value NUMBER) RETURN NUMBER IS
    BEGIN
        RETURN nvl(json_value(json_input, path RETURNING NUMBER), default_value);
    END jn;

    -- Validate an identifier before it is concatenated into dynamic SQL; raises ORA-44003 on anything that is not a simple SQL name.
    -- Filters and formula-mode expressions are deliberately NOT passed through this: they are arbitrary SQL by design.
    FUNCTION quoted (name VARCHAR2) RETURN VARCHAR2 IS
    BEGIN
        RETURN dbms_assert.simple_sql_name(name);
    END quoted;

    -- The rows of one side in scope: those in the window, or, for a side read from another control's results (a chain-rule), those saved
    -- by the upstream run, which applied the window itself.
    FUNCTION scope_predicate (side CHAR, alias VARCHAR2, date_field VARCHAR2, win_from DATE, win_to DATE) RETURN VARCHAR2 IS
        upstream NUMBER := CASE WHEN side = 'A' THEN v_upstream_a ELSE v_upstream_b END;
    BEGIN
        IF upstream IS NOT NULL THEN
            RETURN alias || '.rapo_process_id = ' || to_char(upstream);
        END IF;
        RETURN alias || '.' || quoted(date_field)
               || ' between to_date(''' || to_char(win_from, 'YYYY-MM-DD HH24:MI:SS') || ''', ''YYYY-MM-DD HH24:MI:SS'')'
               || ' and to_date(''' || to_char(win_to, 'YYYY-MM-DD HH24:MI:SS') || ''', ''YYYY-MM-DD HH24:MI:SS'')';
    END scope_predicate;

    -- The canonical text form of a correlation key. The cursor's ORDER BY and cmp_keys must impose the same ordering, so the conversion has
    -- to be type-stable: an implicit date-to-text conversion would follow NLS_DATE_FORMAT and drop the time. Hence the explicit masks.
    FUNCTION canon (expr VARCHAR2, data_type VARCHAR2) RETURN VARCHAR2 IS
    BEGIN
        IF data_type IN ('DATE') THEN
            RETURN 'to_char(' || expr || ', ''YYYY-MM-DD HH24:MI:SS'')';
        ELSIF data_type LIKE 'TIMESTAMP%' THEN
            RETURN 'to_char(cast(' || expr || ' as date), ''YYYY-MM-DD HH24:MI:SS'')';
        ELSIF data_type IN ('NUMBER', 'FLOAT', 'BINARY_FLOAT', 'BINARY_DOUBLE') THEN
            RETURN 'to_char(' || expr || ')';
        ELSE
            RETURN 'cast(' || expr || ' as varchar2(4000))';
        END IF;
    END canon;

    -- TABLE / VIEW / MATERIALIZED VIEW, or NULL when there is no such object. Used to fail early instead of an ORA-00942 from generated SQL.
    FUNCTION object_type_of (name VARCHAR2) RETURN VARCHAR2 IS
        v VARCHAR2(30);
    BEGIN
        SELECT object_type INTO v
          FROM user_objects
         WHERE object_name = upper(name) AND object_type IN ('TABLE', 'VIEW', 'MATERIALIZED VIEW') AND rownum = 1;
        RETURN v;
    EXCEPTION WHEN no_data_found THEN
        RETURN NULL;
    END object_type_of;

    -- Is the configured key field a real column, or does it fall back to rowid? The parameters are qualified with the procedure name because
    -- they collide with the dictionary column names, and an unqualified reference would make the predicate a tautology.
    FUNCTION has_column (source_name VARCHAR2, column_name VARCHAR2) RETURN BOOLEAN IS
        v PLS_INTEGER;
    BEGIN
        SELECT count(*) INTO v
          FROM user_tab_cols t
         WHERE t.table_name = upper(has_column.source_name) AND t.column_name = upper(has_column.column_name);
        RETURN v > 0;
    END has_column;

    -- Drop a table, tolerating "does not exist" (-942) and nothing else.
    PROCEDURE drop_if_exists (name VARCHAR2) IS
    BEGIN
        EXECUTE IMMEDIATE 'drop table ' || name || ' purge';
    EXCEPTION WHEN OTHERS THEN
        IF sqlcode != -942 THEN RAISE; END IF;
    END drop_if_exists;

    ---------------------------------------------------------------------------------------------------------------------------- payload
    -- Read and validate the whole payload, and resolve the two things that depend on the schema rather than the JSON: whether each
    -- datasource exists, and whether its key field is a real column.
    PROCEDURE parse_payload IS
        v_norm_in VARCHAR2(30);
    BEGIN
        v_process_id   := json_value(json_input, '$.process_id' RETURNING NUMBER);
        v_control_name := json_value(json_input, '$.control_name');
        v_date_from    := to_date(json_value(json_input, '$.date_from'), 'YYYY-MM-DD HH24:MI:SS');
        v_date_to      := to_date(json_value(json_input, '$.date_to'), 'YYYY-MM-DD HH24:MI:SS');
        v_debug_mode   := jb('$.debug_mode', FALSE);
        v_parallelism  := jn('$.parallelism', 0);

        IF v_process_id IS NULL OR v_control_name IS NULL OR v_date_from IS NULL OR v_date_to IS NULL THEN
            raise_application_error(-20001, 'RAPO_USAGE_RULE: process_id, control_name, date_from and date_to are all required');
        END IF;

        v_source_a     := json_value(json_input, '$.source_a.name');
        v_filter_a     := json_value(json_input, '$.source_a.filter' RETURNING CLOB);
        v_date_field_a := json_value(json_input, '$.source_a.date_field');
        v_key_field_a  := json_value(json_input, '$.source_a.key_field');
        v_upstream_a   := json_value(json_input, '$.source_a.process_id' RETURNING NUMBER);

        v_source_b     := json_value(json_input, '$.source_b.name');
        v_filter_b     := json_value(json_input, '$.source_b.filter' RETURNING CLOB);
        v_date_field_b := json_value(json_input, '$.source_b.date_field');
        v_key_field_b  := json_value(json_input, '$.source_b.key_field');
        v_upstream_b   := json_value(json_input, '$.source_b.process_id' RETURNING NUMBER);

        v_shift_from     := jn('$.rule_config.time_shift_from', 0);
        v_shift_to       := jn('$.rule_config.time_shift_to', 0);
        v_tol_from       := jn('$.rule_config.time_tolerance_from', 0);
        v_tol_to         := jn('$.rule_config.time_tolerance_to', 0);
        v_allow_dups     := jb('$.rule_config.allow_duplicates', FALSE);
        v_max_candidates := jn('$.rule_config.max_candidates', 100);
        IF v_max_candidates < 1 THEN
            raise_application_error(-20005, 'RAPO_USAGE_RULE: max_candidates must be 1 or more');
        END IF;
        v_fuzzy         := jb('$.rule_config.fuzzy_optimization', TRUE);
        v_disc_matching := jb('$.rule_config.discrepancy_matching', FALSE);
        v_need_issues_a := jb('$.rule_config.need_issues_a', FALSE);
        v_need_issues_b := jb('$.rule_config.need_issues_b', FALSE);
        v_need_recons_a := jb('$.rule_config.need_recons_a', FALSE);
        v_need_recons_b := jb('$.rule_config.need_recons_b', FALSE);
        v_need_a        := jb('$.need_a', TRUE);
        v_need_b        := jb('$.need_b', TRUE);

        v_norm_in := lower(json_value(json_input, '$.rule_config.normalization_type'));
        v_norm := nvl(v_norm_in, 'default');
        IF v_norm = 'minmax' THEN
            raise_application_error(-20002, 'RAPO_USAGE_RULE: normalization_type "minmax" normalizes over the entire candidate set and has '
                                            || 'no streaming equivalent. Use none/default, rank, z_norm or srd, or run this control on the '
                                            || 'DB engine.');
        ELSIF v_norm NOT IN ('default', 'none', 'null', 'rank', 'z_norm', 'srd') THEN
            raise_application_error(-20002, 'RAPO_USAGE_RULE: unknown normalization_type "' || v_norm || '"');
        END IF;

        -- correlation_limit is polymorphic in rapo_config: absent or false is unlimited, true means "size it from the fetched counts"
        -- (only possible once both sides are counted, hence the -1 marker), and a positive integer is a literal cap on candidate pairs.
        IF json_value(json_input, '$.rule_config.correlation_limit') IS NULL THEN
            v_corr_limit := 0;
        ELSIF lower(json_value(json_input, '$.rule_config.correlation_limit')) = 'false' THEN
            v_corr_limit := 0;
        ELSIF lower(json_value(json_input, '$.rule_config.correlation_limit')) = 'true' THEN
            v_corr_limit := -1;
        ELSE
            v_corr_limit := jn('$.rule_config.correlation_limit', 0);
        END IF;

        -- The join keys. In formula mode the configured string is raw SQL and carries its own a./b. qualifier. The editor can leave a
        -- half-filled row behind, so entries without both fields are skipped rather than rejected, as the DB engine also tolerates them.
        FOR item IN (
            SELECT * FROM json_table(
                json_input, '$.rule_config.correlation_config[*]'
                COLUMNS (
                    field_a      VARCHAR2(4000) PATH '$.field_a',
                    field_b      VARCHAR2(4000) PATH '$.field_b',
                    allow_null   VARCHAR2(10)   PATH '$.allow_null',
                    formula_mode VARCHAR2(10)   PATH '$.formula_mode'))
        ) LOOP
            CONTINUE WHEN item.field_a IS NULL OR item.field_b IS NULL;
            n_corr := n_corr + 1;
            IF lower(item.formula_mode) = 'true' THEN
                v_corr(n_corr).expr_a := item.field_a;
                v_corr(n_corr).expr_b := item.field_b;
            ELSE
                v_corr(n_corr).expr_a := 'a.' || quoted(item.field_a);
                v_corr(n_corr).expr_b := 'b.' || quoted(item.field_b);
            END IF;
            v_corr(n_corr).allow_null := lower(item.allow_null) = 'true';
        END LOOP;

        IF n_corr = 0 THEN
            raise_application_error(-20003, 'RAPO_USAGE_RULE: correlation_config must name at least one field');
        END IF;

        -- The compared value fields. NOT join conditions: being out of tolerance labels a matched pair, it never stops a match.
        -- A NULL tolerance means zero, i.e. any difference at all is a discrepancy.
        FOR item IN (
            SELECT * FROM json_table(
                json_input, '$.rule_config.discrepancy_config[*]'
                COLUMNS (
                    field_a      VARCHAR2(4000) PATH '$.field_a',
                    field_b      VARCHAR2(4000) PATH '$.field_b',
                    tol_from     NUMBER         PATH '$.numeric_tolerance_from',
                    tol_to       NUMBER         PATH '$.numeric_tolerance_to',
                    pct          VARCHAR2(10)   PATH '$.percentage_mode',
                    formula_mode VARCHAR2(10)   PATH '$.formula_mode',
                    alias        VARCHAR2(4000) PATH '$.formula_alias'))
        ) LOOP
            CONTINUE WHEN item.field_a IS NULL OR item.field_b IS NULL;
            n_disc := n_disc + 1;
            IF lower(item.formula_mode) = 'true' THEN
                v_disc(n_disc).expr_a  := item.field_a;
                v_disc(n_disc).expr_b  := item.field_b;
                v_disc(n_disc).label_a := nvl(item.alias, item.field_a);
                v_disc(n_disc).label_b := nvl(item.alias, item.field_b);
            ELSE
                v_disc(n_disc).expr_a  := 'a.' || quoted(item.field_a);
                v_disc(n_disc).expr_b  := 'b.' || quoted(item.field_b);
                v_disc(n_disc).label_a := nvl(item.alias, upper(item.field_a));
                v_disc(n_disc).label_b := nvl(item.alias, upper(item.field_b));
            END IF;
            v_disc(n_disc).tol_from := nvl(item.tol_from, 0);
            v_disc(n_disc).tol_to   := nvl(item.tol_to, 0);
            v_disc(n_disc).pct      := lower(item.pct) = 'true';
        END LOOP;

        IF object_type_of(v_source_a) IS NULL THEN
            raise_application_error(-20004, 'RAPO_USAGE_RULE: datasource A "' || v_source_a || '" does not exist');
        END IF;
        IF object_type_of(v_source_b) IS NULL THEN
            raise_application_error(-20004, 'RAPO_USAGE_RULE: datasource B "' || v_source_b || '" does not exist');
        END IF;

        v_key_rowid_a := NOT has_column(v_source_a, v_key_field_a);
        v_key_rowid_b := NOT has_column(v_source_b, v_key_field_b);

        v_tmp_verdict_a := 'rapo_temp_verdict_a_' || v_process_id;
        v_tmp_verdict_b := 'rapo_temp_verdict_b_' || v_process_id;
        v_tmp_error_a   := 'rapo_temp_error_a_'   || v_process_id;
        v_tmp_error_b   := 'rapo_temp_error_b_'   || v_process_id;
        v_tmp_stage_a   := 'rapo_temp_stage_a_'   || v_process_id;
        v_tmp_stage_b   := 'rapo_temp_stage_b_'   || v_process_id;
    END parse_payload;

    ------------------------------------------------------------------------------------------------------------------------- statements
    -- Resolve the data type of every correlation expression, so canon() can pick a type-stable text conversion. The type cannot be looked
    -- up in the dictionary, because in formula mode the key is an expression, so a throwaway "where 1 = 0" is parsed and described instead.
    -- The numbers are the DBMS_SQL / OCI internal type codes.
    FUNCTION describe_key_types (source_name VARCHAR2, alias VARCHAR2, side CHAR) RETURN t_str_tab IS
        probe     CLOB;
        cur       NUMBER;
        col_cnt   NUMBER;
        desc_tab  dbms_sql.desc_tab;
        types     t_str_tab;
    BEGIN
        probe := 'select ';
        FOR i IN 1..n_corr LOOP
            IF i > 1 THEN probe := probe || ', '; END IF;
            probe := probe || CASE WHEN side = 'A' THEN v_corr(i).expr_a ELSE v_corr(i).expr_b END;
        END LOOP;
        probe := probe || ' from ' || source_name || ' ' || alias || ' where 1 = 0';
        cur := dbms_sql.open_cursor;
        BEGIN
            dbms_sql.parse(cur, probe, dbms_sql.native);
            dbms_sql.describe_columns(cur, col_cnt, desc_tab);
            FOR i IN 1..n_corr LOOP
                types(i) := CASE desc_tab(i).col_type
                                WHEN 1   THEN 'VARCHAR2'
                                WHEN 2   THEN 'NUMBER'
                                WHEN 12  THEN 'DATE'
                                WHEN 96  THEN 'CHAR'
                                WHEN 180 THEN 'TIMESTAMP'
                                WHEN 181 THEN 'TIMESTAMP_TZ'
                                WHEN 231 THEN 'TIMESTAMP_LTZ'
                                ELSE 'OTHER'
                            END;
            END LOOP;
            dbms_sql.close_cursor(cur);
        EXCEPTION WHEN OTHERS THEN
            IF dbms_sql.is_open(cur) THEN dbms_sql.close_cursor(cur); END IF;
            RAISE;
        END;
        RETURN types;
    END describe_key_types;

    -- Build the fetch statement for one side:
    --   select <key|rowid> as row_id, <canonical key 1..n>, cast(<date field> as date) as date_value, coalesce(<value field>, 0) as disc_1..n
    --     from <source> a
    --    where <date between the widened window> and (<filter>) and <each correlation key is not null>
    --    order by <keys>, date_value, row_id
    -- The ORDER BY is what the whole merge rests on and must agree with cmp_keys; NLS_SORT/NLS_COMP are BINARY here, so SQL's text ordering
    -- and PL/SQL's comparison coincide.
    FUNCTION build_select (side CHAR) RETURN CLOB IS
        stmt        CLOB;
        alias       VARCHAR2(1) := CASE WHEN side = 'A' THEN 'a' ELSE 'b' END;
        source_name VARCHAR2(128) := CASE WHEN side = 'A' THEN v_source_a ELSE v_source_b END;
        date_field  VARCHAR2(128) := CASE WHEN side = 'A' THEN v_date_field_a ELSE v_date_field_b END;
        key_field   VARCHAR2(128) := CASE WHEN side = 'A' THEN v_key_field_a ELSE v_key_field_b END;
        key_rowid   BOOLEAN := CASE WHEN side = 'A' THEN v_key_rowid_a ELSE v_key_rowid_b END;
        filter      CLOB := CASE WHEN side = 'A' THEN v_filter_a ELSE v_filter_b END;
        win_from    DATE;
        win_to      DATE;
        types       t_str_tab;
        expr        VARCHAR2(4000);
    BEGIN
        types := describe_key_types(source_name, alias, side);

        -- Widen the fetch window by the shift, so a pair straddling the boundary still has both of its rows. A candidate satisfies
        -- a.date BETWEEN b.date+shift_from AND b.date+shift_to, which solved per side gives
        --   A over [from + shift_from, to + shift_to]
        --   B over [from - shift_to,   to - shift_from]   <- note the swap
        -- and only the negative/positive part of each bound may widen, never narrow, hence the least/greatest against 0.
        -- Padding rows are filtered out again in emit_row, which re-applies the unshifted window.
        IF side = 'A' THEN
            win_from := v_date_from + least(v_shift_from, 0) / 86400;
            win_to   := v_date_to   + greatest(v_shift_to, 0) / 86400;
        ELSE
            win_from := v_date_from + least(-v_shift_to, 0) / 86400;
            win_to   := v_date_to   + greatest(-v_shift_from, 0) / 86400;
        END IF;

        stmt := 'select ';
        IF v_parallelism > 0 THEN
            stmt := stmt || '/*+ parallel(' || v_parallelism || ') */ ';
        END IF;

        IF key_rowid THEN
            stmt := stmt || 'rowidtochar(' || alias || '.rowid)';
        ELSE
            stmt := stmt || 'cast(' || alias || '.' || quoted(key_field) || ' as varchar2(4000))';
        END IF;
        stmt := stmt || ' as row_id';

        FOR i IN 1..n_corr LOOP
            expr := CASE WHEN side = 'A' THEN v_corr(i).expr_a ELSE v_corr(i).expr_b END;
            stmt := stmt || ', ' || canon(expr, types(i)) || ' as key_' || i;
        END LOOP;

        stmt := stmt || ', cast(' || alias || '.' || quoted(date_field) || ' as date) as date_value';

        FOR i IN 1..n_disc LOOP
            expr := CASE WHEN side = 'A' THEN v_disc(i).expr_a ELSE v_disc(i).expr_b END;
            stmt := stmt || ', coalesce(' || expr || ', 0) as disc_' || i;
        END LOOP;

        stmt := stmt || ' from ' || source_name || ' ' || alias
                     || ' where ' || scope_predicate(side, alias, date_field, win_from, win_to);

        IF filter IS NOT NULL AND length(filter) > 0 THEN
            stmt := stmt || ' and (' || filter || ')';
        END IF;

        -- A NULL correlation key can never satisfy an equi-join, so such rows are kept out of the merge entirely; allow_null only decides
        -- whether they are fetched at all, by build_null_key_select, and reported as Loss.
        FOR i IN 1..n_corr LOOP
            expr := CASE WHEN side = 'A' THEN v_corr(i).expr_a ELSE v_corr(i).expr_b END;
            stmt := stmt || ' and ' || expr || ' is not null';
        END LOOP;

        -- Ordered by position, not by name, so the sort cannot drift away from the select list: keys, then the date, then row_id.
        stmt := stmt || ' order by ';
        FOR i IN 1..n_corr LOOP
            stmt := stmt || (i + 1) || ', ';
        END LOOP;
        stmt := stmt || (n_corr + 2) || ', 1';

        RETURN stmt;
    END build_select;

    -- Collect the rows build_select leaves out: those with a NULL correlation key, when allow_null keeps them in scope. They cannot take
    -- part in the merge, so they are Loss by construction, and one set-based statement keeps the merge free of null cases.
    --
    -- The window is the UNSHIFTED one, unlike build_select's: these rows go straight into the verdict table without passing emit_row, which
    -- is the only other place the unshifted window is re-applied, so widening it here would report padding rows as losses.
    -- The other correlation fields still have to be NOT NULL, as Parser._parse_not_null_fields_* requires for the DB engine.
    --
    -- Returns NULL when no correlation field allows nulls.
    FUNCTION build_null_key_select (side CHAR) RETURN CLOB IS
        stmt         CLOB;
        alias        VARCHAR2(1) := CASE WHEN side = 'A' THEN 'a' ELSE 'b' END;
        source_name  VARCHAR2(128) := CASE WHEN side = 'A' THEN v_source_a ELSE v_source_b END;
        date_field   VARCHAR2(128) := CASE WHEN side = 'A' THEN v_date_field_a ELSE v_date_field_b END;
        key_field    VARCHAR2(128) := CASE WHEN side = 'A' THEN v_key_field_a ELSE v_key_field_b END;
        key_rowid    BOOLEAN := CASE WHEN side = 'A' THEN v_key_rowid_a ELSE v_key_rowid_b END;
        filter       CLOB := CASE WHEN side = 'A' THEN v_filter_a ELSE v_filter_b END;
        expr         VARCHAR2(4000);
        any_nullable BOOLEAN := FALSE;
        predicate    VARCHAR2(4000) := '';
    BEGIN
        FOR i IN 1..n_corr LOOP
            IF v_corr(i).allow_null THEN
                expr := CASE WHEN side = 'A' THEN v_corr(i).expr_a ELSE v_corr(i).expr_b END;
                IF any_nullable THEN predicate := predicate || ' or '; END IF;
                predicate := predicate || expr || ' is null';
                any_nullable := TRUE;
            END IF;
        END LOOP;
        IF NOT any_nullable THEN RETURN NULL; END IF;

        stmt := 'select ';
        IF key_rowid THEN
            stmt := stmt || 'rowidtochar(' || alias || '.rowid)';
        ELSE
            stmt := stmt || 'cast(' || alias || '.' || quoted(key_field) || ' as varchar2(4000))';
        END IF;
        stmt := stmt || ' as row_id'
                     || ' from ' || source_name || ' ' || alias
                     || ' where ' || scope_predicate(side, alias, date_field, v_date_from, v_date_to);
        IF filter IS NOT NULL AND length(filter) > 0 THEN
            stmt := stmt || ' and (' || filter || ')';
        END IF;
        FOR i IN 1..n_corr LOOP
            IF NOT v_corr(i).allow_null THEN
                expr := CASE WHEN side = 'A' THEN v_corr(i).expr_a ELSE v_corr(i).expr_b END;
                stmt := stmt || ' and ' || expr || ' is not null';
            END IF;
        END LOOP;
        stmt := stmt || ' and (' || predicate || ')';
        RETURN stmt;
    END build_null_key_select;

    ----------------------------------------------------------------------------------------------------------------------------- cursor
    -- Parse, define and execute one side's cursor. The variables handed to define_column only carry the type; values come back through
    -- column_value in next_row. The handle stays local until everything has succeeded: a scalar OUT is copied back only on a normal return,
    -- so assigning it first would leave the caller's c_a NULL on a parse failure and cleanup would have no handle to close.
    PROCEDURE open_side (stmt CLOB, cur OUT NUMBER) IS
        handle   NUMBER;
        ignored  NUMBER;
    BEGIN
        handle := dbms_sql.open_cursor;
        BEGIN
            dbms_sql.parse(handle, stmt, dbms_sql.native);
            dbms_sql.define_column(handle, 1, cur_str, 4000);
            FOR i IN 1..n_corr LOOP
                dbms_sql.define_column(handle, i + 1, cur_str, 4000);
            END LOOP;
            dbms_sql.define_column(handle, col_date_pos, cur_date);
            FOR i IN 1..n_disc LOOP
                dbms_sql.define_column(handle, col_disc_pos + i - 1, cur_num);
            END LOOP;
            ignored := dbms_sql.execute(handle);
        EXCEPTION WHEN OTHERS THEN
            IF dbms_sql.is_open(handle) THEN dbms_sql.close_cursor(handle); END IF;
            RAISE;
        END;
        cur := handle;
    END open_side;

    -- Fetch the next row of a side, FALSE once it is exhausted. End of data is decided by what fetch_rows returns, never by inspecting the
    -- row, or a genuine NULL would truncate the run. `blank` resets every field, so a row can never inherit a value from the previous fetch.
    FUNCTION next_row (cur NUMBER, target OUT t_row) RETURN BOOLEAN IS
        fetched PLS_INTEGER;
        blank   t_row;
    BEGIN
        fetched := dbms_sql.fetch_rows(cur);
        IF fetched = 0 THEN RETURN FALSE; END IF;
        target := blank;
        dbms_sql.column_value(cur, 1, target.row_id);
        FOR i IN 1..n_corr LOOP
            dbms_sql.column_value(cur, i + 1, target.keys(i));
        END LOOP;
        dbms_sql.column_value(cur, col_date_pos, target.dt);
        FOR i IN 1..n_disc LOOP
            dbms_sql.column_value(cur, col_disc_pos + i - 1, target.disc(i));
        END LOOP;
        target.matched := FALSE;
        RETURN TRUE;
    END next_row;

    -- Compare two rows on the correlation key tuple: -1, 0 or 1. Must impose exactly the ordering the cursors were sorted by, or the two
    -- fronts drift apart and rows are silently mis-grouped. Keys are never NULL here.
    FUNCTION cmp_keys (left_row t_row, right_row t_row) RETURN PLS_INTEGER IS
    BEGIN
        FOR i IN 1..n_corr LOOP
            IF left_row.keys(i) < right_row.keys(i) THEN RETURN -1;
            ELSIF left_row.keys(i) > right_row.keys(i) THEN RETURN 1;
            END IF;
        END LOOP;
        RETURN 0;
    END cmp_keys;

    ------------------------------------------------------------------------------------------------------------------------- discrepancy
    -- Is value field `idx` outside its tolerance for this pair? Mirrors exps/discrepancy_rule.sql. In percentage mode the SCALED difference
    -- decides the flag but the description reports the RAW one; with both sides zero the denominator is NULL and SQL's NOT BETWEEN yields
    -- no flag, which FALSE reproduces. The band is inclusive and may be asymmetric, so both ends are tested.
    FUNCTION disc_flagged (idx PLS_INTEGER, va NUMBER, vb NUMBER) RETURN BOOLEAN IS
        cmp   NUMBER;
        denom NUMBER;
    BEGIN
        IF v_disc(idx).pct THEN
            IF va != 0 THEN denom := va;
            ELSIF vb != 0 THEN denom := vb;
            ELSE denom := NULL;
            END IF;
            IF denom IS NULL THEN RETURN FALSE; END IF;
            cmp := (va - vb) / denom * 100;
        ELSE
            cmp := va - vb;
        END IF;
        RETURN cmp < v_disc(idx).tol_from OR cmp > v_disc(idx).tol_to;
    END disc_flagged;

    -- Normalise one dimension of one pair's distance, per exps/distance_formula_*.sql; the caller sums it over every dimension. The peer
    -- statistics are taken over the candidates of the row being ranked, which is the partition the SQL window functions use.
    --   none/default  plain magnitude
    --   rank          divides by the candidate count, the same constant for every dimension of a row, so it cannot change which one wins
    --   z_norm        per-dimension mean and spread, so dimensions get different weights; can go negative
    --   srd           squares the difference relative to the WIDTH of its tolerance band; degenerate band -> plain magnitude
    FUNCTION normalize (raw_value NUMBER, tol_from NUMBER, tol_to NUMBER, peer_count PLS_INTEGER, peer_avg NUMBER,
                        peer_stddev NUMBER) RETURN NUMBER IS
    BEGIN
        IF v_norm = 'rank' THEN
            RETURN abs(raw_value) / greatest(peer_count, 1);
        ELSIF v_norm = 'z_norm' THEN
            IF peer_stddev = 0 THEN RETURN 0; END IF;
            RETURN (abs(raw_value) - peer_avg) / peer_stddev;
        ELSIF v_norm = 'srd' THEN
            IF tol_from = tol_to THEN RETURN abs(raw_value); END IF;
            RETURN power(raw_value / (tol_to - tol_from), 2);
        ELSE
            RETURN abs(raw_value);
        END IF;
    END normalize;

    -- s02's numeric_value: seconds since the epoch plus the magnitude of each value field. Only ever a sort key - the one that orders both
    -- sides of a square cluster before they are paired position by position. Uses the row's own VALUES, not differences against a counterpart.
    FUNCTION numeric_value (r t_row) RETURN NUMBER IS
        total NUMBER := 86400 * (r.dt - EPOCH);
    BEGIN
        FOR i IN 1..n_disc LOOP
            total := total + abs(r.disc(i));
        END LOOP;
        RETURN total;
    END numeric_value;

    -- rapo_discrepancy_description for one pair, as "LABEL|signed_value;" repeated - the time gap first, then the value fields in configured
    -- order, as exps/discrepancy_desc.sql builds it. Only flagged dimensions appear; the value is always the raw signed difference.
    FUNCTION describe_pair (p t_pair, side CHAR) RETURN VARCHAR2 IS
        text VARCHAR2(4000) := NULL;
    BEGIN
        IF p.time_flag THEN
            text := CASE WHEN side = 'A' THEN upper(v_date_field_a) ELSE upper(v_date_field_b) END || '|' || to_char(p.tsv) || ';';
        END IF;
        FOR i IN 1..n_disc LOOP
            IF p.flags(i) = 'Y' THEN
                text := text || CASE WHEN side = 'A' THEN v_disc(i).label_a ELSE v_disc(i).label_b END || '|' || to_char(p.vals(i)) || ';';
            END IF;
        END LOOP;
        RETURN text;
    END describe_pair;

    -- Does this pair differ anywhere? The OR chain of exps/discrepancy_filter.sql: the time gap or any one value field.
    FUNCTION pair_has_discrepancy (p t_pair) RETURN BOOLEAN IS
    BEGIN
        IF p.time_flag THEN RETURN TRUE; END IF;
        FOR i IN 1..n_disc LOOP
            IF p.flags(i) = 'Y' THEN RETURN TRUE; END IF;
        END LOOP;
        RETURN FALSE;
    END pair_has_discrepancy;

    ------------------------------------------------------------------------------------------------------------------------ group logic
    -- Resolve one correlation-key group: stages s01 to s07 over grp_a and grp_b, leaving each row's corr_type, matched, matched_pair and
    -- best_pair set for emit_row. Exact rather than approximate, because two rows can only be candidates if their keys are equal, so every
    -- candidate of a row is inside this group.
    --
    -- pairs_budget carries the remaining correlation_limit across groups; -1 means unlimited. IN OUT because the cap is global.
    PROCEDURE process_group (pairs_budget IN OUT NUMBER) IS
        n_a        PLS_INTEGER := grp_a.COUNT;
        n_b        PLS_INTEGER := grp_b.COUNT;
        n_p        PLS_INTEGER := 0;
        p          t_pair;
        b_used     t_int_tab;                -- pairs already given to each B row
        capped     BOOLEAN := FALSE;         -- the fan-out limit bit in this group

        order_idx  t_int_tab;                -- pair indices in date order, for clustering

        -- Pairs bucketed by the row they belong to, so "every candidate of this A row" is a contiguous slice rather than a scan of all
        -- pairs: a_list(a_start(i) .. a_start(i)+a_count(i)-1) are the pairs of A row i. b_* is the same for the other side.
        a_start    t_int_tab;
        a_count    t_int_tab;
        a_list     t_int_tab;
        b_start    t_int_tab;
        b_count    t_int_tab;
        b_list     t_int_tab;

        -- Counting sort: count per row, turn the counts into offsets, then place each pair. Linear in the number of pairs, and it indexes
        -- both sides even though pairs are generated in A order and scattered from B's point of view.
        PROCEDURE bucket_pairs IS
            pos t_int_tab;                   -- next free slot per row, advanced as we fill
        BEGIN
            FOR i IN 1..n_a LOOP a_count(i) := 0; END LOOP;
            FOR i IN 1..n_b LOOP b_count(i) := 0; END LOOP;
            FOR i IN 1..n_p LOOP
                a_count(pairs(i).ai) := a_count(pairs(i).ai) + 1;
                b_count(pairs(i).bi) := b_count(pairs(i).bi) + 1;
            END LOOP;
            FOR i IN 1..n_a LOOP
                a_start(i) := CASE WHEN i = 1 THEN 1 ELSE a_start(i - 1) + a_count(i - 1) END;
                pos(i) := a_start(i);
            END LOOP;
            FOR i IN 1..n_p LOOP
                a_list(pos(pairs(i).ai)) := i;
                pos(pairs(i).ai) := pos(pairs(i).ai) + 1;
            END LOOP;
            pos.DELETE;
            FOR i IN 1..n_b LOOP
                b_start(i) := CASE WHEN i = 1 THEN 1 ELSE b_start(i - 1) + b_count(i - 1) END;
                pos(i) := b_start(i);
            END LOOP;
            FOR i IN 1..n_p LOOP
                b_list(pos(pairs(i).bi)) := i;
                pos(pairs(i).bi) := pos(pairs(i).bi) + 1;
            END LOOP;
        END bucket_pairs;

        -- dimension value: 0 = the time gap, 1..n_disc = the configured fields
        FUNCTION dim_value (pi PLS_INTEGER, d PLS_INTEGER) RETURN NUMBER IS
        BEGIN
            IF d = 0 THEN RETURN pairs(pi).tsv; END IF;
            RETURN pairs(pi).vals(d);
        END dim_value;

        FUNCTION dim_tol_from (d PLS_INTEGER) RETURN NUMBER IS
        BEGIN
            IF d = 0 THEN RETURN v_tol_from; END IF;
            RETURN v_disc(d).tol_from;
        END dim_tol_from;

        FUNCTION dim_tol_to (d PLS_INTEGER) RETURN NUMBER IS
        BEGIN
            IF d = 0 THEN RETURN v_tol_to; END IF;
            RETURN v_disc(d).tol_to;
        END dim_tol_to;

        -- s06's {conflict_types}: the pairs the fixpoint may touch. Declared once because the ranking and the confirmation both apply it
        -- and must not drift apart.
        FUNCTION is_conflict_pair (pi PLS_INTEGER) RETURN BOOLEAN IS
        BEGIN
            RETURN pairs(pi).corr_type IN ('A', 'B', 'M') OR (NOT v_fuzzy AND pairs(pi).corr_type = 'F');
        END is_conflict_pair;

        -- Distance of every pair from one side's point of view: normalise each dimension over that row's candidates, then sum the dimensions.
        -- The two sides are computed separately because the normalisation is taken over different partitions, so z_norm and srd can make the
        -- sides disagree about which pairing is best - which is what makes the fixpoint in match_conflicts iterate.
        PROCEDURE compute_distances (side CHAR) IS
            first_idx PLS_INTEGER;
            cnt       PLS_INTEGER;
            pi        PLS_INTEGER;
            total     NUMBER;
            peer_avg  NUMBER;
            peer_sd   NUMBER;
            n_part    PLS_INTEGER := CASE WHEN side = 'A' THEN n_a ELSE n_b END;
        BEGIN
            FOR part IN 1..n_part LOOP
                first_idx := CASE WHEN side = 'A' THEN a_start(part) ELSE b_start(part) END;
                cnt := CASE WHEN side = 'A' THEN a_count(part) ELSE b_count(part) END;
                CONTINUE WHEN cnt = 0;
                FOR d IN 0..n_disc LOOP
                    peer_avg := 0;
                    FOR k IN 0..cnt - 1 LOOP
                        pi := CASE WHEN side = 'A' THEN a_list(first_idx + k) ELSE b_list(first_idx + k) END;
                        peer_avg := peer_avg + abs(dim_value(pi, d));
                    END LOOP;
                    peer_avg := peer_avg / cnt;
                    peer_sd := 0;
                    FOR k IN 0..cnt - 1 LOOP
                        pi := CASE WHEN side = 'A' THEN a_list(first_idx + k) ELSE b_list(first_idx + k) END;
                        peer_sd := peer_sd + power(abs(dim_value(pi, d)) - peer_avg, 2);
                    END LOOP;
                    peer_sd := sqrt(peer_sd / cnt);
                    FOR k IN 0..cnt - 1 LOOP
                        pi := CASE WHEN side = 'A' THEN a_list(first_idx + k) ELSE b_list(first_idx + k) END;
                        total := normalize(dim_value(pi, d), dim_tol_from(d), dim_tol_to(d), cnt, peer_avg, peer_sd);
                        IF side = 'A' THEN
                            pairs(pi).dist_a := pairs(pi).dist_a + total;
                        ELSE
                            pairs(pi).dist_b := pairs(pi).dist_b + total;
                        END IF;
                    END LOOP;
                END LOOP;
            END LOOP;
        END compute_distances;

        -- s01's time_shift_rank and discrepancy_rank: a rank over a row's candidates by absolute time gap, and by summed absolute value
        -- difference. s01 makes both DENSE; that is not reproduced because it is unobservable - both are read only in `precedes`, and only
        -- ever compared with each other, and rank() and dense_rank() induce the identical ordering. Counting rows instead of distinct values
        -- is what keeps this O(cnt^2) rather than O(cnt^3).
        --
        -- With no value fields configured the discrepancy rank falls back to the counterparty id, as s01 does with an empty discrepancy_config.
        PROCEDURE compute_ranks (side CHAR) IS
            first_idx PLS_INTEGER;
            cnt       PLS_INTEGER;
            pi        PLS_INTEGER;
            pj        PLS_INTEGER;
            t_rnk     PLS_INTEGER;
            d_rnk     PLS_INTEGER;
            n_part    PLS_INTEGER := CASE WHEN side = 'A' THEN n_a ELSE n_b END;
        BEGIN
            FOR part IN 1..n_part LOOP
                first_idx := CASE WHEN side = 'A' THEN a_start(part) ELSE b_start(part) END;
                cnt := CASE WHEN side = 'A' THEN a_count(part) ELSE b_count(part) END;
                CONTINUE WHEN cnt = 0;
                FOR k IN 0..cnt - 1 LOOP
                    pi := CASE WHEN side = 'A' THEN a_list(first_idx + k) ELSE b_list(first_idx + k) END;
                    t_rnk := 1;
                    d_rnk := 1;
                    FOR j IN 0..cnt - 1 LOOP
                        pj := CASE WHEN side = 'A' THEN a_list(first_idx + j) ELSE b_list(first_idx + j) END;
                        IF abs(pairs(pj).tsv) < abs(pairs(pi).tsv) THEN
                            t_rnk := t_rnk + 1;
                        END IF;
                        IF n_disc = 0 THEN
                            IF (side = 'A' AND grp_b(pairs(pj).bi).row_id < grp_b(pairs(pi).bi).row_id)
                               OR (side = 'B' AND grp_a(pairs(pj).ai).row_id < grp_a(pairs(pi).ai).row_id) THEN
                                d_rnk := d_rnk + 1;
                            END IF;
                        ELSIF pairs(pj).dsum < pairs(pi).dsum THEN
                            d_rnk := d_rnk + 1;
                        END IF;
                    END LOOP;
                    IF side = 'A' THEN
                        pairs(pi).trank_a := t_rnk;
                        pairs(pi).drank_a := d_rnk;
                    ELSE
                        pairs(pi).trank_b := t_rnk;
                        pairs(pi).drank_b := d_rnk;
                    END IF;
                END LOOP;
            END LOOP;
        END compute_ranks;

        -- Rank a row's candidates best to worst: rank_a/rank_b = 1 is that row's first choice. This is s01's distance_rank and s06's
        -- match_position. The chain is distance -> time gap -> value difference -> counterparty id, the id making it total.
        --
        -- residual_only = TRUE reproduces s06: rank only over pairs still in play, which is what lets the fixpoint make progress.
        -- FALSE ranks everything, which is what best_pair needs.
        PROCEDURE compute_positions (side CHAR, residual_only BOOLEAN) IS
            first_idx PLS_INTEGER;
            cnt       PLS_INTEGER;
            pi        PLS_INTEGER;
            pj        PLS_INTEGER;
            rnk       PLS_INTEGER;
            n_part    PLS_INTEGER := CASE WHEN side = 'A' THEN n_a ELSE n_b END;

            -- s06 filters its partition by `m.correlation_type in {conflict_types}` as well as by the three indicators. The type half
            -- matters: an F pair left unmatched by s03-s05 would otherwise hold rank 1 and keep the A/B/M pair behind it from ever being
            -- both sides' first choice, stalling the fixpoint.
            FUNCTION eligible (x PLS_INTEGER) RETURN BOOLEAN IS
            BEGIN
                IF NOT residual_only THEN RETURN TRUE; END IF;
                RETURN is_conflict_pair(x) AND NOT pairs(x).matched AND NOT grp_a(pairs(x).ai).matched AND NOT grp_b(pairs(x).bi).matched;
            END eligible;

            FUNCTION precedes (x PLS_INTEGER, y PLS_INTEGER) RETURN BOOLEAN IS
                dx NUMBER := CASE WHEN side = 'A' THEN pairs(x).dist_a ELSE pairs(x).dist_b END;
                dy NUMBER := CASE WHEN side = 'A' THEN pairs(y).dist_a ELSE pairs(y).dist_b END;
                tx PLS_INTEGER := CASE WHEN side = 'A' THEN pairs(x).trank_a ELSE pairs(x).trank_b END;
                ty PLS_INTEGER := CASE WHEN side = 'A' THEN pairs(y).trank_a ELSE pairs(y).trank_b END;
                rx PLS_INTEGER := CASE WHEN side = 'A' THEN pairs(x).drank_a ELSE pairs(x).drank_b END;
                ry PLS_INTEGER := CASE WHEN side = 'A' THEN pairs(y).drank_a ELSE pairs(y).drank_b END;
                ix VARCHAR2(4000) := CASE WHEN side = 'A' THEN grp_b(pairs(x).bi).row_id ELSE grp_a(pairs(x).ai).row_id END;
                iy VARCHAR2(4000) := CASE WHEN side = 'A' THEN grp_b(pairs(y).bi).row_id ELSE grp_a(pairs(y).ai).row_id END;
            BEGIN
                IF dx != dy THEN RETURN dx < dy; END IF;
                IF tx != ty THEN RETURN tx < ty; END IF;
                IF rx != ry THEN RETURN rx < ry; END IF;
                RETURN ix < iy;
            END precedes;
        BEGIN
            FOR part IN 1..n_part LOOP
                first_idx := CASE WHEN side = 'A' THEN a_start(part) ELSE b_start(part) END;
                cnt := CASE WHEN side = 'A' THEN a_count(part) ELSE b_count(part) END;
                CONTINUE WHEN cnt = 0;
                FOR k IN 0..cnt - 1 LOOP
                    pi := CASE WHEN side = 'A' THEN a_list(first_idx + k) ELSE b_list(first_idx + k) END;
                    IF side = 'A' THEN pairs(pi).rank_a := NULL; ELSE pairs(pi).rank_b := NULL; END IF;
                    CONTINUE WHEN NOT eligible(pi);
                    rnk := 1;
                    FOR j IN 0..cnt - 1 LOOP
                        pj := CASE WHEN side = 'A' THEN a_list(first_idx + j) ELSE b_list(first_idx + j) END;
                        CONTINUE WHEN pj = pi OR NOT eligible(pj);
                        IF precedes(pj, pi) THEN rnk := rnk + 1; END IF;
                    END LOOP;
                    IF side = 'A' THEN pairs(pi).rank_a := rnk; ELSE pairs(pi).rank_b := rnk; END IF;
                END LOOP;
            END LOOP;
        END compute_positions;

        -- Confirm a pair and both of its rows. The single place `matched` is ever set, which is what stops a pair and its rows disagreeing.
        PROCEDURE mark_matched (pi PLS_INTEGER) IS
        BEGIN
            pairs(pi).matched := TRUE;
            grp_a(pairs(pi).ai).matched := TRUE;
            grp_a(pairs(pi).ai).matched_pair := pi;
            grp_b(pairs(pi).bi).matched := TRUE;
            grp_b(pairs(pi).bi).matched_pair := pi;
        END mark_matched;

        -- s01's join: every A x B combination in this group whose dates are within the shift, with its time gap, per-field differences and
        -- flags. With both shifts zero the window degenerates to equality, the form s01 emits in that case. correlation_limit is enforced
        -- here as a running budget over the whole run. Finally the pairs are indexed in date order, which assign_clusters needs.
        PROCEDURE build_pairs IS
            tmp      PLS_INTEGER;
            swap     PLS_INTEGER;
            lo_ptr   PLS_INTEGER := 1;       -- first B still reachable, monotonic
            hi_ptr   PLS_INTEGER := 0;       -- last B reachable so far, monotonic
            lo_bound DATE;
            hi_bound DATE;
            split    PLS_INTEGER;            -- first candidate at or after a.dt
            left     PLS_INTEGER;
            right    PLS_INTEGER;
            taken    PLS_INTEGER;
            bi       PLS_INTEGER;
            gap_l    NUMBER;
            gap_r    NUMBER;
            ignored  BOOLEAN;

            -- Add one pair, unless the counterpart has used up its own fan-out allowance. Returns whether a pair was actually made: a
            -- refusal must not count towards this row's quota, or a row whose preferred candidates are all full would end up with none.
            FUNCTION add_pair (ai PLS_INTEGER, bi PLS_INTEGER) RETURN BOOLEAN IS
            BEGIN
                IF b_used.EXISTS(bi) AND b_used(bi) >= v_max_candidates THEN
                    capped := TRUE;
                    RETURN FALSE;
                END IF;
                n_p := n_p + 1;
                IF pairs_budget > 0 THEN
                    pairs_budget := pairs_budget - 1;
                END IF;
                b_used(bi) := nvl(b_used(bi), 0) + 1;
                p.ai := ai;
                p.bi := bi;
                p.dt := greatest(grp_a(ai).dt, grp_b(bi).dt);
                p.tsv := round(86400 * (grp_a(ai).dt - grp_b(bi).dt), 6);
                p.time_flag := p.tsv < v_tol_from OR p.tsv > v_tol_to;
                p.matched := FALSE;
                p.dist_a := 0;
                p.dist_b := 0;
                p.dsum := 0;
                FOR d IN 1..n_disc LOOP
                    p.vals(d) := grp_a(ai).disc(d) - grp_b(bi).disc(d);
                    p.dsum := p.dsum + abs(p.vals(d));
                    p.flags(d) := CASE WHEN disc_flagged(d, grp_a(ai).disc(d), grp_b(bi).disc(d)) THEN 'Y' ELSE NULL END;
                END LOOP;
                pairs(n_p) := p;
                RETURN TRUE;
            END add_pair;
        BEGIN
            FOR bi IN 1..n_b LOOP b_used(bi) := 0; END LOOP;

            FOR ai IN 1..n_a LOOP
                EXIT WHEN pairs_budget = 0;

                -- The candidate condition solved for B: b.dt BETWEEN a.dt - shift_to AND a.dt - shift_from. With both shifts zero it
                -- degenerates to equality, and the bounds are taken verbatim so no date arithmetic is involved.
                IF v_shift_from = 0 AND v_shift_to = 0 THEN
                    lo_bound := grp_a(ai).dt;
                    hi_bound := grp_a(ai).dt;
                ELSE
                    lo_bound := grp_a(ai).dt - v_shift_to / 86400;
                    hi_bound := grp_a(ai).dt - v_shift_from / 86400;
                END IF;

                -- Both sides are date-ordered, so the reachable B rows are a contiguous window whose ends only move forward as A advances.
                WHILE lo_ptr <= n_b AND grp_b(lo_ptr).dt < lo_bound LOOP
                    lo_ptr := lo_ptr + 1;
                END LOOP;
                WHILE hi_ptr < n_b AND grp_b(hi_ptr + 1).dt <= hi_bound LOOP
                    hi_ptr := hi_ptr + 1;
                END LOOP;
                CONTINUE WHEN lo_ptr > hi_ptr;   -- nothing in reach

                IF hi_ptr - lo_ptr + 1 <= v_max_candidates THEN
                    FOR k IN lo_ptr..hi_ptr LOOP
                        EXIT WHEN pairs_budget = 0;
                        ignored := add_pair(ai, k);   -- everything in reach fits under the cap, so a refusal cannot happen here
                    END LOOP;
                ELSE
                    -- More rows in reach than the fan-out allows. Keep the ones nearest in time: walk outwards from where a.dt falls in the
                    -- window, taking whichever side is closer. Ties go to the earlier row, so the choice is reproducible.
                    capped := TRUE;
                    split := lo_ptr;
                    WHILE split <= hi_ptr AND grp_b(split).dt < grp_a(ai).dt LOOP
                        split := split + 1;
                    END LOOP;
                    left := split - 1;
                    right := split;
                    taken := 0;
                    WHILE taken < v_max_candidates AND (left >= lo_ptr OR right <= hi_ptr) LOOP
                        EXIT WHEN pairs_budget = 0;
                        IF left < lo_ptr THEN
                            bi := right; right := right + 1;
                        ELSIF right > hi_ptr THEN
                            bi := left; left := left - 1;
                        ELSE
                            gap_l := abs(grp_a(ai).dt - grp_b(left).dt);
                            gap_r := abs(grp_b(right).dt - grp_a(ai).dt);
                            IF gap_l <= gap_r THEN
                                bi := left; left := left - 1;
                            ELSE
                                bi := right; right := right + 1;
                            END IF;
                        END IF;
                        IF add_pair(ai, bi) THEN taken := taken + 1; END IF;
                    END LOOP;
                END IF;
            END LOOP;

            -- order pair indices by date_value for the cluster chaining; insertion sort, stable, so pairs sharing a date keep their order
            FOR i IN 1..n_p LOOP order_idx(i) := i; END LOOP;
            FOR i IN 2..n_p LOOP
                tmp := order_idx(i);
                swap := i - 1;
                WHILE swap >= 1 AND pairs(order_idx(swap)).dt > pairs(tmp).dt LOOP
                    order_idx(swap + 1) := order_idx(swap);
                    swap := swap - 1;
                END LOOP;
                order_idx(swap + 1) := tmp;
            END LOOP;
        END build_pairs;

        -- s01's sessionisation. Walking the pairs in date order, a new cluster begins wherever the previous date falls outside the current
        -- one's shift window. Clusters are the unit the correlation type is decided from.
        --
        -- Pairs sharing a date are assigned together by the inner loop: the SQL uses a RANGE window, under which peers with an equal date
        -- always land in the same cluster, and processing them one at a time would sometimes split them.
        PROCEDURE assign_clusters IS
            cid       PLS_INTEGER := 0;
            prev_dt   DATE := NULL;
            i         PLS_INTEGER := 1;
            j         PLS_INTEGER;
            cur_dt    DATE;
        BEGIN
            WHILE i <= n_p LOOP
                cur_dt := pairs(order_idx(i)).dt;
                IF prev_dt IS NULL OR prev_dt < cur_dt + v_shift_from / 86400 OR prev_dt > cur_dt + v_shift_to / 86400 THEN
                    cid := cid + 1;
                END IF;
                j := i;
                WHILE j <= n_p AND pairs(order_idx(j)).dt = cur_dt LOOP
                    pairs(order_idx(j)).cluster_id := cid;
                    j := j + 1;
                END LOOP;
                prev_dt := cur_dt;
                i := j;
            END LOOP;
        END assign_clusters;

        -- Give every pair its correlation type, from the shape of its cluster. cnt_a is how many DISTINCT B rows the cluster holds and cnt_b
        -- how many distinct A rows - counted crosswise, because what characterises the A side is the number of counterparties it faces.
        -- A cluster is one contiguous run of order_idx, so stamping each row with the cluster it was last counted in is enough to dedupe.
        PROCEDURE classify_pairs IS
            n_cluster PLS_INTEGER := 0;
            stamp_b   t_int_tab;             -- cluster each B row was last counted in
            stamp_a   t_int_tab;             -- ... and each A row
            cnt_a     t_int_tab;
            cnt_b     t_int_tab;
            pi        PLS_INTEGER;
            cid       PLS_INTEGER;
        BEGIN
            FOR i IN 1..n_p LOOP
                n_cluster := greatest(n_cluster, pairs(i).cluster_id);
            END LOOP;
            FOR c IN 1..n_cluster LOOP cnt_a(c) := 0; cnt_b(c) := 0; END LOOP;
            FOR i IN 1..n_a LOOP stamp_a(i) := 0; END LOOP;   -- cluster ids start at 1, so 0 is "not counted anywhere yet"
            FOR i IN 1..n_b LOOP stamp_b(i) := 0; END LOOP;
            FOR i IN 1..n_p LOOP                              -- count(distinct b_id) and count(distinct a_id) per cluster
                pi := order_idx(i);
                cid := pairs(pi).cluster_id;
                IF stamp_b(pairs(pi).bi) != cid THEN
                    stamp_b(pairs(pi).bi) := cid;
                    cnt_a(cid) := cnt_a(cid) + 1;
                END IF;
                IF stamp_a(pairs(pi).ai) != cid THEN
                    stamp_a(pairs(pi).ai) := cid;
                    cnt_b(cid) := cnt_b(cid) + 1;
                END IF;
            END LOOP;
            FOR i IN 1..n_p LOOP
                DECLARE
                    ta PLS_INTEGER := cnt_a(pairs(i).cluster_id);
                    tb PLS_INTEGER := cnt_b(pairs(i).cluster_id);
                BEGIN
                    pairs(i).corr_type := CASE
                        WHEN ta = 1 AND tb = 1 THEN 'O'
                        WHEN ta > 1 AND tb > 1 AND ta = tb THEN 'F'
                        WHEN ta = 1 AND ta < tb THEN 'A'
                        WHEN tb = 1 AND ta > tb THEN 'B'
                        WHEN ta > 1 AND tb > 1 AND ta != tb THEN 'M'
                    END;
                END;
            END LOOP;
        END classify_pairs;

        -- s02: carry the pair-level verdict back to the source rows. A row can appear in pairs of different types and takes the strongest,
        -- O > F > A > B > M; rows with no pair keep a NULL type, which is what later marks them as losses. Then the easy case is settled:
        -- a pair alone in its cluster has no rival on either side, so it is matched immediately.
        PROCEDURE organise_rows IS
            FUNCTION priority (t VARCHAR2) RETURN PLS_INTEGER IS
            BEGIN
                RETURN CASE t WHEN 'O' THEN 1 WHEN 'F' THEN 2 WHEN 'A' THEN 3 WHEN 'B' THEN 4 WHEN 'M' THEN 5 ELSE 9 END;
            END priority;
        BEGIN
            FOR i IN 1..n_p LOOP
                IF grp_a(pairs(i).ai).corr_type IS NULL
                   OR priority(pairs(i).corr_type) < priority(grp_a(pairs(i).ai).corr_type) THEN
                    grp_a(pairs(i).ai).corr_type := pairs(i).corr_type;
                END IF;
                IF grp_b(pairs(i).bi).corr_type IS NULL
                   OR priority(pairs(i).corr_type) < priority(grp_b(pairs(i).bi).corr_type) THEN
                    grp_b(pairs(i).bi).corr_type := pairs(i).corr_type;
                END IF;
            END LOOP;
            FOR i IN 1..n_p LOOP
                IF pairs(i).corr_type = 'O' THEN mark_matched(i); END IF;
            END LOOP;
        END organise_rows;

        -- s03 to s05, the fuzzy_optimization path for square (F) clusters: both sides are ordered by numeric_value and position k is paired
        -- with position k. Numbered PER CLUSTER, as s03_prepare_duplicates_* is
        --   row_number() over (partition by {keys_a}, x.cluster_id order by o.numeric_value, {key_field_a})
        -- and the keys are what defines this group. Numbering over the group as a whole lets two clusters interleave, because numeric_value
        -- carries the row's own value fields as well as its date, and need not reorder the two sides the same way; the positions then stop
        -- lining up. test/fixture_fcluster.py is that case in eight rows.
        --
        -- The type test is written positively: `corr_type != 'F'` is NULL, not TRUE, for a row with no candidate at all, so a CONTINUE WHEN
        -- would not fire and such a row would be numbered among the real F rows. s03 gets that right via `where o.correlation_type = 'F'`.
        --
        -- Skipped entirely when fuzzy_optimization is off, in which case F clusters fall through to the fixpoint below.
        PROCEDURE match_duplicates IS
            nv_a   t_num_tab;                -- numeric_value per row, computed ONCE: it is a sort key, not a per-comparison value
            nv_b   t_num_tab;
            pos_a  t_int_tab;                -- position within the cluster being numbered
            pos_b  t_int_tab;
            mark_a t_int_tab;                -- the cluster pos_a(i) was computed for
            mark_b t_int_tab;
            ord_a  t_int_tab;                -- that cluster's F rows, then sorted
            ord_b  t_int_tab;
            n_oa   PLS_INTEGER;
            n_ob   PLS_INTEGER;
            i      PLS_INTEGER;
            j      PLS_INTEGER;
            cid    PLS_INTEGER;
            pi     PLS_INTEGER;
            ai     PLS_INTEGER;
            bi     PLS_INTEGER;

            -- Insertion sort by (numeric_value, row_id), s03's `order by o.numeric_value, {key_field_a}`. A cluster is small, and the sort
            -- is stable, so equal rows keep their collection order.
            PROCEDURE sort_side (idx IN OUT NOCOPY t_int_tab, n PLS_INTEGER, side CHAR) IS
                held PLS_INTEGER;
                slot PLS_INTEGER;

                FUNCTION precedes_row (x PLS_INTEGER, y PLS_INTEGER) RETURN BOOLEAN IS
                BEGIN
                    IF side = 'A' THEN
                        IF nv_a(x) != nv_a(y) THEN RETURN nv_a(x) < nv_a(y); END IF;
                        RETURN grp_a(x).row_id < grp_a(y).row_id;
                    ELSE
                        IF nv_b(x) != nv_b(y) THEN RETURN nv_b(x) < nv_b(y); END IF;
                        RETURN grp_b(x).row_id < grp_b(y).row_id;
                    END IF;
                END precedes_row;
            BEGIN
                FOR k IN 2..n LOOP
                    held := idx(k);
                    slot := k - 1;
                    WHILE slot >= 1 AND precedes_row(held, idx(slot)) LOOP
                        idx(slot + 1) := idx(slot);
                        slot := slot - 1;
                    END LOOP;
                    idx(slot + 1) := held;
                END LOOP;
            END sort_side;
        BEGIN
            FOR k IN 1..n_a LOOP
                nv_a(k) := numeric_value(grp_a(k));
                mark_a(k) := 0;
            END LOOP;
            FOR k IN 1..n_b LOOP
                nv_b(k) := numeric_value(grp_b(k));
                mark_b(k) := 0;
            END LOOP;

            -- order_idx walks the pairs in date order and assign_clusters hands out cluster ids along that same walk, so one cluster is one
            -- contiguous run of it and a single pass covers them all.
            i := 1;
            WHILE i <= n_p LOOP
                cid := pairs(order_idx(i)).cluster_id;
                j := i;
                WHILE j <= n_p AND pairs(order_idx(j)).cluster_id = cid LOOP
                    j := j + 1;
                END LOOP;

                n_oa := 0;                                          -- the distinct F rows this cluster holds, each side
                n_ob := 0;
                FOR k IN i..j - 1 LOOP
                    pi := order_idx(k);
                    ai := pairs(pi).ai;
                    bi := pairs(pi).bi;
                    IF grp_a(ai).corr_type = 'F' AND mark_a(ai) != cid THEN
                        mark_a(ai) := cid;
                        n_oa := n_oa + 1;
                        ord_a(n_oa) := ai;
                    END IF;
                    IF grp_b(bi).corr_type = 'F' AND mark_b(bi) != cid THEN
                        mark_b(bi) := cid;
                        n_ob := n_ob + 1;
                        ord_b(n_ob) := bi;
                    END IF;
                END LOOP;

                IF n_oa > 0 AND n_ob > 0 THEN
                    sort_side(ord_a, n_oa, 'A');
                    sort_side(ord_b, n_ob, 'B');
                    FOR k IN 1..n_oa LOOP pos_a(ord_a(k)) := k; END LOOP;
                    FOR k IN 1..n_ob LOOP pos_b(ord_b(k)) := k; END LOOP;
                    FOR k IN i..j - 1 LOOP                          -- s04 pairs position k with position k, within the pair's own cluster
                        pi := order_idx(k);
                        CONTINUE WHEN pairs(pi).corr_type != 'F';
                        ai := pairs(pi).ai;
                        bi := pairs(pi).bi;
                        CONTINUE WHEN mark_a(ai) != cid OR mark_b(bi) != cid;
                        IF pos_a(ai) = pos_b(bi) THEN
                            mark_matched(pi);
                        END IF;
                    END LOOP;
                END IF;

                i := j;
            END LOOP;
        END match_duplicates;

        -- s06 and s07, for the ambiguous clusters: a stable-marriage style fixpoint. Confirm every pair that is simultaneously A's best
        -- remaining choice and B's, re-rank what is left, and repeat. One pass is not enough because the two sides can rank differently, so
        -- a pair can become mutually-best only after a rival has been taken out of the running by an earlier round.
        --
        -- It terminates because each round either confirms at least one pair or confirms none and stops. "Stops" is not "everything is
        -- matched": preferences can cycle, leaving no mutual first choice, and whatever remains is reported as Duplicate or Loss.
        PROCEDURE match_conflicts IS
            progress BOOLEAN := TRUE;
        BEGIN
            WHILE progress LOOP
                progress := FALSE;
                compute_positions('A', TRUE);
                compute_positions('B', TRUE);
                FOR i IN 1..n_p LOOP
                    CONTINUE WHEN NOT is_conflict_pair(i);
                    CONTINUE WHEN pairs(i).matched;
                    CONTINUE WHEN grp_a(pairs(i).ai).matched OR grp_b(pairs(i).bi).matched;
                    IF pairs(i).rank_a = 1 AND pairs(i).rank_b = 1 THEN
                        mark_matched(i);
                        progress := TRUE;
                    END IF;
                END LOOP;
            END LOOP;
        END match_conflicts;

        -- s08's `distance_rank = 1` join: each row's nearest candidate, matched or not, because an unmatched duplicate still has to report
        -- which row it lost to. Ranked over all candidates here, not just the residual.
        PROCEDURE assign_best_pairs IS
        BEGIN
            compute_positions('A', FALSE);
            compute_positions('B', FALSE);
            FOR i IN 1..n_p LOOP
                IF pairs(i).rank_a = 1 THEN
                    grp_a(pairs(i).ai).best_pair := i;
                END IF;
                IF pairs(i).rank_b = 1 THEN
                    grp_b(pairs(i).bi).best_pair := i;
                END IF;
            END LOOP;
        END assign_best_pairs;
    BEGIN
        IF n_a = 0 AND n_b = 0 THEN RETURN; END IF;
        pairs.DELETE;
        build_pairs;
        -- No candidates at all: every row keeps corr_type NULL and matched FALSE, which emit_row turns into losses. A group is one-sided
        -- whenever a key exists on only one side, so this is the common path, not an edge case - and it does no work.
        IF n_p > 0 THEN
            assign_clusters;          -- s01       group pairs into clusters
            classify_pairs;           -- s01       cluster shape -> O/F/A/B/M
            bucket_pairs;             --           index pairs by row, both sides
            compute_distances('A');
            compute_distances('B');
            compute_ranks('A');       -- s01       time and discrepancy tie-breakers
            compute_ranks('B');
            organise_rows;            -- s02       row types; confirm the 1x1 clusters
            IF v_fuzzy THEN
                match_duplicates;     -- s03-s05   positional pairing of F clusters
            END IF;
            match_conflicts;          -- s06-s07   mutual-best-choice fixpoint
            assign_best_pairs;        -- s08       nearest candidate, for the report
        END IF;
        IF capped THEN capped_groups := capped_groups + 1; END IF;
    END process_group;

    ---------------------------------------------------------------------------------------------------------------------- verdict sink
    -- Write one side's buffered verdicts with a single FORALL, then empty the buffer.
    PROCEDURE flush_side (side CHAR) IS
        target VARCHAR2(128) := CASE WHEN side = 'A' THEN v_tmp_verdict_a ELSE v_tmp_verdict_b END;
        stmt   VARCHAR2(400);
    BEGIN
        stmt := 'insert into ' || target || ' (row_id, result_type, discrepancy_id, discrepancy_description) values (:1, :2, :3, :4)';
        IF side = 'A' THEN
            IF vq_a_id.COUNT = 0 THEN RETURN; END IF;
            FORALL i IN 1..vq_a_id.COUNT
                EXECUTE IMMEDIATE stmt USING vq_a_id(i), vq_a_type(i), vq_a_did(i), vq_a_desc(i);
            vq_a_id.DELETE; vq_a_type.DELETE; vq_a_did.DELETE; vq_a_desc.DELETE;
        ELSE
            IF vq_b_id.COUNT = 0 THEN RETURN; END IF;
            FORALL i IN 1..vq_b_id.COUNT
                EXECUTE IMMEDIATE stmt USING vq_b_id(i), vq_b_type(i), vq_b_did(i), vq_b_desc(i);
            vq_b_id.DELETE; vq_b_type.DELETE; vq_b_did.DELETE; vq_b_desc.DELETE;
        END IF;
    END flush_side;

    -- Buffer one verdict, flushing when the buffer is full. Verdicts accumulate over the whole run, so this is what bounds the memory.
    PROCEDURE push_verdict (side CHAR, row_id VARCHAR2, rtype VARCHAR2, did VARCHAR2, ddesc VARCHAR2) IS
        n PLS_INTEGER;
    BEGIN
        IF side = 'A' THEN
            n := vq_a_id.COUNT + 1;
            vq_a_id(n) := row_id; vq_a_type(n) := rtype;
            vq_a_did(n) := did;   vq_a_desc(n) := ddesc;
            IF n >= FLUSH_LIMIT THEN flush_side('A'); END IF;
        ELSE
            n := vq_b_id.COUNT + 1;
            vq_b_id(n) := row_id; vq_b_type(n) := rtype;
            vq_b_did(n) := did;   vq_b_desc(n) := ddesc;
            IF n >= FLUSH_LIMIT THEN flush_side('B'); END IF;
        END IF;
    END push_verdict;

    -- s08's target_error_types: Loss and Discrepancy always, Duplicate only when allow_duplicates is off. A dropped Duplicate appears in no
    -- output at all - it is not matched either.
    FUNCTION error_type_kept (rtype VARCHAR2) RETURN BOOLEAN IS
    BEGIN
        IF rtype IS NULL THEN RETURN FALSE; END IF;
        IF rtype = 'Duplicate' AND v_allow_dups THEN RETURN FALSE; END IF;
        RETURN rtype IN ('Loss', 'Discrepancy', 'Duplicate');
    END error_type_kept;

    -- Turn one source row into its verdict: s08's two branches, and s09's fallthrough to 'Match' for anything they do not claim. The branches
    -- differ in WHICH pair they report against.
    --
    --   branch 1  clean types (O, F) and rows with no candidate. Reports against the pair the row was MATCHED with.
    --               matched + differs -> Discrepancy | not matched -> Loss | matched, no difference -> s09 -> Match
    --   branch 2  ambiguous types (A, B, M) and unmatched F rows. Reports against the row's NEAREST candidate, matched or not.
    --               matched + differs -> Discrepancy | not matched + differs + discrepancy_matching -> Loss | not matched -> Duplicate
    --
    -- The Loss case in branch 2 is deliberate: Loss survives allow_duplicates filtering and Duplicate does not.
    --
    -- The four fields are read out one by one rather than by copying the row, which carries two nested collections.
    PROCEDURE emit_row (side CHAR, idx PLS_INTEGER) IS
        r_id       VARCHAR2(4000);
        r_dt       DATE;
        r_type     VARCHAR2(1);
        r_matched  BOOLEAN;
        m          PLS_INTEGER;
        has_disc   BOOLEAN := FALSE;
        rtype      VARCHAR2(15) := NULL;
        did        VARCHAR2(4000) := NULL;
        ddesc      VARCHAR2(4000) := NULL;
        branch_two BOOLEAN;
    BEGIN
        IF side = 'A' THEN
            r_id := grp_a(idx).row_id; r_dt := grp_a(idx).dt; r_type := grp_a(idx).corr_type; r_matched := grp_a(idx).matched;
        ELSE
            r_id := grp_b(idx).row_id; r_dt := grp_b(idx).dt; r_type := grp_b(idx).corr_type; r_matched := grp_b(idx).matched;
        END IF;

        -- both s08 and s09 re-filter to the unshifted window, so rows pulled in only as shift padding never reach the output; a side read
        -- from an upstream run has no padding and keeps every row
        IF CASE WHEN side = 'A' THEN v_upstream_a ELSE v_upstream_b END IS NULL AND (r_dt < v_date_from OR r_dt > v_date_to) THEN
            RETURN;
        END IF;

        -- a row with no candidate has a NULL correlation type, and NULL IN (...) is NULL rather than FALSE, so guard it explicitly
        branch_two := r_type IS NOT NULL AND (r_type IN ('A', 'B', 'M') OR (r_type = 'F' AND NOT r_matched));

        IF NOT branch_two THEN
            m := CASE WHEN side = 'A' THEN grp_a(idx).matched_pair ELSE grp_b(idx).matched_pair END;
            IF m IS NOT NULL THEN has_disc := pair_has_discrepancy(pairs(m)); END IF;
            IF r_matched AND has_disc THEN rtype := 'Discrepancy';
            ELSIF NOT r_matched THEN rtype := 'Loss';
            END IF;
        ELSE
            m := CASE WHEN side = 'A' THEN grp_a(idx).best_pair ELSE grp_b(idx).best_pair END;
            IF m IS NOT NULL THEN has_disc := pair_has_discrepancy(pairs(m)); END IF;
            IF r_matched AND has_disc THEN rtype := 'Discrepancy';
            ELSIF (NOT r_matched) AND has_disc AND v_disc_matching THEN rtype := 'Loss';
            ELSIF NOT r_matched THEN rtype := 'Duplicate';
            END IF;
        END IF;

        IF m IS NOT NULL AND rtype IS NOT NULL THEN
            did := CASE WHEN side = 'A' THEN grp_b(pairs(m).bi).row_id ELSE grp_a(pairs(m).ai).row_id END;
            ddesc := describe_pair(pairs(m), side);
        END IF;

        IF error_type_kept(rtype) THEN
            push_verdict(side, r_id, rtype, did, ddesc);
        ELSIF rtype IS NULL AND r_matched THEN
            push_verdict(side, r_id, 'Match', NULL, NULL);
        END IF;
    END emit_row;

    -- Emit verdicts for the group just resolved, before it is overwritten by the next one.
    PROCEDURE emit_group IS
    BEGIN
        IF v_need_a THEN
            FOR i IN 1..grp_a.COUNT LOOP emit_row('A', i); END LOOP;
        END IF;
        IF v_need_b THEN
            FOR i IN 1..grp_b.COUNT LOOP emit_row('B', i); END LOOP;
        END IF;
    END emit_group;

    ------------------------------------------------------------------------------------------------------------------- materialisation
    -- The select list that reproduces what rapo_temp_source_* would have held. Rapo copies by NAME, so the issue and stage tables must carry
    -- the same column names the DB engine's source table would have: every column, plus the two adjustments that engine also makes - a
    -- TIMESTAMP date field narrowed to DATE, and the key aliased from rowid when it is not a real column. Listed explicitly rather than with
    -- a.*, because those adjustments have to replace columns rather than duplicate them. Hidden columns are left out; virtual ones are kept.
    -- An upstream run's own result columns are left out where this control writes the same ones, as Parser._parse_select does.
    FUNCTION column_list (source_name VARCHAR2, alias VARCHAR2, date_field VARCHAR2, key_field VARCHAR2, key_rowid BOOLEAN) RETURN CLOB IS
        list     CLOB := NULL;
        upstream NUMBER := CASE WHEN alias = 'a' THEN v_upstream_a ELSE v_upstream_b END;
    BEGIN
        FOR c IN (
            SELECT column_name, data_type FROM user_tab_cols WHERE table_name = upper(source_name) AND hidden_column = 'NO' ORDER BY column_id
        ) LOOP
            CONTINUE WHEN upstream IS NOT NULL
                      AND c.column_name IN ('RAPO_PROCESS_ID', 'RAPO_RESULT_TYPE', 'RAPO_DISCREPANCY_ID', 'RAPO_DISCREPANCY_DESCRIPTION');
            IF list IS NOT NULL THEN list := list || ', '; END IF;
            IF upper(c.column_name) = upper(date_field) AND c.data_type LIKE 'TIMESTAMP%' THEN
                list := list || 'cast(' || alias || '."' || c.column_name || '" as date) as "' || c.column_name || '"';
            ELSE
                list := list || alias || '."' || c.column_name || '"';
            END IF;
        END LOOP;
        IF key_rowid THEN
            list := list || ', rowidtochar(' || alias || '.rowid) as ' || quoted(key_field);
        END IF;
        RETURN list;
    END column_list;

    -- Turn one side's verdicts into the two tables Rapo saves from: the issue table (everything that is not a Match) and the stage table
    -- (the Matches), each carrying the full source row plus the three rapo_* result columns. The verdict table only holds row ids, so the
    -- source is joined back here.
    --
    -- The join-back repeats the source filter and the unshifted window: row_id is the configured key field, which rapo does not require to
    -- be unique, and where it is not one verdict row would otherwise join to every source row sharing that value, including rows of other
    -- days and rows the filter excluded. The DB engine cannot reach those because it joins rapo_temp_source_*, already restricted.
    --
    -- The stage table follows need_recons, as prepare_save does for s09: it is what Executor.count_results_* keys off.
    PROCEDURE materialise (side CHAR) IS
        source_name VARCHAR2(128) := CASE WHEN side = 'A' THEN v_source_a ELSE v_source_b END;
        alias       VARCHAR2(1) := CASE WHEN side = 'A' THEN 'a' ELSE 'b' END;
        date_field  VARCHAR2(128) := CASE WHEN side = 'A' THEN v_date_field_a ELSE v_date_field_b END;
        key_field   VARCHAR2(128) := CASE WHEN side = 'A' THEN v_key_field_a ELSE v_key_field_b END;
        key_rowid   BOOLEAN := CASE WHEN side = 'A' THEN v_key_rowid_a ELSE v_key_rowid_b END;
        verdict     VARCHAR2(128) := CASE WHEN side = 'A' THEN v_tmp_verdict_a ELSE v_tmp_verdict_b END;
        error_table VARCHAR2(128) := CASE WHEN side = 'A' THEN v_tmp_error_a ELSE v_tmp_error_b END;
        stage_table VARCHAR2(128) := CASE WHEN side = 'A' THEN v_tmp_stage_a ELSE v_tmp_stage_b END;
        filter      CLOB := CASE WHEN side = 'A' THEN v_filter_a ELSE v_filter_b END;
        need_recons BOOLEAN := CASE WHEN side = 'A' THEN v_need_recons_a ELSE v_need_recons_b END;
        cols        CLOB;
        join_rule   VARCHAR2(4000);
        base        CLOB;
        stmt        CLOB;
        issues      NUMBER;
        matches     NUMBER := NULL;
    BEGIN
        cols := column_list(source_name, alias, date_field, key_field, key_rowid);
        IF key_rowid THEN
            join_rule := alias || '.rowid = chartorowid(v.row_id)';
        ELSE
            join_rule := 'cast(' || alias || '.' || quoted(key_field) || ' as varchar2(4000)) = v.row_id';
        END IF;
        base := ' from ' || source_name || ' ' || alias || ' join ' || verdict || ' v on ' || join_rule
                || ' where ' || scope_predicate(side, alias, date_field, v_date_from, v_date_to);
        IF filter IS NOT NULL AND length(filter) > 0 THEN
            base := base || ' and (' || filter || ')';
        END IF;

        stmt := 'create table ' || error_table || ' nologging as select ';
        IF v_parallelism > 0 THEN
            stmt := stmt || '/*+ parallel(' || v_parallelism || ') */ ';
        END IF;
        stmt := stmt || cols
                || ', v.result_type as rapo_result_type'
                || ', v.discrepancy_id as rapo_discrepancy_id'
                || ', v.discrepancy_description as rapo_discrepancy_description'
                || base || ' and v.result_type != ''Match''';
        log_info('Creating ' || error_table || ' with query:' || chr(10) || stmt);
        EXECUTE IMMEDIATE stmt;
        EXECUTE IMMEDIATE 'select count(*) from ' || error_table INTO issues;

        IF need_recons THEN
            stmt := 'create table ' || stage_table || ' nologging as select ';
            IF v_parallelism > 0 THEN
                stmt := stmt || '/*+ parallel(' || v_parallelism || ') */ ';
            END IF;
            stmt := stmt || cols
                    || ', v.result_type as rapo_result_type'
                    || ', v.discrepancy_id as rapo_discrepancy_id'
                    || ', v.discrepancy_description as rapo_discrepancy_description'
                    || base || ' and v.result_type = ''Match''';
            log_info('Creating ' || stage_table || ' with query:' || chr(10) || stmt);
            EXECUTE IMMEDIATE stmt;
            EXECUTE IMMEDIATE 'select count(*) from ' || stage_table INTO matches;
        END IF;

        log_info('Side ' || side || ': ' || CASE WHEN need_recons THEN to_char(matches) ELSE 'no' END || ' matched, ' || issues
                 || ' with issues');
    END materialise;

    -- The per-side scratch table the merge writes its verdicts into. Dropped first in case a previous run with this process_id left one
    -- behind, and NOLOGGING because it never outlives the run.
    PROCEDURE create_verdict_table (name VARCHAR2) IS
    BEGIN
        drop_if_exists(name);
        EXECUTE IMMEDIATE 'create table ' || name || ' (row_id varchar2(4000), result_type varchar2(15), '
                       || 'discrepancy_id varchar2(4000), discrepancy_description varchar2(4000)) nologging';
    END create_verdict_table;

    -- allow_null keeps these rows in scope, but a NULL key cannot satisfy an equi-join, so they are Loss by construction.
    PROCEDURE count_null_key_rows (side CHAR) IS
        stmt CLOB := build_null_key_select(side);
        n    NUMBER := 0;
    BEGIN
        IF stmt IS NULL THEN RETURN; END IF;
        EXECUTE IMMEDIATE 'insert into ' || CASE WHEN side = 'A' THEN v_tmp_verdict_a ELSE v_tmp_verdict_b END
                       || ' (row_id, result_type) select row_id, ''Loss'' from (' || stmt || ')';
        n := sql%rowcount;
        IF side = 'A' THEN fetched_a := fetched_a + n;
        ELSE fetched_b := fetched_b + n; END IF;
    END count_null_key_rows;

    -- Close the cursors and drop the scratch tables. Called on both the success and the failure path, hence `quiet`: while unwinding from an
    -- error, a failure to clean up must not replace the original exception. debug_mode keeps the verdict tables for inspection.
    PROCEDURE cleanup (quiet BOOLEAN) IS
    BEGIN
        BEGIN
            IF c_a IS NOT NULL AND dbms_sql.is_open(c_a) THEN dbms_sql.close_cursor(c_a); END IF;
            IF c_b IS NOT NULL AND dbms_sql.is_open(c_b) THEN dbms_sql.close_cursor(c_b); END IF;
        EXCEPTION WHEN OTHERS THEN
            IF NOT quiet THEN RAISE; END IF;
        END;
        IF NOT v_debug_mode THEN
            BEGIN
                drop_if_exists(v_tmp_verdict_a);
                drop_if_exists(v_tmp_verdict_b);
            EXCEPTION WHEN OTHERS THEN
                IF NOT quiet THEN RAISE; END IF;
            END;
        END IF;
    END cleanup;

BEGIN
    parse_payload;

    DELETE FROM rapo_engine_log WHERE process_id = v_process_id;   -- a retry reusing the same process_id must not replay the old lines
    COMMIT;

    log_info('PL-SQL engine started for control ' || v_control_name || ' over ' || to_char(v_date_from, 'YYYY-MM-DD HH24:MI:SS')
             || ' .. ' || to_char(v_date_to, 'YYYY-MM-DD HH24:MI:SS'));
    log_info('Source A: ' || v_source_a || ' (' || v_date_field_a || ', key ' || v_key_field_a
             || CASE WHEN v_key_rowid_a THEN ' as rowid' END || ')');
    log_info('Source B: ' || v_source_b || ' (' || v_date_field_b || ', key ' || v_key_field_b
             || CASE WHEN v_key_rowid_b THEN ' as rowid' END || ')');
    log_info('Rules: ' || n_corr || ' correlation field(s), ' || n_disc || ' discrepancy field(s), time shift ' || v_shift_from || '..'
             || v_shift_to || 's, time tolerance ' || v_tol_from || '..' || v_tol_to || 's');

    col_date_pos := n_corr + 2;
    col_disc_pos := n_corr + 3;

    -- Built once: build_select parses and describes a throwaway probe to type each correlation key, so rebuilding costs another round trip.
    v_sql_a := build_select('A');
    v_sql_b := build_select('B');

    -- correlation_limit = true sizes the cap from the fetched counts, i.e. two extra full passes over sources about to be read again.
    IF v_corr_limit = -1 THEN
        DECLARE
            ca NUMBER;
            cb NUMBER;
        BEGIN
            log_info('correlation_limit=true: counting both sources to size the cap');
            EXECUTE IMMEDIATE 'select count(*) from (' || v_sql_a || ')' INTO ca;
            EXECUTE IMMEDIATE 'select count(*) from (' || v_sql_b || ')' INTO cb;
            v_corr_limit := trunc(greatest(ca, cb) * 2.5);
        END;
    END IF;

    -- logged after the resolution above, so the line names the cap actually in force rather than the -1 marker
    log_info('Options: normalization_type=' || v_norm
             || ', fuzzy_optimization=' || CASE WHEN v_fuzzy THEN 'true' ELSE 'false' END
             || ', discrepancy_matching=' || CASE WHEN v_disc_matching THEN 'true' ELSE 'false' END
             || ', allow_duplicates=' || CASE WHEN v_allow_dups THEN 'true' ELSE 'false' END
             || ', correlation_limit=' || v_corr_limit
             || ', max_candidates=' || v_max_candidates);

    log_info('Fetching side A with query:' || chr(10) || v_sql_a);
    log_info('Fetching side B with query:' || chr(10) || v_sql_b);

    create_verdict_table(v_tmp_verdict_a);
    create_verdict_table(v_tmp_verdict_b);
    drop_if_exists(v_tmp_error_a);
    drop_if_exists(v_tmp_error_b);
    drop_if_exists(v_tmp_stage_a);
    drop_if_exists(v_tmp_stage_b);

    open_side(v_sql_a, c_a);
    open_side(v_sql_b, c_b);

    have_a := next_row(c_a, row_a);
    IF have_a THEN fetched_a := fetched_a + 1; END IF;
    have_b := next_row(c_b, row_b);
    IF have_b THEN fetched_b := fetched_b + 1; END IF;

    DECLARE
        cmp       PLS_INTEGER;
        group_key t_row;
        budget    NUMBER := CASE WHEN v_corr_limit > 0 THEN v_corr_limit ELSE -1 END;
    BEGIN
        -- THE MERGE. Both cursors are sorted by correlation key, so the classic merge step applies: compare the two fronts, take the lower
        -- key, and collect every row that shares it. When the fronts are equal both sides contribute and the group has candidates; when one
        -- side is lower it forms a group of its own and every row in it is a loss. Exactly one group is in memory at a time, which is the
        -- whole point. An exhausted side is treated as infinitely large, draining the remaining rows of the other as one-sided groups.
        WHILE have_a OR have_b LOOP
            grp_a.DELETE;
            grp_b.DELETE;

            IF have_a AND have_b THEN cmp := cmp_keys(row_a, row_b);
            ELSIF have_a THEN cmp := -1;   -- B exhausted: A rows are losses
            ELSE cmp := 1;                 -- A exhausted: B rows are losses
            END IF;

            -- the key of the group about to be collected, copied because row_a/row_b advance underneath us as the group is gathered
            IF cmp <= 0 THEN group_key := row_a; ELSE group_key := row_b; END IF;

            -- cmp <= 0: A holds the group key, so collect its run of rows. The EXIT relies on short-circuit evaluation - once have_a is
            -- false, row_a is spent and must not be compared.
            IF cmp <= 0 THEN
                LOOP
                    grp_a(grp_a.COUNT + 1) := row_a;
                    have_a := next_row(c_a, row_a);
                    IF have_a THEN fetched_a := fetched_a + 1; END IF;
                    EXIT WHEN NOT have_a OR cmp_keys(row_a, group_key) != 0;
                END LOOP;
            END IF;

            -- cmp >= 0: likewise for B. When cmp = 0 both branches run and the group has rows from both sides, the only case that can match.
            IF cmp >= 0 THEN
                LOOP
                    grp_b(grp_b.COUNT + 1) := row_b;
                    have_b := next_row(c_b, row_b);
                    IF have_b THEN fetched_b := fetched_b + 1; END IF;
                    EXIT WHEN NOT have_b OR cmp_keys(row_b, group_key) != 0;
                END LOOP;
            END IF;

            process_group(budget);
            emit_group;
            groups_done := groups_done + 1;

            IF fetched_a + fetched_b - last_reported >= REPORT_EVERY THEN
                report_progress;
                log_info('Matching in progress: ' || groups_done || ' key group(s), ' || fetched_a || '/' || fetched_b || ' records read');
            END IF;
        END LOOP;

        IF budget = 0 THEN
            log_line('WARNING', 'correlation_limit of ' || v_corr_limit || ' candidate pairs was reached; the remaining rows were left '
                                || 'uncorrelated and are reported as losses');
        END IF;
    END;

    dbms_sql.close_cursor(c_a);
    dbms_sql.close_cursor(c_b);

    log_info('Matching finished: ' || groups_done || ' key group(s), ' || fetched_a || ' records read from A, ' || fetched_b || ' from B');

    IF capped_groups > 0 THEN
        log_line('WARNING', capped_groups || ' key group(s) had more than ' || v_max_candidates || ' rows within reach of one another, so '
                            || 'each row was matched against its nearest ' || v_max_candidates || ' candidates by time only. Correlation '
                            || 'keys this coarse make the matching approximate: consider a more selective correlation_config, a narrower '
                            || 'time_shift, or raise rule_config.max_candidates if the clusters are genuinely that large.');
    END IF;

    flush_side('A');
    flush_side('B');

    IF v_need_a THEN count_null_key_rows('A'); END IF;
    IF v_need_b THEN count_null_key_rows('B'); END IF;
    COMMIT;

    IF v_need_a THEN materialise('A'); END IF;
    IF v_need_b THEN materialise('B'); END IF;

    report_progress;
    log_info('PL-SQL engine finished: ' || fetched_a || '/' || fetched_b || ' records fetched');

    cleanup(FALSE);

EXCEPTION
    WHEN OTHERS THEN
        -- record where it got to before unwinding; the control process drains these lines into the run log even though the run ends in error
        BEGIN
            report_progress;
            log_line('ERROR', sqlerrm || chr(10) || dbms_utility.format_error_backtrace);
        EXCEPTION WHEN OTHERS THEN NULL;
        END;
        cleanup(TRUE);
        RAISE;
END;
