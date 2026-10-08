"""Contains the viewer of the files PDI Core loaded.

A file is read from where PDI Core kept it, under the same rules as a
download (download.locate), and sent a few lines at a time. Archived files
are mostly gzipped and may have gigabytes, so nothing is kept between
requests: each one opens the file and seeks to the uncompressed byte offset
the previous one ended at (a gzip is decompressed up to it, which is fast in
C), so a request costs the lines it sends plus the bytes before them.
"""

import codecs
import gzip
import re
import time
import zipfile

from ..logger import logger

from . import download
from .files import number_option
from .store import DatasourceError

SNIFF_BYTES = 64 * 1024
SKIP_BYTES = 1024 * 1024
MAX_LINES = 5000
# A cut line is read up to this many bytes per character it keeps.
BYTES_PER_CHAR = 4
# A search reads blocks of whole lines of about this size.
BLOCK_BYTES = 1024 * 1024


def read(id, offset=0, line=1, lines=None):
    """Get lines of a loaded file, from an uncompressed byte offset.

    Parameters
    ----------
    id : int
        File ID of the file log.
    offset : int
        Uncompressed byte offset of the first line, the `next_offset` of
        the previous request (0: the start).
    line : int
        Number of the line at `offset`, only shown.
    lines : int
        How many lines, [DATASOURCES] view_lines by default.

    Returns
    -------
    result : dict
        The file's facts (see `_meta`) and `lines`, `[{no, offset, text,
        cut}]` (`cut`: the bytes left out of a long line), `next_offset`,
        `next_line` and `eof`.
    """
    file = download.locate(id)
    offset, line = _cursor(offset, line)
    count = min(max(int(lines or number_option('view_lines')), 1), MAX_LINES)
    with _open(file['path']) as stream:
        meta = _meta(file, stream)
        result = {**meta, 'lines': [], 'next_offset': offset,
                  'next_line': line, 'eof': False}
        if meta['binary']:
            result['eof'] = True
            return result
        _seek(stream, offset)
        chars = _line_chars()
        reader = _lines(stream, chars * BYTES_PER_CHAR)
        for _ in range(count):
            item = next(reader, None)
            if item is None:
                result['eof'] = True
                break
            data, size, cut = item
            text, cut = _decode(data, meta['encoding'], chars, cut)
            result['lines'].append({'no': line, 'offset': offset,
                                    'text': text, 'cut': cut})
            offset += size
            line += 1
        else:
            result['eof'] = not stream.peek(1) if hasattr(
                stream, 'peek') else False
        result['next_offset'], result['next_line'] = offset, line
    if result['lines'] and result['lines'][0]['offset'] == 0:
        logger.info(f'File viewed: {file["name"]} (file ID {id})')
    return result


