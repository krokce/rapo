"""Contains the discrepancy analysis: what makes a run's discrepancies special.

The discrepancies of one side of a run are contrasted with its normal records,
the side's fetched records less the discrepancies. Nothing joins them: every
attribute is binned the same way on both datasets and counted by Oracle, so
the normal count of a bin is the fetched count less the discrepancy count
(`analyze`). It runs in two stages, so a large datasource answers at once:

Quick look, on a sample of `quick_rows` records of each dataset (`_quick`):
1. Profile the fetched records (`_profile`): non-null and distinct counts,
   min/max, deciles, digit-only share and prefix distinct counts per column.
2. Plan the features (`_plan`): the bins of each column (values, deciles,
   hour/weekday/timeline of a date (whole hours, days or months of the
   run's window: `timebins`), prefixes and length of an identifier).
3. Count each feature's bins in both datasets (`_count`): one scan each, the
   features unpivoted into (feature, code, count) rows.
4. Score (`_score`): per feature the uncertainty coefficient (mutual
   information over the entropy of the discrepancy flag), per bin the lift,
   coverage and a two-proportion z.
5. Combine the strongest attributes in pairs (`_pair_features`,
   `_score_pairs`), pick the findings the page leads with (`_findings`) and
   read the differences of REC value discrepancies (`_magnitude`). The
   report is published as preliminary.

Refine: the same bins and pairs counted together in one scan of each dataset
(`_refine`), whole up to `exact_rows` records, else on a sample of about that
many, with a parallel hint; it replaces the preliminary report.

A sample is a `SAMPLE BLOCK` of the datasource table (`_block`), reading only
part of it; where Oracle refuses one (a join view, a database link) the quick
look takes the first records and refine a Bernoulli sample (`_sampled`).
Counts of a sample are scaled to the run's logged totals.
"""

import datetime as dt
import json
import math
import re

import numpy as np
import sqlalchemy as sa

from ..database import db
from ..core import sqlcheck
from ..core.control import Control

from . import datasets
from . import timebins
from .frame import NUMERIC, DATETIME, column_kind


RESULT_TYPES = ('Loss', 'Discrepancy', 'Duplicate')
PREFIXES = (3, 5, 6, 8)
TEXT_PREFIXES = (2, 4, 6)
RAW_DISTINCT = 30          # numbers with up to this many values are binned by value
FEATURE_DISTINCT = 1000    # a feature with more values is not counted
SHOWN_BINS = 30            # the rest of a value feature is Other
UNIQUE_SHARE = 0.9         # a feature this unique has nothing to tell
DIGIT_SHARE = 0.95
# The timeline codes of the records before and after its buckets.
BEFORE = '0000'
AFTER = '9999'
PROFILE_COLUMNS = 40       # columns profiled per statement (Oracle's 1000 items)
COUNT_FEATURES = 200       # features counted per statement
MIN_SUPPORT = 10
MIN_COVERAGE = 0.01
MIN_LIFT = 2.0
MIN_Z = 4.0
UNDER_SHARE = 0.05
RELATED = 0.02             # uncertainty coefficient of a driver
UNRELATED = 0.005          # below it an attribute is "not related"
DRIVERS = 3
STEPS = 6
SEED = 42                  # the same blocks for every statement of a stage
MIN_BLOCK_SHARE = 0.2      # a block sample this much smaller is replaced
SAMPLE_METHODS = ('none', 'block', 'row', 'first', 'bernoulli')
# A block sample of clustered data (records loaded in time or key order) varies
# far more than a random one: its z is taken as if this many times fewer
# records were read.
BLOCK_EFFECT = 25
COMBINED = 6               # attributes combined in pairs
GROUPS = 5                 # groups of an attribute in a combination
COMBINATIONS = 8
INTERACTION = 1.5          # a pair's rate over the better of its parts
FINDING_COMBINATIONS = 2
DESCRIPTIONS = 2000
DRIFT = 0.01
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
ORDERED = ('decile', 'hour', 'weekday', 'timeline', 'length')
NUMBER_TEXT = "'TM9', 'NLS_NUMERIC_CHARACTERS=''.,'''"
# Types that can not be grouped (LOBs come back from a parse as LONG).
UNGROUPED = ('LONG', 'LONG_RAW', 'RAW', 'BLOB', 'CLOB', 'NCLOB', 'BFILE',
             'OBJECT', 'ROWID', 'UROWID', 'INTERVAL_DS', 'INTERVAL_YM',
             'CURSOR', 'JSON', 'VECTOR')


class ExplainError(ValueError):
    """The run's discrepancies can not be analysed."""


def analyze(process_id, side, result_type=None, quick_rows=100000,
            exact_rows=1000000, parallel=4, progress=None, publish=None):
    """Explain the discrepancies of one side of a run.

    Parameters
    ----------
    process_id : int
    side : str
        `a` or `b`.
    result_type : str, optional
        REC only: one of `RESULT_TYPES`; all of them by default.
    quick_rows : int
        Records of each dataset the quick look reads.
    exact_rows : int
        Records counted whole by refine; a larger dataset is sampled.
    parallel : int
        Degree of the parallel hint of the refine scans; 0 for none.
    progress : callable, optional
        progress(step, done, total) as the analysis goes.
    publish : callable, optional
        publish(report) with the preliminary report of the quick look.

    Returns
    -------
    report : dict
        The refined report.
    """
    step = progress or (lambda *args: None)
    step('Reading the run', 0, STEPS)
    source = _source(process_id, side, result_type)
    meta = source['meta']
    if not source['columns']:
        raise ExplainError(
            'No column of the discrepancies can be traced back to the '
            f"fetched records of side {meta['side']} (output columns that "
            'coalesce both sides or are of a type that can not be grouped '
            'are left out)')
    quick = _quick(source, quick_rows, step)
    if publish:
        publish(quick)
    return _refine(source, quick, exact_rows, parallel, step)


def _quick(source, quick_rows, step):
    """Get the preliminary report from a sample of each dataset."""
    meta = dict(source['meta'])
    step('Quick look: sampling', 1, STEPS)
    fetched = _quick_sample(source['fetched_sql'], source['fetched_from'],
                            meta['fetched_logged'], quick_rows)
    window = _window(meta)
    profile = _profile(fetched['sql'], source['columns'], window)
    if (fetched['method'] == 'block' and profile['rows']
            < MIN_BLOCK_SHARE * min(quick_rows, meta['fetched_logged'] or 0)):
        fetched = _first(source['fetched_sql'], quick_rows)
        profile = _profile(fetched['sql'], source['columns'], window)
    found = _quick_sample(source['result_sql'], source['result_from'],
                          meta['disc_logged'], quick_rows)
    _widen_dates(profile, found['sql'], source['columns'])
    features, excluded = _plan(source['columns'], profile, window)
    meta['excluded'] = source['excluded'] + excluded

    step('Quick look: counting', 2, STEPS)
    fetched, fetched_raw = _counted(
        fetched, features, 'fetched', meta['fetched_logged'], quick_rows,
        lambda: _first(source['fetched_sql'], quick_rows))
    found, found_raw = _counted(
        found, features, 'result', meta['disc_logged'], quick_rows,
        lambda: _first(source['result_sql'], quick_rows))
    fetched['factor'] = _factor(fetched_raw[1], meta['fetched_logged'],
                                fetched)
    found['factor'] = _factor(found_raw[1], meta['disc_logged'], found)
    meta.update({'stage': 'quick', 'sample_method': fetched['method'],
                 'result_sample_method': found['method'],
                 'sample_rows': fetched_raw[1],
                 'weights': [_weight(found), _weight(fetched)]})
    fetched_counts = _scaled(fetched_raw, fetched['factor'])
    found_counts = _scaled(found_raw, found['factor'])
    report = _score(meta, features, fetched_counts, found_counts)
    report['type_split'] = source['type_split']

    step('Quick look: combining', 3, STEPS)
    pairs = _pair_features(features, report)
    if pairs:
        report['combinations'] = _score_pairs(
            pairs, report,
            _scaled(_count(fetched['sql'], pairs, 'fetched'),
                    fetched['factor'])[0],
            _scaled(_count(found['sql'], pairs, 'result'),
                    found['factor'])[0])
    else:
        report['combinations'] = []
    report['findings'] = _findings(report)
    report['unrelated'] = _unrelated(report)
    report['magnitude'] = _magnitude(source)
    report['_features'] = features
    report['_pairs'] = pairs
    return report


