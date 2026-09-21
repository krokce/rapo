# Rapo v0.8.1 Change Log

## Annotation
This release adds a third control engine that runs reconciliation inside Oracle, and fixes three defects in
the reconciliation algorithm. The upgrade steps are in the [migration instructions](README.md).

1. **PL-SQL engine for reconciliation**. A REC control can now be set to `control_engine = 'PL'`, which runs
   the whole matching pipeline inside Oracle through the `RAPO_USAGE_RULE` procedure instead of the Python
   `s01..s09` scripts. It is a drop-in replacement: the sources, filters, `rule_config`, output tables and
   `rapo_log` counters are unchanged, and results land in `rapo_resa_<name>` / `rapo_resb_<name>` as before.
   The control editor offers the engine on reconciliation controls.
1. **No Cartesian join**. The `DB` engine materialises the full A × B candidate set in `s01_correlate`, which
   `correlation_limit` only truncates and which is off by default. The `PL` engine streams both sources in
   key order and holds one correlation-key group at a time, and keeps that group bounded two ways: a
   **two-pointer band join** (both sides arrive date-ordered, so the rows in reach of a row are a contiguous
   window whose ends only move forward) and a **per-row fan-out cap**, `rule_config.max_candidates`, default
   100. A group of n rows therefore costs `O(n × max_candidates)` candidate pairs rather than `n²`.

   On one key group with every row inside the window, n rows per side, `DB` versus `PL`: n=300 7.4s / 23.1s,
   n=1000 25.5s / 48.1s, with identical results at every size. Without the cap n=300 alone took 383s and
   185 MB of PGA — which matters because PGA is process memory and does not spill, unlike the temp table the
   `DB` engine writes, and exceeding `pga_aggregate_limit` affects other sessions on the instance.

   On a cluster larger than `max_candidates` the matching becomes approximate, and the run log says so with
   a `WARNING` naming how many groups were affected. That normally means the correlation key is too coarse
   or `time_shift` too wide.

   It also fetches from the datasources itself, so no `rapo_temp_source_*` tables are created.
1. **Same answers, deliberately**. The `O`/`F`/`A`/`B`/`M` correlation taxonomy, the positional pairing of
   fuzzy clusters and the mutual-best-choice fixpoint for ambiguous ones are all reproduced, the last one
   cluster-locally — which is the same answer as the global computation, because every candidate of a row
   lies in its own group. `fuzzy_optimization`, `discrepancy_matching`, `allow_duplicates` and
   `correlation_limit` behave as they do on the `DB` engine.
1. **The engine's log reaches the run log, live.** The procedure appends to the new `rapo_engine_log` table
   and the control process drains it into `logs/controls/<control_id>/<process_id>.log` every two seconds, so
   the window and sources, the generated fetch SQL, progress every 50 000 rows, the issue and stage table
   counts and any Oracle error all show up under **Show full log** while the run is still going. The drain
   also runs when the call fails, so a failed run keeps the context that led to it.
1. **`normalization_type = "minmax"` is rejected on the new engine.** It normalises over the entire candidate
   set, which a streaming engine never holds. The run fails with a message naming the option rather than
   quietly producing different numbers. The other values (`none`/`default`, `rank`, `z_norm`, `srd`) are
   cluster-local and behave identically.

   While verifying this, one thing became clear that applies to **both** engines: `rank` divides every
   dimension by the same per-row constant, so it cannot change which candidate wins — it is a no-op for
   match selection, kept only for compatibility. `z_norm` and `srd` weight the dimensions differently and
   genuinely can change the outcome. See `docs/rapo_usage_rule_payload.md`.

## Fixes

These **change the results of existing REC controls** on both engines. Re-baseline any comparison kept
against previous runs.

1. **Duplicates inside a fuzzy cluster were cross-matched.** `s03_prepare_duplicates_{a,b}.sql` numbered
   rows by partitioning on the *unique* key rather than the correlation keys, so `cluster_position_number`
   was always 1, `s04` paired every A row with every B row in the cluster and `s05` marked them all matched.
   A regression from commit `01eb3ec`, which left `{keys_a}` computed and passed but no longer referenced.
1. **`rapo_discrepancy_id` was wrong on the B side.** `s08_save_error_b.sql` selected `m.b_id` on a query
   joined by `{key_field_b} = m.b_id`, so the column pointed at the B row itself instead of its A
   counterpart. It now selects `m.a_id`, mirroring the A side.
1. **Unmatched fuzzy rows disappeared.** A row of correlation type `F` that ended up unmatched satisfied
   neither branch of `s08_save_error_*` nor the matched condition of `s09_save_stage_*`, so it was written to
   neither the issue nor the reconciled output. It is now classified with the other unmatched conflict types,
   as `Duplicate` or, under `discrepancy_matching`, as `Loss`.
