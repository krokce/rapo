"""Contains the API tokens the master token issues (rapo_api_token).

A token is `rapo_` + 43 URL-safe characters (256 random bits). Only its
SHA-256 is stored, with the first characters for display, so a token is
shown once, when it is created or regenerated. Validated rows are kept in
memory for `[API] token_cache_seconds`; a change made here clears them at
once, other servers sharing the database see it after that time.

This module is the only code that knows the table. Every write is logged.
"""

import datetime as dt
import hashlib
import json
import re
import secrets
import threading
import time

import sqlalchemy as sa

from ...config import config
from ...database import db
from ...logger import logger
from ... import options

from . import scopes as scope_rules

TABLE = 'rapo_api_token'
PREFIX = 'rapo_'
PREFIX_SHOWN = 12
DURATIONS = {'1m': 1, '6m': 6, '1y': 12, 'unlimited': None}
TOUCH_SECONDS = 60
EMAIL_PATTERN = re.compile(r'[^@\s]+@[^@\s]+')
COLUMNS = ('token_id, token_prefix, user_name, user_email, label, scopes, '
           'free_sql, expires_at, revoked_at, last_used_at, last_used_ip, '
           'created_date, updated_date')


class TokenError(Exception):
    """A token request that can not be done, with its HTTP status."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def generate():
    """Get a new random token."""
    return PREFIX + secrets.token_urlsafe(32)


def digest(token):
    """Get the SHA-256 of a token as hex, the form it is stored in."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def add_months(moment, months):
    """Get the same day `months` later, the month's last day if it has none."""
    month = moment.month - 1 + months
    year = moment.year + month // 12
    month = month % 12 + 1
    for day in (moment.day, 30, 29, 28):
        try:
            return moment.replace(year=year, month=month, day=day)
        except ValueError:
            continue


def expiry(duration, start=None):
    """Get the expiry of a duration key from now (None: unlimited)."""
    if duration not in DURATIONS:
        raise TokenError(f'Unknown duration {duration!r} '
                         f'({", ".join(DURATIONS)}).')
    months = DURATIONS[duration]
    if months is None:
        return None
    start = start or dt.datetime.now().replace(microsecond=0)
    return add_months(start, months)


def _missing(error):
    if 'ORA-00942' in str(error) or 'ORA-02289' in str(error):
        raise TokenError('The API token table is missing: run '
                         'migrations/v0.8.7/upgrade.sql.', 503)


def _read(row):
    row = dict(row)
    try:
        row['scopes'] = json.loads(row.get('scopes') or '{}')
    except ValueError:
        row['scopes'] = {}
    row['free_sql'] = row.get('free_sql') == 'Y'
    return row


def describe(row, now=None):
    """Get a token row as the API answers it, with its state."""
    now = now or dt.datetime.now()
    result = {key: row.get(key) for key in (
        'token_id', 'token_prefix', 'user_name', 'user_email', 'label',
        'scopes', 'free_sql', 'expires_at', 'revoked_at', 'last_used_at',
        'last_used_ip', 'created_date', 'updated_date')}
    if row.get('revoked_at'):
        result['state'] = 'revoked'
    elif row.get('expires_at') and row['expires_at'] <= now:
        result['state'] = 'expired'
    else:
        result['state'] = 'active'
    return result


