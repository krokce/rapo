"""Contains application configurator.

Used to transfer parameters from user to application.
"""

import datetime as dt
import glob
import hashlib
import os
import re
import shutil
import tempfile
import configparser


path = os.path.abspath(
    os.environ.get('RAPO_CONFIG') or
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rapo.ini'))
encoding = 'utf-8'

# Options of rapo.ini never sent to the browser, matched by name fragment.
SECRET_OPTIONS = ('password', 'token', 'secret')
# Options the server uses only at startup: a reload leaves them at their
# startup value, so they wait for a restart. A section name alone means all
# of its options.
RESTART_OPTIONS = ('DATABASE', 'API', 'LOGGING.directory', 'SCHEDULER.enabled')
# [LOGGING] options passed to pepperoni. A new value is applied on reload,
# but pepperoni has no way back to its default, so a removed one waits.
PEPPERONI_OPTIONS = ['console', 'file', 'info', 'debug', 'warning', 'error',
                     'critical', 'format', 'maxsize', 'maxlevel', 'maxerrors']
# Backups of rapo.ini kept by write_option, the newest first.
BACKUPS_KEPT = 10


class ConfigConflict(Exception):
    """rapo.ini changed since the caller read it."""


def is_secret(option):
    """Check whether the option holds a secret."""
    return any(secret in option.lower() for secret in SECRET_OPTIONS)


def needs_restart(section, option, change=None):
    """Check whether a change of the option applies only after a restart."""
    name = f'{section.upper()}.{option.lower()}'
    if any(item == section.upper() or item.lower() == name.lower()
           for item in RESTART_OPTIONS):
        return True
    return (section.upper() == 'LOGGING' and option.lower()
            in PEPPERONI_OPTIONS and change == 'removed')


class Configurator(dict):
    """Represents main configurator."""

    def __init__(self):
        super().__init__()
        if self.found:
            names = ['SCHEDULER', 'ALGORITHM', 'DATABASE', 'LOGGING', 'API']
            for name in names:
                self[name] = Configuration(name)
            self.load()

    def load(self):
        """Load configuration from file into memory."""
        for section, options in self.read_file().items():
            if section not in self:
                self[section] = Configuration(section)
            for option, value in options.items():
                self[section][option] = value
        return self

    def read_file(self):
        """Read the file as {section: {option: normalized value}}.

        A missing file or one that can not be parsed raises
        configparser.Error, so that it never reads as all options removed.
        """
        parser = configparser.ConfigParser(allow_no_value=True)
        if not parser.read(path, encoding=encoding):
            raise configparser.Error(f'{path} not found')
        return {section: {option: self.normalize(parser[section][option])
                          for option in parser.options(section)}
                for section in parser.sections()}

    def changes(self, content=None):
        """Get the differences between the loaded options and the file.

        Returns
        -------
        changes : list of dict
            One per option: section, option, change (added, removed or
            changed), restart (applies only after a restart), secret, and
            the loaded and file values, which are None for a secret.
        """
        content = self.read_file() if content is None else content
        result = []
        sections = list(self)
        sections += [name for name in content if name not in self]
        for section in sections:
            loaded = dict(self.get(section) or {})
            written = content.get(section) or {}
            options = list(loaded)
            options += [name for name in written if name not in loaded]
            for option in options:
                if option not in written:
                    change = 'removed'
                elif option not in loaded:
                    change = 'added'
                elif loaded[option] != written[option] or (
                        type(loaded[option]) is not type(written[option])):
                    change = 'changed'
                else:
                    continue
                secret = is_secret(option)
                result.append({
                    'section': section,
                    'option': option,
                    'change': change,
                    'restart': needs_restart(section, option, change),
                    'secret': secret,
                    'loaded': None if secret else loaded.get(option),
                    'file': None if secret else written.get(option)
                })
        return result

    def reload(self):
        """Apply the changes of the file that do not need a restart.

        Options that need one keep their loaded value.

        Returns
        -------
        applied : list of dict
            The changes applied, as `changes()` describes them.
        """
        content = self.read_file()
        applied = []
        for item in self.changes(content):
            if item['restart']:
                continue
            section, option = item['section'], item['option']
            if section not in self:
                self[section] = Configuration(section)
            if item['change'] == 'removed':
                self[section].pop(option, None)
            else:
                self[section][option] = content[section][option]
            applied.append(item)
        return applied

    def digest(self):
        """Get a checksum of rapo.ini as it is on disk, None without one."""
        try:
            with open(path, 'rb') as file:
                return hashlib.sha256(file.read()).hexdigest()
        except OSError:
            return None

    def write_option(self, section, option, value, expected_digest=None):
        """Set an option in rapo.ini, or remove it with `value` None.

        Only the option's own line changes: comments, order and the other
        options stay as written. A missing option is added at the end of its
        section, a missing section at the end of the file. The file is first
        copied to rapo.ini.bak-<timestamp> (the newest BACKUPS_KEPT kept),
        then replaced at once, keeping its mode.

        Raises ConfigConflict when the file's checksum is not
        `expected_digest`. Returns the path of the backup.
        """
        with open(path, 'r', encoding=encoding) as file:
            text = file.read()
        digest = hashlib.sha256(text.encode(encoding)).hexdigest()
        if expected_digest and expected_digest != digest:
            raise ConfigConflict(f'{path} changed meanwhile')
        lines = text.split('\n')
        header = re.compile(r'^\s*\[([^\]]+)\]')
        pattern = re.compile(rf'^\s*{re.escape(option)}\s*[=:]', re.IGNORECASE)
        start = end = None
        for number, line in enumerate(lines):
            match = header.match(line)
            if match:
                if start is not None:
                    end = number
                    break
                if match.group(1).strip().upper() == section.upper():
                    start = number
        if start is not None and end is None:
            end = len(lines)
        found = None
        if start is not None:
            for number in range(start + 1, end):
                if pattern.match(lines[number]):
                    found = number
        entry = f'{option}={value}'
        if found is not None:
            if value is None:
                del lines[found]
                end -= 1
                # A section left without options or comments goes too.
                if not any(line.strip() for line in lines[start + 1:end]):
                    del lines[start:end]
                    # The last section: no blank lines left at the end.
                    if start >= len(lines):
                        while lines and not lines[-1].strip():
                            lines.pop()
            else:
                lines[found] = entry
        elif value is not None:
            if start is None:
                while lines and not lines[-1].strip():
                    lines.pop()
                lines += ['', f'[{section.upper()}]', entry, '']
            else:
                last = start
                for number in range(start + 1, end):
                    if lines[number].strip():
                        last = number
                lines.insert(last + 1, entry)
        content = '\n'.join(lines)
        if not content.endswith('\n'):
            content += '\n'
        if content == text:
            return None
        backup = self.backup()
        mode = os.stat(path).st_mode & 0o7777
        folder = os.path.dirname(path)
        handle, temporary = tempfile.mkstemp(prefix='.rapo.ini.', dir=folder)
        try:
            with os.fdopen(handle, 'w', encoding=encoding) as file:
                file.write(content)
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        except Exception:
            if os.path.exists(temporary):
                os.remove(temporary)
            raise
        return backup

    def backup(self):
        """Copy rapo.ini to rapo.ini.bak-<timestamp>, readable by the owner
        only, and delete all but the newest BACKUPS_KEPT copies.
        """
        stamp = dt.datetime.now().strftime('%Y%m%d%H%M%S%f')
        target = f'{path}.bak-{stamp}'
        shutil.copy2(path, target)
        os.chmod(target, 0o600)
        backups = sorted(glob.glob(glob.escape(path) + '.bak-*'), reverse=True)
        for old in backups[BACKUPS_KEPT:]:
            try:
                os.remove(old)
            except OSError:
                pass
        return target

    def normalize(self, value):
        """Normalize given parameter value."""
        if value is None or value.upper() in ['NONE', ''] or value.isspace():
            return None
        elif value.upper() == 'TRUE':
            return True
        elif value.upper() == 'FALSE':
            return False
        elif re.match(r'^[+-]?\d+$', value):
            return int(value)
        elif re.match(r'^[+-]?(\d*\.\d+|\d+\.\d*)$', value):
            return float(value)
        return value

    def check(self, configuration_name):
        """Determine whether configuration presented or not."""
        if self.get(configuration_name) is not None:
            return True
        return False

    @property
    def found(self):
        """Determine whether configuration file found or not."""
        if os.path.exists(path):
            return True
        return False


class Configuration(dict):
    """Represents some configuration."""

    def __init__(self, name):
        super().__init__()
        self.name = name

    def __setitem__(self, key, value):
        """Set the parameter value."""
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        """Get the parameter value or raise an exception if not found."""
        return super().__getitem__(key.lower())

    def get(self, key, default=None):
        """Get the parameter value or return default if not found."""
        return super().get(key.lower(), default)

    def get_deprecated(self, used, required):
        """Get the parameter, considering the depreciations."""
        parameter = self.get(required)
        if not parameter:
            if self.get(used):
                parameter = self.get(used)
                print(f'Please use parameter [{required}] instead of',
                      f'[{used}], which is deprecated and will be',
                      f'removed soon from [{self.name}] section',
                      f'of {path} configuration file!')
        return parameter


config = Configurator()


def get_algorithm_setting(name):
    """Get ALGORITHM option, read at every call so that a reload applies."""
    if config.check('ALGORITHM'):
        return config['ALGORITHM'].get(name)
    return None
