"""Contains the comparison of two analysis samples.

The samples live in two workers; neither sends its rows. The server asks both
for the facts of the mapped columns (`describe`), bins each pair the same way
(numbers and date-times on common edges, anything else by the values most
frequent in either), asks both for the counts in those bins (`distribution`),
and compares the shares:
- the Population Stability Index of a column, sum of (a - b) * ln(a / b)
  over its bins, the missing values and the other values;
- the lift of a value, its share in A over its share in B, which names what is
  over-represented in A (e.g. in the discrepancies against their source).
"""

import datetime as dt
import math

from ..core.control import Control
from .frame import DATETIME, NUMERIC, to_json


BINS = 20
VALUES = 30
EPSILON = 1e-4
PSI_MODERATE = 0.1
PSI_MAJOR = 0.25
IGNORED = ('rapo_process_id', 'rapo_discrepancy_id')
# A column this unique in both samples is a key: its values hardly repeat,
# so their shares say nothing and it is not ranked.
UNIQUE_SHARE = 0.9


def default_mapping(meta_a, columns_a, meta_b, columns_b):
    """Get the column pairs a comparison starts with.

    Columns of the same name (the result metadata only when both have it),
    and for the two sides of one reconciliation the correlation and
    discrepancy fields of its rule configuration.
    """
    names_a = [column['name'] for column in columns_a]
    names_b = [column['name'] for column in columns_b]
    pairs = []
    if meta_a['control_id'] == meta_b['control_id'] \
            and meta_a['control_type'] == 'REC' \
            and meta_a['side'] != meta_b['side']:
        pairs.extend(_criteria_pairs(meta_a, names_a, names_b))
    taken_a = {pair['a'] for pair in pairs}
    taken_b = {pair['b'] for pair in pairs}
    lower_b = {name.lower(): name for name in names_b}
    for name in names_a:
        other = lower_b.get(name.lower())
        if other and name not in taken_a and other not in taken_b \
                and name.lower() not in IGNORED:
            pairs.append({'a': name, 'b': other, 'source': 'name'})
            taken_a.add(name)
            taken_b.add(other)
    return {'pairs': pairs,
            'unmatched_a': [name for name in names_a if name not in taken_a],
            'unmatched_b': [name for name in names_b if name not in taken_b]}


def _criteria_pairs(meta, names_a, names_b):
    """Get the field pairs of a reconciliation's criteria, side A first."""
    try:
        control = Control(meta['control_name'])
        rule_config = control.rule_config
    except Exception:
        return []
    swap = meta['side'] == 'B'
    pairs = []
    items = (rule_config.get('correlation_config') or []) + \
        (rule_config.get('discrepancy_config') or [])
    for item in items:
        if item.get('formula_mode'):
            continue
        field_a = str(item['field_a']).lower()
        field_b = str(item['field_b']).lower()
        if swap:
            field_a, field_b = field_b, field_a
        if field_a in names_a and field_b in names_b and not any(
                pair['a'] == field_a for pair in pairs):
            pairs.append({'a': field_a, 'b': field_b, 'source': 'criteria'})
    return pairs


def compare(session_a, session_b, pairs):
    """Compare the mapped columns of two sessions' samples."""
    pairs = [pair for pair in pairs or [] if pair.get('a') and pair.get('b')]
    if not pairs:
        raise ValueError('Map at least one column of A to one of B')
    described_a = session_a.request('describe',
                                    names=[pair['a'] for pair in pairs])
    described_b = session_b.request('describe',
                                    names=[pair['b'] for pair in pairs])
    specs_a, specs_b, plans = [], [], []
    for pair in pairs:
        info_a = described_a['columns'][pair['a']]
        info_b = described_b['columns'][pair['b']]
        plan = _plan(info_a, info_b)
        plans.append(plan)
        specs_a.append({'name': pair['a'], **plan['spec']})
        specs_b.append({'name': pair['b'], **plan['spec']})
    counted_a = session_a.request('distribution', spec=specs_a)
    counted_b = session_b.request('distribution', spec=specs_b)
    rows_a, rows_b = counted_a['rows'], counted_b['rows']
    columns = []
    for pair, plan in zip(pairs, plans):
        info_a = described_a['columns'][pair['a']]
        info_b = described_b['columns'][pair['b']]
        columns.append(_column(pair, plan, info_a, info_b,
                               counted_a['columns'][pair['a']],
                               counted_b['columns'][pair['b']],
                               rows_a, rows_b))
    columns.sort(key=lambda item: (item['level'] == 'unique',
                                   -(item['psi'] or 0)))
    return {'rows_a': rows_a, 'rows_b': rows_b,
            'version_a': counted_a['version'],
            'version_b': counted_b['version'],
            'columns': columns}