def _refine(source, quick, exact_rows, parallel, step):
    """Get the final report: the quick look's bins and pairs counted in one
    scan of each dataset, whole up to `exact_rows` records.
    """
    meta = dict(source['meta'])
    meta['excluded'] = quick['meta']['excluded']
    features = _refined_features(quick['_features'], quick)
    pairs = quick['_pairs']
    hint = f'/*+ PARALLEL({int(parallel)}) */ ' if parallel else ''
    fetched = _refine_sample(source['fetched_sql'], source['fetched_from'],
                             meta['fetched_logged'], exact_rows)
    found = _refine_sample(source['result_sql'], source['result_from'],
                           meta['disc_logged'], exact_rows)
    share = fetched.get('share')
    what = ('all records' if fetched['method'] == 'none'
            else f'a {_pct(share)} sample' if share else 'a sample')
    step(f'Refining ({what}): fetched records', 4, STEPS)
    fetched, fetched_raw = _counted(
        fetched, features + pairs, 'fetched', meta['fetched_logged'],
        exact_rows, lambda: _bernoulli(source['fetched_sql'],
                                       meta['fetched_logged'], exact_rows),
        hint)
    step(f'Refining ({what}): discrepancies', 5, STEPS)
    found, found_raw = _counted(
        found, features + pairs, 'result', meta['disc_logged'], exact_rows,
        lambda: _bernoulli(source['result_sql'], meta['disc_logged'],
                           exact_rows), hint)
    fetched['factor'] = _factor(fetched_raw[1], meta['fetched_logged'],
                                fetched)
    found['factor'] = _factor(found_raw[1], meta['disc_logged'], found)
    fetched_counts = _scaled(fetched_raw, fetched['factor'])
    found_counts = _scaled(found_raw, found['factor'])
    meta.update({'stage': 'final', 'sample_method': fetched['method'],
                 'result_sample_method': found['method'],
                 'sample': fetched.get('share')
                 if fetched['method'] != 'none' else None,
                 'weights': [_weight(found), _weight(fetched)]})
    report = _score(meta, features, fetched_counts, found_counts)
    report['type_split'] = source['type_split']
    report['combinations'] = (_score_pairs(pairs, report, fetched_counts[0],
                                           found_counts[0]) if pairs else [])
    report['findings'] = _findings(report)
    report['unrelated'] = _unrelated(report)
    report['magnitude'] = quick['magnitude']
    step('Done', STEPS, STEPS)
    return report


def _refined_features(features, quick):
    """Get the features refine counts: of a column's prefixes the best
    scored one and the next shorter one, and every other feature.
    """
    scores = {item['id']: item['score'] for item in quick['attributes']}
    kept = set()
    by_column = {}
    for feature in features:
        if feature['kind'] == 'prefix':
            by_column.setdefault(feature['column'], []).append(feature)
    for prefixes in by_column.values():
        prefixes.sort(key=lambda feature: feature['digits'])
        best = max(prefixes, key=lambda feature: scores.get(feature['id'], 0))
        index = prefixes.index(best)
        kept.update(feature['id'] for feature in prefixes[max(index - 1, 0):
                                                          index + 1])
    return [feature for feature in features
            if feature['kind'] != 'prefix' or feature['id'] in kept]


def _source(process_id, side, result_type):
    """Get the two datasets of a side and the columns they share."""
    if side not in ('a', 'b'):
        raise ExplainError(f'Unknown side {side}')
    try:
        control = Control(process_id=process_id)
    except ValueError as error:
        raise ExplainError(str(error))
    if control.is_report:
        raise ExplainError('A report has no discrepancies to explain')
    if side == 'b' and control.is_analysis:
        raise ExplainError('An analysis has no side B')
    if result_type and not control.is_reconciliation:
        raise ExplainError('Only a reconciliation has result types')
    if result_type and result_type not in RESULT_TYPES:
        raise ExplainError(f'Unknown result type {result_type}')

    dataset = 'result_a' if not control.is_reconciliation else f'result_{side}'
    try:
        result_sql, table_name = datasets._result_select(control, side)
        select, source_name = datasets._fetched_select(control, side)
    except datasets.DatasetError as error:
        raise ExplainError(str(error))
    fetched_sql = db.compile(select).string
    type_split = None
    if control.is_reconciliation:
        rows = db.execute(sa.text(
            f'select rapo_result_type t, count(*) n from ({result_sql}) '
            'group by rapo_result_type order by 2 desc'), as_table=True)
        type_split = [{'type': row['t'], 'count': int(row['n'])}
                      for row in rows]
        if result_type:
            result_sql += f" and RAPO_RESULT_TYPE = '{result_type}'"

    if type_split is not None:
        disc_logged = sum(item['count'] for item in type_split
                          if not result_type or item['type'] == result_type)
    else:
        disc_logged = datasets.count(result_sql)
    alias = 's' if control.is_analysis else side
    found_columns = _describe(result_sql)
    fetched_columns = _describe(fetched_sql)
    columns = _shared_columns(control, side, found_columns, fetched_columns)
    excluded = [{'column': column['name'].upper(),
                 'reason': f"Type {column['type']} can not be grouped"}
                for column in columns if column['type'] in UNGROUPED]
    columns = [column for column in columns
               if column['type'] not in UNGROUPED]

    run = control.result
    if control.is_analysis:
        logged = control.fetched_number
    else:
        logged = (control.fetched_number_a if side == 'a'
                  else control.fetched_number_b)
    meta = {
        'process_id': control.process_id,
        'control_id': control.id,
        'control_name': control.name,
        'control_type': control.type,
        'control_engine': control.engine,
        'status': control.status,
        'date_from': control.date_from,
        'date_to': control.date_to,
        'start_date': control.start_date,
        'end_date': control.end_date,
        'side': side.upper(),
        'dataset': dataset,
        'fetched_dataset': f'fetched_{side}',
        'result_type': result_type,
        'table_name': table_name.upper(),
        'source_name': (source_name or '').upper() or None,
        'fetched_logged': logged,
        'disc_logged': disc_logged,
        'stale': datasets._changed_since(control, run),
        'datasets': _sides(control),
    }
    return {'meta': meta, 'columns': columns, 'excluded': excluded,
            'result_sql': result_sql, 'fetched_sql': fetched_sql,
            'fetched_from': _from_pattern(fetched_sql, alias),
            'result_from': _from_pattern(result_sql, None),
            'type_split': type_split}


def _describe(sql):
    """Get the columns of a select with their kinds and Oracle types."""
    check = sqlcheck.parse(f'select * from ({sql}) q where 1 = 0')
    if not check['valid']:
        raise ExplainError(f"The dataset can not be parsed: {check['error']}")
    return [{'name': column['name'], 'type': column['type'],
             'kind': column_kind(column['type'])}
            for column in check['columns']]