def grep(id, pattern, regex=False, case=False, offset=0, line=1):
    """Find the lines of a loaded file that contain a text or expression.

    It reads from the cursor until [DATASOURCES] view_grep_matches lines
    matched, the file ended or view_grep_seconds passed; the next request
    goes on from `next_offset`. Matching is done line by line on the part of
    a line that is shown (view_line_chars).

    Returns
    -------
    result : dict
        The file's facts (see `_meta`) and `matches`, `[{no, offset, text,
        cut, spans}]` (`spans`: `[start, end]` of each match in `text`),
        `next_offset`, `next_line`, `eof`, `scanned_bytes`, `scanned_lines`
        and `stopped` (`matches`, `time` or None).
    """
    if not pattern:
        raise DatasourceError('Give a text to search for.')
    try:
        expression = re.compile(pattern if regex else re.escape(pattern),
                                0 if case else re.IGNORECASE)
    except re.error as error:
        raise DatasourceError(f'Invalid regular expression: {error}.')
    file = download.locate(id)
    offset, line = _cursor(offset, line)
    limit = max(number_option('view_grep_matches'), 1)
    deadline = time.monotonic() + max(number_option('view_grep_seconds'), 1)
    started = time.monotonic()
    with _open(file['path']) as stream:
        meta = _meta(file, stream)
        result = {**meta, 'matches': [], 'next_offset': offset,
                  'next_line': line, 'eof': False, 'scanned_bytes': 0,
                  'scanned_lines': 0, 'stopped': None}
        if meta['binary']:
            result['eof'] = True
            return result
        encoding = meta['encoding']
        hit_lines = _hit_lines(pattern, regex, case, encoding)
        _seek(stream, offset)
        chars = _line_chars()
        limit_bytes = chars * BYTES_PER_CHAR
        start_offset, scanned = offset, 0
        matches = result['matches']

        def match(data, cut, number, at):
            text, cut = _decode(data, encoding, chars, cut)
            spans = [[found.start(), found.end()]
                     for found in expression.finditer(text)
                     if found.end() > found.start()]
            if spans:
                matches.append({'no': number, 'offset': at, 'text': text,
                                'cut': cut, 'spans': spans})

        for block, size, cut in _blocks(stream, limit_bytes):
            if cut is not None:
                match(block, cut, line, offset)
                offset, line, scanned = offset + size, line + 1, scanned + 1
            else:
                count = block.count(b'\n') + (not block.endswith(b'\n'))
                for index, start, end in _lines_at(block, hit_lines(block)):
                    data = block[start:end]
                    if data.endswith(b'\n'):
                        data = data[:-1]
                    if data.endswith(b'\r'):
                        data = data[:-1]
                    match(data[:limit_bytes], max(len(data) - limit_bytes, 0),
                          line + index, offset + start)
                    if len(matches) >= limit:
                        size, count = end, index + 1
                        break
                offset, line = offset + size, line + count
                scanned += count
            if len(matches) >= limit:
                result['stopped'] = 'matches'
                break
            if time.monotonic() > deadline:
                result['stopped'] = 'time'
                break
        else:
            result['eof'] = True
        result.update(next_offset=offset, next_line=line,
                      scanned_bytes=offset - start_offset,
                      scanned_lines=scanned)
    logger.info(f'File searched: {file["name"]} (file ID {id}) for '
                f'{pattern!r}, {len(result["matches"])} line(s) matched in '
                f'{scanned} read in {time.monotonic() - started:.1f} s')
    return result


def _cursor(offset, line):
    try:
        return max(int(offset or 0), 0), max(int(line or 1), 1)
    except (TypeError, ValueError):
        raise DatasourceError('offset and line must be numbers.')


def _line_chars():
    return max(number_option('view_line_chars'), 100)


class _open:
    """Open a file as uncompressed bytes: a gzip by its magic bytes, the
    first file of a ZIP, anything else as it is."""

    def __init__(self, path):
        self.path = path
        self.handles = []

    def __enter__(self):
        try:
            with open(self.path, 'rb') as probe:
                magic = probe.read(4)
            if magic[:2] == b'\x1f\x8b':
                stream = gzip.open(self.path, 'rb')
                self.handles.append(stream)
                self.kind = 'gzip'
            elif magic == b'PK\x03\x04':
                archive = zipfile.ZipFile(self.path)
                self.handles.append(archive)
                members = [info for info in archive.infolist()
                           if not info.is_dir()]
                if not members:
                    raise DatasourceError('The ZIP file has no files.')
                stream = archive.open(members[0])
                self.handles.append(stream)
                self.kind = f'zip:{members[0].filename}'
            else:
                stream = open(self.path, 'rb')
                self.handles.append(stream)
                self.kind = 'plain'
        except (OSError, zipfile.BadZipFile) as error:
            self.__exit__(None, None, None)
            raise DatasourceError(f'The file is not readable: '
                                  f'{getattr(error, "strerror", None) or error}.')
        stream.kind = self.kind
        return stream

    def __exit__(self, *args):
        for handle in reversed(self.handles):
            try:
                handle.close()
            except Exception:
                pass
        self.handles = []
        if args[0] is not None and issubclass(
                args[0], (OSError, EOFError, zipfile.BadZipFile,
                          gzip.BadGzipFile)):
            raise DatasourceError(f'The file is not readable: {args[1]}.')
        return False


def _meta(file, stream):
    """Get what a page shows of a file, read from its first 64 KB.

    `encoding` is UTF-8 when they decode as it, else Latin-1 (any byte is a
    character); `binary` when they hold a NUL byte; `header` is the first
    line, for the names of the columns.
    """
    sniff = stream.read(SNIFF_BYTES)
    binary = b'\x00' in sniff
    try:
        codecs.getincrementaldecoder('utf-8')().decode(sniff, final=False)
        encoding = 'utf-8'
    except UnicodeDecodeError:
        encoding = 'latin-1'
    header = None
    if not binary and sniff:
        first = sniff.split(b'\n', 1)[0].rstrip(b'\r')
        header = first.decode(encoding, 'replace').lstrip('﻿')
        header = header[:_line_chars()]
    return {'id': file['id'], 'name': file['name'], 'size': file['size'],
            'compression': stream.kind, 'encoding': encoding,
            'binary': binary, 'header': header}