class Store:
    """The issued tokens: lookup with a cache, and their management."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {}
        self.touched = {}
        self.available = None

    @property
    def cache_seconds(self):
        value = config['API'].get('token_cache_seconds') \
            if config.check('API') else None
        if value is None:
            value = options.default('API', 'token_cache_seconds')
        return max(int(value), 0)

    def invalidate(self):
        """Forget the validated tokens, after a change."""
        with self.lock:
            self.cache.clear()

    def lookup(self, token):
        """Get the valid (not revoked, not expired) row of a token, or None.

        A missing table means no user token (the master token still works).
        Another database failure keeps a token validated before trusted and
        raises TokenError (503) for others, so a database hiccup never
        answers 401, which signs the UI out.
        """
        if not isinstance(token, str) or not token.startswith(PREFIX):
            return None
        key = digest(token)
        now = time.monotonic()
        with self.lock:
            cached = self.cache.get(key)
        if cached and now - cached[1] < self.cache_seconds:
            row = cached[0]
        else:
            try:
                row = self._fetch(key)
            except TokenError:
                if not cached:
                    raise
                row = cached[0]
            else:
                if row is not None:
                    with self.lock:
                        self.cache[key] = (row, now)
        if row is None or row.get('revoked_at'):
            return None
        if row.get('expires_at') and row['expires_at'] <= dt.datetime.now():
            return None
        return row

    def _fetch(self, key):
        statement = sa.text(f'select {COLUMNS} from {TABLE} '
                            f'where token_hash = :hash')
        try:
            row = db.execute(statement.bindparams(hash=key), as_dict=True)
        except sa.exc.DatabaseError as error:
            if self.available is not False:
                logger.warning(f'API tokens can not be read: {error}')
            self.available = False
            if 'ORA-00942' in str(error):
                return None
            raise TokenError('API tokens can not be checked now: the '
                             'database failed.', 503)
        self.available = True
        return _read(row) if row else None

    def touch(self, row, address):
        """Note that a token was used, at most once a minute per token, in a
        thread so the request does not wait for it."""
        token_id = row['token_id']
        now = time.monotonic()
        with self.lock:
            if now - self.touched.get(token_id, -TOUCH_SECONDS) \
                    < TOUCH_SECONDS:
                return
            self.touched[token_id] = now

        def write():
            statement = sa.text(f'update {TABLE} set last_used_at = :now, '
                                f'last_used_ip = :ip where token_id = :id')
            try:
                db.execute(statement.bindparams(
                    now=dt.datetime.now().replace(microsecond=0),
                    ip=(address or '')[:64] or None, id=token_id))
            except sa.exc.DatabaseError as error:
                logger.warning(f'Last use of API token {token_id} not '
                               f'written: {error}')

        threading.Thread(target=write, name='rapo-token-touch',
                         daemon=True).start()

    def list(self):
        """Get every token, latest first."""
        statement = sa.text(f'select {COLUMNS} from {TABLE} '
                            f'order by token_id desc')
        try:
            rows = db.execute(statement, as_table=True)
        except sa.exc.DatabaseError as error:
            _missing(error)
            raise
        now = dt.datetime.now()
        return [describe(_read(row), now) for row in rows]

    def get(self, token_id):
        statement = sa.text(f'select {COLUMNS} from {TABLE} '
                            f'where token_id = :id')
        try:
            row = db.execute(statement.bindparams(id=int(token_id)),
                             as_dict=True)
        except sa.exc.DatabaseError as error:
            _missing(error)
            raise
        if not row:
            raise TokenError(f'API token {token_id} not found.', 404)
        return _read(row)

    @staticmethod
    def _identity(data):
        name = str(data.get('user_name') or '').strip()
        email = str(data.get('user_email') or '').strip()
        label = str(data.get('label') or '').strip() or None
        if not name or len(name) > 128:
            raise TokenError('A user name of up to 128 characters is needed.')
        if not EMAIL_PATTERN.fullmatch(email) or len(email) > 256:
            raise TokenError('A valid email address is needed.')
        if label and len(label) > 128:
            raise TokenError('The label has up to 128 characters.')
        free_sql = bool(data.get('free_sql'))
        try:
            scopes = scope_rules.normalize(data.get('scopes') or {}, free_sql)
        except ValueError as error:
            raise TokenError(str(error))
        return {'user_name': name, 'user_email': email, 'label': label,
                'scopes': json.dumps(scopes), 'free_sql': 'Y' if free_sql
                else 'N'}

    def create(self, data):
        """Create a token; get its row and the token, shown only now."""
        values = self._identity(data)
        values['expires_at'] = expiry(data.get('duration') or '1y')
        token = generate()
        values['token_hash'] = digest(token)
        values['token_prefix'] = token[:PREFIX_SHOWN]
        now = dt.datetime.now().replace(microsecond=0)
        statement = sa.text(
            f'insert into {TABLE} (token_hash, token_prefix, user_name, '
            f'user_email, label, scopes, free_sql, expires_at, created_date, '
            f'updated_date) values (:token_hash, :token_prefix, :user_name, '
            f':user_email, :label, :scopes, :free_sql, :expires_at, :now, '
            f':now)')
        try:
            db.execute(statement.bindparams(**values, now=now))
        except sa.exc.DatabaseError as error:
            _missing(error)
            raise
        row = self._by_hash(values['token_hash'])
        logger.info(f'API token {row["token_id"]} created for '
                    f'{row["user_email"]} ({row["label"] or "no label"}), '
                    f'expires {row["expires_at"] or "never"}')
        return describe(row), token

    def _by_hash(self, key):
        statement = sa.text(f'select {COLUMNS} from {TABLE} '
                            f'where token_hash = :hash')
        return _read(db.execute(statement.bindparams(hash=key),
                                as_dict=True))

    def _update(self, token_id, values, message):
        row = self.get(token_id)
        values['updated_date'] = dt.datetime.now().replace(microsecond=0)
        sets = ', '.join(f'{key} = :{key}' for key in values)
        statement = sa.text(f'update {TABLE} set {sets} '
                            f'where token_id = :token_id')
        db.execute(statement.bindparams(**values, token_id=row['token_id']))
        self.invalidate()
        logger.info(f'API token {token_id} of {row["user_email"]} '
                    f'{message}')
        return describe(self.get(token_id))

    def update(self, token_id, data):
        """Change the person, label, scopes and Free SQL of a token that is
        not revoked."""
        if self.get(token_id).get('revoked_at'):
            raise TokenError('A revoked token can not be changed.')
        return self._update(token_id, self._identity(data), 'changed')

    def extend(self, token_id, duration):
        """Set a token to expire `duration` from now; its secret stays."""
        row = self.get(token_id)
        if row.get('revoked_at'):
            raise TokenError('A revoked token can not be extended.')
        expires_at = expiry(duration)
        return self._update(token_id, {'expires_at': expires_at},
                            f'extended to {expires_at or "never"}')

    def regenerate(self, token_id):
        """Give a token a new secret; get its row and the new token."""
        row = self.get(token_id)
        if row.get('revoked_at'):
            raise TokenError('A revoked token can not be regenerated.')
        if describe(row)['state'] == 'expired':
            raise TokenError('An expired token can not be regenerated: '
                             'extend it first.')
        token = generate()
        result = self._update(token_id, {'token_hash': digest(token),
                                         'token_prefix': token[:PREFIX_SHOWN]},
                              'regenerated')
        return result, token

    def revoke(self, token_id):
        """Stop a token from working; its row stays for the records."""
        row = self.get(token_id)
        if row.get('revoked_at'):
            return describe(row)
        return self._update(token_id, {'revoked_at': dt.datetime.now()
                                       .replace(microsecond=0)}, 'revoked')

    def delete(self, token_id):
        """Delete a revoked or expired token."""
        row = self.get(token_id)
        if describe(row)['state'] == 'active':
            raise TokenError('Only a revoked or expired token can be '
                             'deleted; revoke it first.')
        statement = sa.text(f'delete from {TABLE} where token_id = :id')
        db.execute(statement.bindparams(id=row['token_id']))
        self.invalidate()
        logger.info(f'API token {token_id} of {row["user_email"]} deleted')


store = Store()
