"""Contains the time spans of the Dashboard and their buckets.

A span is the last 24 whole hours (the current one included) in hours, or the
last 7 or 30 days (today included) in days. The same windows are taken on the
app server's clock (runs, scheduler, KPIs) and on the database's (files), each
from its own `now`.
"""

import datetime as dt


SPANS = {'24h': ('hour', 24), '7d': ('day', 7), '30d': ('day', 30)}
DEFAULT_SPAN = '7d'


def check(span):
    """Raise ValueError for a span that is not offered."""
    if span not in SPANS:
        raise ValueError(f'span is one of {", ".join(SPANS)}')
    return span


def unit(span):
    """Get the bucket unit of a span: hour or day."""
    return SPANS[span][0]


def window(span, now):
    """Get the start of a span's window and the start of each bucket.

    Returns
    -------
    start : datetime
        The start of the first bucket.
    buckets : list of datetime
        The start of every bucket, oldest first, the current one last.
    """
    bucket_unit, count = SPANS[span]
    if bucket_unit == 'hour':
        last = now.replace(minute=0, second=0, microsecond=0)
        step = dt.timedelta(hours=1)
    else:
        last = dt.datetime.combine(now.date(), dt.time())
        step = dt.timedelta(days=1)
    start = last - step * (count - 1)
    return start, [start + step * index for index in range(count)]


def truncate(moment, bucket_unit):
    """Get the start of the bucket of a moment."""
    if bucket_unit == 'hour':
        return moment.replace(minute=0, second=0, microsecond=0)
    return dt.datetime.combine(moment.date(), dt.time())


def labels(buckets, bucket_unit):
    """Get the buckets as the naive ISO texts the UI slices."""
    if bucket_unit == 'hour':
        return [bucket.isoformat() for bucket in buckets]
    return [bucket.date().isoformat() for bucket in buckets]


def index(buckets):
    """Get {bucket start: position}, to place values into series."""
    return {bucket: position for position, bucket in enumerate(buckets)}
