"""Contains the exploratory profile of a sample.

Every function takes the DataFrame and the kind of each column (`frame.py`)
and returns JSON-safe dictionaries. `step(done, total)` is called between
columns, so that the worker can report progress and stop a canceled step.
"""

import numpy as np
import pandas as pd

from . import timebins
from .frame import DATETIME, NUMERIC, TEXT, floats, to_json


TOP_VALUES = 8
HISTOGRAM_BINS = 24
CATEGORICAL_DISTINCT = 50
# A column with this few values, or one value this dominant, is shown by its
# values rather than by a histogram.
TOP_DISTINCT = 20
DOMINANT_PCT = 50
# Text this unique is an identifier: nothing to profile, and so is text half
# unique whose most frequent value is under RARE_PCT of the records; so are
# whole numbers all different in at least UNIQUE_NUMBERS records.
UNIQUE_PCT = 90
SPREAD_PCT = 50
RARE_PCT = 1
UNIQUE_NUMBERS = 50
MISSING_PCT = 5
METADATA_PREFIX = 'rapo_'


def columns(frame, kinds, step=None, window=None):
    """Get the profile of every column, in order; `window` is the run's
    {from, to} (ISO date-times), for the date columns inside it."""
    result = []
    names = list(frame.columns)
    for number, name in enumerate(names):
        if step:
            step(number, len(names))
        result.append(column(name, frame[name], kinds[name], window))
    return result


def column(name, series, kind, window=None):
    """Get the profile of one column.

    Besides the counts and the most frequent values, `unusable` says why a
    column tells nothing (`empty`, `constant`, `unique`), `group` where it
    is listed (`category`, `number`, `date`, `text`) and `visual` how it is
    best shown (`top` values or a `histogram`; None for nothing).
    """
    rows = len(series)
    present = series.dropna()
    count = len(present)
    counts = present.value_counts(sort=True)
    distinct = len(counts)
    info = {
        'name': name,
        'kind': kind,
        'metadata': name.startswith(METADATA_PREFIX),
        'categorical': kind == TEXT and 0 < distinct <= CATEGORICAL_DISTINCT,
        'count': count,
        'missing': rows - count,
        'missing_pct': _pct(rows - count, rows),
        'distinct': distinct,
        'distinct_pct': _pct(distinct, count),
        'top': _top(counts, count),
        'other_count': int(counts.iloc[TOP_VALUES:].sum()),
        'stats': None,
        'histogram': None,
    }
    # Values that never repeat are shown by their spread, however few.
    spread = distinct > TOP_DISTINCT or distinct == count
    if count:
        if kind == NUMERIC:
            info.update(_numeric(present, spread))
        elif kind == DATETIME:
            info.update(_datetime(present, spread, window))
        else:
            info.update(_text(present))
    info['unusable'] = _unusable(info)
    info['visual'] = _visual(info)
    info['group'] = _group(info)
    return info


def _top(counts, count):
    return [{'value': to_json(value), 'count': int(number),
             'pct': _pct(number, count)}
            for value, number in counts.iloc[:TOP_VALUES].items()]


def _numeric(present, spread):
    values = floats(present)
    zeros = int((values == 0).sum())
    stats = {
        'min': float(values.min()),
        'max': float(values.max()),
        'median': float(np.median(values)),
        'zeros': zeros,
        'zeros_pct': _pct(zeros, len(values)),
        'integral': bool(np.all(np.mod(values, 1) == 0)),
    }
    histogram = None
    if spread:
        counts, edges = np.histogram(values, bins=HISTOGRAM_BINS)
        histogram = {'counts': counts.tolist(), 'edges': edges.tolist()}
    return {'stats': stats, 'histogram': histogram}


def _datetime(present, spread, window=None):
    """Get the facts of a date-time column, with a histogram of whole hours,
    days or months (`timebins`): over the run's window when most values lie
    in it (`window` true; `before`/`after` count the others), else over the
    values' own range."""
    low, high = present.min(), present.max()
    midnight = bool((present == present.dt.normalize()).all())
    start, end = low, high
    inside = False
    if window and window.get('from') and window.get('to'):
        first, last = pd.Timestamp(window['from']), pd.Timestamp(window['to'])
        share = float(((present >= first) & (present <= last)).mean())
        if share >= timebins.WINDOW_SHARE and last > first:
            start, end, inside = first, last, True
    histogram = None
    if (spread or inside) and end > start:
        unit, edges = timebins.edges(start.to_pydatetime(), end.to_pydatetime())
        marks = np.array(edges, dtype='datetime64[ns]').astype('int64')
        values = present.to_numpy(dtype='datetime64[ns]').astype('int64')
        positions = np.searchsorted(marks, values, side='right') - 1
        bins = len(edges) - 1
        kept = positions[(positions >= 0) & (positions < bins)]
        histogram = {
            'counts': np.bincount(kept, minlength=bins).tolist(),
            'edges': [to_json(pd.Timestamp(edge)) for edge in edges],
            'unit': unit,
            'window': inside,
            'before': int((positions < 0).sum()),
            'after': int((positions >= bins).sum()),
        }
    return {
        'stats': {
            'min': to_json(low),
            'max': to_json(high),
            'date_only': midnight,
        },
        'histogram': histogram,
    }