def _sides(control):
    """Get the sides the page can switch between, with their counts."""
    if control.is_reconciliation:
        return [{'side': 'A', 'count': control.error_number_a},
                {'side': 'B', 'count': control.error_number_b}]
    if control.is_comparison:
        return [{'side': 'A', 'count': control.error_number},
                {'side': 'B', 'count': control.error_number}]
    return [{'side': 'A', 'count': control.error_number}]


def _shared_columns(control, side, found_columns, fetched_columns):
    """Pair the discrepancy columns with the fetched columns they hold.

    A result column holds a fetched column of the same name, or the one its
    output column configuration names for this side. A CMP without output
    columns labels them `a_<col>`/`b_<col>`; a coalesce of both sides and the
    RAPO_ metadata are left out.
    """
    fetched = {column['name'].lower(): column for column in fetched_columns}
    if control.is_reconciliation:
        config = (control.output_columns_a if side == 'a'
                  else control.output_columns_b)
    else:
        config = control.output_columns
    origin = {}
    for item in config or []:
        name = (item.get('column') or item.get(f'column_{side}') or '').lower()
        other = 'b' if side == 'a' else 'a'
        if item.get(f'column_{side}') and not item.get(f'column_{other}'):
            origin[name] = item[f'column_{side}'].lower()
        elif item.get(f'column_{other}'):
            origin[name] = None
    result = []
    for column in found_columns:
        name = column['name'].lower()
        if name.startswith('rapo_'):
            continue
        if name in origin:
            source = origin[name]
        elif control.is_comparison and not config:
            prefix = f'{side}_'
            source = name[len(prefix):] if name.startswith(prefix) else None
        else:
            source = name
        if source is None or source not in fetched:
            continue
        kind = fetched[source]['kind']
        if kind != column['kind']:
            continue
        result.append({'name': column['name'], 'source': fetched[source]['name'],
                       'kind': kind, 'type': fetched[source]['type']})
    return result


def _quoted(name):
    return 'q."' + name.replace('"', '') + '"'


def _sampled(sql, sample):
    """Get a Bernoulli sample of a select's records.

    The random value is a column of an unmerged view: a `dbms_random`
    predicate merged into the select is evaluated unreliably by Oracle (none
    or all of the records), and an unpivot would draw it once per feature.
    """
    if sample >= 1:
        return sql
    return ('select * from (select /*+ no_merge */ s.*, dbms_random.value '
            f'rapo_sample from ({sql}) s) where rapo_sample < {sample!r}')


def _from_pattern(sql, alias):
    """Get the span of the table of a select's first FROM where a sample
    clause goes: before the alias, or before the WHERE of an unaliased one.
    """
    name = r'(?:"[^"]+"|[A-Za-z_][\w$#]*)(?:\.(?:"[^"]+"|[A-Za-z_][\w$#]*))?'
    follow = rf'\s+{alias}\b' if alias else r'\s+where\b'
    match = re.search(rf'\bfrom\s+({name})(?={follow})', sql, re.I)
    if not match or '@' in match.group(1):
        return None
    return match.span(1)


def _block(sql, span, share, block=True):
    """Get a select reading a sample of its table, or None when Oracle refuses
    one (a join view, a database link). A block sample reads only that share
    of the table's blocks; a row sample (`block=False`) reads every block but
    keeps that share of the records, at random.
    """
    if not span or share >= 1:
        return None
    percent = min(max(share * 100, 0.000001), 99.99)
    start, end = span
    clause = 'sample block' if block else 'sample'
    statement = (f'{sql[:end]} {clause} ({percent:.6f}) seed ({SEED})'
                 f'{sql[end:]}')
    check = sqlcheck.parse(f'select * from ({statement}) q where 1 = 0')
    return statement if check['valid'] else None


def _first(sql, rows):
    return {'sql': f'select * from ({sql}) where rownum <= {int(rows)}',
            'method': 'first'}


def _quick_sample(sql, span, logged, rows):
    """Get the quick look's select of a dataset: whole when small, else a
    block sample of about `rows` records, else its first `rows` records.
    """
    if logged is not None and logged <= rows:
        return {'sql': sql, 'method': 'none'}
    if logged:
        statement = _block(sql, span, rows / logged)
        if statement:
            return {'sql': statement, 'method': 'block',
                    'share': rows / logged}
    return _first(sql, rows)


def _refine_sample(sql, span, logged, rows):
    """Get refine's select of a dataset: whole up to `rows` records, else a
    row sample of about `rows` (unbiased, unlike a block sample of clustered
    data; the scan is whole but the bins are computed for the sample only),
    else a Bernoulli sample.
    """
    if not logged or logged <= rows:
        return {'sql': sql, 'method': 'none'}
    share = rows / logged
    statement = _block(sql, span, share, block=False)
    if statement:
        return {'sql': statement, 'method': 'row', 'share': share}
    return {'sql': _sampled(sql, share), 'method': 'bernoulli',
            'share': share}


def _bernoulli(sql, logged, rows):
    share = min(1.0, rows / logged) if logged else 1.0
    return {'sql': _sampled(sql, share), 'method': 'bernoulli',
            'share': share}


def _counted(sample, features, which, logged, rows, fallback, hint=''):
    """Count a sample's bins; a block sample far smaller than expected (a
    small or clustered table) is replaced by the `fallback` sample.
    """
    counted = _count(sample['sql'], features, which, hint)
    expected = min(rows, logged or 0)
    if (sample['method'] in ('block', 'row')
            and counted[1] < MIN_BLOCK_SHARE * expected):
        sample = fallback()
        counted = _count(sample['sql'], features, which, hint)
    return sample, counted


def _factor(total, logged, sample):
    """Get the factor scaling a sample's counts to its dataset: 1/share of a
    Bernoulli sample, the logged total over the counted one of a block or
    first-records sample, 1 for a whole count.
    """
    if sample['method'] == 'none' or not total:
        return 1.0
    if sample['method'] in ('bernoulli', 'row'):
        return 1 / sample['share']
    return logged / total if logged else 1.0


def _weight(sample):
    """Get the weight z is computed with: the scale factor, times
    `BLOCK_EFFECT` for a block or first-records sample (clustered)."""
    effect = BLOCK_EFFECT if sample['method'] in ('block', 'first') else 1
    return sample['factor'] * effect


def _scaled(counted, factor):
    counts, total = counted
    if factor == 1:
        return counts, total
    return ({key: {code: value * factor for code, value in bins.items()}
             for key, bins in counts.items()}, total * factor)


def _widen_dates(profile, sql, columns):
    """Widen the fetched sample's date ranges to the discrepancies', so the
    timeline covers both (a sample may miss the first and last records).
    """
    dates = [column for column in columns if column['kind'] == DATETIME]
    if not dates:
        return
    items = ', '.join(f'min(cast({_quoted(column["name"])} as date)) mn{i}, '
                      f'max(cast({_quoted(column["name"])} as date)) mx{i}'
                      for i, column in enumerate(dates))
    row = db.execute(sa.text(f'select {items} from ({sql}) q'), as_dict=True)
    row = {key.lower(): value for key, value in (row or {}).items()}
    for i, column in enumerate(dates):
        facts = profile['columns'][column['name']]
        for key, pick in (('mn', min), ('mx', max)):
            values = [value for value in (facts.get(key), row.get(f'{key}{i}'))
                      if value is not None]
            facts[key] = pick(values) if values else None


def _window(meta):
    """Get the run's window (date_from, date_to), or None."""
    start, end = meta.get('date_from'), meta.get('date_to')
    if isinstance(start, dt.datetime) and isinstance(end, dt.datetime) \
            and end > start:
        return start, end
    return None


def _date_literal(moment):
    return (f"to_date('{moment:%Y-%m-%d %H:%M:%S}', "
            "'YYYY-MM-DD HH24:MI:SS')")


