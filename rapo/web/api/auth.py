"""Contains web API authentication and access scopes.

The master token ([API] token of rapo.ini) may do everything, including the
management of the API tokens of users (`tokens.py`). A user token reaches
the routes its scopes allow (`scopes.py`); others answer 403. The caller of
a request is kept in `database.CLIENT`, so the database session names it
(client_identifier) and the rapo_config triggers record it.
"""

import asyncio
import contextvars
import dataclasses
import datetime as dt
import secrets

import fastapi
import fastapi.security

from ...config import config
from ...database import CLIENT

from . import scopes as scope_rules
from .tokens import store as token_store, PREFIX


bearer = fastapi.security.HTTPBearer(auto_error=False)
# A digits-only token is read from rapo.ini as a number, so it is kept as a
# string here, otherwise every comparison below would fail with a TypeError.
_token = config['API'].get('token') if config.check('API') else None
TOKEN = str(_token) if _token is not None else None


@dataclasses.dataclass(frozen=True)
class Caller:
    """Who calls the API: the master token or a user token's row."""

    master: bool
    token_id: int | None = None
    user_name: str | None = None
    user_email: str | None = None
    label: str | None = None
    scopes: dict = dataclasses.field(default_factory=dict)
    free_sql: bool = False
    expires_at: dt.datetime | None = None

    @property
    def identifier(self):
        """The name the database records for this caller (None: master,
        which keeps the server's OS user)."""
        return None if self.master else self.user_email

    @property
    def display(self):
        if self.master:
            return 'master token'
        label = f' ({self.label})' if self.label else ''
        return f'{self.user_name} <{self.user_email}>{label}'

    @property
    def requester(self):
        """Who asked for a run, as the scheduler events record it."""
        if self.master:
            return 'master token'
        return f'{self.user_name} <{self.user_email}>'

    def allows(self, area, level):
        return self.master or scope_rules.allows(self.scopes, area, level)

    def describe(self):
        """The caller as `whoami` answers it."""
        scopes = (scope_rules.PRESETS['full']['scopes'] if self.master
                  else self.scopes)
        return {'master': self.master, 'token_id': self.token_id,
                'user_name': self.user_name, 'user_email': self.user_email,
                'label': self.label, 'scopes': scopes,
                'free_sql': self.master or self.free_sql,
                'expires_at': self.expires_at}


MASTER = Caller(master=True)

# The Caller of the current request (set by verify_token).
CALLER = contextvars.ContextVar('rapo_caller', default=None)


def check_master(token):
    """Check that given token matches the configured API token."""
    if not isinstance(token, str) or not token or not TOKEN:
        return False
    return secrets.compare_digest(token, TOKEN)


def resolve(token, address=None):
    """Get the Caller of a token, or None when it is not valid. Blocking:
    a user token not in the cache is read from the database."""
    if check_master(token):
        return MASTER
    if not isinstance(token, str) or not token.startswith(PREFIX):
        return None
    row = token_store.lookup(token)
    if row is None:
        return None
    token_store.touch(row, address)
    return Caller(master=False, token_id=row['token_id'],
                  user_name=row['user_name'], user_email=row['user_email'],
                  label=row['label'], scopes=row['scopes'],
                  free_sql=row['free_sql'], expires_at=row['expires_at'])


def check_token(token):
    """Check that given token is the master token or a valid user token."""
    return resolve(token) is not None


def _unauthorized():
    return fastapi.HTTPException(status_code=401,
                                 detail='Unauthorized Access',
                                 headers={'WWW-Authenticate': 'Bearer'})


def forbidden(detail):
    return fastapi.HTTPException(status_code=403, detail=detail)


def required_text(area, level):
    return f'Requires {scope_rules.AREAS[area][0]}: {level.title()}'


async def verify_token(request: fastapi.Request,
                       credentials=fastapi.Depends(bearer)):
    """Check that request carries a valid Bearer token allowed to call the
    route, and remember its caller for the request.

    It is async so that `CLIENT` is set in the request's context, which the
    sync routes run in (the threadpool copies it).
    """
    token = credentials.credentials if credentials else None
    address = request.client.host if request.client else None
    if check_master(token):
        caller = MASTER
    else:
        caller = await asyncio.to_thread(resolve, token, address)
    if caller is None:
        raise _unauthorized()
    name = scope_rules.route_name(request.scope.get('path') or '')
    if name in scope_rules.MASTER:
        if not caller.master:
            raise forbidden('Requires the master token')
    elif name not in scope_rules.PUBLIC:
        rule = scope_rules.ROUTES.get(name)
        if rule is None:
            raise forbidden('Route without an access scope')
        rules = (rule, *scope_rules.ALSO.get(name, ()))
        if not any(caller.allows(*item) for item in rules):
            raise forbidden(required_text(*rule))
        if name in scope_rules.FREE_SQL_ROUTES:
            require_free_sql(caller)
    CALLER.set(caller)
    CLIENT.set(caller.identifier)
    return caller


def current():
    """Get the caller of the current request (it passed `verify_token`)."""
    caller = CALLER.get()
    if caller is None:
        raise _unauthorized()
    return caller


def require_filter(caller, where):
    """Answer 403 for a raw SQL filter that is more than a plain filter of
    the dataset's columns, unless the caller may send SQL text."""
    if caller.master or caller.free_sql or not where:
        return
    from ...core import sqlcheck
    problem = sqlcheck.plain_filter(where)
    if problem:
        raise forbidden(f'Requires Free SQL: {problem}')


def require_free_sql(caller):
    """Answer 403 unless the caller may send SQL text."""
    if not (caller.master or caller.free_sql):
        raise forbidden('Requires Free SQL')