def _text(present):
    text = present.astype(str)
    blank = int((text.str.strip() == '').sum())
    return {'stats': {'blank': blank, 'blank_pct': _pct(blank, len(text))}}


def _unusable(info):
    if info['count'] == 0:
        return 'empty'
    if info['distinct'] == 1:
        return 'constant'
    if info['kind'] == TEXT and info['count'] > 1 and (
            info['distinct_pct'] >= UNIQUE_PCT
            or (info['distinct_pct'] >= SPREAD_PCT
                and info['top'][0]['pct'] < RARE_PCT)):
        return 'unique'
    if info['kind'] == NUMERIC and info['count'] >= UNIQUE_NUMBERS \
            and info['distinct'] == info['count'] and info['stats']['integral']:
        return 'unique'
    return None


def _group(info):
    if info['kind'] == DATETIME:
        return 'date'
    if info['kind'] == NUMERIC:
        return 'category' if info['visual'] == 'top' \
            and info['distinct'] <= TOP_DISTINCT else 'number'
    return 'category' if info['categorical'] else 'text'


def _visual(info):
    if info['unusable']:
        return None
    top = info['top']
    histogram = info['histogram']
    # The records of a run's window, in time order, whatever their values.
    if histogram and histogram.get('window'):
        return 'histogram'
    repeats = bool(top) and top[0]['count'] > 1
    if repeats and (info['distinct'] <= TOP_DISTINCT
                    or top[0]['pct'] >= DOMINANT_PCT):
        return 'top'
    if histogram:
        return 'histogram' if sum(1 for count in histogram['counts']
                                  if count) >= 2 else None
    # Text of many values: the most frequent, when they repeat at all.
    return 'top' if repeats else None


def overview(frame, kinds, column_profiles):
    """Get the facts of the whole sample.

    The RAPO_ metadata columns of a result table are not counted.
    """
    rows = len(frame)
    shown = [item for item in column_profiles if not item['metadata']]
    duplicates = int(frame.duplicated().sum()) if rows and len(frame.columns) \
        else 0
    return {
        'rows': rows,
        'columns': len(shown),
        'duplicate_rows': duplicates,
        'duplicate_pct': _pct(duplicates, rows),
        'missing_columns': [item['name'] for item in shown
                            if item['missing_pct'] >= MISSING_PCT],
        'unusable': [{'name': item['name'], 'reason': item['unusable'],
                      'value': item['top'][0]['value']
                      if item['unusable'] == 'constant' else None}
                     for item in shown if item['unusable']],
    }


CORRELATION_ROWS = 200000
CRAMERS_ROWS = 100000
CORRELATION_COLUMNS = 40
CRAMERS_COLUMNS = 30
CRAMERS_DISTINCT = 50
CRAMERS_MIN_ROWS = 20
RELATION_MIN = 0.4
RELATIONS = 5
RELATED_METADATA = ('rapo_result_type',)
BREAKDOWN_TYPES = 'rapo_result_type'
BREAKDOWN_VALUES = 'rapo_result_value'
BREAKDOWN_DESCRIPTION = 'rapo_discrepancy_description'
BREAKDOWN_TOP = 10