def _profile(sql, columns, window=None):
    """Get the facts the bins are chosen from, per fetched column; a date
    column also counts its records in the run's `window` (`iw`)."""
    result = {'rows': 0, 'columns': {}}
    for start in range(0, len(columns), PROFILE_COLUMNS):
        chunk = columns[start:start + PROFILE_COLUMNS]
        items = ['count(*) n']
        for i, column in enumerate(chunk):
            name = _quoted(column['source'])
            items += [f'count({name}) nn{i}',
                      f'approx_count_distinct({name}) d{i}']
            if column['kind'] == NUMERIC:
                items += [f'min({name}) mn{i}', f'max({name}) mx{i}']
                items += [f'approx_percentile({q / 10}) within group '
                          f'(order by {name}) p{i}_{q}' for q in range(1, 10)]
                text = f'to_char(trunc(abs({name})), {NUMBER_TEXT})'
                items += [f"sum(case when {name} = trunc({name}) then 1 end) "
                          f'int{i}', f'max(length({text})) ml{i}']
                items += [f'approx_count_distinct(substr({text}, 1, {k})) '
                          f'x{i}_{k}' for k in PREFIXES]
            elif column['kind'] == DATETIME:
                items += [f'min(cast({name} as date)) mn{i}',
                          f'max(cast({name} as date)) mx{i}']
                if window:
                    items.append(
                        f'sum(case when {name} >= {_date_literal(window[0])} '
                        f'and {name} <= {_date_literal(window[1])} then 1 '
                        f'end) iw{i}')
            else:
                items += [f"sum(case when ltrim({name}, '0123456789') is null "
                          f'then 1 end) dig{i}',
                          f'min(length({name})) ln{i}',
                          f'max(length({name})) ml{i}',
                          f'approx_count_distinct(length({name})) dl{i}']
                items += [f'approx_count_distinct(substr({name}, 1, {k})) '
                          f'x{i}_{k}' for k in sorted(set(PREFIXES
                                                          + TEXT_PREFIXES))]
        statement = (f'select {", ".join(items)} '
                     f'from ({sql}) q')
        row = db.execute(sa.text(statement), as_dict=True)
        row = {key.lower(): value for key, value in row.items()}
        result['rows'] = int(row['n'] or 0)
        for i, column in enumerate(chunk):
            facts = {key[:-len(str(i))] if key.endswith(str(i)) else key: value
                     for key, value in row.items()
                     if re.fullmatch(rf'[a-z]+{i}', key)}
            facts['deciles'] = [row.get(f'p{i}_{q}') for q in range(1, 10)]
            facts['prefixes'] = {k: row.get(f'x{i}_{k}')
                                 for k in sorted(set(PREFIXES + TEXT_PREFIXES))
                                 if row.get(f'x{i}_{k}') is not None}
            result['columns'][column['name']] = facts
    return result


def _plan(columns, profile, window=None):
    """Choose the features of every column, and say why others are left out.

    A feature is an expression giving a bin code (text) of a column, the same
    over the fetched and the discrepancy column, with a label and a filter for
    each code.
    """
    rows = profile['rows']
    features = []
    excluded = []
    for column in columns:
        facts = profile['columns'][column['name']]
        present = int(facts.get('nn') or 0)
        distinct = int(facts.get('d') or 0)
        upper = column['name'].upper()
        if rows == 0:
            excluded.append({'column': upper, 'reason': 'No fetched records'})
            continue
        if present == 0:
            excluded.append({'column': upper, 'reason': 'Always empty'})
            continue
        if distinct <= 1 and present == rows:
            excluded.append({'column': upper, 'reason': 'Constant'})
            continue
        kind = column['kind']
        planned = []
        if kind == NUMERIC:
            planned = _numeric_features(column, facts, present, distinct)
        elif kind == DATETIME:
            planned = _date_features(column, facts, window)
        else:
            planned = _text_features(column, facts, present, distinct)
        planned = [feature for feature in planned if feature]
        if not planned:
            excluded.append({'column': upper, 'reason': _unique_reason(facts)})
            continue
        features.extend(planned)
    for i, feature in enumerate(features):
        feature['id'] = f'f{i}'
    return features, excluded


def _unique_reason(facts):
    return ('Unique per record (an identifier); no prefix or length of it '
            'groups the records')


def _feature(column, kind, name, label, expression, ordered=False, **extra):
    """Get a feature whose expression is built per dataset from a column."""
    return {'column': column['name'], 'source': column['source'],
            'column_kind': column['kind'], 'kind': kind, 'name': name,
            'label': label, 'expression': expression, 'ordered': ordered,
            **extra}


def _usable(distinct, present):
    """Whether a feature with this many values can group the records."""
    return (distinct is not None and 1 < distinct <= FEATURE_DISTINCT
            and distinct < UNIQUE_SHARE * present)


def _numeric_features(column, facts, present, distinct):
    features = []
    integral = int(facts.get('int') or 0) == present
    if distinct <= RAW_DISTINCT:
        features.append(_feature(column, 'value', 'value', 'Value',
                                 lambda name: f'to_char({name}, '
                                 f'{NUMBER_TEXT})'))
        return features
    edges = []
    for value in facts['deciles']:
        if value is not None and (not edges or value > edges[-1]):
            edges.append(value)
    if facts.get('mn') is not None and edges and edges[0] <= facts['mn']:
        edges = edges[1:]
    if edges:
        features.append(_feature(
            column, 'decile', 'range', 'Range', _decile_expression(edges),
            ordered=True, edges=[_plain(edge) for edge in edges],
            low=_plain(facts.get('mn')), high=_plain(facts.get('mx'))))
    if integral and distinct >= UNIQUE_SHARE * present:
        length = int(facts.get('ml') or 0)
        for k in PREFIXES:
            if k < length and _usable(facts['prefixes'].get(k), present):
                features.append(_feature(
                    column, 'prefix', f'prefix{k}', f'First {k} digits',
                    lambda name, k=k: f'substr(to_char(trunc(abs({name})), '
                    f'{NUMBER_TEXT}), 1, {k})', digits=k))
    return features


def _decile_expression(edges):
    def expression(name):
        branches = ' '.join(f'when {name} < {_number(edge)} then '
                            f"'{i:02d}'" for i, edge in enumerate(edges))
        return f"case {branches} when {name} is not null then " \
               f"'{len(edges):02d}' end"
    return expression


def _date_features(column, facts, window=None):
    """Get the features of a date column: hour of day, weekday (unless the
    values are of one day) and the timeline, whole hours, days or months
    (`timebins`) of the run's window when most values lie in it, else of the
    values' range, the records before and after it as codes of their own;
    none when it is one day of hours, which the hour of day already is.
    """
    low, high = facts.get('mn'), facts.get('mx')
    present = int(facts.get('nn') or 0)
    start, end, inside = low, high, False
    if window and present \
            and int(facts.get('iw') or 0) >= timebins.WINDOW_SHARE * present:
        start, end, inside = window[0], window[1], True
    features = [
        _feature(column, 'hour', 'hour', 'Hour of day',
                 lambda name: f"to_char({name}, 'HH24')", ordered=True),
    ]
    one_day = bool(start and end) and timebins.same_day(start, end)
    if not one_day:
        features.append(_feature(
            column, 'weekday', 'weekday', 'Weekday',
            lambda name: f"to_char(trunc({name}) - trunc({name}, 'IW'))",
            ordered=True))
    if start and end and end > start:
        unit, edges = timebins.edges(start, end)
        if not (unit == 'hour' and one_day):
            features.append(_feature(
                column, 'timeline', 'timeline', 'Time',
                lambda name: _timeline_expression(name, unit, edges),
                ordered=True, unit=unit, edges=edges, window=inside))
    return features


