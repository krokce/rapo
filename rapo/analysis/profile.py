"""Contains the exploratory profile of a sample, as pandas-profiling has it.

Every function takes the DataFrame and the kind of each column (`frame.py`)
and returns JSON-safe dictionaries. `step(done, total)` is called between
columns, so that the worker can report progress and stop a canceled step.
"""

import numpy as np
import pandas as pd

from .frame import DATETIME, NUMERIC, TEXT, floats, to_json


TOP_VALUES = 10
EXTREME_VALUES = 5
HISTOGRAM_BINS = 30
CATEGORICAL_DISTINCT = 50
MISSING_ALERT = 20
DOMINANT_ALERT = 90
ZEROS_ALERT = 10
SKEW_ALERT = 10
MATRIX_BUCKETS = 100
DUPLICATE_ROWS = 50
MEMORY_SAMPLE = 10000


def columns(frame, kinds, step=None):
    """Get the profile of every column, in order."""
    result = []
    names = list(frame.columns)
    for number, name in enumerate(names):
        if step:
            step(number, len(names))
        result.append(column(name, frame[name], kinds[name]))
    return result


def column(name, series, kind):
    """Get the profile of one column."""
    rows = len(series)
    present = series.dropna()
    count = len(present)
    counts = present.value_counts(sort=True)
    distinct = len(counts)
    info = {
        'name': name,
        'kind': kind,
        'categorical': kind == TEXT and 0 < distinct <= CATEGORICAL_DISTINCT,
        'count': count,
        'missing': rows - count,
        'missing_pct': _pct(rows - count, rows),
        'distinct': distinct,
        'distinct_pct': _pct(distinct, count),
        'unique': count > 1 and distinct == count,
        'top': _top(counts, count),
        'other_count': int(counts.iloc[TOP_VALUES:].sum()),
    }
    if kind == NUMERIC:
        info.update(_numeric(present, counts))
    elif kind == DATETIME:
        info.update(_datetime(present))
    else:
        info.update(_text(present))
    info['alerts'] = _alerts(info, rows)
    return info


def _top(counts, count):
    return [{'value': to_json(value), 'count': int(number),
             'pct': _pct(number, count)}
            for value, number in counts.iloc[:TOP_VALUES].items()]


def _numeric(present, counts):
    values = floats(present)
    if not len(values):
        return {'stats': None, 'histogram': None}
    ordered = counts.sort_index()
    quantiles = np.quantile(values, [0.05, 0.25, 0.5, 0.75, 0.95])
    mean = float(values.mean())
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    series = pd.Series(values)
    zeros = int((values == 0).sum())
    negatives = int((values < 0).sum())
    stats = {
        'min': float(values.min()),
        'max': float(values.max()),
        'range': float(values.max() - values.min()),
        'mean': mean,
        'std': std,
        'cv': std / mean if mean else None,
        'sum': float(values.sum()),
        'q05': float(quantiles[0]),
        'q25': float(quantiles[1]),
        'median': float(quantiles[2]),
        'q75': float(quantiles[3]),
        'q95': float(quantiles[4]),
        'iqr': float(quantiles[3] - quantiles[1]),
        'mad': float((series - series.median()).abs().median()),
        'skew': _number(series.skew()) if len(values) > 2 else None,
        'kurtosis': _number(series.kurt()) if len(values) > 3 else None,
        'zeros': zeros,
        'zeros_pct': _pct(zeros, len(values)),
        'negatives': negatives,
        'negatives_pct': _pct(negatives, len(values)),
    }
    return {
        'stats': stats,
        'smallest': _extremes(ordered.iloc[:EXTREME_VALUES]),
        'largest': _extremes(ordered.iloc[::-1].iloc[:EXTREME_VALUES]),
        'histogram': _histogram(values, len(counts)),
    }


def _histogram(values, distinct):
    bins = max(1, min(HISTOGRAM_BINS, distinct))
    counts, edges = np.histogram(values, bins=bins)
    return {'counts': counts.tolist(), 'edges': edges.tolist()}


