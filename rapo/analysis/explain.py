"""Contains the discrepancy analysis: what makes a run's discrepancies special.

The discrepancies of one side of a run are contrasted with its normal records,
the side's fetched records less the discrepancies. Nothing joins them: every
attribute is binned the same way on both datasets and counted by Oracle over
the whole data, so the normal count of a bin is the fetched count less the
discrepancy count (`analyze`).

1. Profile the fetched records (`_profile`): non-null and distinct counts,
   min/max, deciles, digit-only share and prefix distinct counts per column.
2. Plan the features (`_plan`): the bins of each column (values, deciles,
   hour/weekday/timeline of a date, prefixes and length of an identifier).
3. Count each feature's bins in both datasets (`_count`): one scan each, the
   features unpivoted into (feature, code, count) rows.
4. Score (`_score`): per feature the uncertainty coefficient (mutual
   information over the entropy of the discrepancy flag) and phik, per bin
   the lift, coverage and a two-proportion z, then the story (`_story`).

A fetched dataset above `discrepancy_exact_rows` is counted on a Bernoulli
sample (`_sampled`) scaled back by 1/p; the discrepancies are always counted
whole.
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
from .frame import NUMERIC, DATETIME, column_kind


RESULT_TYPES = ('Loss', 'Discrepancy', 'Duplicate')
PREFIXES = (3, 5, 6, 8)
TEXT_PREFIXES = (2, 4, 6)
RAW_DISTINCT = 30          # numbers with up to this many values are binned by value
FEATURE_DISTINCT = 1000    # a feature with more values is not counted
SHOWN_BINS = 30            # the rest of a value feature is Other
UNIQUE_SHARE = 0.9         # a feature this unique has nothing to tell
DIGIT_SHARE = 0.95
TIMELINE_BUCKETS = 20
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
DRIFT = 0.01
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
ORDERED = ('decile', 'hour', 'weekday', 'timeline', 'length')
NUMBER_TEXT = "'TM9', 'NLS_NUMERIC_CHARACTERS=''.,'''"
DAY_ZERO = "date '2000-01-01'"
EPOCH = dt.datetime(2000, 1, 1)
# Types that can not be grouped (LOBs come back from a parse as LONG).
UNGROUPED = ('LONG', 'LONG_RAW', 'RAW', 'BLOB', 'CLOB', 'NCLOB', 'BFILE',
             'OBJECT', 'ROWID', 'UROWID', 'INTERVAL_DS', 'INTERVAL_YM',
             'CURSOR', 'JSON', 'VECTOR')


class ExplainError(ValueError):
    """The run's discrepancies can not be analysed."""


def analyze(process_id, side, result_type=None, exact_rows=5000000,
            progress=None):
    """Explain the discrepancies of one side of a run.

    Parameters
    ----------
    process_id : int
    side : str
        `a` or `b`.
    result_type : str, optional
        REC only: one of `RESULT_TYPES`; all of them by default.
    exact_rows : int
        Fetched records counted whole; a larger dataset is sampled.
    progress : callable, optional
        progress(step, done, total) as the analysis goes.

    Returns
    -------
    report : dict
        JSON-safe.
    """
    step = progress or (lambda *args: None)
    step('Reading the run', 0, 5)
    source = _source(process_id, side, result_type)
    meta = source['meta']
    if not source['columns']:
        raise ExplainError(
            'No column of the discrepancies can be traced back to the '
            f"fetched records of side {meta['side']} (output columns that "
            'coalesce both sides or are of a type that can not be grouped '
            'are left out)')

    step('Profiling the fetched records', 1, 5)
    logged = meta['fetched_logged'] or 0
    sample = (min(1.0, exact_rows / logged)
              if exact_rows and logged > exact_rows else 1.0)
    profile = _profile(source['fetched_sql'], source['columns'], sample)
    meta['sample'] = sample if sample < 1 else None
    meta['fetched_scanned'] = round(profile['rows'] / sample)

    step('Choosing the bins', 2, 5)
    features, excluded = _plan(source['columns'], profile)
    meta['excluded'] = source['excluded'] + excluded

    step('Counting the fetched records', 3, 5)
    fetched = _count(source['fetched_sql'], features, 'fetched', sample)
    step('Counting the discrepancies', 4, 5)
    found = _count(source['result_sql'], features, 'result', 1.0)

    report = _score(meta, features, fetched, found)
    report['type_split'] = source['type_split']
    report['story'] = _story(report)
    step('Done', 5, 5)
    return report


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
        'stale': datasets._changed_since(control, run),
        'datasets': _sides(control),
    }
    return {'meta': meta, 'columns': columns, 'excluded': excluded,
            'result_sql': result_sql, 'fetched_sql': fetched_sql,
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


def _profile(sql, columns, sample):
    """Get the facts the bins are chosen from, per fetched column."""
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
                     f'from ({_sampled(sql, sample)}) q')
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


