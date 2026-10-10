"""Contains the stored instance health: one row per server, group and minute.

rapo_health_minute keeps the one-minute aggregates of every group (os, db,
and files: the files waiting in the input directories) of every server for
[HEALTH] history_days, so that the history outlives a restart and spans
longer than the memory's can be shown. This module is the only code that
knows the table.
"""

import datetime as dt
import json

import sqlalchemy as sa

from ..database import db


TABLE = 'rapo_health_minute'
MAX_CHARS = 4000
# Left out of a minute that does not fit, the longest first.
LIST_FIELDS = ('tablespaces', 'disks', 'errors')


def server_name():
    """Get this server's name, as its runs are marked (host:API.port)."""
    from ..core.runner import get_runner_name
    return get_runner_name()


def minute_of(point):
    """Get the minute (a datetime) of a minute aggregate (`t` at hh:mm:30)."""
    return dt.datetime.fromisoformat(point['t'][:16])


def encode(point):
    """Get a minute as the JSON text stored, at most MAX_CHARS long."""
    point = dict(point)
    text = json.dumps(point, separators=(',', ':'), default=str)
    for field in LIST_FIELDS:
        if len(text) <= MAX_CHARS:
            break
        point.pop(field, None)
        text = json.dumps(point, separators=(',', ':'), default=str)
    if len(text) > MAX_CHARS:
        point = {key: value for key, value in point.items()
                 if isinstance(value, (int, float, str)) and len(str(value)) < 64}
        text = json.dumps(point, separators=(',', ':'), default=str)
    return text


def write(server, rows):
    """Store minutes, [(group, point)]; a minute stored already is kept."""
    if not rows:
        return
    statement = sa.text(f"""
        merge into {TABLE} t
        using (select :server server, :sample_group sample_group,
                      :minute minute from dual) s
           on (t.server = s.server and t.sample_group = s.sample_group
               and t.minute = s.minute)
         when not matched then
              insert (server, sample_group, minute, content)
              values (:server, :sample_group, :minute, :content)""")
    params = [{'server': server, 'sample_group': group,
               'minute': minute_of(point), 'content': encode(point)}
              for group, point in rows]
    with db.engine.begin() as connection:
        connection.execute(statement, params)


def read(server, group, since):
    """Get the stored minutes of a server's group since a moment, oldest
    first.
    """
    statement = sa.text(
        f'select content from {TABLE} where server = :server '
        'and sample_group = :sample_group and minute >= :since '
        'order by minute').bindparams(server=server, sample_group=group,
                                      since=since)
    return [json.loads(row['content'])
            for row in db.execute(statement, as_table=True)]


def read_any(group, since):
    """Get the stored minutes of a group of any server since a moment, as
    (minute, point), oldest first; a minute stored by several servers once
    per server.
    """
    statement = sa.text(
        f'select minute, content from {TABLE} '
        'where sample_group = :sample_group and minute >= :since '
        'order by minute').bindparams(sample_group=group, since=since)
    return [(row['minute'], json.loads(row['content']))
            for row in db.execute(statement, as_table=True)]


def purge(before):
    """Delete the minutes older than a moment, of every server."""
    statement = sa.text(f'delete from {TABLE} where minute < :before'
                        ).bindparams(before=before)
    return db.execute(statement).rowcount


def _field(field):
    if not field.isidentifier():
        raise ValueError(f'Not a field name: {field}')
    return f"json_value(content, '$.{field}' returning number)"


def read_daily_max(group, field, since):
    """Get {date: the highest value of a numeric field} per day of a group's
    stored minutes (any server) since a moment.
    """
    statement = sa.text(f"""
        select trunc(minute) day, max({_field(field)}) value
          from {TABLE}
         where sample_group = :sample_group and minute >= :since
         group by trunc(minute)""").bindparams(sample_group=group, since=since)
    return {row['day'].date(): row['value']
            for row in db.execute(statement, as_table=True)}


def read_value_near(group, field, moment, minutes=10):
    """Get a numeric field of the group's stored minute nearest a moment
    (within `minutes`), the highest of the servers at it; None without one.
    """
    statement = sa.text(f"""
        select max({_field(field)}) keep (dense_rank first
                                          order by abs(minute - :moment)) value
          from {TABLE}
         where sample_group = :sample_group
           and minute between :since and :until""").bindparams(
        sample_group=group, moment=moment,
        since=moment - dt.timedelta(minutes=minutes),
        until=moment + dt.timedelta(minutes=minutes))
    return db.execute(statement, as_scalar=True)