def _timeline_expression(name, unit, edges):
    """Get the timeline code of a date: its bucket's 1-based number in four
    digits, `BEFORE` or `AFTER`. Counted in whole days, hours and months, so
    no fraction of a day rounds a record into the next hour."""
    moment = f'cast({name} as date)'
    first, last = _date_literal(edges[0]), _date_literal(edges[-1])
    if unit == 'hour':
        index = (f'(trunc({moment}) - trunc({first})) * 24 + '
                 f"to_number(to_char({moment}, 'HH24')) - {edges[0].hour}")
    elif unit == 'day':
        index = f'trunc({moment}) - {first}'
    elif unit == 'month':
        index = f"months_between(trunc({moment}, 'MM'), {first})"
    else:
        index = f'extract(year from {moment}) - {edges[0].year}'
    return (f"case when {moment} < {first} then '{BEFORE}' "
            f"when {moment} >= {last} then '{AFTER}' "
            f"else to_char({index} + 1, 'FM0000') end")


def _text_features(column, facts, present, distinct):
    if distinct <= FEATURE_DISTINCT and distinct < UNIQUE_SHARE * present:
        return [_feature(column, 'value', 'value', 'Value',
                         lambda name: f'substr({name}, 1, 200)')]
    features = []
    digits = int(facts.get('dig') or 0) >= DIGIT_SHARE * present
    length = int(facts.get('ml') or 0)
    for k in PREFIXES if digits else TEXT_PREFIXES:
        if k < length and _usable(facts['prefixes'].get(k), present):
            features.append(_feature(
                column, 'prefix', f'prefix{k}',
                f'First {k} digits' if digits else f'First {k} characters',
                lambda name, k=k: f'substr({name}, 1, {k})', digits=k))
    if facts.get('dl') and int(facts['dl']) > 1:
        features.append(_feature(
            column, 'length', 'length', 'Length',
            lambda name: f"to_char(length({name}), 'FM0000')", ordered=True))
    return features


def _count(sql, features, which, hint=''):
    """Count every feature's bins in one dataset.

    Returns
    -------
    counts : dict
        {feature id: {code: count}}; NULL is code None.
    total : int
        The records counted.
    """
    counts = {feature['id']: {} for feature in features}
    name_of = 'source' if which == 'fetched' else 'column'
    for start in range(0, len(features), COUNT_FEATURES):
        chunk = features[start:start + COUNT_FEATURES]
        items = [f"cast({_render(feature, which, name_of)} "
                 f"as varchar2(200)) {feature['id']}" for feature in chunk]
        aliases = ', '.join(f"{feature['id']} as '{feature['id']}'"
                            for feature in chunk)
        inner = f'select {", ".join(items)} from ({sql}) q'
        statement = (
            f'select {hint}feature, code, count(*) n from '
            f'({inner}) unpivot include nulls (code for feature in '
            f'({aliases})) group by feature, code')
        rows = db.execute(sa.text(statement), as_table=True)
        for row in rows:
            counts[row['feature']][row['code']] = int(row['n'])
    if features:
        total = sum(counts[features[0]['id']].values())
    else:
        total = db.execute(sa.text(f'select count(*) from ({sql})'),
                           as_scalar=True)
    return counts, total


def _render(feature, which, name_of):
    if 'render' in feature:
        return feature['render'](which)
    return feature['expression'](_quoted(feature[name_of]))


def _score(meta, features, fetched, found):
    """Score the features and their bins, normal = fetched − discrepancies."""
    fetched_counts, fetched_total = fetched
    found_counts, found_total = found
    found_total = round(found_total)
    normal_total = max(round(fetched_total) - found_total, 0)
    meta['discrepancies'] = found_total
    meta['normal'] = normal_total
    meta['fetched_total'] = round(fetched_total)
    logged = meta.get('fetched_logged')
    sample = meta.get('sample')
    # Only a whole or a Bernoulli count measures the total (a block or
    # first-records sample is scaled to the logged one); a Bernoulli total is
    # off by chance too: 3 standard deviations allowed.
    noise = (3 * math.sqrt(logged * (1 - sample) / sample)
             if logged and sample else 0)
    measured = meta.get('sample_method') in ('none', 'bernoulli', 'row')
    meta['drift'] = bool(logged and measured
                         and abs(fetched_total - logged)
                         > max(DRIFT * logged, noise))
    meta['sampled'] = (meta.get('sample_method') != 'none'
                       or meta.get('result_sample_method') != 'none')
    meta['clamped'] = []
    report = {'meta': meta, 'attributes': []}
    if not features or found_total == 0:
        return report
    for feature in features:
        bins = _bins(feature, fetched_counts[feature['id']],
                     found_counts[feature['id']], found_total, normal_total,
                     meta)
        disc = np.array([item['disc'] for item in bins], dtype=float)
        norm = np.array([item['normal'] for item in bins], dtype=float)
        attribute = {
            'id': feature['id'],
            'column': feature['column'].upper(),
            'source': feature['source'].upper(),
            'kind': feature['column_kind'],
            'feature': feature['kind'],
            'feature_label': feature['label'],
            'ordered': feature['ordered'],
            'score': _uncertainty(disc, norm),
            'bins': bins,
        }
        attribute['special'] = [item['code'] for item in bins
                                if item['flag'] == 'over']
        attribute['under'] = [item['code'] for item in bins
                              if item['flag'] == 'under']
        attribute['bands'] = _bands(attribute)
        report['attributes'].append(attribute)
    report['attributes'].sort(key=lambda item: -(item['score'] or 0))
    meta['clamped'] = sorted(set(meta['clamped']))
    return report


def _bins(feature, fetched, found, found_total, normal_total, meta):
    """Get a feature's bins: counts, shares, lift, z and the filter of each."""
    codes = set(fetched) | set(found)
    items = []
    for code in codes:
        disc = found.get(code, 0)
        normal = fetched.get(code, 0) - disc
        uncertain = normal < -0.5 and bool(meta.get('sampled'))
        if normal < -0.5 and not uncertain:
            meta['clamped'].append(feature['column'].upper())
        items.append({'code': code, 'disc': round(disc),
                      'normal': max(round(normal), 0)})
        if uncertain:
            items[-1]['uncertain'] = True
    if feature['kind'] in ('value', 'prefix') and len(items) > SHOWN_BINS:
        def weight(item):
            return max(item['disc'] / max(found_total, 1),
                       item['normal'] / max(normal_total, 1))
        items.sort(key=weight, reverse=True)
        kept, rest = items[:SHOWN_BINS - 1], items[SHOWN_BINS - 1:]
        other = {'code': '\x00other', 'disc': sum(i['disc'] for i in rest),
                 'normal': sum(i['normal'] for i in rest),
                 'values': len(rest)}
        items = kept + [other]
    for item in items:
        _measure(item, found_total, normal_total, meta.get('weights'))
        item['label'] = _label(feature, item)
        item['filter'] = _filter(feature, item['code'])
        item['code'] = None if item['code'] is None else str(item['code'])
    items.sort(key=lambda item: _order(feature, item))
    return items


