"""Contains a tolerant reader of BER (and so DER and CER) encodings.

A file is read as TLVs one after another from a start offset (the root),
skipping 00 and FF bytes between them (the padding of block-written CDR
files); a TLV is a node, the TLVs inside a constructed one its children.
Nothing is decoded ahead: a request reads the headers of one page of the
children of one node. Bytes that are no TLV become an undecodable node, so a
broken file is shown as far as it can be.

The children of a node are counted from its start, so a page from the n-th
child needs the headers before it: every INDEX_EVERY children the offset is
noted (per file, start offset and parent), and a later request starts from
the note before it.
"""

import bisect
import collections
import io
import threading

# The universal class number names, for labels (X.680 8.6).
UNIVERSAL_NAMES = {
    0: 'EOC', 1: 'BOOLEAN', 2: 'INTEGER', 3: 'BIT STRING',
    4: 'OCTET STRING', 5: 'NULL', 6: 'OBJECT IDENTIFIER',
    7: 'ObjectDescriptor', 8: 'EXTERNAL', 9: 'REAL', 10: 'ENUMERATED',
    11: 'EMBEDDED PDV', 12: 'UTF8String', 13: 'RELATIVE-OID', 14: 'TIME',
    16: 'SEQUENCE', 17: 'SET', 18: 'NumericString', 19: 'PrintableString',
    20: 'TeletexString', 21: 'VideotexString', 22: 'IA5String',
    23: 'UTCTime', 24: 'GeneralizedTime', 25: 'GraphicString',
    26: 'VisibleString', 27: 'GeneralString', 28: 'UniversalString',
    29: 'CHARACTER STRING', 30: 'BMPString', 31: 'DATE', 32: 'TIME-OF-DAY',
    33: 'DATE-TIME', 34: 'DURATION'
}
CLASSES = ('UNIVERSAL', 'APPLICATION', 'CONTEXT', 'PRIVATE')
FILLER = b'\x00\xff'
# Bytes the source reads at once; headers of nearby TLVs come from them.
WINDOW = 256 * 1024
# A child offset is noted every this many children.
INDEX_EVERY = 256
# How far a broken root is searched for the next TLV, and how deep TLVs nest.
RESYNC_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 64
# Value bytes a node carries for its preview.
PREVIEW_BYTES = 64
FILES = 16


class Source:
    """Random access to the uncompressed bytes of a stream of viewer._open,
    through a window of WINDOW bytes."""

    def __init__(self, stream, size=None):
        self.stream = stream
        self.base = 0
        self.data = b''
        # The end, once a read found it (or as known before).
        self.size = size

    def read(self, offset, size):
        end = offset + size
        if self.base <= offset and end <= self.base + len(self.data):
            return self.data[offset - self.base:end - self.base]
        self.stream.seek(offset)
        self.data = self.stream.read(max(size, WINDOW))
        self.base = offset
        if len(self.data) < max(size, WINDOW):
            self.size = offset + len(self.data)
        return self.data[:size]

    def byte(self, offset):
        data = self.read(offset, 1)
        return data[0] if data else None

    def at_end(self, offset):
        return not self.read(offset, 1)


class Header:
    """The header of a TLV at an offset: `cls` (0-3), `constructed`,
    `number`, `tag_len`, `header_len`, `length` (None: indefinite)."""

    __slots__ = ('offset', 'first', 'cls', 'constructed', 'number',
                 'tag_len', 'header_len', 'length', 'end')

    @property
    def value_offset(self):
        return self.offset + self.header_len

    @property
    def tag(self):
        return self.cls, self.number


def header(source, offset, limit=None):
    """Read the header of a TLV, or None when the bytes are none (or its
    definite length passes `limit`)."""
    data = source.read(offset, 16)
    if len(data) < 2:
        return None
    first = data[0]
    number = first & 0x1f
    index = 1
    if number == 0x1f:
        number = 0
        while True:
            if index >= len(data) or index > 5:
                return None
            byte = data[index]
            index += 1
            number = (number << 7) | (byte & 0x7f)
            if not byte & 0x80:
                break
    if index >= len(data):
        return None
    tag_len = index
    byte = data[index]
    index += 1
    if byte < 0x80:
        length = byte
    elif byte == 0x80:
        if not first & 0x20:
            return None
        length = None
    else:
        count = byte & 0x7f
        if count > 8 or index + count > len(data):
            return None
        length = int.from_bytes(data[index:index + count], 'big')
        index += count
    item = Header()
    item.offset = offset
    item.first = first
    item.cls = first >> 6
    item.constructed = bool(first & 0x20)
    item.number = number
    item.tag_len = tag_len
    item.header_len = index
    item.length = length
    item.end = None if length is None else offset + index + length
    if limit is not None and item.end is not None and item.end > limit:
        return None
    return item