def _plan(info_a, info_b):
    """Get how a pair of columns is binned: on edges, or by values."""
    kinds = {info_a['kind'], info_b['kind']}
    if kinds - {NUMERIC, DATETIME} and all(
            info['count'] > 1 and info['distinct'] >= UNIQUE_SHARE
            * info['count'] for info in (info_a, info_b)):
        kind = info_a['kind'] if len(kinds) == 1 else 'text'
        return {'kind': kind, 'unique': True,
                'spec': {'mode': 'values', 'values': []}}
    if len(kinds) == 1 and kinds <= {NUMERIC, DATETIME} \
            and 'min' in info_a and 'min' in info_b:
        low = min(info_a['min'], info_b['min'])
        high = max(info_a['max'], info_b['max'])
        distinct = max(info_a['distinct'], info_b['distinct'])
        if high > low and distinct > VALUES / 2:
            step = (high - low) / BINS
            edges = [low + step * index for index in range(BINS)] + [high]
            return {'kind': info_a['kind'],
                    'spec': {'mode': 'bins', 'edges': edges}}
    shares = {}
    for info in (info_a, info_b):
        for value, count in info['top']:
            share = count / info['count'] if info['count'] else 0
            shares[value] = max(shares.get(value, 0), share)
    values = sorted(shares, key=lambda value: -shares[value])[:VALUES]
    kind = info_a['kind'] if len(kinds) == 1 else 'text'
    if kind in (NUMERIC, DATETIME):
        values.sort(key=lambda value: _sortable(value, kind))
    return {'kind': kind, 'spec': {'mode': 'values', 'values': values}}


def _sortable(value, kind):
    if kind == NUMERIC:
        try:
            return (0, float(value), '')
        except ValueError:
            return (1, 0.0, value)
    return (0, 0.0, value)


def _column(pair, plan, info_a, info_b, counts_a, counts_b, rows_a, rows_b):
    spec = plan['spec']
    if spec['mode'] == 'bins':
        edges = spec['edges']
        if plan['kind'] == DATETIME:
            edges = [to_json(dt.datetime.fromtimestamp(edge, dt.timezone.utc)
                             .replace(tzinfo=None)) for edge in edges]
        labels = [list(pair) for pair in zip(edges[:-1], edges[1:])]
    else:
        labels = list(spec['values'])
    buckets_a = counts_a['counts'] + [counts_a['missing'], counts_a['other']]
    buckets_b = counts_b['counts'] + [counts_b['missing'], counts_b['other']]
    shares_a = [count / rows_a if rows_a else 0 for count in buckets_a]
    shares_b = [count / rows_b if rows_b else 0 for count in buckets_b]
    psi = None
    if rows_a and rows_b and not plan.get('unique'):
        psi = sum((a - b) * math.log((a + EPSILON) / (b + EPSILON))
                  for a, b in zip(shares_a, shares_b))
    level = 'unique' if plan.get('unique') else None if psi is None \
        else 'major' if psi >= PSI_MAJOR \
        else 'moderate' if psi >= PSI_MODERATE else 'stable'
    lifts = []
    for index, label in enumerate(labels + ['(missing)', '(other)']):
        a, b = shares_a[index], shares_b[index]
        if not a and not b:
            continue
        lifts.append({'index': index, 'label': label,
                      'missing': index == len(labels),
                      'other': index == len(labels) + 1,
                      'count_a': buckets_a[index], 'count_b': buckets_b[index],
                      'share_a': round(a * 100, 4),
                      'share_b': round(b * 100, 4),
                      'lift': round(a / b, 4) if b else None})
    stats = {}
    for name in ('mean', 'median', 'min', 'max'):
        if name in info_a and name in info_b:
            stats[name] = [info_a[name], info_b[name]]
            if plan['kind'] == DATETIME:
                stats[name] = [to_json(dt.datetime.fromtimestamp(
                    value, dt.timezone.utc).replace(tzinfo=None))
                    for value in stats[name]]
    return {'a': pair['a'], 'b': pair['b'], 'kind': plan['kind'],
            'mode': spec['mode'], 'source': pair.get('source'),
            'psi': None if psi is None else round(psi, 4), 'level': level,
            'missing_pct': [_pct(counts_a['missing'], rows_a),
                            _pct(counts_b['missing'], rows_b)],
            'distinct': [info_a['distinct'], info_b['distinct']],
            'stats': stats,
            'labels': labels,
            'shares_a': [round(share * 100, 4) for share in shares_a],
            'shares_b': [round(share * 100, 4) for share in shares_b],
            'lifts': lifts}


def _pct(part, whole):
    return round(part * 100 / whole, 4) if whole else 0.0
