"""Contains scheduler event journal.

Every control run request (scheduled, manual, catch-up, iteration and
cascade) and every scheduled fire missed while no scheduler was running is
recorded as one row of `rapo_scheduler_event`. The row moves through event
types while the request is served:

* `FIRED` - the run is initiated and queued for an execution slot;
* `STARTED` - the run got a slot and its process was spawned;
* `MISSED` - the fire fell into scheduler downtime and was not run;
* `FAILED` - the run could not be initiated or spawned;
* `CANCELED` - the run was canceled or dropped before it started.

Outcome of a started run is not duplicated here, it is the `rapo_log` row
linked by `process_id`.
"""

import datetime as dt

import sqlalchemy as sa

from ..database import db


FIRED = 'FIRED'
STARTED = 'STARTED'
MISSED = 'MISSED'
FAILED = 'FAILED'
CANCELED = 'CANCELED'

SCHEDULE = 'SCHEDULE'
MANUAL = 'MANUAL'
CATCHUP = 'CATCHUP'
ITERATION = 'ITERATION'
CASCADE = 'CASCADE'

MESSAGE_LENGTH = 4000


def to_datetime(timestamp):
    """Convert control timestamp to naive local datetime."""
    if timestamp is None:
        return None
    return dt.datetime.fromtimestamp(int(timestamp))


def record(control_id, trigger_type, event_type, scheduled_time=None,
           process_id=None, message=None, runner=None, start_time=None):
    """Insert new event and get its ID."""
    table = db.tables.scheduler_event
    now = dt.datetime.now()
    insert = table.insert().values(control_id=control_id,
                                   trigger_type=trigger_type,
                                   event_type=event_type,
                                   scheduled_time=scheduled_time,
                                   event_time=now,
                                   start_time=start_time,
                                   updated=now,
                                   process_id=process_id,
                                   message=_truncate(message),
                                   runner=runner)
    result = db.execute(insert)
    return int(result.inserted_primary_key[0])


def update(event_id, **values):
    """Update event by ID."""
    if 'message' in values:
        values['message'] = _truncate(values['message'])
    table = db.tables.scheduler_event
    update = (table.update()
                   .values(**values, updated=dt.datetime.now())
                   .where(table.c.event_id == event_id))
    db.execute(update)


def read(event_id):
    """Get event by ID as a dictionary."""
    table = db.tables.scheduler_event
    select = table.select().where(table.c.event_id == event_id)
    return db.execute(select, as_dict=True)


def read_events(control_name=None, event_type=None, trigger_type=None,
                date_from=None, date_to=None, limit=500):
    """Get events with their control and run details, latest first."""
    event = db.tables.scheduler_event
    config = db.tables.config
    log = db.tables.log
    join = (event.join(config, event.c.control_id == config.c.control_id,
                       isouter=True)
                 .join(log, event.c.process_id == log.c.process_id,
                       isouter=True))
    select = (sa.select(event.c.event_id,
                        event.c.control_id,
                        config.c.control_name,
                        config.c.control_type,
                        event.c.trigger_type,
                        event.c.event_type,
                        event.c.scheduled_time,
                        event.c.event_time,
                        event.c.start_time,
                        event.c.process_id,
                        event.c.message,
                        event.c.runner,
                        log.c.status,
                        log.c.date_from,
                        log.c.date_to,
                        log.c.start_date,
                        log.c.end_date)
                .select_from(join)
                .order_by(event.c.event_id.desc())
                .limit(limit))
    if control_name:
        select = select.where(config.c.control_name == control_name)
    if event_type:
        select = select.where(event.c.event_type == event_type)
    if trigger_type:
        select = select.where(event.c.trigger_type == trigger_type)
    if date_from:
        select = select.where(event.c.event_time >= date_from)
    if date_to:
        select = select.where(event.c.event_time < date_to)
    return db.execute(select, as_table=True)


def read_orphans(runner):
    """Get events of this runner whose runs are still marked as active."""
    event = db.tables.scheduler_event
    log = db.tables.log
    join = event.join(log, event.c.process_id == log.c.process_id)
    select = (sa.select(event.c.event_id, event.c.process_id, log.c.status)
                .select_from(join)
                .where(event.c.runner == runner,
                       sa.or_(log.c.status.in_(['I', 'W', 'S', 'P', 'F']),
                              log.c.status.is_(None))))
    return db.execute(select, as_table=True)


def purge(days):
    """Delete events older than the given number of days."""
    event = db.tables.scheduler_event
    border = dt.datetime.now()-dt.timedelta(days=days)
    delete = event.delete().where(event.c.event_time < border)
    return db.execute(delete).rowcount


def _truncate(message):
    if message is None:
        return None
    message = str(message)
    if len(message) > MESSAGE_LENGTH:
        message = message[:MESSAGE_LENGTH-3]+'...'
    return message