def _measure(item, found_total, normal_total, weights=None):
    """Measure a bin: shares, lift, rate, z and its flag.

    `weights` are the factors the discrepancy and fetched counts were scaled
    by from a sample; z is taken over the records actually read, and a bin
    whose sample held fewer fetched records than discrepancies is
    `uncertain`, never over-represented.
    """
    disc, normal = item['disc'], item['normal']
    disc_share = disc / found_total if found_total else 0
    normal_share = normal / normal_total if normal_total else 0
    item['disc_share'] = disc_share
    item['normal_share'] = normal_share
    item['lift'] = (disc_share / normal_share if normal_share
                    else (None if disc_share == 0 else math.inf))
    item['rate'] = disc / (disc + normal) if disc + normal else None
    disc_weight, normal_weight = weights or (1, 1)
    item['z'] = _z(disc / disc_weight, normal / normal_weight,
                   found_total / disc_weight, normal_total / normal_weight)
    flag = None
    lift = item['lift']
    if item.get('uncertain'):
        pass
    elif (disc >= max(MIN_SUPPORT, MIN_COVERAGE * found_total)
            and lift is not None and lift >= MIN_LIFT
            and (item['z'] is None or item['z'] >= MIN_Z)):
        flag = 'over'
    elif (normal_share >= UNDER_SHARE and lift is not None
          and lift <= 1 / MIN_LIFT and item['z'] is not None
          and item['z'] <= -MIN_Z):
        flag = 'under'
    item['flag'] = flag
    if lift == math.inf:
        item['lift'] = None
        item['only_disc'] = True


def _z(disc, normal, found_total, normal_total):
    """Two-proportion z of the discrepancy rate inside vs outside a bin."""
    inside = disc + normal
    outside = found_total + normal_total - inside
    total = found_total + normal_total
    if inside == 0 or outside == 0 or total == 0:
        return None
    pooled = found_total / total
    if pooled in (0, 1):
        return None
    rate_in = disc / inside
    rate_out = (found_total - disc) / outside
    error = math.sqrt(pooled * (1 - pooled) * (1 / inside + 1 / outside))
    return round((rate_in - rate_out) / error, 2)


def _uncertainty(disc, norm):
    """Get the share of the discrepancy flag's entropy a feature explains.

    Theil's U of the flag given the feature, from its 2×K counts, less the
    Miller–Madow bias of K bins so many sparse bins do not look informative.
    """
    total = disc.sum() + norm.sum()
    if total <= 0 or disc.sum() == 0 or norm.sum() == 0:
        return 0.0
    table = np.vstack([disc, norm]) / total
    flag = table.sum(axis=1)
    bins = table.sum(axis=0)
    expected = np.outer(flag, bins)
    mask = table > 0
    information = float((table[mask]
                         * np.log(table[mask] / expected[mask])).sum())
    occupied = int((bins > 0).sum())
    information -= (occupied - 1) / (2 * total)
    entropy = float(-(flag * np.log(flag)).sum())
    if entropy <= 0:
        return 0.0
    return round(max(information / entropy, 0.0), 4)


def _bands(attribute):
    """Get the runs of adjacent over-represented bins of an ordered feature."""
    if not attribute['ordered'] or not attribute['special']:
        return []
    bands = []
    current = None
    for item in attribute['bins']:
        if item['code'] is None:
            continue
        if item['flag'] == 'over':
            if current is None:
                current = {'bins': []}
                bands.append(current)
            current['bins'].append(item)
        else:
            current = None
    result = []
    for band in bands:
        first, last = band['bins'][0], band['bins'][-1]
        disc = sum(item['disc'] for item in band['bins'])
        normal = sum(item['normal'] for item in band['bins'])
        result.append({
            'codes': [item['code'] for item in band['bins']],
            'label': (first['label'] if first is last
                      else _band_label(first, last)),
            'disc': disc, 'normal': normal,
            'disc_share': sum(i['disc_share'] for i in band['bins']),
            'normal_share': sum(i['normal_share'] for i in band['bins']),
        })
    return result


def _band_label(first, last):
    start = first['label'].split(' – ')[0]
    end = last['label'].split(' – ')[-1]
    return f'{start} – {end}'


def _order(feature, item):
    code = item['code']
    if code is None:
        return (2, '')
    if code == '\x00other':
        return (1, '')
    if feature['ordered']:
        return (0, code)
    return (0, -item['disc'] - item['normal'], code)


def _label(feature, item):
    code = item['code']
    if code is None:
        return 'Empty'
    if code == '\x00other':
        return f"Other ({item['values']} values)"
    kind = feature['kind']
    if kind == 'decile':
        edges = feature['edges']
        index = int(code)
        low = feature['low'] if index == 0 else edges[index - 1]
        high = feature['high'] if index == len(edges) else edges[index]
        return f'{_short(low)} – {_short(high)}'
    if kind == 'hour':
        return f'{int(code):02d}:00 – {int(code):02d}:59'
    if kind == 'weekday':
        return WEEKDAYS[int(code)] if code.isdigit() and int(code) < 7 \
            else code
    if kind == 'timeline':
        edges = feature['edges']
        if code == BEFORE:
            return f'Before {timebins.moment_text(edges[0])}'
        if code == AFTER:
            return f'From {timebins.moment_text(edges[-1])}'
        index = int(code) - 1
        if not 0 <= index < len(edges) - 1:
            return 'Outside the range'
        return timebins.label(edges[index], feature['unit'])
    if kind == 'prefix':
        return f'{code}…'
    if kind == 'length':
        return f'{int(code)} characters'
    return code


def _filter(feature, code):
    """Get a condition selecting a bin's records, over the dataset's columns.

    Written for the analysis page's database filter (`select * from (...) q
    where ...`), for the discrepancies and the fetched records each, since a
    result column can be named apart from its source. None for Other.
    """
    if code == '\x00other':
        return None
    return {'result': _condition(feature, feature['column'], code),
            'fetched': _condition(feature, feature['source'], code)}


def _condition(feature, column, code):
    name = '"' + column.upper().replace('"', '') + '"'
    if code is None:
        if feature['kind'] in ('value', 'decile', 'hour', 'weekday',
                               'timeline'):
            return f'{name} is null'
        return f'{feature["expression"](name)} is null'
    kind = feature['kind']
    if kind == 'value':
        if feature['column_kind'] == NUMERIC:
            return f'{name} = {code}'
        if len(code) >= 200:
            return f"substr({name}, 1, 200) = {_text(code)}"
        return f'{name} = {_text(code)}'
    if kind == 'decile':
        edges = feature['edges']
        index = int(code)
        parts = []
        if index > 0:
            parts.append(f'{name} >= {_number(edges[index - 1])}')
        if index < len(edges):
            parts.append(f'{name} < {_number(edges[index])}')
        return ' and '.join(parts)
    if kind == 'prefix':
        if feature['column_kind'] == NUMERIC:
            return f"to_char(trunc(abs({name}))) like '{code}%'"
        return f"{name} like {_text(code + '%')}"
    if kind == 'hour':
        return f"to_char({name}, 'HH24') = '{code}'"
    if kind == 'weekday':
        return f"trunc({name}) - trunc({name}, 'IW') = {int(code)}"
    if kind == 'length':
        return f'length({name}) = {int(code)}'
    if kind == 'timeline':
        edges = feature['edges']
        if code == BEFORE:
            return f'{name} < {_date_literal(edges[0])}'
        if code == AFTER:
            return f'{name} >= {_date_literal(edges[-1])}'
        index = int(code) - 1
        if not 0 <= index < len(edges) - 1:
            return None
        return (f'{name} >= {_date_literal(edges[index])} and '
                f'{name} < {_date_literal(edges[index + 1])}')
    return None


def _text(value):
    return "'" + str(value).replace("'", "''") + "'"