def _datetime(present):
    if not len(present):
        return {'stats': None, 'histogram': None}
    low, high = present.min(), present.max()
    seconds = present.astype('int64').to_numpy() // 10**9
    distinct = len(np.unique(seconds)) if len(seconds) < 10**6 \
        else HISTOGRAM_BINS
    counts, edges = np.histogram(seconds, bins=max(1, min(HISTOGRAM_BINS,
                                                          distinct)))
    moments = pd.to_datetime(edges, unit='s')
    hours = present.dt.hour.value_counts().reindex(range(24), fill_value=0)
    weekdays = present.dt.dayofweek.value_counts() \
        .reindex(range(7), fill_value=0)
    midnight = bool((present == present.dt.normalize()).all())
    return {
        'stats': {
            'min': to_json(low),
            'max': to_json(high),
            'range_days': (high - low).total_seconds() / 86400,
            'date_only': midnight,
        },
        'histogram': {'counts': counts.tolist(),
                      'edges': [to_json(moment) for moment in moments]},
        'hours': None if midnight else hours.tolist(),
        'weekdays': weekdays.tolist(),
    }


def _text(present):
    if not len(present):
        return {'stats': None, 'histogram': None}
    text = present.astype(str)
    lengths = text.str.len().to_numpy()
    empty = int((text.str.strip() == '').sum())
    counts, edges = np.histogram(
        lengths, bins=max(1, min(HISTOGRAM_BINS, len(np.unique(lengths)))))
    return {
        'stats': {
            'min_length': int(lengths.min()),
            'max_length': int(lengths.max()),
            'mean_length': float(lengths.mean()),
            'median_length': float(np.median(lengths)),
            'blank': empty,
            'blank_pct': _pct(empty, len(text)),
        },
        'histogram': {'counts': counts.tolist(), 'edges': edges.tolist()},
    }


def _extremes(counts):
    return [{'value': to_json(value), 'count': int(number)}
            for value, number in counts.items()]


def _alerts(info, rows):
    alerts = []

    def alert(code, level, message):
        alerts.append({'column': info['name'], 'code': code,
                       'level': level, 'message': message})

    stats = info.get('stats') or {}
    if rows and info['count'] == 0:
        alert('empty', 'warning', 'All values are missing')
        return alerts
    if info['distinct'] == 1:
        alert('constant', 'warning',
              f"Has a constant value {info['top'][0]['value']!r}")
    elif info['unique'] and info['missing'] == 0:
        alert('unique', 'info', 'All values are unique')
    if info['missing_pct'] >= MISSING_ALERT:
        alert('missing', 'warning',
              f"{info['missing_pct']:.1f}% of the values are missing")
    elif info['missing']:
        alert('some_missing', 'info',
              f"{info['missing']} missing values")
    if info['kind'] == TEXT and info['distinct'] > CATEGORICAL_DISTINCT \
            and not info['unique']:
        alert('high_cardinality', 'info',
              f"High cardinality: {info['distinct']} distinct values")
    if info['distinct'] > 1 and info['top'] \
            and info['top'][0]['pct'] >= DOMINANT_ALERT:
        alert('imbalanced', 'warning',
              f"Value {info['top'][0]['value']!r} is "
              f"{info['top'][0]['pct']:.1f}% of the values")
    if info['kind'] == NUMERIC and stats:
        if stats['zeros_pct'] >= ZEROS_ALERT and info['distinct'] > 1:
            alert('zeros', 'info', f"{stats['zeros_pct']:.1f}% zeros")
        if stats['skew'] is not None and abs(stats['skew']) >= SKEW_ALERT:
            alert('skewed', 'info',
                  f"Highly skewed (skewness {stats['skew']:.1f})")
    if info['kind'] == TEXT and stats and stats.get('blank'):
        alert('blank', 'info', f"{stats['blank']} blank values")
    return alerts


