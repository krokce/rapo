"""Contains the uploads of files into the input directory of a datasource.

A file goes into the first directory of the saved INPUT_DIRECTORY, where PDI
Core picks it up when its name matches FILES_MASK. It is written under a
temporary name the mask does not match and renamed when complete, so a
partial file is never loaded, and an existing file is never overwritten.
"""

import errno
import os
import secrets

from ..logger import logger

from .files import compile_mask, number_option, option, scanner
from .store import DatasourceError, pdi, split_directories

NAME_MAX_BYTES = 255
TEMP_PREFIX = '.rapo-upload-'
TEMP_SUFFIX = '.part'
# Used when the mask matches the temporary name and the subdirectories of the
# input directory are not scanned.
TEMP_DIRECTORY = '.rapo-upload'


def enabled():
    """Check whether [DATASOURCES] file_upload allows uploads."""
    value = option('file_upload')
    if isinstance(value, str):
        return value.strip().lower() not in ('false', 'no', 'off', '0', '')
    return bool(value)


def target(id):
    """Get a saved datasource and the directory files are uploaded to.

    Returns
    -------
    row, directory : dict, str
        Raises DatasourceError when uploads are off, the datasource does not
        exist or has no input directory.
    """
    if not enabled():
        raise DatasourceError('File uploads are switched off on this server '
                              '([DATASOURCES] file_upload).', 403)
    row = pdi.read_datasource(id)
    if row is None:
        raise DatasourceError(f'Datasource {id} does not exist.', 404)
    directories = split_directories(row['input_directory'])
    if not directories:
        raise DatasourceError(f'Datasource {row["sourcename"]} has no input '
                              'directory.')
    return row, directories[0]


def name_error(name):
    """Get why a name can not be the name of an uploaded file, or None."""
    if not name or not name.strip():
        return 'no file name'
    if '/' in name or '\\' in name or name in ('.', '..'):
        return 'a file name may not have a path'
    if name.startswith('.'):
        return 'a file name may not start with a dot'
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        return 'a file name may not have control characters'
    if name != name.strip():
        return 'a file name may not start or end with spaces'
    if len(name.encode('utf-8')) > NAME_MAX_BYTES:
        return f'a file name may have at most {NAME_MAX_BYTES} bytes'
    return None


def check(id, names):
    """Check the names of files to upload to a datasource.

    Returns
    -------
    check : dict
        `sourcename`, `directory`, `exists` and `writable` (of the
        directory), `active`,
        `max_bytes` and `files`, `[{name, error, exists, matches_mask}]`
        (`exists`: a file of the name is already in the directory).
    """
    row, directory = target(id)
    pattern, _ = compile_mask(row['files_mask'])
    exists = os.path.isdir(directory)
    files = []
    for name in names or []:
        name = str(name)
        error = name_error(name)
        files.append({
            'name': name, 'error': error,
            'exists': bool(exists and not error and os.path.lexists(
                os.path.join(directory, name))),
            'matches_mask': bool(pattern and pattern.fullmatch(name))})
    return {'sourcename': row['sourcename'], 'directory': directory,
            'exists': exists,
            'writable': exists and os.access(directory, os.W_OK | os.X_OK),
            'active': bool(row['isactive']), 'max_bytes': _max_bytes(),
            'files': files}


def _max_bytes():
    return number_option('max_upload_mb') * 1024 * 1024


class Upload:
    """One file being uploaded: `write` its chunks, then `finish`, or
    `abort` to remove what was written."""

    def __init__(self, id, name):
        row, directory = target(id)
        error = name_error(name)
        if error:
            raise DatasourceError(f'{name!r} can not be uploaded: {error}.')
        if not os.path.isdir(directory):
            raise DatasourceError(f'The input directory {directory} does not '
                                  'exist.')
        self.row, self.name = row, name
        self.directory = directory
        self.path = os.path.join(directory, name)
        if os.path.lexists(self.path):
            raise DatasourceError(f'{name} is already waiting in the input '
                                  f'directory {directory}.', 409)
        self.pattern, _ = compile_mask(row['files_mask'])
        self.limit = _max_bytes()
        self.bytes = 0
        self.temp = self._temp_path()
        try:
            self.fd = os.open(self.temp,
                              os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except OSError as error:
            raise DatasourceError(f'{name} can not be written to {directory}: '
                                  f'{error.strerror or error}.') from error

    def _temp_path(self):
        """Get a temporary path PDI Core does not pick up."""
        name = f'{TEMP_PREFIX}{secrets.token_hex(8)}{TEMP_SUFFIX}'
        if not (self.pattern and self.pattern.fullmatch(name)):
            return os.path.join(self.directory, name)
        if self.row['input_scan_subdirs']:
            raise DatasourceError(
                'The file name pattern of the datasource would pick up a '
                'partly uploaded file, so nothing can be uploaded to it.')
        folder = os.path.join(self.directory, TEMP_DIRECTORY)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as error:
            raise DatasourceError(f'{folder} can not be created: '
                                  f'{error.strerror or error}.') from error
        return os.path.join(folder, name)

    def write(self, data):
        """Write a chunk; raises DatasourceError (413) past max_upload_mb."""
        self.bytes += len(data)
        if self.bytes > self.limit:
            raise DatasourceError(
                f'{self.name} has more than the {self.limit // 1024 // 1024} '
                'MB a file may have ([DATASOURCES] max_upload_mb).', 413)
        view = memoryview(data)
        while view:
            written = os.write(self.fd, view)
            view = view[written:]

    def finish(self):
        """Give the file its name, never overwriting one that appeared."""
        os.fsync(self.fd)
        os.close(self.fd)
        self.fd = None
        try:
            try:
                os.link(self.temp, self.path)
                os.unlink(self.temp)
            except FileExistsError:
                raise
            except OSError as error:
                # A file system without hard links: check, then rename.
                if error.errno not in (errno.EPERM, errno.EOPNOTSUPP,
                                       errno.ENOTSUP, errno.EXDEV,
                                       errno.EMLINK):
                    raise
                if os.path.lexists(self.path):
                    raise FileExistsError(errno.EEXIST, 'File exists')
                os.rename(self.temp, self.path)
        except FileExistsError:
            self.abort()
            raise DatasourceError(f'{self.name} is already waiting in the '
                                  f'input directory {self.directory}.', 409)
        except OSError as error:
            self.abort()
            raise DatasourceError(f'{self.name} was not uploaded: '
                                  f'{error.strerror or error}.') from error
        self._remove_temp_directory()
        matches = bool(self.pattern and self.pattern.fullmatch(self.name))
        logger.info(f'File uploaded: {self.path} ({self.bytes} bytes) for '
                    f'datasource {self.row["sourcename"]}'
                    f'{"" if matches else ", not matching its file mask"}')
        scanner.poke()
        return {'status': 200, 'path': self.path, 'bytes': self.bytes,
                'matches_mask': matches}

    def abort(self):
        """Remove the temporary file."""
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        try:
            os.unlink(self.temp)
        except FileNotFoundError:
            pass
        except OSError as error:
            logger.warning(f'Partly uploaded file {self.temp} not removed: '
                           f'{error.strerror or error}')
        self._remove_temp_directory()

    def _remove_temp_directory(self):
        folder = os.path.dirname(self.temp)
        if os.path.basename(folder) == TEMP_DIRECTORY:
            try:
                os.rmdir(folder)
            except OSError:
                pass