def _plan(columns, profile):
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
            planned = _date_features(column, facts)
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


def _date_features(column, facts):
    features = [
        _feature(column, 'hour', 'hour', 'Hour of day',
                 lambda name: f"to_char({name}, 'HH24')", ordered=True),
        _feature(column, 'weekday', 'weekday', 'Weekday',
                 lambda name: f"to_char(trunc({name}) - trunc({name}, 'IW'))",
                 ordered=True),
        _feature(column, 'weekhour', 'weekhour', 'Weekday and hour',
                 lambda name: f"to_char(trunc({name}) - trunc({name}, 'IW'))"
                 f" || to_char({name}, 'HH24')", heatmap=True),
    ]
    low, high = facts.get('mn'), facts.get('mx')
    if low and high and high > low:
        start = (low - EPOCH).total_seconds() / 86400
        end = (high - EPOCH).total_seconds() / 86400
        end += (end - start) * 1e-6
        features.append(_feature(
            column, 'timeline', 'timeline', 'Time',
            lambda name: f'to_char(width_bucket(cast({name} as date) - '
            f'{DAY_ZERO}, {start!r}, {end!r}, {TIMELINE_BUCKETS}), '
            "'FM00')", ordered=True, start=start, end=end))
    return features


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


def _count(sql, features, which, sample):
    """Count every feature's bins in one dataset.

    Returns
    -------
    counts : dict
        {feature id: {code: count}}, scaled by 1/sample; NULL is code None.
    """
    counts = {feature['id']: {} for feature in features}
    total = 0
    for start in range(0, len(features), COUNT_FEATURES):
        chunk = features[start:start + COUNT_FEATURES]
        name_of = 'source' if which == 'fetched' else 'column'
        items = [f"cast({feature['expression'](_quoted(feature[name_of]))} "
                 f"as varchar2(200)) {feature['id']}" for feature in chunk]
        aliases = ', '.join(f"{feature['id']} as '{feature['id']}'"
                            for feature in chunk)
        inner = (f'select {", ".join(items)} '
                 f'from ({_sampled(sql, sample)}) q')
        statement = (
            'select feature, code, count(*) n from '
            f'({inner}) unpivot include nulls (code for feature in '
            f'({aliases})) group by feature, code')
        rows = db.execute(sa.text(statement), as_table=True)
        for row in rows:
            counts[row['feature']][row['code']] = int(row['n']) / sample
    if features:
        total = sum(counts[features[0]['id']].values())
    else:
        total = db.execute(sa.text(f'select count(*) from ({_sampled(sql, sample)})'),
                           as_scalar=True) / sample
    return counts, total


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
    # A sampled total is off by chance too: 3 standard deviations allowed.
    noise = (3 * math.sqrt(logged * (1 - sample) / sample)
             if logged and sample else 0)
    meta['drift'] = bool(logged and abs(fetched_total - logged)
                         > max(DRIFT * logged, noise))
    meta['clamped'] = []
    report = {'meta': meta, 'attributes': [], 'heatmaps': []}
    if not features or found_total == 0:
        return report
    for feature in features:
        bins = _bins(feature, fetched_counts[feature['id']],
                     found_counts[feature['id']], found_total, normal_total,
                     meta)
        if feature.get('heatmap'):
            report['heatmaps'].append(_heatmap(feature, bins))
            continue
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
            'phik': _phik(disc, norm),
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
        if normal < -0.5 and not meta.get('sample'):
            meta['clamped'].append(feature['column'].upper())
        items.append({'code': code, 'disc': round(disc),
                      'normal': max(round(normal), 0)})
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
        _measure(item, found_total, normal_total)
        item['label'] = _label(feature, item)
        item['filter'] = _filter(feature, item['code'])
        item['code'] = None if item['code'] is None else str(item['code'])
    items.sort(key=lambda item: _order(feature, item))
    return items