def overview(frame, kinds, column_profiles):
    """Get the facts of the whole sample and every column's alerts."""
    rows, width = frame.shape
    missing = int(sum(item['missing'] for item in column_profiles))
    duplicates = int(frame.duplicated().sum()) if rows and width else 0
    types = {}
    for item in column_profiles:
        name = 'categorical' if item['categorical'] else item['kind']
        types[name] = types.get(name, 0) + 1
    alerts = [alert for item in column_profiles for alert in item['alerts']]
    if duplicates:
        alerts.insert(0, {'column': None, 'code': 'duplicates',
                          'level': 'warning',
                          'message': f'{duplicates} duplicate rows '
                                     f'({_pct(duplicates, rows):.1f}%)'})
    return {
        'rows': rows,
        'columns': width,
        'missing_cells': missing,
        'missing_pct': _pct(missing, rows * width),
        'duplicate_rows': duplicates,
        'duplicate_pct': _pct(duplicates, rows),
        'memory_bytes': _memory(frame),
        'types': types,
        'alerts': alerts,
    }


def _memory(frame):
    rows = len(frame)
    if rows <= MEMORY_SAMPLE:
        return int(frame.memory_usage(deep=True).sum())
    sample = frame.iloc[:MEMORY_SAMPLE].memory_usage(deep=True).sum()
    return int(sample * rows / MEMORY_SAMPLE)


def missing(frame, step=None):
    """Get the missing values per column and the nullity matrix.

    The matrix splits the sample in order into up to 100 buckets and gives
    the share of missing values of each column in each bucket.
    """
    rows = len(frame)
    nulls = frame.isna()
    counts = nulls.sum()
    buckets = max(1, min(MATRIX_BUCKETS, rows))
    matrix = []
    if rows:
        groups = np.arange(rows) * buckets // rows
        shares = nulls.groupby(groups).mean()
        matrix = [[round(float(value), 4) for value in row]
                  for row in shares.to_numpy().T]
    return {
        'columns': [{'name': name, 'missing': int(counts[name]),
                     'missing_pct': _pct(counts[name], rows)}
                    for name in frame.columns],
        'buckets': buckets,
        'matrix': matrix,
    }


def duplicates(frame, step=None):
    """Get the most frequent duplicate rows of the sample."""
    rows = len(frame)
    repeated = frame[frame.duplicated(keep=False)]
    top = []
    if len(repeated):
        hashes = pd.util.hash_pandas_object(repeated, index=False)
        counts = hashes.value_counts().iloc[:DUPLICATE_ROWS]
        first = ~hashes.duplicated()
        representatives = repeated[first.to_numpy()]
        by_hash = dict(zip(hashes[first].to_numpy(),
                           range(len(representatives))))
        for value, number in counts.items():
            row = representatives.iloc[by_hash[value]]
            top.append({'count': int(number),
                        'values': [to_json(item) for item in row.tolist()]})
    duplicate_rows = int(frame.duplicated().sum()) if rows else 0
    return {
        'columns': list(frame.columns),
        'duplicate_rows': duplicate_rows,
        'duplicate_pct': _pct(duplicate_rows, rows),
        'distinct_duplicated': int(len(top)),
        'rows': top,
    }


CORRELATION_ROWS = 200000
CRAMERS_ROWS = 100000
CORRELATION_COLUMNS = 40
CRAMERS_COLUMNS = 30
CRAMERS_DISTINCT = 50
CRAMERS_MIN_ROWS = 20
CORRELATION_ALERT = 0.9
CORRELATION_PAIRS = 20
BREAKDOWN_COLUMNS = (('rapo_result_type', 'Result type'),
                     ('rapo_result_value', 'Result value'),
                     ('rapo_discrepancy_description', 'Discrepancy'))
BREAKDOWN_VALUES = 20


