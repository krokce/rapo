"""Contains the DataFrame helpers of the analysis worker.

Rows fetched from Oracle become typed columns (`build`), a view of the sample
is the positions left by the filters, the search and the sort (`view`), and
every value leaves the worker JSON-safe (`to_json`): naive ISO date-times,
numbers, strings, None for missing.
"""

import datetime as dt
import decimal
import math

import numpy as np
import pandas as pd


NUMERIC = 'numeric'
DATETIME = 'datetime'
TEXT = 'text'

INT64_MAX = 2**63 - 1


def column_kind(type_code):
    """Get the kind of a column from its cursor type."""
    name = getattr(type_code, 'name', str(type_code)).upper()
    if 'NUMBER' in name or 'BINARY_' in name or 'INTEGER' in name \
            or 'FLOAT' in name:
        return NUMERIC
    if 'DATE' in name or 'TIMESTAMP' in name:
        return DATETIME
    return TEXT


def unique_names(names):
    """Get column names made unique by a numeric suffix."""
    seen = {}
    result = []
    for name in names:
        name = str(name).lower()
        if name in seen:
            seen[name] += 1
            name = f'{name}_{seen[name]}'
        else:
            seen[name] = 1
        result.append(name)
    return result


def build(rows, columns):
    """Get a DataFrame of fetched rows.

    Parameters
    ----------
    rows : list of tuple
    columns : list of dict
        name and kind of each column, in the cursor's order.
    """
    data = {}
    for index, column in enumerate(columns):
        values = [row[index] for row in rows]
        data[column['name']] = _series(values, column['kind'])
    return pd.DataFrame(data)


def _series(values, kind):
    if kind == NUMERIC:
        present = [value for value in values if value is not None]
        if all(isinstance(value, int) and not isinstance(value, bool)
               and abs(value) <= INT64_MAX for value in present):
            return pd.array(values, dtype='Int64')
        return pd.Series([None if value is None else float(value)
                          for value in values], dtype='float64')
    if kind == DATETIME:
        return pd.to_datetime(pd.Series(values, dtype='object'),
                              errors='coerce')
    return pd.Series([_text(value) for value in values], dtype='object')


def _text(value):
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return value.hex().upper()
    if isinstance(value, str):
        return value
    read = getattr(value, 'read', None)
    if read is not None:
        value = read()
        return value.hex().upper() if isinstance(value, bytes) else value
    return str(value)


def floats(series):
    """Get the values of a numeric column as a float array, NaN missing."""
    return series.to_numpy(dtype='float64', na_value=np.nan)


def to_json(value):
    """Get a JSON-safe value."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, dt.datetime)):
        return value.strftime('%Y-%m-%dT%H:%M:%S')
    if isinstance(value, dt.date):
        return value.strftime('%Y-%m-%dT00:00:00')
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def text_values(series, kind):
    """Get a column as strings, the way it is shown and searched."""
    if kind == DATETIME:
        return series.dt.strftime('%Y-%m-%d %H:%M:%S')
    if kind == NUMERIC:
        return series.astype('object').map(
            lambda value: None if value is None or value is pd.NA
            or (isinstance(value, float) and math.isnan(value))
            else _number_text(value))
    return series


def _number_text(value):
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    return str(value)


class FilterError(ValueError):
    """A filter can not be applied."""


def mask(frame, kinds, filters=None, search=None):
    """Get the rows left by the column filters and the search.

    A filter is {column, op, value}; `op` is one of eq, ne, in, contains,
    starts, range ({min, max, max_inclusive}), null, notnull, or
    `duplicated` without a column (rows repeated in the sample).
    """
    result = pd.Series(True, index=frame.index)
    for item in filters or []:
        result &= _filter_mask(frame, kinds, item)
    if search:
        found = pd.Series(False, index=frame.index)
        term = str(search)
        for name in frame.columns:
            values = text_values(frame[name], kinds[name])
            found |= values.astype('object').fillna('').astype(str) \
                .str.contains(term, case=False, regex=False)
        result &= found
    return result


def _filter_mask(frame, kinds, item):
    op = item.get('op')
    if op == 'duplicated':
        return frame.duplicated(keep=False)
    name = item.get('column')
    if name not in frame.columns:
        raise FilterError(f'Unknown column {name}')
    series = frame[name]
    kind = kinds[name]
    value = item.get('value')
    if op == 'null':
        return series.isna()
    if op == 'notnull':
        return series.notna()
    if op in ('eq', 'ne', 'in'):
        values = value if op == 'in' else [value]
        values = [_typed(item, kind) for item in values]
        present = [item for item in values if item is not None]
        result = series.isin(present).fillna(False).astype(bool)
        if len(present) < len(values):
            result |= series.isna()
        return ~result if op == 'ne' else result
    if op in ('contains', 'starts'):
        text = text_values(series, kind).astype('object').fillna('')
        text = text.astype(str)
        if op == 'contains':
            return text.str.contains(str(value), case=False, regex=False)
        return text.str.lower().str.startswith(str(value).lower())
    if op == 'range':
        value = value or {}
        low = _typed(value.get('min'), kind)
        high = _typed(value.get('max'), kind)
        data = series
        if kind == NUMERIC:
            data = pd.Series(floats(series), index=series.index)
        result = series.notna()
        if low is not None:
            result &= (data >= low).fillna(False).astype(bool)
        if high is not None:
            if value.get('max_inclusive', True):
                result &= (data <= high).fillna(False).astype(bool)
            else:
                result &= (data < high).fillna(False).astype(bool)
        return result
    raise FilterError(f'Unknown filter {op}')


def _typed(value, kind):
    if value is None:
        return None
    try:
        if kind == NUMERIC:
            return float(value)
        if kind == DATETIME:
            return pd.Timestamp(value)
    except (TypeError, ValueError):
        raise FilterError(f'{value!r} is not a valid {kind} value')
    return str(value)


def order(frame, positions, sort):
    """Get the positions sorted by [{column, desc}], missing values last."""
    if not sort:
        return positions
    subset = frame.iloc[positions]
    names = [item['column'] for item in sort
             if item.get('column') in frame.columns]
    if not names:
        return positions
    ascending = [not item.get('desc') for item in sort
                 if item.get('column') in frame.columns]
    subset = subset.assign(_position=positions)
    subset = subset.sort_values(names, ascending=ascending,
                                na_position='last', kind='stable')
    return subset['_position'].to_numpy()
