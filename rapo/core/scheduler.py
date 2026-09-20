"""Contains RAPO scheduler interface."""

import datetime as dt
import getpass
import os
import platform
import threading as th
import time
import uuid

import sqlalchemy as sa

from ..database import db
from ..config import config
from ..logger import logger
from ..reader import reader

from . import journal
from . import schedule
from .control import Control
from .runner import runner, get_runner_name


LEASE_INTERVAL = 10
CONFIG_CHECK_INTERVAL = 5
# Fires found later than this after their time (e.g. after the host was
# suspended) are recorded as missed instead of being run.
LATE_TOLERANCE = 60
MISSED_LIMIT = 100


def get_setting(name, default=None):
    """Get SCHEDULER option or default when it is not set."""
    if config.check('SCHEDULER'):
        value = config['SCHEDULER'].get(name)
        if value is not None:
            return value
    return default


def is_enabled():
    """Check whether this server should run the scheduler.

    RAPO_SCHEDULER environment variable (0/1) overrides the `enabled` option,
    which is how `rapo-server start dev` keeps the scheduler off by default.
    """
    override = os.environ.get('RAPO_SCHEDULER')
    if override is not None:
        return override.strip().lower() in ('1', 'true', 'y', 'yes')
    return get_setting('enabled', True) is not False


