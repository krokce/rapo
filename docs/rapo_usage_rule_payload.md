# RAPO_USAGE_RULE payload

`RAPO_USAGE_RULE(json_input IN CLOB)` takes one argument, and that JSON is its whole truth: the procedure
never reads `rapo_config`. Rapo builds it in `Parser.parse_procedure_payload` (`rapo/core/control.py`), which
reuses `parse_reconciliation_rule_config`, so every `[ALGORITHM]` fallback is already resolved and the
procedure applies no defaults of its own.

A payload is therefore self-contained: capture one from the run log and it replays the run exactly.

## Shape

```json
{
  "process_id": 1000002007,
  "control_name": "RAPO_FIX_REC",
  "date_from": "2026-09-01 00:00:00",
  "date_to": "2026-09-01 23:59:59",
  "debug_mode": false,
  "parallelism": 4,
  "need_a": true,
  "need_b": true,
  "source_a": {
    "name": "ds_fix_msw",
    "filter": "ORIG_PARTY_GRP is not null",
    "date_field": "start_time",
    "key_field": "tag"
  },
  "source_b": {
    "name": "ds_fix_dr_msw",
    "filter": null,
    "date_field": "start_date_time",
    "key_field": "tag"
  },
  "rule_config": {
    "correlation_config": [
      { "field_a": "charged_party_addr", "field_b": "a_number_extension",
        "allow_null": false, "formula_mode": false }
    ],
    "discrepancy_config": [
      { "field_a": "call_duration", "field_b": "duration",
        "numeric_tolerance_from": -1, "numeric_tolerance_to": 1,
        "percentage_mode": false, "formula_mode": false,
        "formula_alias": "CALL_DURATION" }
    ],
    "time_shift_from": -10, "time_shift_to": 10,
    "time_tolerance_from": -1, "time_tolerance_to": 1,
    "allow_duplicates": false,
    "fuzzy_optimization": true,
    "normalization_type": "none",
    "discrepancy_matching": true,
    "correlation_limit": false,
    "need_issues_a": true, "need_issues_b": true,
    "need_recons_a": false, "need_recons_b": false
  }
}
```

## Top level

| Key | Required | Meaning |
|---|---|---|
| `process_id` | yes | The `rapo_log` row rapo already created. The procedure **updates** it (`fetched_number_a/b`) and never inserts — `RAPO_LOG_ID_TRG` overwrites a supplied id on insert, so an insert here would orphan the row |
| `control_name` | yes | Used for messages only |
| `date_from`, `date_to` | yes | `YYYY-MM-DD HH24:MI:SS`. The **unshifted** window. Output is re-filtered to it, so rows pulled in only as shift padding correlate but never reach the result |
| `debug_mode` | no (false) | Keeps the verdict tables for inspection |
| `parallelism` | no (0) | `0` emits no hint; otherwise `/*+ parallel(N) */` |
| `need_a`, `need_b` | no (true) | Whether each side is processed at all |

## `source_a` / `source_b`

| Key | Meaning |
|---|---|
| `name` | Table, view or materialized view in the current schema |
| `filter` | Raw SQL predicate, or null. Wrapped in parentheses and ANDed |
| `date_field` | The correlation date column. Cast to `DATE`, so a `TIMESTAMP` loses sub-second precision exactly as the Python engine's fetch does |
| `key_field` | The row identity. If the source has no such column, `rowid` is aliased under that name — the same fallback `_parse_select` makes |

## `rule_config`

Passed through from `rapo_config.rule_config` after parsing. Same keys, same meanings as the `DB` engine.

**The two time windows are different things and must not be conflated:**

- `time_shift_from` / `time_shift_to` (seconds) — how far apart an A and a B row may be and still be
  *candidates*. Widens the fetch window and defines the cluster chaining.
- `time_tolerance_from` / `time_tolerance_to` (seconds) — how far apart before a matched pair is *flagged*
  as a time discrepancy. Never affects matching.

A pair 7s apart under shift ±10 and tolerance ±5 correlates, and is reported `Discrepancy`.

