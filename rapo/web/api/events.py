"""Contains web API live events pushed to UI over socket.io."""

import asyncio

import socketio
import sqlalchemy as sa

from . import auth

from ...database import db
from ...logger import logger


INTERVAL = 2
MAX_IDS = 500
# Seconds between checks that the token of every connection is still valid.
SWEEP_INTERVAL = 30

# The rooms each event goes to: a connection is in the room of every area its
# token may view (`area:<name>`), so it hears only of what it may look at.
ROOMS = {
    'runs:changed': ('runs', 'controls', 'kpis', 'scheduler', 'dashboard'),
    'controls:changed': ('controls', 'runs', 'kpis', 'scheduler',
                         'dashboard'),
    'scheduler:changed': ('scheduler', 'runs', 'controls', 'dashboard'),
    'datasources:changed': ('datasources', 'files', 'dashboard'),
    'discrepancy:progress': ('data',),
    'health:level': ('instance', 'dashboard'),
}


def rooms(event):
    return [f'area:{area}' for area in ROOMS[event]]


def owner_room(token_id):
    """The room of the connections of one token (None: the master token)."""
    return 'token:master' if token_id is None else f'token:{token_id}'

# Origin check is off because the dev proxy rewrites Host but not Origin;
# connections are guarded by the API token passed in the handshake instead.
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[])


class Watcher:
    """Watches application tables and notifies connected UI clients.

    Control processes write to the database, not to the web API process,
    so changes are detected by comparing a cheap signature of each table on
    every tick. The watcher only runs while clients are connected.
    """

    def __init__(self):
        self.clients = 0
        self.task = None
        self.loop = None
        self.wake = None
        self.states = {}
        self.scheduler_changed = False
        self.datasources = None
        # The token and Caller of every connection, by sid.
        self.callers = {}
        self.swept = 0
        # Called when a client connects, e.g. to refresh what it will ask for.
        self.connect_listeners = []
        # Called with the kind of a change before it is emitted (runs,
        # controls, scheduler or a kind of datasources:changed), so that what
        # was computed from the old state is not handed out after the event.
        self.change_listeners = []

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
        self.datasources = None
        logger.debug('Live events watcher stopped')

    async def check(self):
        """Emit events for tables changed since the previous check."""
        await self.sweep()
        changed, self.scheduler_changed = self.scheduler_changed, False
        runs, controls, events = await asyncio.to_thread(self.read)
        for kind in await asyncio.to_thread(self.read_datasources):
            self.changed(kind)
            await sio.emit('datasources:changed', {'kind': kind},
                           room=rooms('datasources:changed'))
        if runs:
            self.changed('runs')
            await sio.emit('runs:changed', runs, room=rooms('runs:changed'))
        if controls:
            self.changed('controls')
            await sio.emit('controls:changed', controls,
                           room=rooms('controls:changed'))
        if events or changed:
            self.changed('scheduler')
            await sio.emit('scheduler:changed',
                           {'event_ids': events['ids'] if events else []},
                           room=rooms('scheduler:changed'))

    async def sweep(self):
        """Disconnect the connections whose token was revoked, expired or
        changed since they connected; a changed one reconnects with its new
        scopes, the others are refused."""
        now = asyncio.get_running_loop().time()
        if now - self.swept < SWEEP_INTERVAL:
            return
        self.swept = now
        for sid, (token, caller) in list(self.callers.items()):
            if caller.master:
                continue
            try:
                current = await asyncio.to_thread(auth.resolve, token,
                                                  touch=False)
            except auth.TokenError:
                # The database failed: check again at the next sweep.
                continue
            if current != caller:
                logger.info(f'Live connection of {caller.display} closed: '
                            f'its token was changed or is no longer valid')
                await sio.disconnect(sid)

    def changed(self, kind):
        """Tell the change listeners about a kind of change."""
        for listener in self.change_listeners:
            try:
                listener(kind)
            except Exception:
                logger.error()

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
        event = db.tables.scheduler_event
        events = self.diff(event, event.c.event_id, event.c.updated)
        return runs, controls, events

    def read_datasources(self):
        """Get what of PDI Core changed, by anyone: the kinds of change.

        `config` the datasources, `state` the lane locks, `files` the files
        loaded today.
        """
        from ...pdi import pdi
        if not pdi.available:
            return []
        signatures = {'config': pdi.signature(),
                      'state': pdi.state_signature(),
                      'files': pdi.files_signature()}
        previous = self.datasources or {}
        self.datasources = signatures
        return [kind for kind, value in signatures.items()
                if kind in previous and previous[kind] != value]

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
main_loop = None


