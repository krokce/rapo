"""Contains web API authentication."""

import secrets

import fastapi
import fastapi.security

from ...config import config


bearer = fastapi.security.HTTPBearer(auto_error=False)
TOKEN = config['API'].get('token') if config.check('API') else None


def check_token(token):
    """Check that given token matches the configured API token."""
    if not isinstance(token, str) or not token or not TOKEN:
        return False
    return secrets.compare_digest(token, TOKEN)


def verify_token(credentials=fastapi.Depends(bearer)):
    """Check that request carries the valid Bearer token."""
    token = credentials.credentials if credentials else None
    if not check_token(token):
        raise fastapi.HTTPException(status_code=401,
                                    detail='Unauthorized Access',
                                    headers={'WWW-Authenticate': 'Bearer'})
    return token