def _measure(item, found_total, normal_total):
    disc, normal = item['disc'], item['normal']
    disc_share = disc / found_total if found_total else 0
    normal_share = normal / normal_total if normal_total else 0
    item['disc_share'] = disc_share
    item['normal_share'] = normal_share
    item['lift'] = (disc_share / normal_share if normal_share
                    else (None if disc_share == 0 else math.inf))
    item['rate'] = disc / (disc + normal) if disc + normal else None
    item['z'] = _z(disc, normal, found_total, normal_total)
    flag = None
    lift = item['lift']
    if (disc >= max(MIN_SUPPORT, MIN_COVERAGE * found_total)
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


def _phik(disc, norm):
    """Get phik of the flag and a feature from their 2×K counts."""
    keep = (disc + norm) > 0
    if keep.sum() < 2 or disc.sum() == 0 or norm.sum() == 0:
        return None
    try:
        from phik.phik import phik_from_hist2d
        value = phik_from_hist2d(np.vstack([disc[keep], norm[keep]]))
    except Exception:
        return None
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), 4)


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


def _heatmap(feature, bins):
    """Get the weekday × hour discrepancy rates of a date column."""
    cells = []
    for item in bins:
        code = item['code']
        if code is None or len(code) != 3:
            continue
        cells.append({'weekday': int(code[0]), 'hour': int(code[1:]),
                      'disc': item['disc'], 'normal': item['normal'],
                      'rate': item['rate'], 'lift': item['lift']})
    return {'column': feature['column'].upper(), 'cells': cells}


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
        index = int(code)
        if index < 1 or index > TIMELINE_BUCKETS:
            return 'Outside the fetched range'
        width = (feature['end'] - feature['start']) / TIMELINE_BUCKETS
        start = EPOCH + dt.timedelta(days=feature['start'] + width * (index - 1))
        end = start + dt.timedelta(days=width)
        return f'{_moment(start)} – {_moment(end)}'
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
        index = int(code)
        if index < 1 or index > TIMELINE_BUCKETS:
            return None
        width = (feature['end'] - feature['start']) / TIMELINE_BUCKETS
        start = EPOCH + dt.timedelta(days=feature['start'] + width * (index - 1))
        end = start + dt.timedelta(days=width)
        return (f"{name} >= to_date('{start:%Y-%m-%d %H:%M:%S}', "
                "'YYYY-MM-DD HH24:MI:SS') and "
                f"{name} < to_date('{end:%Y-%m-%d %H:%M:%S}', "
                "'YYYY-MM-DD HH24:MI:SS')")
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


def _moment(value):
    value = value.replace(microsecond=0)
    if value.second >= 30:
        value += dt.timedelta(seconds=60 - value.second)
    value = value.replace(second=0)
    return f'{value:%Y-%m-%d %H:%M}'


def _pct(value):
    if value is None:
        return '–'
    value *= 100
    if value >= 10 or value == 0:
        return f'{value:.0f}%'
    if value >= 1:
        return f'{value:.1f}%'
    return f'{value:.2f}%'


def _times(lift):
    if lift is None:
        return 'only among the discrepancies'
    if lift >= 10:
        return f'{lift:.0f}× as often'
    return f'{lift:.1f}× as often'