class Scheduler:
    """Represents application scheduler running inside the web server.

    Only one server at a time runs the scheduler. It holds a lease on the
    `rapo_scheduler` row renewed every few seconds. Other enabled servers
    stay on standby and take over when the lease expires. Scheduler can be
    stopped and started from the UI, which is persisted in the `disabled`
    flag of the same row and applies to all servers.

    Instead of checking every second, the scheduler computes the next fire of
    every scheduled control and sleeps until the earliest one, or until the
    configuration changes. Every fire between two wake-ups is served, so a
    slow iteration never skips fires. Each fire is submitted to the run
    manager with its exact scheduled time as the control timestamp.

    Attributes
    ----------
    enabled : bool
        Whether this server runs the scheduler at all (rapo.ini).
    leader : bool
        Whether this server currently holds the scheduler lease.
    schedule : dict
        Schedules of active controls by control name.
    """

    def __init__(self):
        self.enabled = is_enabled()
        self.instance_id = f'{get_runner_name()}:{os.getpid()}:' \
                           f'{uuid.uuid4().hex[:8]}'
        self.server = platform.node()
        self.username = getpass.getuser()
        self.pid = os.getpid()

        self.leader = False
        self.leader_since = None
        self.active = False
        self.thread = None
        self.wake = th.Event()
        self.reload = True

        self.schedule = {}
        self.cursor = None
        self.signature = None
        self.loaded = 0
        self.checked = 0
        self.heartbeat = 0
        self.next_maintenance = None
        self.next_report = None
        self.last_fire = None
        self.warned = False
        self.listeners = []

    def start(self):
        """Start scheduler thread."""
        if not self.enabled or self.active:
            return
        self.active = True
        self.thread = th.Thread(name='Scheduler', target=self._run,
                                daemon=True)
        self.thread.start()
        logger.info(f'Scheduler started as {self.instance_id}')

    def stop(self):
        """Stop scheduler thread releasing the lease."""
        if not self.active:
            return
        self.active = False
        self.wake.set()
        if self.thread:
            self.thread.join(15)
        self._release()
        logger.info('Scheduler stopped')

    def disable(self):
        """Stop scheduling on all servers until enabled again."""
        self._set_disabled(True)
        self._release()
        self.wake.set()
        self._notify()

    def enable(self):
        """Resume scheduling from now on, without recording missed fires."""
        self._set_disabled(False)
        self.wake.set()
        self._notify()

    def refresh(self):
        """Request reload of the control configuration."""
        self.reload = True
        self.wake.set()

    def status(self):
        """Get scheduler status report."""
        record = reader.read_scheduler_record() or {}
        disabled = record.get('disabled') == 'Y'
        timeout = get_setting('lease_timeout', 60)
        heartbeat = record.get('heartbeat')
        alive = (record.get('status') == 'Y' and heartbeat is not None
                 and (dt.datetime.now()-heartbeat).total_seconds() < timeout)
        if not self.enabled:
            state = 'off'
        elif disabled:
            state = 'stopped'
        elif self.leader:
            state = 'running'
        elif alive:
            state = 'standby'
        else:
            state = 'starting'
        return {
            'state': state,
            'enabled': self.enabled,
            'disabled': disabled,
            'leader': self.leader,
            'instance_id': self.instance_id,
            'holder': {
                'instance_id': record.get('instance_id'),
                'server': record.get('server'),
                'username': record.get('username'),
                'pid': record.get('pid'),
                'start_date': record.get('start_date'),
                'stop_date': record.get('stop_date'),
                'heartbeat': heartbeat,
                'alive': alive,
            },
            'scheduled_controls': len(self.schedule) if self.leader else None,
            'last_fire': self.last_fire,
            'next_maintenance': (dt.datetime.fromtimestamp(
                self.next_maintenance) if self.next_maintenance else None),
            'lease_timeout': timeout,
            'server_time': dt.datetime.now().replace(microsecond=0),
        }

    def _run(self):
        while self.active:
            try:
                self._step()
            except Exception:
                logger.error()
                self.wake.wait(LEASE_INTERVAL)
        logger.debug('Scheduler thread finished')

    def _step(self):
        self.wake.clear()
        now = time.time()
        if now-self.heartbeat >= LEASE_INTERVAL or not self.leader:
            self._lease()
        if not self.leader:
            self.wake.wait(LEASE_INTERVAL)
            return
        self._load(now)
        self._fire()
        if not self.leader:
            # The lease was lost during this pass, so the maintenance of the
            # new holder is not duplicated here.
            return
        self._maintain(now)
        self.wake.wait(self._delay())

    def _lease(self):
        """Acquire or renew the scheduler lease."""
        self.heartbeat = time.time()
        now = dt.datetime.now()
        table = db.tables.scheduler
        if self.leader:
            update = (table.update()
                           .values(heartbeat=now)
                           .where(table.c.instance_id == self.instance_id,
                                  table.c.status == 'Y',
                                  table.c.disabled == 'N'))
            if db.execute(update).rowcount == 1:
                return
            logger.warning('Scheduler lease lost or scheduler stopped')
            self._release()
            return

        record = reader.read_scheduler_record()
        if not record or record['disabled'] == 'Y':
            return
        timeout = get_setting('lease_timeout', 60)
        if record['status'] == 'Y' and record['instance_id'] is None:
            # Row left by a standalone rapo-scheduler of an older version.
            pid = record['pid']
            if record['server'] == self.server and pid and \
                    not _pid_exists(int(pid)):
                logger.info('Taking over stale standalone scheduler lease')
            else:
                if not self.warned:
                    logger.warning('Standalone rapo-scheduler seems to be '
                                   f'running at {record["server"]} PID '
                                   f'{pid}, stop it to start this one')
                self.warned = True
                return
        elif (record['status'] == 'Y'
              and record['instance_id'] != self.instance_id
              and record['heartbeat'] is not None
              and (now-record['heartbeat']).total_seconds() < timeout
              and not (record['server'] == self.server and record['pid']
                       and not _pid_exists(int(record['pid'])))):
            # Holder is alive, or on another host and its lease is fresh.
            return

        conditions = [table.c.disabled == 'N']
        for column in ('instance_id', 'heartbeat', 'status'):
            value = record[column]
            column = table.c[column]
            conditions.append(column.is_(None) if value is None
                              else column == value)
        update = (table.update()
                       .values(server=self.server,
                               username=self.username,
                               pid=self.pid,
                               instance_id=self.instance_id,
                               heartbeat=now,
                               start_date=now,
                               stop_date=None,
                               status='Y')
                       .where(*conditions))
        if db.execute(update).rowcount != 1:
            return

        self.leader = True
        self.leader_since = now
        self.reload = True
        self.cursor = now.replace(microsecond=0)
        since = max([date for date in (record['heartbeat'],
                                       record['stop_date'])
                     if date is not None], default=None)
        self._record_missed(since, self.cursor)
        interval = get_setting('maintenance_interval')
        self.next_maintenance = _next_multiple(interval)
        interval = get_setting('database_report_interval')
        self.next_report = _next_multiple(interval)
        logger.info(f'Scheduler lease acquired by {self.instance_id}')
        self._notify()

    def _release(self):
        if not self.leader:
            return
        self._resign()
        table = db.tables.scheduler
        now = dt.datetime.now()
        update = (table.update()
                       .values(stop_date=now, heartbeat=now, status='N')
                       .where(table.c.instance_id == self.instance_id))
        try:
            db.execute(update)
        except Exception:
            logger.error()
        logger.info('Scheduler lease released')

    def _resign(self):
        self.leader = False
        self.leader_since = None
        self.schedule = {}
        self._notify()

    def _set_disabled(self, disabled):
        table = db.tables.scheduler
        values = {'disabled': 'Y' if disabled else 'N'}
        if not disabled:
            # Start from the UI resumes from now. Moving the marks the next
            # holder measures downtime from keeps that true on whichever
            # server takes the lease, not only on this one.
            now = dt.datetime.now()
            values.update(heartbeat=now, stop_date=now)
        update = table.update().values(**values)
        db.execute(update)
        logger.info(f'Scheduler {"stopped" if disabled else "started"} '
                    'from the UI')

    def _load(self, now):
        """Reload schedules when configuration changed."""
        interval = get_setting('refresh_interval', 300)
        if not self.reload and now-self.checked >= CONFIG_CHECK_INTERVAL:
            self.checked = now
            signature = _read_config_signature()
            if signature != self.signature:
                self.reload = True
        if not self.reload and now-self.loaded < interval:
            return
        # Read before the schedules, so that a change committed while they
        # are read is seen again by the next check instead of being hidden
        # by a signature that already includes it.
        signature = _read_config_signature()
        self.schedule = dict(schedule.read_all())
        self.signature = signature
        self.loaded = self.checked = now
        self.reload = False
        logger.debug(f'Schedule: {len(self.schedule)} jobs found')

    def _fire(self):
        """Submit every fire between the cursor and now."""
        now = dt.datetime.now().replace(microsecond=0)
        if now <= self.cursor:
            return
        border = now+dt.timedelta(seconds=1)
        fires = []
        for name, item in self.schedule.items():
            for moment in schedule.next_fire(item['schedule'], self.cursor,
                                             limit=MISSED_LIMIT,
                                             before=border):
                fires.append((moment, name, item['control_id']))
        self.cursor = now
        for moment, name, control_id in sorted(fires):
            # A pass that took longer than the lease renews it here instead of
            # at the next step, so a server that lost the lease while it was
            # busy does not submit fires the new holder has already recorded
            # as missed.
            if time.time()-self.heartbeat >= LEASE_INTERVAL:
                self._lease()
            if not self.leader:
                logger.warning('Scheduler lease lost, remaining fires of '
                               'this pass abandoned')
                break
            late = (now-moment).total_seconds()
            if late > LATE_TOLERANCE:
                journal.record(control_id, journal.SCHEDULE, journal.MISSED,
                               scheduled_time=moment,
                               message=f'Fire found {int(late)} seconds '
                                       'late, scheduler was not running.',
                               runner=runner.name)
                continue
            try:
                runner.submit(name, journal.SCHEDULE,
                              timestamp=moment.timestamp(),
                              cascade=True, iterations=True)
            except Exception as error:
                logger.error()
                journal.record(control_id, journal.SCHEDULE, journal.FAILED,
                               scheduled_time=moment, message=str(error),
                               runner=runner.name)
            self.last_fire = moment
        if fires:
            self._notify()

    def _record_missed(self, since, until):
        """Record fires that fell into scheduler downtime."""
        if since is None:
            return
        window = get_setting('missed_window_hours', 24)
        since = max(since, until-dt.timedelta(hours=window))
        if since >= until:
            return
        fires = []
        for name, item in schedule.read_all():
            for moment in schedule.next_fire(item['schedule'], since,
                                             limit=MISSED_LIMIT,
                                             before=until):
                fires.append((moment, item['control_id']))
        fires = sorted(fires)[-MISSED_LIMIT:]
        for moment, control_id in fires:
            journal.record(control_id, journal.SCHEDULE, journal.MISSED,
                           scheduled_time=moment,
                           message='Scheduler was not running.',
                           runner=runner.name)
        if fires:
            logger.warning(f'{len(fires)} missed fires recorded since '
                           f'{since:%Y-%m-%d %H:%M:%S}')

    def _maintain(self, now):
        if self.next_maintenance and now >= self.next_maintenance:
            interval = get_setting('maintenance_interval')
            self.next_maintenance = _next_multiple(interval)
            th.Thread(name='Maintainer', target=self._clean,
                      daemon=True).start()
        if self.next_report and now >= self.next_report:
            interval = get_setting('database_report_interval')
            self.next_report = _next_multiple(interval)
            report = db.engine.pool.status()
            logger.info(f'Database connection report: {report}')

    def _clean(self):
        logger.info('Starting maintenance')
        try:
            db.cleanup()
            config = db.tables.config
            select = config.select().order_by(config.c.control_id)
            for record in db.execute(select, as_records=True):
                try:
                    Control(name=record.control_name).clean()
                except Exception:
                    logger.error()
            days = get_setting('event_retention_days', 90)
            deleted = journal.purge(days)
            logger.info(f'{deleted} scheduler events older than {days} '
                        'days deleted')
        except Exception:
            logger.error()
        logger.info('Maintenance performed')

    def _delay(self):
        """Get seconds to sleep until the next thing to do."""
        now = time.time()
        wakes = [self.heartbeat+LEASE_INTERVAL,
                 self.checked+CONFIG_CHECK_INTERVAL]
        if self.next_maintenance:
            wakes.append(self.next_maintenance)
        if self.next_report:
            wakes.append(self.next_report)
        after = self.cursor
        for item in self.schedule.values():
            fire = schedule.next_fire(item['schedule'], after)
            if fire:
                wakes.append(fire[0].timestamp())
        return max(min(wakes)-now, 0)

    def _notify(self):
        for listener in self.listeners:
            try:
                listener()
            except Exception:
                logger.error()


def upcoming(hours=24, control_name=None, limit=1000):
    """Get upcoming fires of active scheduled controls.

    Returns
    -------
    fires : list of dict
        Fires ordered by time with control ID, name, type and group.
    """
    now = dt.datetime.now().replace(microsecond=0)
    until = now+dt.timedelta(hours=hours)
    fires = []
    for name, item in schedule.read_all():
        if control_name and name != control_name:
            continue
        for moment in schedule.next_fire(item['schedule'], now, limit=limit,
                                         before=until):
            fires.append({'scheduled_time': moment,
                          'control_id': item['control_id'],
                          'control_name': name,
                          'control_type': item['control_type'],
                          'control_group': item['control_group']})
    fires.sort(key=lambda fire: (fire['scheduled_time'],
                                 fire['control_name']))
    return fires[:limit]


def _read_config_signature():
    table = db.tables.config
    select = sa.select(sa.func.count(), sa.func.max(table.c.updated_date))
    return tuple(db.execute(select, as_one=True))


def _next_multiple(interval):
    """Get next epoch time that is a multiple of the interval."""
    if not interval:
        return None
    now = time.time()
    return (int(now)//interval+1)*interval


def _pid_exists(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


scheduler = Scheduler()