def _seek(stream, offset):
    """Go to an uncompressed offset (a gzip or ZIP decompresses up to it)."""
    if offset == 0:
        stream.seek(0)
        return
    if stream.seekable():
        stream.seek(offset)
        return
    stream.seek(0)
    left = offset
    while left > 0:
        data = stream.read(min(left, SKIP_BYTES))
        if not data:
            break
        left -= len(data)


def _lines(stream, limit):
    """Yield (bytes kept, bytes taken, bytes cut) of each line.

    The kept bytes have no line end; a line longer than `limit` is read to
    its end in chunks, which are counted, not kept.
    """
    while True:
        data = stream.readline(limit)
        if not data:
            return
        size = len(data)
        cut = 0
        if not data.endswith(b'\n'):
            while True:
                rest = stream.readline(SKIP_BYTES)
                if not rest:
                    break
                size += len(rest)
                cut += len(rest)
                if rest.endswith(b'\n'):
                    cut -= 1 + rest.endswith(b'\r\n')
                    break
        else:
            data = data[:-1]
        if data.endswith(b'\r') and not cut:
            data = data[:-1]
        yield data, size, cut


def _blocks(stream, limit):
    """Yield (bytes, bytes taken, None) of blocks of whole lines, or (bytes
    kept, bytes taken, bytes cut) of one line longer than `limit`."""
    while True:
        data = stream.read(BLOCK_BYTES)
        if not data:
            return
        if not data.endswith(b'\n'):
            rest = stream.readline(limit)
            data += rest
            if not rest.endswith(b'\n') and len(rest) == limit:
                end = data.rfind(b'\n') + 1
                if end:
                    yield data[:end], end, None
                head = data[end:]
                size, cut = len(head), max(len(head) - limit, 0)
                while True:
                    rest = stream.readline(SKIP_BYTES)
                    if not rest:
                        break
                    size += len(rest)
                    cut += len(rest)
                    if rest.endswith(b'\n'):
                        cut -= 1 + rest.endswith(b'\r\n')
                        break
                yield head[:limit], size, cut
                continue
        yield data, len(data), None


def _decode(data, encoding, chars, cut):
    """Get the text of a line, at most `chars` characters, and the bytes
    cut off it."""
    text = data.decode(encoding, 'replace')
    if len(text) > chars:
        cut += len(text[chars:].encode(encoding, 'replace'))
        text = text[:chars]
    return text, cut


def _hit_lines(pattern, regex, case, encoding):
    """Get a function finding the lines of a block of whole lines that may
    match: it yields their indexes in the block, ascending, each once. A line
    found is then matched on its own (a match across lines is no match)."""
    if not regex:
        try:
            needle = pattern.encode(encoding)
        except UnicodeEncodeError:
            return lambda block: ()
        if case or pattern.isascii():
            if not case:
                needle = needle.lower()
            return lambda block: _find_lines(
                block if case else block.lower(), needle)
    # ^ and $ of a line; a line ends with \n, also after \r. Decoding
    # neither adds nor removes a \n, so lines are counted the same.
    expression = re.compile(pattern if regex else re.escape(pattern),
                            re.MULTILINE | (0 if case else re.IGNORECASE))

    def search(block):
        text = block.decode(encoding, 'replace').replace('\r\n', '\n')
        index, position = 0, 0
        last = None
        for found in expression.finditer(text):
            index += text.count('\n', position, found.start())
            position = found.start()
            if index != last:
                last = index
                yield index
    return search


def _find_lines(block, needle):
    index, position = 0, 0
    found = block.find(needle)
    while found >= 0:
        index += block.count(b'\n', position, found)
        yield index
        position = block.find(b'\n', found)
        if position < 0:
            return
        index += 1
        position += 1
        found = block.find(needle, position)


def _lines_at(block, indexes):
    """Yield (index, start, end) of the lines of a block at the indexes
    (ascending); `end` is after the line end."""
    index, position = 0, 0
    for wanted in indexes:
        while index < wanted:
            position = block.find(b'\n', position) + 1
            index += 1
            if position == 0:
                return
        end = block.find(b'\n', position)
        yield index, position, len(block) if end < 0 else end + 1