def end_of(source, item, limit=None, depth=0):
    """Get the end of a TLV; an indefinite one is read to its EOC. None when
    its content is no TLVs."""
    if item.end is not None:
        return item.end
    if depth > MAX_DEPTH:
        return None
    position = item.value_offset
    while True:
        if source.read(position, 2) == b'\x00\x00':
            item.end = position + 2
            return item.end
        child = header(source, position, limit)
        if child is None:
            return None
        end = end_of(source, child, limit, depth + 1)
        if end is None:
            return None
        position = end


def content_end(item):
    """Get where the content of a TLV ends (before an EOC)."""
    return item.end - 2 if item.length is None else item.end


class Node:
    """A TLV, or bytes that are none (`undecodable`), as listed."""

    __slots__ = ('item', 'offset', 'end', 'ordinal', 'undecodable')

    def __init__(self, item, offset, end, ordinal, undecodable=False):
        self.item = item
        self.offset = offset
        self.end = end
        self.ordinal = ordinal
        self.undecodable = undecodable

    def value(self, source, limit=PREVIEW_BYTES):
        """Get the first `limit` bytes of a primitive TLV's value."""
        item = self.item
        if item is None or item.constructed:
            return b''
        return source.read(item.value_offset, min(item.length, limit))

    def as_dict(self):
        item = self.item
        if self.undecodable or item is None:
            return {'offset': self.offset, 'end': self.end,
                    'ordinal': self.ordinal, 'undecodable': True,
                    'length': self.end - self.offset}
        return {'offset': self.offset, 'end': self.end,
                'ordinal': self.ordinal, 'undecodable': False,
                'cls': CLASSES[item.cls], 'number': item.number,
                'constructed': item.constructed,
                'indefinite': item.length is None,
                'tag_len': item.tag_len, 'header_len': item.header_len,
                'length': content_end(item) - item.value_offset,
                'has_children': item.constructed and (
                    content_end(item) > item.value_offset)}


class Parent:
    """Where the children of a node (or the root) are read from."""

    def __init__(self, key, start, limit, root=False):
        # key: the parent's offset (None for the root).
        self.key = key
        self.start = start
        self.limit = limit
        self.root = root

    @classmethod
    def of(cls, source, item):
        end = end_of(source, item)
        if end is None:
            return None
        return cls(item.offset, item.value_offset, content_end(item))


class _Index:
    """The noted child offsets of the parents of one file: per parent
    `[(ordinal, offset)]` ascending, and the root's first tag byte."""

    def __init__(self):
        self.parents = {}
        self.first = None
        self.lock = threading.Lock()

    def before(self, key, ordinal):
        with self.lock:
            notes = self.parents.get(key) or [(0, None)]
            at = bisect.bisect_right([note[0] for note in notes], ordinal)
            return notes[max(at - 1, 0)]

    def before_offset(self, key, offset):
        with self.lock:
            notes = self.parents.get(key) or [(0, None)]
            found = notes[0]
            for note in notes:
                if note[1] is not None and note[1] > offset:
                    break
                found = note
            return found

    def note(self, key, ordinal, offset):
        if ordinal % INDEX_EVERY:
            return
        with self.lock:
            notes = self.parents.setdefault(key, [(0, None)])
            if ordinal > notes[-1][0]:
                notes.append((ordinal, offset))


_indexes = collections.OrderedDict()
_indexes_lock = threading.Lock()


def index(key):
    """Get the noted offsets of a file, kept for the FILES read last; the key
    names the file as it is (path, size, mtime) and the start offset."""
    with _indexes_lock:
        found = _indexes.pop(key, None) or _Index()
        _indexes[key] = found
        while len(_indexes) > FILES:
            _indexes.popitem(last=False)
    return found


