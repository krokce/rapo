"""Contains web API live events pushed to UI over socket.io."""

import asyncio

import socketio
import sqlalchemy as sa

from .auth import check_token

from ...database import db
from ...logger import logger


INTERVAL = 2
MAX_IDS = 500

# Origin check is off because the dev proxy rewrites Host but not Origin;
# connections are guarded by the API token passed in the handshake instead.
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[])


class Watcher:
    """Watches application tables and notifies connected UI clients.

    Scheduler and control processes write to the database, not to the web
    API process, so changes are detected by comparing a cheap signature of
    each table on every tick. The watcher only runs while clients are
    connected.
    """

    def __init__(self):
        self.clients = 0
        self.task = None
        self.loop = None
        self.wake = None
        self.states = {}

    def start(self):
        """Start watching if not already started."""
        if self.task is None:
            self.loop = asyncio.get_running_loop()
            self.wake = asyncio.Event()
            self.task = sio.start_background_task(self.run)

    def poke(self):
        """Request an immediate check, callable from any thread."""
        loop, wake = self.loop, self.wake
        if self.task is None or loop is None:
            return
        try:
            loop.call_soon_threadsafe(wake.set)
        except RuntimeError:
            pass

    async def run(self):
        """Check tables every tick until the last client disconnects."""
        logger.debug('Live events watcher started')
        while self.clients > 0:
            try:
                await self.check()
            except Exception:
                logger.error()
            try:
                await asyncio.wait_for(self.wake.wait(), INTERVAL)
            except asyncio.TimeoutError:
                pass
            self.wake.clear()
        self.task = None
        self.states = {}
        logger.debug('Live events watcher stopped')

    async def check(self):
        """Emit events for tables changed since the previous check."""
        runs, controls = await asyncio.to_thread(self.read)
        if runs:
            await sio.emit('runs:changed', runs)
        if controls:
            await sio.emit('controls:changed', controls)

    def read(self):
        log = db.tables.log
        config = db.tables.config
        runs = self.diff(log, log.c.process_id, log.c.updated)
        if runs:
            names = []
            if runs['ids']:
                join = log.join(config,
                                log.c.control_id == config.c.control_id)
                select = (sa.select(config.c.control_name).distinct()
                            .select_from(join)
                            .where(log.c.process_id.in_(runs['ids'])))
                names = [name for name, in db.execute(select,
                                                      as_records=True)]
            runs = {'resync': runs['resync'],
                    'process_ids': runs['ids'],
                    'control_names': names}
        controls = self.diff(config, config.c.control_id,
                             config.c.updated_date)
        if controls:
            controls = {'resync': controls['resync'],
                        'control_ids': controls['ids']}
        return runs, controls

    def diff(self, table, id_column, updated_column):
        """Get IDs of rows changed since the previous call.

        Returns None when nothing changed. New rows are found by ID and
        updated rows by update date. As update date has 1 second precision,
        rows of the latest second are kept as fingerprints and compared again
        on the next call, so repeated updates within one second are not
        missed. Deletions can not be pinpointed, so they only set resync flag.
        """
        select = sa.select(sa.func.count(), sa.func.max(id_column),
                           sa.func.max(updated_column))
        stats = tuple(db.execute(select, as_one=True))
        count, max_id, max_updated = stats
        last_stats, last_rows = self.states.get(table.name, (None, None))
        if last_stats is not None:
            last_count, last_id, last_updated = last_stats
        else:
            last_count, last_id, last_updated = stats

        conditions = []
        if last_id is not None:
            conditions.append(id_column > last_id)
        since = last_updated if last_updated is not None else max_updated
        if since is not None:
            conditions.append(updated_column >= since)
        fingerprint = [
            sa.func.length(column)
            if isinstance(column.type, (sa.Text, sa.LargeBinary)) else column
            for column in table.columns
        ]
        rows = {}
        if conditions:
            select = sa.select(id_column, updated_column, *fingerprint)\
                       .where(sa.or_(*conditions))
            for row in db.execute(select, as_records=True):
                rows[int(row[0])] = tuple(row[1:])
        self.states[table.name] = (stats, {
            id: row for id, row in rows.items()
            if max_updated is not None and row[0] is not None
            and row[0] >= max_updated
        })
        if last_stats is None:
            return None

        ids = [id for id, row in rows.items() if last_rows.get(id) != row]
        inserted = len([id for id in rows if last_id is None or id > last_id])
        resync = (count != last_count + inserted
                  or any(id not in rows for id in last_rows))
        if not ids and not resync:
            return None
        if len(ids) > MAX_IDS:
            return {'resync': True, 'ids': []}
        return {'resync': resync, 'ids': ids}


watcher = Watcher()


@sio.event
async def connect(sid, environ, auth):
    token = auth.get('token') if isinstance(auth, dict) else None
    if not check_token(token):
        raise socketio.exceptions.ConnectionRefusedError('Unauthorized Access')
    watcher.clients += 1
    watcher.start()


@sio.event
async def disconnect(sid, *args):
    watcher.clients = max(watcher.clients - 1, 0)


def poke():
    """Request an immediate check of changes, e.g. after an API mutation."""
    watcher.poke()
