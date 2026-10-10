"""Contains the compression of what the web server sends.

The built UI is compressed once per file and kept in memory (`ui_response`),
so a bundle costs no CPU after its first request; JSON answers are
compressed as they leave (`JsonGzipMiddleware`). Nothing else is touched:
downloads and file views are often compressed already, are streamed, or
must keep their length, and Starlette's GZipMiddleware would take them all.
"""

import gzip
import mimetypes
import os
import threading

import anyio
import fastapi
import fastapi.responses
from starlette.datastructures import Headers, MutableHeaders


# Bundles named by their content hash: a new build gets new names.
ASSET_DIRS = ('js/', 'css/', 'fonts/')
COMPRESSIBLE = ('.js', '.css', '.html', '.svg', '.ico', '.json', '.txt')
IMMUTABLE = 'public, max-age=31536000, immutable'
JSON_MINIMUM = 1024
JSON_LEVEL = 6
# Larger answers are compressed outside the event loop.
JSON_THREAD = 128 * 1024


def accepts_gzip(headers):
    """Check whether the client takes gzip (Accept-Encoding)."""
    return 'gzip' in headers.get('accept-encoding', '').lower()


class FileCache:
    """Compressed UI files by path, valid while the file is unchanged."""

    def __init__(self):
        self.lock = threading.Lock()
        self.files = {}

    def get(self, path, stat):
        key = (stat.st_mtime_ns, stat.st_size)
        with self.lock:
            entry = self.files.get(path)
        if entry and entry[0] == key:
            return entry[1]
        with open(path, 'rb') as file:
            body = gzip.compress(file.read(), compresslevel=9, mtime=0)
        with self.lock:
            self.files[path] = (key, body)
            # A rebuild leaves the old bundles' entries behind.
            for old in [old for old in self.files if not os.path.exists(old)]:
                del self.files[old]
        return body


file_cache = FileCache()


def ui_response(path, request, cache_control):
    """Get the response of a UI file: compressed when it pays and the
    client takes it, with an ETag for revalidation.
    """
    stat = os.stat(path)
    etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
    headers = {'Cache-Control': cache_control, 'Vary': 'Accept-Encoding'}
    compress = (path.endswith(COMPRESSIBLE)
                and accepts_gzip(request.headers))
    if compress:
        etag = etag[:-1] + '-gz"'
    headers['ETag'] = etag
    if etag in request.headers.get('if-none-match', ''):
        return fastapi.Response(status_code=304, headers=headers)
    if not compress:
        return fastapi.responses.FileResponse(path, headers=headers,
                                              stat_result=stat)
    media_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    return fastapi.Response(file_cache.get(path, stat), media_type=media_type,
                            headers={**headers, 'Content-Encoding': 'gzip'})


class JsonGzipMiddleware:
    """Compresses the JSON answers of the API for clients taking gzip.

    Only a complete application/json body of JSON_MINIMUM bytes or more,
    not encoded already; every other response passes untouched.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not accepts_gzip(Headers(scope=scope)):
            await self.app(scope, receive, send)
            return
        start = None
        parts = []

        async def wrapped(message):
            nonlocal start
            if message['type'] == 'http.response.start':
                headers = Headers(raw=message['headers'])
                if (headers.get('content-type', '').startswith(
                        'application/json')
                        and 'content-encoding' not in headers):
                    start = message
                    return
                await send(message)
                return
            if start is None or message['type'] != 'http.response.body':
                await send(message)
                return
            parts.append(message.get('body', b''))
            if message.get('more_body'):
                return
            body = b''.join(parts)
            if len(body) >= JSON_MINIMUM:
                if len(body) > JSON_THREAD:
                    body = await anyio.to_thread.run_sync(_compress, body)
                else:
                    body = _compress(body)
                headers = MutableHeaders(raw=list(start['headers']))
                headers['Content-Encoding'] = 'gzip'
                headers['Content-Length'] = str(len(body))
                headers.add_vary_header('Accept-Encoding')
                start = {**start, 'headers': headers.raw}
            await send(start)
            await send({'type': 'http.response.body', 'body': body})

        await self.app(scope, receive, wrapped)


def _compress(body):
    return gzip.compress(body, compresslevel=JSON_LEVEL)