def _number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _plain(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return int(number) if number.is_integer() else number


def _short(value):
    if value is None:
        return '?'
    if isinstance(value, float):
        return f'{value:,.4g}' if abs(value) < 1e6 else f'{value:,.0f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value)


def _pct(value):
    if value is None:
        return '–'
    value *= 100
    if value >= 10 or value == 0:
        return f'{value:.0f}%'
    if value >= 1:
        return f'{value:.1f}%'
    return f'{value:.2f}%'


def _drivers(report):
    """Get the attributes the story names, a column at most once."""
    drivers = []
    seen = set()
    for attribute in report['attributes']:
        if attribute['column'] in seen:
            continue
        if attribute['score'] >= RELATED and _leading(attribute):
            drivers.append(attribute)
            seen.add(attribute['column'])
        if len(drivers) == DRIVERS:
            break
    return drivers


def _leading(attribute):
    """Get up to 3 bins or bands of an attribute that tell its story.

    The over-represented ones (bands merged), else, for a related attribute
    without one (e.g. most fetched records are discrepancies, so no lift can
    reach `MIN_LIFT`), the bins whose discrepancy share exceeds their normal
    share the most.
    """
    groups = attribute['bands'] or _prefix_group(attribute) or [
        item for item in attribute['bins'] if item['flag'] == 'over']
    if not groups:
        groups = [item for item in attribute['bins']
                  if item['code'] != '\x00other'
                  and item['disc'] >= MIN_SUPPORT and not item.get('uncertain')
                  and item['disc_share'] - item['normal_share'] >= 0.05]
        groups.sort(key=lambda item: item['normal_share'] - item['disc_share'])
        return groups[:2]
    return sorted(groups, key=lambda item: -item['disc_share'])[:3]


def _prefix_group(attribute):
    """Get the over-represented bins of a prefix feature as one group under
    their longest common prefix (`2940181…` for 29401811…, 29401812…), when
    there are several and they share one.
    """
    if attribute['feature'] != 'prefix':
        return []
    bins = [item for item in attribute['bins']
            if item['flag'] == 'over' and item['code'] is not None]
    if len(bins) < 2:
        return []
    common = bins[0]['code']
    for item in bins[1:]:
        while not item['code'].startswith(common):
            common = common[:-1]
    if not common:
        return []
    return [{
        'codes': [item['code'] for item in bins],
        'label': f'{common}…',
        'disc': sum(item['disc'] for item in bins),
        'normal': sum(item['normal'] for item in bins),
        'disc_share': sum(item['disc_share'] for item in bins),
        'normal_share': sum(item['normal_share'] for item in bins),
    }]


def _what(attribute):
    """Get the name of an attribute in a sentence."""
    column = attribute['column']
    if attribute['feature'] in ('value', 'decile'):
        return column
    if attribute['feature'] == 'prefix':
        return f'{column} (prefix)'
    return f"{column} ({attribute['feature_label'].lower()})"


def _phrase(attribute, label):
    """Get a bin of an attribute in a sentence: `MSC = MSC07`, `AMOUNT
    100 – 104`, `EVENT_TIME (hour of day) 02:00 – 04:59`."""
    if attribute['feature'] == 'value':
        return f"{attribute['column']} = {label}"
    return f'{_what(attribute)} {label}'


def _group_filter(attribute, codes):
    """Get the filter of a group of an attribute's bins: any of them."""
    filters = [item['filter'] for item in attribute['bins']
               if item['code'] in codes]
    if not filters or any(item is None or not item['result']
                          or not item['fetched'] for item in filters):
        return None
    if len(filters) == 1:
        return filters[0]
    return {key: '(' + ' or '.join(f'({item[key]})' for item in filters) + ')'
            for key in ('result', 'fetched')}


def _groups(attribute):
    """Get up to `GROUPS` groups of an attribute's bins for combinations.

    Bands, a common prefix and over-represented bins first, then the bins
    holding the most discrepancies; the rest of the bins form no group.
    """
    groups = []
    taken = set()

    def add(codes, label):
        codes = [code for code in codes if code not in taken]
        if not codes or len(groups) == GROUPS:
            return
        taken.update(codes)
        bins = [item for item in attribute['bins'] if item['code'] in codes]
        groups.append({'key': f'g{len(groups)}', 'codes': codes,
                       'label': label,
                       'disc': sum(item['disc'] for item in bins),
                       'normal': sum(item['normal'] for item in bins)})
    for band in attribute['bands']:
        add(band['codes'], band['label'])
    for group in _prefix_group(attribute):
        add(group['codes'], group['label'])
    ranked = sorted((item for item in attribute['bins']
                     if item['code'] != '\x00other'),
                    key=lambda item: (item['flag'] != 'over',
                                      -item['disc_share']))
    for item in ranked:
        if item['disc']:
            add([item['code']], item['label'])
    return groups


def _group_case(feature, attribute, groups, which):
    name = feature['source'] if which == 'fetched' else feature['column']
    expression = feature['expression'](_quoted(name))
    branches = []
    for group in groups:
        present = [code for code in group['codes'] if code is not None]
        parts = []
        if present:
            parts.append(f'{expression} in ('
                         + ', '.join(_text(code) for code in present) + ')')
        if None in group['codes']:
            parts.append(f'{expression} is null')
        branches.append(f"when {' or '.join(parts)} then '{group['key']}'")
    return f"case {' '.join(branches)} else '~' end"


def _pair_features(features, report):
    """Get the pairs of the strongest attributes, counted like features.

    The strongest attribute of up to `COMBINED` columns is reduced to a few
    groups of bins (`_groups`); a pair's code is the two groups' keys.
    """
    meta = report['meta']
    if not meta['discrepancies'] or not meta['normal']:
        return []
    by_id = {feature['id']: feature for feature in features}
    chosen = []
    seen = set()
    for attribute in report['attributes']:
        if attribute['column'] in seen or attribute['score'] < UNRELATED * 2:
            continue
        groups = _groups(attribute)
        if groups:
            chosen.append((attribute, groups))
            seen.add(attribute['column'])
        if len(chosen) == COMBINED:
            break
    if len(chosen) < 2:
        return []
    pairs = []
    for i in range(len(chosen)):
        for j in range(i + 1, len(chosen)):
            first, second = chosen[i], chosen[j]
            pair = {'id': f'p{len(pairs)}', 'first': first, 'second': second}

            def render(which, first=first, second=second):
                return (_group_case(by_id[first[0]['id']], first[0],
                                    first[1], which) + " || '|' || "
                        + _group_case(by_id[second[0]['id']], second[0],
                                      second[1], which))
            pair['render'] = render
            pairs.append(pair)
    return pairs


def _score_pairs(pairs, report, fetched, found):
    """Find pairs of bins of two attributes that together set the
    discrepancies apart more than either alone (depth-2 subgroups).

    A cell is kept when it is over-represented and its discrepancy rate is
    `INTERACTION` times the better of its two groups' (counted again from the
    report's own bins). Ranked by weighted relative accuracy, coverage ×
    (rate − base rate).
    """
    meta = report['meta']
    found_total, normal_total = meta['discrepancies'], meta['normal']
    if not found_total or not normal_total:
        return []
    attributes = {item['id']: item for item in report['attributes']}
    base = found_total / (found_total + normal_total)
    cells = []
    for pair in pairs:
        (first, first_groups), (second, second_groups) = (pair['first'],
                                                          pair['second'])
        first = attributes.get(first['id'], first)
        second = attributes.get(second['id'], second)
        codes = set(fetched[pair['id']]) | set(found[pair['id']])
        for code in codes:
            if not code or '~' in code:
                continue
            key_a, key_b = code.split('|')
            group_a = _regroup(first, next(
                g for g in first_groups if g['key'] == key_a))
            group_b = _regroup(second, next(
                g for g in second_groups if g['key'] == key_b))
            disc = round(found[pair['id']].get(code, 0))
            normal = round(fetched[pair['id']].get(code, 0) - disc)
            if normal < 0 and meta.get('sampled'):
                continue
            item = {'disc': disc, 'normal': max(normal, 0)}
            _measure(item, found_total, normal_total, meta.get('weights'))
            if item['flag'] != 'over':
                continue
            parents = [_rate(group_a), _rate(group_b)]
            if item['rate'] < INTERACTION * max(parents):
                continue
            filters = [_group_filter(first, group_a['codes']),
                       _group_filter(second, group_b['codes'])]
            item.update({
                'attributes': [first['id'], second['id']],
                'parts': [{'attribute': first['id'], 'what': _what(first),
                           'label': group_a['label'],
                           'phrase': _phrase(first, group_a['label']),
                           'codes': group_a['codes'],
                           'lift': _lift(group_a, found_total, normal_total)},
                          {'attribute': second['id'], 'what': _what(second),
                           'label': group_b['label'],
                           'phrase': _phrase(second, group_b['label']),
                           'codes': group_b['codes'],
                           'lift': _lift(group_b, found_total, normal_total)}],
                'wracc': round((disc + normal) / (found_total + normal_total)
                               * (item['rate'] - base), 6),
                'filter': None if None in filters else {
                    key: f'({filters[0][key]}) and ({filters[1][key]})'
                    for key in ('result', 'fetched')},
            })
            cells.append(item)
    cells.sort(key=lambda item: -item['wracc'])
    result = []
    per_pair = {}
    for item in cells:
        key = tuple(item['attributes'])
        if per_pair.get(key, 0) >= 2:
            continue
        per_pair[key] = per_pair.get(key, 0) + 1
        item['id'] = f'c{len(result)}'
        result.append(item)
        if len(result) == COMBINATIONS:
            break
    return result


def _regroup(attribute, group):
    """Get a group's counts from an attribute's (refined) bins."""
    bins = [item for item in attribute['bins'] if item['code'] in group['codes']]
    if not bins:
        return group
    return {**group, 'disc': sum(item['disc'] for item in bins),
            'normal': sum(item['normal'] for item in bins)}


def _rate(group):
    total = group['disc'] + group['normal']
    return group['disc'] / total if total else 0


def _lift(group, found_total, normal_total):
    disc_share = group['disc'] / found_total if found_total else 0
    normal_share = group['normal'] / normal_total if normal_total else 0
    return disc_share / normal_share if normal_share else None


def _findings(report):
    """Get the findings the page leads with: the leading group of each
    driver, then the strongest combinations.

    Each is {id, kind (`driver`, `time` or `combination`), attribute, column,
    what, label, phrase, codes, filter, disc, normal, disc_share,
    normal_share, lift, rate}, a combination also with its two `parts`.
    """
    meta = report['meta']
    found_total, normal_total = meta['discrepancies'], meta['normal']
    findings = []
    for attribute in _drivers(report):
        group = _leading(attribute)[0]
        codes = group.get('codes') or [group['code']]
        findings.append({
            'id': f'd{len(findings)}',
            'kind': 'time' if attribute['kind'] == DATETIME else 'driver',
            'attribute': attribute['id'], 'column': attribute['column'],
            'what': _what(attribute), 'label': group['label'],
            'phrase': _phrase(attribute, group['label']),
            'codes': codes, 'filter': _group_filter(attribute, codes),
            **_shares(group, found_total, normal_total)})
    for item in (report.get('combinations') or [])[:FINDING_COMBINATIONS]:
        first, second = item['parts']
        findings.append({
            'id': item['id'], 'kind': 'combination',
            'attribute': first['attribute'], 'column': None,
            'what': f"{first['what']} and {second['what']}",
            'label': f"{first['label']} · {second['label']}",
            'phrase': f"{first['phrase']} and {second['phrase']}",
            'codes': None, 'filter': item['filter'], 'parts': item['parts'],
            **_shares(item, found_total, normal_total)})
    return [item for item in findings if item['filter']]


def _shares(group, found_total, normal_total):
    """Get the counts, shares, lift and rate of a bin or a group of bins."""
    disc, normal = group['disc'], group['normal']
    disc_share = disc / found_total if found_total else 0
    normal_share = normal / normal_total if normal_total else 0
    return {'disc': disc, 'normal': normal, 'disc_share': disc_share,
            'normal_share': normal_share,
            'lift': disc_share / normal_share if normal_share else None,
            'rate': disc / (disc + normal) if disc + normal else None}


def _unrelated(report):
    """Get the columns no binning of which tells the discrepancies apart."""
    best = {}
    for attribute in report['attributes']:
        best.setdefault(attribute['column'], attribute['score'])
    return sorted(column for column, score in best.items()
                  if (score or 0) < UNRELATED)


def _magnitude(source):
    """Get the differences of a REC's value discrepancies by field, read from
    RAPO_DISCREPANCY_DESCRIPTION (`FIELD|difference;` per field that
    differs).
    """
    meta = source['meta']
    if (meta['control_type'] != 'REC'
            or meta.get('result_type') not in (None, 'Discrepancy')):
        return None
    statement = (
        'select rapo_discrepancy_description d, count(*) n '
        f"from ({source['result_sql']}) where rapo_result_type = "
        "'Discrepancy' group by rapo_discrepancy_description "
        f'order by 2 desc fetch first {DESCRIPTIONS} rows only')
    rows = db.execute(sa.text(statement), as_table=True)
    total = sum(int(row['n']) for row in rows)
    if not total:
        return None
    fields = {}
    for row in rows:
        count = int(row['n'])
        for part in str(row['d'] or '').split(';'):
            if '|' not in part:
                continue
            field, value = part.rsplit('|', 1)
            values = fields.setdefault(field.strip().upper(), {})
            values[value.strip()] = values.get(value.strip(), 0) + count
    result = []
    for field, values in fields.items():
        records = sum(values.values())
        ranked = sorted(values.items(), key=lambda item: -item[1])
        numbers = []
        for value, count in values.items():
            try:
                numbers.append((float(value), count))
            except ValueError:
                numbers = None
                break
        item = {'field': field, 'records': records, 'share': records / total,
                'distinct': len(values), 'sum': None,
                'values': [{'value': value, 'count': count,
                            'share': count / records}
                           for value, count in ranked[:10]],
                'numeric': bool(numbers)}
        if numbers:
            numbers.sort()
            if len(rows) < DESCRIPTIONS:
                item['sum'] = _plain(round(sum(number * count for number, count
                                               in numbers), 6))
            item['min'] = _plain(numbers[0][0])
            item['max'] = _plain(numbers[-1][0])
            half, running = records / 2, 0
            for number, count in numbers:
                running += count
                if running >= half:
                    item['median'] = _plain(number)
                    break
            item['histogram'] = _magnitude_histogram(numbers)
        result.append(item)
    result.sort(key=lambda item: -item['records'])
    return {'total': total, 'fields': result,
            'cut': len(rows) == DESCRIPTIONS}


def _magnitude_histogram(numbers, buckets=20):
    low, high = numbers[0][0], numbers[-1][0]
    if low == high or len(numbers) <= buckets:
        return [{'low': _plain(value), 'high': _plain(value), 'count': count}
                for value, count in numbers]
    width = (high - low) / buckets
    counts = [0] * buckets
    for value, count in numbers:
        counts[min(int((value - low) / width), buckets - 1)] += count
    return [{'low': _plain(round(low + i * width, 6)),
             'high': _plain(round(low + (i + 1) * width, 6)),
             'count': count} for i, count in enumerate(counts)]


def to_json(report):
    """Get the report as JSON-safe values (dates as naive ISO strings)."""
    def default(value):
        if isinstance(value, (dt.datetime, dt.date)):
            return value.isoformat()
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return str(value)
    return json.loads(json.dumps(report, default=default))