@sio.event
async def connect(sid, environ, data):
    token = data.get('token') if isinstance(data, dict) else None
    address = environ.get('REMOTE_ADDR')
    try:
        caller = await asyncio.to_thread(auth.resolve, token, address)
    except auth.TokenError as error:
        raise socketio.exceptions.ConnectionRefusedError(str(error))
    if caller is None:
        raise socketio.exceptions.ConnectionRefusedError('Unauthorized Access')
    watcher.callers[sid] = (token, caller)
    await sio.enter_room(sid, owner_room(caller.token_id))
    for area in auth.scope_rules.AREAS:
        if caller.allows(area, 'view'):
            await sio.enter_room(sid, f'area:{area}')
    watcher.clients += 1
    watcher.start()
    for listener in watcher.connect_listeners:
        listener()


@sio.event
async def disconnect(sid, *args):
    watcher.callers.pop(sid, None)
    watcher.clients = max(watcher.clients - 1, 0)


def poke():
    """Request an immediate check of changes, e.g. after an API mutation."""
    watcher.poke()


def poke_scheduler():
    """Notify clients about a scheduler or run manager state change."""
    watcher.scheduler_changed = True
    watcher.poke()


def bind(loop):
    """Remember the server's event loop, for emits from other threads."""
    global main_loop
    main_loop = loop


def emit_analysis(payload):
    """Push an analysis session's state to the connections of its owner's
    token, from any thread.

    Sessions are private to a page, which picks its own by `session_id`.
    """
    loop = main_loop
    if loop is None or watcher.clients <= 0:
        return
    payload = dict(payload)
    room = owner_room(payload.pop('owner', None))
    try:
        asyncio.run_coroutine_threadsafe(
            sio.emit('analysis:progress', payload, room=room), loop)
    except RuntimeError:
        pass


def emit_discrepancy(payload):
    """Push a discrepancy analysis job's state to the clients, from any
    thread; a page picks its own by process_id, side and result_type.
    """
    loop = main_loop
    if loop is None or watcher.clients <= 0:
        return
    try:
        asyncio.run_coroutine_threadsafe(
            sio.emit('discrepancy:progress', payload,
                     room=rooms('discrepancy:progress')), loop)
    except RuntimeError:
        pass


def emit_datasources(kind='status'):
    """Tell the clients that the datasources changed, from any thread.

    `kind` is `status` for the files waiting (the scanner), `config` for the
    configuration, `summary` for the Dashboard's file log summary.
    """
    watcher.changed(kind)
    loop = main_loop
    if loop is None or watcher.clients <= 0:
        return
    try:
        asyncio.run_coroutine_threadsafe(
            sio.emit('datasources:changed', {'kind': kind},
                     room=rooms('datasources:changed')), loop)
    except RuntimeError:
        pass


HEALTH_ROOM = 'health'


@sio.on('health:join')
async def health_join(sid, *args):
    """Send the instance health samples to this client, while it looks
    (Instance details or the Dashboard)."""
    _, caller = watcher.callers.get(sid, (None, None))
    if caller and (caller.allows('instance', 'view')
                   or caller.allows('dashboard', 'view')):
        await sio.enter_room(sid, HEALTH_ROOM)


@sio.on('health:leave')
async def health_leave(sid, *args):
    await sio.leave_room(sid, HEALTH_ROOM)


def emit_health(kind, payload):
    """Push an instance health sample to the clients showing it, or a change
    of the worst level to every client, from any thread.
    """
    loop = main_loop
    if loop is None or watcher.clients <= 0:
        return
    if kind == 'sample':
        coroutine = sio.emit('health:sample', payload, room=HEALTH_ROOM)
    else:
        coroutine = sio.emit('health:level', payload,
                             room=rooms('health:level'))
    try:
        asyncio.run_coroutine_threadsafe(coroutine, loop)
    except RuntimeError:
        coroutine.close()