def relations(frame, kinds, step=None):
    """Get the strongest relations between pairs of columns.

    Pearson and Spearman over the numeric columns, Cramér's V over the
    columns with few distinct values, each pair once by its strongest
    measure, from `RELATION_MIN` on. The RAPO_ metadata columns are left
    out but the result type. A large sample is measured on its first rows.
    """
    names = [name for name in frame.columns
             if not name.startswith(METADATA_PREFIX)
             or name in RELATED_METADATA]
    subset = frame.iloc[:CORRELATION_ROWS][names]
    numeric = [name for name in names if kinds[name] == NUMERIC
               and subset[name].nunique(dropna=True) > 1]
    numeric = sorted(numeric, key=lambda name: -subset[name].count())
    numeric = numeric[:CORRELATION_COLUMNS]
    values = pd.DataFrame({name: floats(subset[name]) for name in numeric},
                          index=subset.index)
    pairs = []
    for number, method in enumerate(('pearson', 'spearman')):
        if step:
            step(number, 3)
        if len(numeric) < 2:
            continue
        matrix = values.corr(method=method, min_periods=3)
        for i, first in enumerate(numeric):
            for j in range(i + 1, len(numeric)):
                value = _number(matrix.iloc[i, j])
                if value is not None:
                    pairs.append((method, first, numeric[j], value))
    if step:
        step(2, 3)
    pairs.extend(_cramers(subset.iloc[:CRAMERS_ROWS], kinds))
    strongest = {}
    for method, first, second, value in sorted(pairs,
                                               key=lambda item: -abs(item[3])):
        if abs(value) < RELATION_MIN:
            break
        key = tuple(sorted((first, second)))
        if key not in strongest:
            strongest[key] = {'a': first, 'b': second, 'method': method,
                              'value': round(value, 4)}
    return {'pairs': list(strongest.values())[:RELATIONS]}


def _cramers(frame, kinds):
    """Get Cramér's V between the columns with 2..50 distinct values."""
    # A column nearly unique in the sample, like a key, is perfectly
    # associated with any other, which says nothing, and so is every pair
    # of a tiny sample.
    names = []
    for name in frame.columns:
        distinct = frame[name].nunique(dropna=True)
        count = frame[name].count()
        if 1 < distinct <= CRAMERS_DISTINCT and distinct * 2 <= count \
                and count >= CRAMERS_MIN_ROWS and kinds[name] != DATETIME:
            names.append(name)
    names = names[:CRAMERS_COLUMNS]
    codes = {name: pd.factorize(frame[name])[0] for name in names}
    pairs = []
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            value = _cramers_v(codes[first], codes[second])
            if value is not None:
                pairs.append(('cramers', first, second, value))
    return pairs


def _cramers_v(first, second):
    """Get Cramér's V of two factorized columns (-1 is missing)."""
    present = (first >= 0) & (second >= 0)
    first, second = first[present], second[present]
    total = len(first)
    if total < 2:
        return None
    _, first = np.unique(first, return_inverse=True)
    _, second = np.unique(second, return_inverse=True)
    rows, cols = int(first.max()) + 1, int(second.max()) + 1
    if min(rows, cols) < 2:
        return None
    table = np.bincount(first * cols + second, minlength=rows * cols) \
        .reshape(rows, cols).astype('float64')
    expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / total
    chi2 = float(((table - expected) ** 2 / expected).sum())
    value = np.sqrt(chi2 / (total * (min(rows, cols) - 1)))
    return round(float(min(value, 1.0)), 4)


def breakdown(frame, kinds, step=None):
    """Get the result metadata of a result table, where it has them.

    `types` counts the result types (Loss, Discrepancy, Duplicate, or a
    case's type); `fields` the fields the discrepancy descriptions name
    (`FIELD|difference;` per field that differs), out of the `described`
    records; `values` the case values, only when there are several.
    """
    rows = len(frame)
    result = {'rows': rows, 'types': [], 'fields': [], 'described': 0,
              'values': []}
    if BREAKDOWN_TYPES in frame.columns:
        counts = frame[BREAKDOWN_TYPES].value_counts(dropna=False)
        result['types'] = [{'value': to_json(value), 'count': int(number),
                            'pct': _pct(number, rows)}
                           for value, number in counts.items()]
    if BREAKDOWN_DESCRIPTION in frame.columns:
        described = frame[BREAKDOWN_DESCRIPTION].dropna().astype(str)
        described = described[described.str.contains('|', regex=False)]
        fields = {}
        for text, number in described.value_counts().items():
            for name in {part.rsplit('|', 1)[0].strip().upper()
                         for part in text.split(';') if '|' in part}:
                fields[name] = fields.get(name, 0) + int(number)
        result['described'] = len(described)
        result['fields'] = [{'field': name, 'count': number,
                             'pct': _pct(number, len(described))}
                            for name, number in sorted(
                                fields.items(), key=lambda item: -item[1])]
    if BREAKDOWN_VALUES in frame.columns:
        counts = frame[BREAKDOWN_VALUES].value_counts(dropna=False)
        if len(counts) > 1:
            result['values'] = [{'value': to_json(value),
                                 'count': int(number),
                                 'pct': _pct(number, rows)}
                                for value, number
                                in counts.iloc[:BREAKDOWN_TOP].items()]
    return result


def _pct(part, whole):
    return round(float(part) * 100 / whole, 4) if whole else 0.0


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(value) or np.isinf(value) else value