def correlations(frame, kinds, step=None):
    """Get the correlation matrices of the sample.

    Pearson and Spearman over the numeric columns, Cramér's V over the
    columns with few distinct values. Columns with a single value are left
    out; a large sample is measured on its first rows (`sampled`).
    """
    rows = len(frame)
    numeric = [name for name in frame.columns if kinds[name] == NUMERIC
               and frame[name].nunique(dropna=True) > 1]
    numeric = sorted(numeric, key=lambda name: -frame[name].count())
    numeric = numeric[:CORRELATION_COLUMNS]
    subset = frame.iloc[:CORRELATION_ROWS]
    values = pd.DataFrame({name: floats(subset[name]) for name in numeric},
                          index=subset.index)
    if step:
        step(0, 3)
    pearson = values.corr(method='pearson', min_periods=3) if numeric \
        else pd.DataFrame()
    if step:
        step(1, 3)
    spearman = values.corr(method='spearman', min_periods=3) if numeric \
        else pd.DataFrame()
    if step:
        step(2, 3)
    cramers = _cramers(frame.iloc[:CRAMERS_ROWS], kinds, step)
    result = {'rows': min(rows, CORRELATION_ROWS),
              'sampled': rows > CORRELATION_ROWS,
              'pearson': _matrix(pearson),
              'spearman': _matrix(spearman),
              'cramers': cramers}
    pairs = []
    for method in ('pearson', 'spearman', 'cramers'):
        matrix = result[method]
        names = matrix['columns']
        for i, first in enumerate(names):
            for j in range(i + 1, len(names)):
                value = matrix['matrix'][i][j]
                if value is not None:
                    pairs.append({'method': method, 'a': first,
                                  'b': names[j], 'value': value})
    pairs.sort(key=lambda item: -abs(item['value']))
    strongest = {}
    for pair in pairs:
        key = (pair['a'], pair['b'])
        if key not in strongest:
            strongest[key] = pair
    result['pairs'] = list(strongest.values())[:CORRELATION_PAIRS]
    result['alerts'] = [
        {'column': pair['a'], 'code': 'high_correlation', 'level': 'warning',
         'message': f"Highly correlated with {pair['b'].upper()} "
                    f"({_method_label(pair['method'])} {pair['value']:.2f})"}
        for pair in result['pairs']
        if abs(pair['value']) >= CORRELATION_ALERT]
    return result


def _method_label(method):
    return {'pearson': 'Pearson', 'spearman': 'Spearman',
            'cramers': "Cramér's V"}[method]


def _matrix(frame):
    names = list(frame.columns)
    matrix = [[_rounded(frame.iloc[i, j]) for j in range(len(names))]
              for i in range(len(names))]
    return {'columns': names, 'matrix': matrix}


def _rounded(value):
    value = _number(value)
    return None if value is None else round(value, 4)


def _cramers(frame, kinds, step):
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
    codes = {name: pd.Series(pd.factorize(frame[name])[0], index=frame.index)
             for name in names}
    size = len(names)
    matrix = [[None] * size for _ in range(size)]
    for i in range(size):
        matrix[i][i] = 1.0
        for j in range(i + 1, size):
            value = _cramers_v(codes[names[i]], codes[names[j]])
            matrix[i][j] = matrix[j][i] = value
    return {'columns': names, 'matrix': matrix}


def _cramers_v(first, second):
    present = (first >= 0) & (second >= 0)
    first, second = first[present], second[present]
    total = len(first)
    if total < 2:
        return None
    table = pd.crosstab(first, second).to_numpy(dtype='float64')
    if min(table.shape) < 2:
        return None
    expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / total
    chi2 = float(((table - expected) ** 2 / expected).sum())
    value = np.sqrt(chi2 / (total * (min(table.shape) - 1)))
    return round(float(min(value, 1.0)), 4)


def breakdown(frame, kinds, step=None):
    """Get the counts of the result metadata columns of a result table.

    The result type (Loss, Discrepancy, Duplicate, or a case's type), the
    case value and the discrepancy description, where the table has them.
    """
    rows = len(frame)
    result = []
    for name, label in BREAKDOWN_COLUMNS:
        if name not in frame.columns:
            continue
        counts = frame[name].value_counts(dropna=False)
        if counts.index.isna().all():
            continue
        values = [{'value': to_json(value), 'count': int(number),
                   'pct': _pct(number, rows)}
                  for value, number in counts.iloc[:BREAKDOWN_VALUES].items()]
        result.append({'column': name, 'label': label,
                       'distinct': int(len(counts)), 'values': values})
    return {'rows': rows, 'columns': result}


def _pct(part, whole):
    return round(float(part) * 100 / whole, 4) if whole else 0.0


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(value) or np.isinf(value) else value