def _story(report):
    """Tell the findings as sentences, each pointing at its attribute.

    Returns
    -------
    story : list of dict
        {kind, text, attribute?, codes?}: `headline`, `types`, `driver`,
        `time`, `unrelated`, `none`, `note`.
    """
    meta = report['meta']
    story = []
    found, normal = meta.get('discrepancies', 0), meta.get('normal', 0)
    fetched = meta.get('fetched_total', 0)
    side = f" on side {meta['side']}" if meta['control_type'] != 'ANL' else ''
    kind = f" {meta['result_type']}" if meta.get('result_type') else ''
    rate = found / fetched if fetched else None
    story.append({'kind': 'headline', 'text': (
        f'{found:,}{kind} discrepancies{side} among {fetched:,} fetched '
        f'records ({_pct(rate)}); they are contrasted with the {normal:,} '
        'normal records.')})
    split = report.get('type_split') or []
    if len(split) > 1 and not meta.get('result_type'):
        total = sum(item['count'] for item in split)
        parts = ', '.join(f"{_pct(item['count'] / total)} {item['type']}"
                          for item in split)
        story.append({'kind': 'types', 'text': f'By result type: {parts}.'})
    if meta.get('sample'):
        story.append({'kind': 'note', 'text': (
            f"The fetched records were counted on a {_pct(meta['sample'])} "
            'random sample and scaled up; the discrepancies are counted '
            'whole.')})
    if found == 0:
        story.append({'kind': 'none', 'text': 'There are no discrepancies '
                      'to explain.'})
        return story
    if normal == 0:
        story.append({'kind': 'none', 'text': (
            'Every fetched record is a discrepancy, so there are no normal '
            'records to contrast them with.')})
        return story

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
    for rank, attribute in enumerate(drivers):
        story.append(_driver_sentence(attribute, rank))
    if not drivers:
        story.append({'kind': 'none', 'text': (
            'No attribute sets the discrepancies apart: in every one of them '
            'they are spread like the normal records. The cause is likely '
            'outside these attributes, e.g. in the other side, the matching '
            'rules or the timing of the data load.')})
    best = {}
    for attribute in report['attributes']:
        best.setdefault(attribute['column'], attribute['score'])
    unrelated = sorted(column for column, score in best.items()
                       if score < UNRELATED)
    if unrelated and drivers:
        shown = ', '.join(unrelated[:8])
        more = f' and {len(unrelated) - 8} more' if len(unrelated) > 8 else ''
        story.append({'kind': 'unrelated', 'text': (
            f'Not related to the discrepancies: {shown}{more}.')})
    if meta.get('stale'):
        story.append({'kind': 'note', 'text': (
            'The control was changed after this run; the fetched records are '
            'selected with its current configuration.')})
    if meta.get('drift'):
        story.append({'kind': 'note', 'text': (
            f"The fetched records counted now ({meta['fetched_total']:,}) "
            f"differ from what the run fetched ({meta['fetched_logged']:,}): "
            'the source data changed since.')})
    if meta.get('clamped'):
        story.append({'kind': 'note', 'text': (
            'Some bins hold more discrepancies than fetched records ('
            + ', '.join(meta['clamped'][:5]) + '), e.g. a key shared by '
            'several records, or source records changed since the run; '
            'their normal count is taken as 0.')})
    return story


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


def _driver_sentence(attribute, rank):
    column = attribute['column']
    what = (column if attribute['feature'] in ('value', 'decile')
            else f'{column} (prefix)' if attribute['feature'] == 'prefix'
            else f"{column} ({attribute['feature_label'].lower()})")
    groups = _leading(attribute)
    parts = []
    for group in groups:
        lift = (group['disc_share'] / group['normal_share']
                if group['normal_share'] else None)
        parts.append(f"{group['label']} holds {_pct(group['disc_share'])} of "
                     f"the discrepancies against {_pct(group['normal_share'])}"
                     f' of the normal records ({_times(lift)})')
    lead = ('The strongest driver is' if rank == 0
            else 'Next comes' if rank == 1 else 'Also')
    text = f'{lead} {what}: ' + '; '.join(parts) + '.'
    codes = [code for group in groups
             for code in (group.get('codes') or [group['code']])]
    return {'kind': 'time' if attribute['kind'] == DATETIME else 'driver',
            'text': text, 'attribute': attribute['id'], 'codes': codes}


def to_json(report):
    """Get the report as JSON-safe values (dates as naive ISO strings)."""
    def default(value):
        if isinstance(value, (dt.datetime, dt.date)):
            return value.isoformat()
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return str(value)
    return json.loads(json.dumps(report, default=default))