def _skip_filler(source, position, limit):
    """Get the offset of the first byte from `position` that is no filler."""
    while limit is None or position < limit:
        data = source.read(position, 4096)
        if not data:
            return position
        stripped = data.lstrip(FILLER)
        position += len(data) - len(stripped)
        if stripped:
            return position
    return position


def _valid_root_tlv(source, position, first=None):
    """Get the header of a whole TLV at a root offset, or None: its end must
    be in the file and followed by the end, filler or another header."""
    if first is not None and source.byte(position) != first:
        return None
    item = header(source, position)
    if item is None or end_of(source, item) is None:
        return None
    if item.end > position + item.header_len and \
            not source.read(item.end - 1, 1):
        return None
    following = source.read(item.end, 16)
    if following and following[0] not in FILLER and \
            header(source, item.end) is None:
        return None
    return item


def _resync(source, position, first):
    """Get the next root offset after `position` where a whole TLV starts
    (with the tag byte of the root's first TLV, when known), or None."""
    stop = position + RESYNC_BYTES
    position += 1
    while position < stop:
        data = source.read(position, 64 * 1024)
        if not data:
            return None
        if first is None:
            candidates = range(len(data))
        else:
            candidates = []
            at = data.find(bytes([first]))
            while at >= 0:
                candidates.append(at)
                at = data.find(bytes([first]), at + 1)
        for at in candidates:
            if _valid_root_tlv(source, position + at, first) is not None:
                return position + at
        position += len(data)
    return None


def children(source, parent, notes):
    """Yield the children of a parent as Nodes, from the first, noting their
    offsets in `notes` (an _Index)."""
    yield from _children_from(source, parent, notes, 0, None)


def _children_from(source, parent, notes, ordinal, position):
    if position is None:
        position = parent.start
    limit = parent.limit
    while True:
        if parent.root:
            position = _skip_filler(source, position, limit)
        if (limit is not None and position >= limit) or \
                source.at_end(position):
            return
        notes.note(parent.key, ordinal, position)
        if parent.root:
            item = _valid_root_tlv(source, position)
            if item is not None and notes.first is None:
                notes.first = item.first
        else:
            item = header(source, position, limit)
            if item is not None and end_of(source, item, limit) is None:
                item = None
        if item is None:
            end = _resync(source, position, notes.first) \
                if parent.root else None
            if end is None:
                end = limit if limit is not None else _file_end(source,
                                                                position)
            yield Node(None, position, end, ordinal, undecodable=True)
            if end is None or end <= position:
                return
            position = end
        else:
            yield Node(item, position, item.end, ordinal)
            position = item.end
        ordinal += 1


def _file_end(source, position):
    """Get the end of the file, reading on from a position."""
    while True:
        data = source.read(position, WINDOW)
        if len(data) < WINDOW:
            return position + len(data)
        position += len(data)


def page(source, parent, notes, ordinal, count):
    """Get `count` children of a parent from the `ordinal`-th, and whether
    they are the last ones."""
    start_ordinal, position = notes.before(parent.key, ordinal)
    found = []
    walker = _children_from(source, parent, notes, start_ordinal, position)
    for node in walker:
        if node.ordinal < ordinal:
            continue
        if len(found) == count:
            return found, False
        found.append(node)
    return found, True


def children_after(source, parent, notes, offset):
    """Yield the children of a parent that end after an offset."""
    ordinal, position = notes.before_offset(parent.key, offset)
    for node in _children_from(source, parent, notes, ordinal, position):
        if node.end is None or node.end > offset:
            yield node


def child_at(source, parent, notes, offset):
    """Get the child of a parent that holds an offset, or None."""
    ordinal, position = notes.before_offset(parent.key, offset)
    for node in _children_from(source, parent, notes, ordinal, position):
        if node.offset > offset:
            return None
        if node.end is not None and offset < node.end:
            return node
    return None


def sniff(data):
    """Whether the first bytes of a file look like BER: after any filler a
    constructed TLV whose header reads, followed (when within the bytes) by
    filler, the end or another TLV."""
    source = Source(io.BytesIO(data), len(data))
    position = _skip_filler(source, 0, len(data))
    item = header(source, position)
    if item is None or not item.constructed:
        return False
    end = end_of(source, item) if item.end is None or item.end <= len(
        data) else item.end
    if end is None:
        return False
    if end >= len(data):
        return item.length is None or item.length < (1 << 40)
    following = data[end:end + 16]
    return following[0] in FILLER or header(source, end) is not None
