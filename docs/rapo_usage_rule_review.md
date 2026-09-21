# RAPO_USAGE_RULE — code review

Review of the procedure as first compiled (the MoneyMap-derived streaming merge-join), recorded so the
rewrite is traceable. "Disposition" says whether the rewrite removes the issue or it needs a deliberate fix.

Environment the findings were verified against: Oracle 19.9, `NLS_DATE_FORMAT = DD-MON-RR`,
`NLS_SORT = NLS_COMP = BINARY`.

## Critical

| # | Finding | Disposition |
|---|---|---|
| C1 | `compare_rows`'s `WHEN OTHERS` sets `result := 2`. No branch of the main loop handles `2` — not the `=1`, `=-1` or `=0` branch — so **no row is fetched and the loop spins forever**. It also swallows the original error. | Remove the blanket handler; let errors propagate |
| C2 | `ret.missmatch_tag_a := row_a.tag` assigns `VARCHAR2(4000)` into `VARCHAR2(100)` → ORA-06502, caught by C1 → infinite loop. Latent with `ROWID` (18 chars), live for a VIEW with a long `TAG`. | Size all key carriers consistently |
| C3 | **The A-side window is inverted.** A is fetched `[from - tol_from, to - tol_to]`. With `tol_from=-1, tol_to=+1` that is `[from+1s, to-1s]` — the window *shrinks* where it must *widen*. Correct is `[from - tol_to, to - tol_from]`. `in_global_tolerance_band` exists only to mask the B-side false `Loss` rows this creates. | Fix; delete `in_global_tolerance_band` |
| C4 | `done_A`/`done_B` are never cleared when the rewind buffer pushes rows back into a dequeue. After the fuzzy loop exhausts a cursor, buffered rows are returned but the side stays "done", so the tail of every cluster is misclassified. | Gone — group-at-a-time buffering replaces the dequeues |
| C5 | Once a side is exhausted, the drain branch still calls `fetch_row` on it every iteration — each call appends another `Cursor X exhausted` line to the `text_log` CLOB and does an `UPDATE`+`COMMIT`. O(n) commits and an unbounded CLOB on a large run. | Gone — no per-row logging |
| C6 | `RAPO_LOG_ID_TRG` has no `WHEN (new.process_id IS NULL)` guard, so it overwrites a supplied `process_id`. The explicit-id `INSERT` branch orphans its row and every later `UPDATE ... WHERE process_id = <supplied>` hits **zero rows**. | Gone — the procedure no longer INSERTs; Rapo owns the log row |

## High

| # | Finding | Disposition |
|---|---|---|
| H1 | `v_sql_a`/`v_sql_b` are `VARCHAR2(4000)`. Real filters are CLOBs — control 45's is multi-line with inline `--` comments. Overflow → ORA-06502. | CLOB + the `dbms_sql.parse` CLOB overload |
| H2 | Date-typed mismatch fields are bound as `VARCHAR2` and re-parsed with `TO_DATE(x)` **with no format mask**. `NLS_DATE_FORMAT` is `DD-MON-RR`, so **the time component is silently lost** and PL/SQL comparison disagrees with the cursor's `ORDER BY`. | Bind typed, or use an explicit mask |
| H3 | `MATCH_KEY` is `field ||'#@'|| field`. NULL-collapsing (`NULL||'#@'||'x'` = `'#@x'`), and a value containing `#@` collides. Distinct tuples can compare equal. | Canonical per-field encoding; NULL-key rows routed straight to `Loss` |
| H4 | `RTRIM(v_sql_a, ' ||''#@''|| ')` trims a **character set**, not a suffix. With zero match fields it emits `ROWID TAG, MATCH_KEY,` — invalid SQL. A formula key ending in a quote over-trims. | Build the list with a separator flag |
| H5 | End-of-data is detected by `ret.tag IS NULL`, not by `dbms_sql.fetch_rows` returning 0. A genuine NULL `TAG` from a view truncates the run silently. | Use the fetch return value |
| H6 | The exception handler neither closes the cursors nor drops the `RAPO_TMP_*` tables, and **does not re-raise** — the caller sees success. | Cleanup + re-raise |
| H7 | `invalid_datasource` is raised but never handled; it surfaces through `WHEN OTHERS` as "User-Defined Exception". `control_not_defined` is declared and never used. | Handle explicitly |
| H8 | Unbounded PGA: the rewind buffer and both dequeues can grow to a whole key group with nothing capping them. | Bound by `correlation_limit` per group |
| H9 | Datasource names, filters and field names are concatenated into dynamic SQL. | `dbms_assert.simple_sql_name` on identifiers; filters stay raw by design |

## Medium

| # | Finding |
|---|---|
| M1 | `fetch_status_c1 := DBMS_SQL.EXECUTE(c2)` assigns c2's result to c1's variable; `fetch_status_c2` is unused |
| M2 | `update_log` writes `fetched_number`/`success_number`/`error_number`/`error_level`, which are never assigned — always NULL. Harmless (Rapo leaves them NULL for REC too) but misleading |
| M3 | `chr(13)` (CR) as line separator instead of `chr(10)` |
| M4 | Asymmetric duplicate check — `compare_rows(row_a, prev_row_a)` on A but `compare_rows(prev_row_b, row_b)` on B, reversed arguments over a signed distance |
| M5 | `rec_in_tolerance_band` is incremented inside a function used in a boolean condition → double counting |
| M6 | `text_log` built by repeated CLOB `||` → O(n²) |
| M7 | Dead code: `v_desc_tab`, `v_insert_sql`, `cursor_number_value`, `fetch_status_c2` |
| M8 | Per-row `EXECUTE IMMEDIATE` insert in `print_row` |
| M9 | `"_PID" VARCHAR2(10 CHAR)` holds a NUMBER; `rapo_log_seq` runs to 2000000000 — exactly 10 digits, no margin |
| M10 | A NULL `v_to_date` is defaulted for the log row but used raw in the cursor SQL → `TO_DATE('')` |

## Semantic gaps against Rapo's REC

Not defects in the procedure's own terms, but differences that had to be closed for the two engines to agree.

1. **`mismatch` fields were match criteria.** They sat in `ORDER BY` and in `compare_rows`, so an
   out-of-tolerance value made rows *fail to match* → `Missing`. In Rapo, `discrepancy_config` fields are
   never join conditions; the pair correlates on keys + date and the value difference only *labels* it
   `Discrepancy`.
2. **One time window instead of two.** Rapo has `time_shift_*` (how far apart rows may be and still be
   candidates) and `time_tolerance_*` (how far apart before the match is flagged). The procedure's single
   `date.tolerance_from/to` conflated them.
3. **No `O/F/A/B/M` taxonomy.** It depends on cluster cardinalities, which a pointer-walk never has. The
   rewrite consumes one key-hash group at a time, which makes them computable while keeping memory bounded
   by the largest group rather than the dataset.

## Related defects found in Rapo's own REC SQL

Fixed in the same work, under "parity with Rapo as intended" — see `migrations/` and git history.

1. `s03_prepare_duplicates_{a,b}.sql` partitioned `cluster_position_number` by the **unique** key, so it was
   always 1 and `s04` cross-matched every pair in an `F` cluster instead of pairing positionally. A
   regression from commit `01eb3ec`: `{keys_a}` was still computed and passed, just no longer referenced.
2. `s08_save_error_b.sql` wrote `m.b_id` as `rapo_discrepancy_id` on a query joined by `{key_field_b} = m.b_id`,
   so the B row's discrepancy id pointed at itself rather than its A counterparty.
3. Unmatched `F` rows failed every branch of `s08` and `s09`, so they appeared in neither output.
