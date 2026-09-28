"""Contains the downloads of the files PDI Core loaded.

A file is sent from where PDI Core kept it (OUTPUTFULLFILENAME), read from the
file system of this server, and only when its real path lies in the archive,
error or duplicate directory of its datasource, so that a file log row can
not name any other file of the server. Only SUCCESS and ERROR files whose
archived file is kept (OUTFILEDELETED = 0) are sent. Several files are sent
as one ZIP, written while it is sent.
"""

import os
import zipfile

from ..logger import logger

from .files import OTHER_DIRECTORIES, number_option, option
from .store import DOWNLOAD_FROM, DatasourceError, pdi

CHUNK_BYTES = 1024 * 1024
# Files already compressed are stored in the ZIP as they are.
STORED_SUFFIXES = ('.gz', '.tgz', '.zip', '.bz2', '.xz', '.7z', '.zst')
MISSING_NAME = 'MISSING.txt'


def enabled():
    """Check whether [DATASOURCES] file_download allows downloads."""
    value = option('file_download')
    if isinstance(value, str):
        return value.strip().lower() not in ('false', 'no', 'off', '0')
    return bool(value)


def prepare(ids):
    """Find the files of the file log that can be sent.

    Parameters
    ----------
    ids : list of int
        File IDs of the file log.

    Returns
    -------
    download : dict
        `files`, `[{id, path, name, size, sourcename, day}]` in ID order,
        `skipped`, `[{id, name, reason}]`, and `bytes`, their total size.
        Raises DatasourceError when none can be sent, or when they are more
        than [DATASOURCES] max_download_mb.
    """
    if not enabled():
        raise DatasourceError('File downloads are switched off on this '
                              'server ([DATASOURCES] file_download).', 403)
    ids, rows = pdi.read_download_files(ids)
    roots = {}
    files, skipped = [], []
    for id in ids:
        row = rows.get(id)
        name = os.path.basename(str((row or {}).get('outputfullfilename')
                                    or (row or {}).get('inputfilename')
                                    or f'file {id}'))
        if row is None:
            skipped.append({'id': id, 'name': name,
                            'reason': 'not in the file log'})
            continue
        if row['sourceid'] not in roots:
            roots[row['sourceid']] = _roots(row['sourceid'])
        reason, path, size = _check(row, roots[row['sourceid']])
        if reason:
            skipped.append({'id': id, 'name': name, 'reason': reason})
            continue
        day = row['startloaddate']
        files.append({'id': id, 'path': path, 'name': name, 'size': size,
                      'sourcename': row['sourcename'],
                      'day': day.strftime('%Y%m%d') if day else None})
    if not files:
        reasons = ', '.join(sorted({item['reason'] for item in skipped}))
        raise DatasourceError(f'No file can be downloaded: {reasons}.')
    total = sum(file['size'] for file in files)
    limit = number_option('max_download_mb')
    if total > limit * 1024 * 1024:
        raise DatasourceError(
            f'The {len(files)} file(s) have {total / 1024 / 1024:.1f} MB, more '
            f'than the {limit} MB a download may have ([DATASOURCES] '
            'max_download_mb).')
    return {'files': files, 'skipped': skipped, 'bytes': total}


def _roots(sourceid):
    """Get the real paths of the directories a datasource keeps files in."""
    datasource = pdi.read_datasource(sourceid)
    if datasource is None:
        return None
    return [os.path.realpath(datasource[name]) for name in OTHER_DIRECTORIES
            if datasource.get(name)]


def _check(row, roots):
    """Get why a file can not be sent (or None), its real path and size."""
    if row['filestatus'] not in DOWNLOAD_FROM:
        return f'status is {row["filestatus"]}', None, None
    if row['outfiledeleted']:
        return 'archived file deleted', None, None
    if not row['outputfullfilename']:
        return 'no archived file named', None, None
    if roots is None:
        return 'datasource not configured', None, None
    path = os.path.realpath(row['outputfullfilename'])
    if not any(_inside(path, root) for root in roots):
        return "outside the datasource's directories", None, None
    try:
        if not os.path.isfile(path):
            return 'missing on this server', None, None
        if not os.access(path, os.R_OK):
            return 'not readable on this server', None, None
        size = os.path.getsize(path)
    except OSError as error:
        return f'not readable ({error.strerror})', None, None
    return None, path, size


def _inside(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def zip_name(download):
    """Get the name of the ZIP of several files: <SOURCENAME>_<YYYYMMDD>."""
    names = {file['sourcename'] for file in download['files']}
    days = sorted({file['day'] for file in download['files'] if file['day']})
    name = names.pop() if len(names) == 1 else 'FILES'
    if days:
        name += f'_{days[0]}' + (f'-{days[-1]}' if len(days) > 1 else '')
    return f'{name}.zip'


def log(download):
    """Write a download to the server log."""
    ids = [file['id'] for file in download['files']]
    logger.info(f'Files downloaded: {len(ids)} ({download["bytes"]} bytes, '
                f'IDs {ids[0]}..{ids[-1]}), {len(download["skipped"])} '
                'left out')


class _Pipe:
    """A file the ZIP is written into, emptied by each chunk sent.

    It can not tell its position, so zipfile writes a data descriptor after
    each file instead of seeking back to its header.
    """

    def __init__(self):
        self.chunks = []

    def write(self, data):
        self.chunks.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def take(self):
        data = b''.join(self.chunks)
        self.chunks = []
        return data


def stream_zip(download):
    """Yield the ZIP of the files of a download, written while it is read.

    The files left out are named in MISSING.txt, with why, also a file that
    disappeared since it was found.
    """
    pipe = _Pipe()
    skipped = list(download['skipped'])
    names = set()
    with zipfile.ZipFile(pipe, 'w', allowZip64=True) as archive:
        for file in download['files']:
            try:
                source = open(file['path'], 'rb')
            except OSError as error:
                skipped.append({'id': file['id'], 'name': file['name'],
                                'reason': f'not readable ({error.strerror})'})
                continue
            with source:
                info = zipfile.ZipInfo.from_file(file['path'],
                                                 _unique(file['name'], names))
                info.compress_type = (
                    zipfile.ZIP_STORED
                    if file['name'].lower().endswith(STORED_SUFFIXES)
                    else zipfile.ZIP_DEFLATED)
                with archive.open(info, 'w') as target:
                    while True:
                        data = source.read(CHUNK_BYTES)
                        if not data:
                            break
                        target.write(data)
                        chunk = pipe.take()
                        if chunk:
                            yield chunk
            chunk = pipe.take()
            if chunk:
                yield chunk
        if skipped:
            lines = [f'{item["name"]}\t(file ID {item["id"]})\t'
                     f'{item["reason"]}' for item in skipped]
            text = ('Files not in this download:\n\n' + '\n'.join(lines)
                    + '\n')
            archive.writestr(_unique(MISSING_NAME, names), text)
    yield pipe.take()


def _unique(name, names):
    """Get a name not yet in the ZIP: a repeated one gets ` (2)`."""
    stem, suffix = name, ''
    if '.' in name.lstrip('.'):
        stem, suffix = name.split('.', 1)
        suffix = '.' + suffix
    candidate, number = name, 1
    while candidate.lower() in names:
        number += 1
        candidate = f'{stem} ({number}){suffix}'
    names.add(candidate.lower())
    return candidate