`correlation_config[]` are the join keys — `field_a = field_b`, ANDed. `allow_null: false` (the default)
drops rows with a NULL key before they are fetched or counted; `allow_null: true` keeps and counts them, but
a NULL can never satisfy an equi-join, so they are reported `Loss`. `formula_mode: true` means the string is
raw SQL carrying its own `a.` / `b.` qualifier; otherwise the bare column name is qualified by the procedure.

`discrepancy_config[]` are **compared, never joined**. Each yields a signed
`coalesce(a.x, 0) - coalesce(b.x, 0)`; outside `[numeric_tolerance_from, numeric_tolerance_to]` it flags the
pair. `formula_alias` is the label in `rapo_discrepancy_description`. Details worth knowing:

- The band is **inclusive and may be asymmetric** — `-2 … +5` flags a difference of `-4` but not `+4`.
- A NULL tolerance means `0`, i.e. any difference at all is a discrepancy.
- `percentage_mode` divides by whichever side is non-zero and scales by 100 **for the flag only**; the value
  written to the description stays the raw signed difference. `0` against `0` gives a NULL denominator and is
  therefore *not* a discrepancy.
- A NULL value is coalesced to `0` before subtracting, so NULL against `100` reports `-100`.
- With several fields configured, `rapo_discrepancy_description` concatenates every flagged one in
  **configured order, with the time gap first**: `EVENT_TIME|-5;AMOUNT|5;QTY|10;`.

| Key | Effect |
|---|---|
| `allow_duplicates` | `true` drops `Duplicate` rows from the output entirely |
| `fuzzy_optimization` | `true` pairs square (`F`) clusters positionally; `false` sends them through the mutual-best-choice fixpoint instead |
| `normalization_type` | `none`/`default`, `rank`, `z_norm`, `srd`. **`minmax` is rejected** — it normalizes over the whole candidate set, which a streaming engine never holds |
| `discrepancy_matching` | `true` reclassifies an unmatched duplicate that also carries a discrepancy as `Loss` rather than `Duplicate`, which matters because `Loss` survives `allow_duplicates` |
| `correlation_limit` | `false`/absent = unlimited; `true` = `2.5 × max(fetched_a, fetched_b)`; a positive integer = that many candidate pairs |
| `max_candidates` | **PL engine only**, default `100`. The per-row fan-out cap that keeps a key group from degenerating into a cross join — see below |
| `need_issues_a/b`, `need_recons_a/b` | Which of the issue and reconciled outputs rapo copies into the result table |

### `max_candidates` and the cross-join guard

The `DB` engine materializes the whole A × B candidate set in `s01_correlate`; `correlation_limit` is its only
brake, and it is off by default. The `PL` engine instead keeps the candidate set bounded by construction:

1. **Band join.** Both sides arrive date-ordered, so the rows within reach of an A row form a contiguous
   window of B whose ends only move forward. When dates are spread, that window is small and nothing else
   is needed.
2. **Fan-out cap.** When more than `max_candidates` rows are in reach, a row keeps only the nearest in time,
   and no row may be *offered* more than that many times either. A group of *n* rows therefore costs
   `O(n × max_candidates)` pairs instead of `n²`.

One key group, every row inside the window, *n* rows per side:

| n | potential pairs | DB engine | PL engine | results |
|---|---|---|---|---|
| 100 | 10 000 | 3.2s | 6.5s | identical |
| 200 | 40 000 | 4.4s | 9.7s | identical |
| 300 | 90 000 | 7.4s | 23.1s | identical |
| 1 000 | 1 000 000 | 25.5s | 48.1s | identical |

Without the cap, `n=300` alone took **383s and 185 MB of PGA**, and `n=1000` was not reachable —
PGA is process memory and does not spill, unlike the temp table the `DB` engine writes.

**The trade-off:** on a cluster larger than `max_candidates`, a row can only be compared against a subset of
its rivals, so the matching becomes approximate. The run log carries a `WARNING` naming how many groups hit
the limit. If that appears, the correlation key is usually too coarse or `time_shift` too wide; raising
`max_candidates` is the last resort, since the ranking cost is quadratic in it.

### Which normalization actually changes anything

Each `normalization_type` is applied per dimension (the time gap, then each value field) and the results are
summed; that sum is only ever used to **order** a row's candidates. So a transform that scales every
dimension by the same factor cannot change the outcome:

| value | effect on the winner |
|---|---|
| `none` / `default` | plain magnitude — the baseline |
| `rank` | divides by the candidate count, the **same constant for every dimension and candidate of a row**, so the ordering is identical to `none`. It is a **no-op for match selection** and exists only for parity |
| `z_norm` | per-dimension mean and spread ⇒ different weight per dimension ⇒ **can** change the winner. May go negative, so distances are not necessarily positive |
| `srd` | squares each difference relative to the **width of its tolerance band**, so a narrow-band field outweighs a wide-band one ⇒ **can** change the winner |
| `minmax` | per-dimension global min/max ⇒ could change the winner, which is why rejecting it on this engine is a real restriction, not a cosmetic one |

Worked example from `test/fixture_multi.py` (bands: `amount` 2, `qty` 7). Against an A row, candidate B19
differs by 6 on `qty`, B20 by 4 on `amount`:

- `none`: `6` vs `4` → **B20** wins
- `srd`: `(6/7)² = 0.73` vs `(4/2)² = 4` → **B19** wins

Both engines flip together, which is what verifies the port of the distance formulas.

## What the procedure leaves behind

| Table | Contents |
|---|---|
| `rapo_temp_error_{a,b}_<pid>` | `Loss`, `Discrepancy` and (unless `allow_duplicates`) `Duplicate` rows |
| `rapo_temp_stage_{a,b}_<pid>` | `Match` rows |
| `rapo_temp_verdict_{a,b}_<pid>` | Internal; dropped unless `debug_mode` |

The error and stage tables carry every source column plus `rapo_result_type`, `rapo_discrepancy_id` and
`rapo_discrepancy_description` — the names `save_reconciliation_output_a/b` matches on. Rapo's ordinary
`_save` path copies them into `rapo_resa_<name>` / `rapo_resb_<name>`, and `_finish` drops the temp tables.

`rapo_discrepancy_id` is the counterparty's key. `rapo_discrepancy_description` is `LABEL|signed_value;`
repeated, time first, e.g. `START_TIME|-5;CALL_DURATION|2;`.

## Logging

The procedure cannot write to the run's log file — it may not even run on the host that keeps it. It appends
to **`rapo_engine_log`** instead (`process_id`, `record_number`, `logged`, `log_level`, `message`), in an
autonomous transaction so each line is visible at once without committing the work in flight.

The control process drains that table every two seconds into its own run log
(`logs/controls/<control_id>/<process_id>.log`), deleting the rows it has taken, so the table is a transport
buffer and never a second log. Lines therefore appear in **Show full log** while the run is still going, and
carry the `[engine]` marker on the `MainThread(engine-log)` thread. The drain also runs in a `finally`, so a
run that fails keeps the context that led to the failure.

What is logged: the window and sources, the rule and option summary, the **generated fetch SQL for both
sides**, a progress line every 50 000 source rows, the `create table` for each issue and stage table with its
row counts, and, on failure, the Oracle error and backtrace.

`report_progress` publishes `fetched_number_a/b` as it goes but deliberately leaves `rapo_log.updated`
alone — rapo stamps that column with the **application** clock, which need not be the database clock (on this
Dev instance they are two hours apart), and a `sysdate` there would drag the column backwards and hide a live
run from the event watcher. The draining process writes the counts back through rapo's own metric path, which
moves `updated` correctly and is what tells the UI a long run is still alive.

Rows left behind by a hard-killed process are the only way the table can grow; a rerun of the same
`process_id` clears its own rows first.

## Errors

The procedure re-raises everything, so rapo's `_escape()` records the traceback in `rapo_log.text_error` and
marks the run `E`. Named failures use `raise_application_error`:

| Code | Cause |
|---|---|
| `-20001` | `process_id`, `control_name`, `date_from` or `date_to` missing |
| `-20002` | `normalization_type` unsupported (`minmax`) or unknown |
| `-20003` | `correlation_config` names no field |
| `-20004` | A datasource does not exist |
| `-20005` | `max_candidates` is less than 1 |

## Deployment note

`RAPO_USAGE_RULE` is declared `AUTHID CURRENT_USER`. It creates and drops tables, and privileges held through
a role are disabled inside a definer's-rights unit, so a definer's-rights version raises `ORA-01031` wherever
`CREATE TABLE` comes from a role.
