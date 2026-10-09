"""Contains tag maps, the field definitions of Pentaho ASN.1 decoders.

A tag map names fields by their tag path, as the decoders' Java ObjectParser
builds it: every TLV that is not UNIVERSAL adds its tag number (a context or
application tag), a UNIVERSAL one (SEQUENCE, SET, a string) adds none. Its
entries are `"82.4.1" -> "nodeAddress,ia5,4"` (name, type, field id, `#`
to keep a value for the next row), written as the decoders' Java does
(`props.put("82.4.1","nodeAddress,ia5,4");`) or as properties
(`82.4.1=nodeAddress,ia5,4`); `_ROW` marks the tag of a record. Only the
name and type are used here: the type picks the decoder of the value
(values.py, `tagmap:<type>`), the same as the Java's.

A TagMap answers what view.py asks a Grammar: a node's state is its path.
"""

import json
import re

from .grammar import GrammarError

PUT = re.compile(r'''props\s*\.\s*(?:put|setProperty)\s*\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)''')
LINE = re.compile(r'^\s*([0-9]+(?:\.[0-9]+)*)\s*[=:]\s*(.*?)\s*$')
PATH = re.compile(r'[0-9]+(?:\.[0-9]+)*')
TYPES = ('bcdstring', 'ebcdstring', 'tbcdstring', 'rbcdstring', 'integer',
         'octstring', 'ia5')


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'(^|\s)//.*$', ' ', text, flags=re.M)


def looks_like(text):
    """Whether a file is a tag map rather than ASN.1 modules."""
    text = _strip_comments(text)
    if re.search(r'\bDEFINITIONS\b', text):
        return False
    if PUT.search(text):
        return True
    return any(LINE.match(line) for line in text.splitlines())


def parse(files):
    """Parse the files of a tag map, `[(file name, text)]`.

    Returns
    -------
    result : dict
        `{entries: {path: [name, type]}, rows: [paths]}`; raises GrammarError
        naming the file and line of an entry that is none.
    """
    entries, rows = {}, []
    for name, text in files:
        text = text.replace('\r\n', '\n')
        found = []
        if PUT.search(text):
            for match in PUT.finditer(text):
                line = text.count('\n', 0, match.start()) + 1
                found.append((line, match.group(1), match.group(2)))
        else:
            for number, line in enumerate(text.split('\n'), 1):
                stripped = line.strip()
                if not stripped or stripped.startswith(('#', '!', '//')):
                    continue
                match = LINE.match(line)
                if match is None:
                    raise GrammarError(f'{name}: line {number} is no '
                                       f'"path=name,type" entry.')
                found.append((number, match.group(1), match.group(2)))
        for line, path, value in found:
            if not PATH.fullmatch(path.strip()):
                raise GrammarError(f'{name}: line {line}: "{path}" is no tag '
                                   f'path (numbers separated by dots).')
            parts = [part.strip() for part in value.split(',')]
            if parts[0].upper() == '_ROW':
                rows.append(path.strip())
                continue
            if len(parts) < 2 or not parts[0]:
                raise GrammarError(f'{name}: line {line}: "{value}" is no '
                                   f'"name,type[,id]" value.')
            entries[path.strip()] = [parts[0], parts[1].lower()]
    if not entries and not rows:
        raise GrammarError('The tag map has no entries.')
    return {'entries': entries, 'rows': rows}


class TagMap:
    """A tag map, used as a Grammar by view.py: the state of a node is its
    tag path."""

    kind = 'tagmap'

    def __init__(self, parsed):
        self.entries = parsed['entries']
        self.rows = set(parsed['rows'])

    def top_handle(self, name):
        return None

    def guess_top(self, tag):
        return None

    def tops(self):
        return [], 0

    def _info(self, path):
        key = '.'.join(map(str, path))
        entry = self.entries.get(key)
        name = entry[0] if entry else ('record' if key in self.rows
                                       else None)
        return {'name': name, 'alternatives': [], 'state': tuple(path)}

    def top(self, name, tag):
        return self.child((), tag)

    def child(self, state, tag):
        cls, number = tag
        path = tuple(state or ())
        if cls != 0:
            path += (number,)
        return self._info(path)

    def describe(self, state):
        key = '.'.join(map(str, state or ()))
        entry = self.entries.get(key)
        kind = entry[1] if entry else None
        return {'type': kind, 'chain': [f'tagmap:{kind}'] if kind else [],
                'named_numbers': None, 'named_bits': None,
                'map_path': key or None}

    def dump_state(self, state):
        return None if state is None else json.dumps(list(state))

    def load_state(self, text):
        if not text:
            return ()
        try:
            value = json.loads(text)
            return tuple(int(part) for part in value)
        except (ValueError, TypeError):
            return None
