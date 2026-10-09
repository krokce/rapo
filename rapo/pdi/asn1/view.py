"""Contains the ASN.1 view of the files of the file log.

A file is read under the rules of a download (download.locate), decompressed
as the text viewer does (viewer._open), as BER from a start offset. Nothing
is kept between requests but the noted child offsets (ber.index) and the
gzip checkpoints, so each request opens the file and reads what it answers:
a page of the children of one node, one node's value, the nodes down to an
offset, a node's subtree as XML or text, or a stretch of a search.

With a grammar (an uploaded one, by name) and a top type, a node also gets
its name and type; its `state` is what the client sends back to get its
children named.
"""

import os
import re
import time
from xml.sax.saxutils import escape, quoteattr

from ...logger import logger

from .. import download, viewer, viewer_config
from ..files import number_option
from ..store import DatasourceError
from . import ber, values
from .ber import FILLERS, MAX_RECORD_HEADER
from .grammar import GrammarError

MAX_BYTES = 64 * 1024
DETAIL_BYTES = 4096
RENDER_CHARS = 2 * 1024 * 1024
MAX_PAGE = 5000
SEARCH_BLOCK = 1024 * 1024
XML_NAME = re.compile(r'[A-Za-z_][\w.-]*')


def tag_text(cls, number):
    """Get the tag as ASN.1 writes it: [3], [APPLICATION 1], SEQUENCE."""
    if cls == 0:
        return ber.UNIVERSAL_NAMES.get(number, f'[UNIVERSAL {number}]')
    if cls == 2:
        return f'[{number}]'
    return f'[{ber.CLASSES[cls]} {number}]'


def _number(value, name):
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        raise DatasourceError(f'{name} must be a number.')
    if number < 0:
        raise DatasourceError(f'{name} must not be negative.')
    return number


class _File:
    """A file of the file log read as BER from a start offset (with a record
    header before each record and the filler between records), and the
    grammar (and top type) naming its nodes."""

    def __init__(self, id, start_offset=0, grammar=None, top=None,
                 record_header=0, filler='00ff'):
        self.file = download.locate(id)
        self.start = _number(start_offset, 'start_offset')
        self.record_header = _number(record_header, 'record_header')
        if self.record_header > MAX_RECORD_HEADER:
            raise DatasourceError(f'record_header is at most '
                                  f'{MAX_RECORD_HEADER} bytes.')
        if (filler or '00ff') not in FILLERS:
            raise DatasourceError('filler is 00ff, ff or none.')
        self.filler = filler or '00ff'
        self.grammar_name = grammar or None
        self.grammar = viewer_config.load_grammar(grammar) \
            if grammar else None
        self.top = top or None
        if self.grammar is not None and self.top:
            try:
                self.grammar.top_handle(self.top)
            except GrammarError as error:
                raise DatasourceError(str(error))

    def __enter__(self):
        self.opener = viewer._open(self.file['path'])
        self.stream = self.opener.__enter__()
        try:
            self.source = ber.Source(self.stream)
            status = os.stat(self.file['path'])
            self.notes = ber.index((self.file['path'], status.st_size,
                                    status.st_mtime_ns, self.start,
                                    self.record_header, self.filler))
        except Exception:
            self.opener.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args):
        return self.opener.__exit__(*args)

    def meta(self):
        return {'id': self.file['id'], 'name': self.file['name'],
                'size': self.file['size'], 'compression': self.stream.kind,
                'data_size': self.stream.data_size(),
                'start_offset': self.start,
                'record_header': self.record_header, 'filler': self.filler,
                'grammar': self.grammar_name,
                'grammar_kind': self.grammar.kind if self.grammar else None,
                'top': self.top}

    def root(self):
        return ber.Parent(None, self.start, None, root=True,
                          record_header=self.record_header,
                          filler=FILLERS[self.filler])

    def guess_top(self):
        """Take the first top type the file's first TLV matches, when a
        grammar is given without one."""
        if self.grammar is None or self.top:
            return
        found, _ = ber.page(self.source, self.root(), self.notes, 0, 1)
        if found and found[0].item is not None:
            self.top = self.grammar.guess_top(found[0].item.tag)

    def root_info(self, node):
        if self.grammar is None or node.item is None or (
                not self.top and self.grammar.kind == 'asn1'):
            return None
        return self.grammar.top(self.top, node.item.tag)

    def child_info(self, state):
        """Get a function naming the children of a node of a state."""
        def info(node):
            if state is None or node.item is None:
                return None
            return self.grammar.child(state, node.item.tag)
        return info

    def describe(self, node, info, detail=False):
        """Get a node as answered: its TLV facts, tag, name, type and state
        with a grammar, and the preview of a primitive value (with
        `detail`, its readings and first DETAIL_BYTES bytes too)."""
        result = node.as_dict()
        if node.undecodable:
            return result
        item = node.item
        result['tag'] = tag_text(item.cls, item.number)
        description = None
        if self.grammar is not None:
            result['unknown'] = info is None
            if info is not None:
                result['name'] = info['name']
                result['alternatives'] = info['alternatives']
                result['state'] = self.grammar.dump_state(info['state'])
                description = self.grammar.describe(info['state'])
                result['type'] = description['type']
        if not item.constructed:
            length = result['length']
            data = node.value(self.source, DETAIL_BYTES if detail
                              else ber.PREVIEW_BYTES)
            read = values.read(data, item.cls, item.number, description,
                               length)
            result['preview'] = read['preview']
            if read['preview'] is None and length:
                result['preview_hex'] = values.hex_text(data, length=length)
            if detail:
                result['readings'] = read['readings']
                result['hex'] = data.hex()
                result['hex_cut'] = length > len(data)
        if detail and description is not None:
            result['type_chain'] = [name for name in description['chain']
                                    if not name.startswith('tagmap:')]
            if description.get('map_path'):
                result['map_path'] = description['map_path']
        return result

    def node_at(self, offset):
        item = ber.header(self.source, offset)
        if item is None:
            raise DatasourceError(f'There is no ASN.1 node at offset '
                                  f'{offset}.')
        end = ber.end_of(self.source, item)
        if end is None:
            raise DatasourceError(f'The node at offset {offset} has no '
                                  f'end.')
        return ber.Node(item, offset, end, None)

    def label(self, node, info):
        """Get the path segment of a node: its name, else its tag."""
        if node.undecodable:
            return 'undecodable'
        if info is not None:
            if info['name']:
                return info['name']
            if info['alternatives']:
                return info['alternatives'][-1]
            # An element of a SEQUENCE OF: its type.
            declared = self.grammar.describe(info['state'])['type']
            if declared and XML_NAME.fullmatch(declared):
                return declared
        return tag_text(node.item.cls, node.item.number)


def nodes(id, parent=None, state=None, ordinal=0, count=None,
          start_offset=0, grammar=None, top=None, record_header=0,
          filler='00ff'):
    """Get a page of the children of a node (`parent`: its offset), or of the
    root.

    Returns
    -------
    result : dict
        The file's facts, `nodes` from the `ordinal`-th child, `eof` when they
        are the last ones, and `top`, the top type (guessed when a grammar
        is given without one).
    """
    count = min(max(int(count or number_option('asn1_page_nodes')), 1),
                MAX_PAGE)
    ordinal = _number(ordinal, 'ordinal')
    with _File(id, start_offset, grammar, top, record_header,
               filler) as file:
        if parent is None:
            file.guess_top()
            holder = file.root()
            info = file.root_info
        else:
            item = ber.header(file.source, _number(parent, 'parent'))
            holder = ber.Parent.of(file.source, item) \
                if item is not None and item.constructed else None
            if holder is None:
                raise DatasourceError(f'There is no constructed node at '
                                      f'offset {parent}.')
            info = file.child_info(file.grammar.load_state(state)
                                   if file.grammar is not None else None)
        found, eof = ber.page(file.source, holder, file.notes, ordinal,
                              count)
        return {**file.meta(), 'parent': parent, 'ordinal': ordinal,
                'nodes': [file.describe(node, info(node)) for node in found],
                'eof': eof}


def node(id, offset, state=None, start_offset=0, grammar=None, top=None,
         record_header=0, filler='00ff'):
    """Get one node with what its value reads as (the details pane)."""
    with _File(id, start_offset, grammar, top, record_header,
               filler) as file:
        found = file.node_at(_number(offset, 'offset'))
        info = None
        if file.grammar is not None:
            loaded = file.grammar.load_state(state)
            if loaded is not None:
                info = {'name': None, 'alternatives': [], 'state': loaded}
        return {**file.meta(), 'node': file.describe(found, info,
                                                     detail=True)}


def locate(id, offset, start_offset=0, grammar=None, top=None,
           record_header=0, filler='00ff'):
    """Get the nodes holding an offset, from the root down to the deepest.

    Returns
    -------
    result : dict
        The file's facts and `levels`, `[{parent, node}]` (`parent`: the
        offset of the node the node is a child of, None for the root).
    """
    offset = _number(offset, 'offset')
    with _File(id, start_offset, grammar, top, record_header,
               filler) as file:
        file.guess_top()
        levels = []
        for parent, found, info in _chain(file, offset):
            levels.append({'parent': parent,
                           'node': file.describe(found, info)})
        return {**file.meta(), 'offset': offset, 'levels': levels}


def _chain(file, offset):
    holder, info_of = file.root(), file.root_info
    while True:
        found = ber.child_at(file.source, holder, file.notes, offset)
        if found is None:
            return
        info = info_of(found)
        yield holder.key, found, info
        item = found.item
        if found.undecodable or not item.constructed or \
                offset < item.value_offset:
            return
        holder = ber.Parent.of(file.source, item)
        if holder is None or offset >= holder.limit:
            return
        info_of = _info_of(file, info)


def read_bytes(id, offset, size=MAX_BYTES):
    """Get uncompressed bytes of a file of the file log.

    Returns
    -------
    result : tuple
        `(bytes, data size or None)`; fewer bytes than asked at the end.
    """
    offset = _number(offset, 'offset')
    size = min(max(_number(size, 'size'), 1), MAX_BYTES)
    file = download.locate(id)
    with viewer._open(file['path']) as stream:
        stream.seek(offset)
        data = stream.read(size)
        return data, stream.data_size()


def render(id, offset, state=None, format='xml', start_offset=0,
           grammar=None, top=None, record_header=0, filler='00ff'):
    """Get a node's subtree as XML or as an indented text listing, at most
    [DATASOURCES] asn1_render_nodes nodes and RENDER_CHARS characters.

    Returns
    -------
    result : dict
        `{text, nodes, truncated}`.
    """
    if format not in ('xml', 'text'):
        raise DatasourceError('format is xml or text.')
    limit = max(number_option('asn1_render_nodes'), 1)
    with _File(id, start_offset, grammar, top, record_header,
               filler) as file:
        root = file.node_at(_number(offset, 'offset'))
        info = None
        if file.grammar is not None:
            loaded = file.grammar.load_state(state)
            if loaded is not None:
                info = {'name': None, 'alternatives': [], 'state': loaded}
        lines, count = [], 0
        size, truncated = 0, False
        for depth, event, found, found_info in _subtree(file, root, info):
            if event == 'node':
                count += 1
                if count > limit:
                    truncated = True
                    break
            line = (_xml_line if format == 'xml' else _text_line)(
                file, depth, event, found, found_info)
            if line is None:
                continue
            size += len(line) + 1
            if size > RENDER_CHARS:
                truncated = True
                break
            lines.append(line)
        if truncated and format == 'xml':
            lines.append('<!-- cut: the subtree has more nodes than shown '
                         '-->')
        return {'text': '\n'.join(lines), 'nodes': min(count, limit),
                'truncated': truncated}


def _subtree(file, node, info, depth=0):
    """Yield `(depth, 'node' | 'close', node, info)` of a subtree, depth
    first; 'close' after the children of a constructed node."""
    yield depth, 'node', node, info
    item = node.item
    if node.undecodable or not item.constructed:
        return
    holder = ber.Parent.of(file.source, item)
    if holder is None:
        return
    info_of = _info_of(file, info)
    for child in ber.children(file.source, holder, file.notes):
        yield from _subtree(file, child, info_of(child), depth + 1)
    yield depth, 'close', node, info


def _xml_name(file, node, info):
    label = file.label(node, info) if info is not None else 'Tag'
    return label if XML_NAME.fullmatch(label) else 'Tag'


def _xml_line(file, depth, event, node, info):
    indent = '  ' * depth
    if node.undecodable:
        return None if event == 'close' else (
            f'{indent}<Undecodable offset="{node.offset}" '
            f'length="{node.end - node.offset}"/>')
    name = _xml_name(file, node, info)
    if event == 'close':
        return f'{indent}</{name}>'
    described = file.describe(node, info)
    attributes = f'tag={quoteattr(described["tag"])} ' \
                 f'offset="{node.offset}" length="{described["length"]}"'
    if described.get('type'):
        attributes += f' type={quoteattr(described["type"])}'
    if described['constructed']:
        if not described['has_children']:
            return f'{indent}<{name} {attributes}/>'
        return f'{indent}<{name} {attributes}>'
    data = node.value(file.source, DETAIL_BYTES)
    hex_value = data.hex().upper() + ('…' if described['length'] > len(
        data) else '')
    attributes += f' hex="{hex_value}"'
    preview = described.get('preview')
    if preview is None:
        return f'{indent}<{name} {attributes}/>'
    return f'{indent}<{name} {attributes}>{escape(preview)}</{name}>'


def _text_line(file, depth, event, node, info):
    if event == 'close':
        return None
    if node.undecodable:
        return f'{node.offset:>10} {"":>2} {node.end - node.offset:>7}: ' \
               f'{"  " * depth}(undecodable)'
    described = file.describe(node, info)
    label = file.label(node, info)
    tag = described['tag']
    head = f'{label} {tag}' if label != tag else tag
    if described.get('type'):
        head += f' {described["type"]}'
    line = f'{node.offset:>10} {described["header_len"]:>2} ' \
           f'{described["length"]:>7}: {"  " * depth}{head}'
    if not described['constructed']:
        value = described.get('preview')
        if value is None:
            value = described.get('preview_hex', '')
        line += f': {value}'
    return line


def search(id, field=None, value=None, match='contains', hex=None,
           offset=0, start_offset=0, grammar=None, top=None, record_header=0,
           filler='00ff'):
    """Find nodes by field and value, or byte sequences, from an offset.

    `field` is a path of names or tags (`servedIMSI`, `[20]/[3]`,
    `listOfTrafficVolumes.dataVolumeGPRSUplink`), matched against the end of
    a node's path; `value` matches (`equals` or `contains`, any case) what a
    primitive value reads as or its hex. `hex` finds bytes instead. It reads
    on until [DATASOURCES] view_grep_matches hits or view_grep_seconds
    passed; the next request goes on from `next_offset`.

    Returns
    -------
    result : dict
        The file's facts, `hits` (`[{offset, path, preview}]`),
        `next_offset`, `eof`, `scanned_bytes` and `stopped` (`matches`,
        `time` or None).
    """
    offset = _number(offset, 'offset')
    if match not in ('contains', 'equals'):
        raise DatasourceError('match is contains or equals.')
    pattern = None
    if hex:
        text = re.sub(r'[\s:]', '', hex)
        if not text or len(text) % 2 or not re.fullmatch(r'[0-9A-Fa-f]+',
                                                         text):
            raise DatasourceError('Give the bytes as hex digits, e.g. '
                                  '80 04 0A F9.')
        pattern = bytes.fromhex(text)
    elif not (field or '').strip() and not (value or '').strip():
        raise DatasourceError('Give a field, a value or hex bytes to find.')
    limit = max(number_option('view_grep_matches'), 1)
    deadline = time.monotonic() + max(number_option('view_grep_seconds'), 1)
    started = time.monotonic()
    with _File(id, start_offset, grammar, top, record_header,
               filler) as file:
        file.guess_top()
        if pattern is not None:
            result = _search_bytes(file, pattern, offset, limit, deadline)
        else:
            result = _search_nodes(file, field, value, match, offset, limit,
                                   deadline)
        result = {**file.meta(), **result,
                  'scanned_bytes': result['next_offset'] - offset}
    what = f'bytes {hex}' if pattern is not None else \
        f'field {field!r} value {value!r}'
    logger.info(f'File searched as ASN.1: {result["name"]} (file ID {id}) '
                f'for {what}, {len(result["hits"])} hit(s) in '
                f'{time.monotonic() - started:.1f} s')
    return result


def _field_test(field):
    """Get a test of a node's path for a field path, or None for any."""
    parts = [part.strip().lower() for part in re.split(r'[/.]', field or '')
             if part.strip()]
    if not parts:
        return None
    parts = [f'[{part}]' if part.isdigit() else part for part in parts]

    def test(path):
        if len(path) < len(parts):
            return False
        for wanted, segment in zip(reversed(parts), reversed(path)):
            if wanted not in segment:
                return False
        return True
    return test


def _value_test(value, match):
    if not (value or '').strip():
        return None
    wanted = value.strip().lower()
    hex_wanted = re.sub(r'\s', '', wanted)

    def test(described):
        texts = [described.get('preview') or '']
        texts += [reading['value'] for reading in
                  described.get('readings') or []]
        texts.append(described.get('hex') or '')
        for text in texts:
            text = str(text).lower()
            if (match == 'equals' and text == wanted) or (
                    match == 'contains' and wanted in text):
                return True
        hex_text = (described.get('hex') or '').lower()
        return bool(hex_wanted) and (hex_text == hex_wanted if
                                     match == 'equals' else
                                     hex_wanted in hex_text)
    return test


def _search_nodes(file, field, value, match, offset, limit, deadline):
    field_test = _field_test(field)
    value_test = _value_test(value, match)
    hits, position, stopped, eof = [], offset, None, True
    for found, info, path, labels in _walk(file, offset):
        if found.offset < offset:
            continue
        if time.monotonic() > deadline:
            stopped, eof, position = 'time', False, found.offset
            break
        position = found.offset + 1
        if found.undecodable:
            continue
        if field_test is not None and not field_test(path):
            continue
        if value_test is not None:
            if found.item.constructed:
                continue
            described = file.describe(found, info, detail=True)
            if not value_test(described):
                continue
        else:
            described = file.describe(found, info)
        hits.append({'offset': found.offset, 'path': '/'.join(labels),
                     'preview': described.get('preview') or
                     described.get('preview_hex')})
        if len(hits) >= limit:
            stopped, eof = 'matches', False
            break
    if eof and file.source.size is not None:
        position = max(position, file.source.size)
    return {'hits': hits, 'next_offset': position, 'eof': eof,
            'stopped': stopped}


def _walk(file, offset):
    """Yield `(node, info, path, labels)` of every node ending after an
    offset, depth first: `path` holds the names and tag of each node down
    to it (lower case, to match), `labels` the labels shown."""
    def walk(holder, info_of, path, labels):
        for found in ber.children_after(file.source, holder, file.notes,
                                        offset):
            info = info_of(found)
            label = file.label(found, info)
            segment = {label.lower()}
            if found.item is not None:
                segment.add(tag_text(found.item.cls,
                                     found.item.number).lower())
            if info is not None:
                segment.update(name.lower() for name in info['alternatives'])
            here, shown = path + [segment], labels + [label]
            yield found, info, here, shown
            item = found.item
            if found.undecodable or not item.constructed:
                continue
            inner = ber.Parent.of(file.source, item)
            if inner is not None:
                yield from walk(inner, _info_of(file, info), here, shown)
    yield from walk(file.root(), file.root_info, [], [])


def _info_of(file, info):
    if file.grammar is None:
        return lambda child: None
    return file.child_info(info['state'] if info else None)


def _search_bytes(file, pattern, offset, limit, deadline):
    hits, position, stopped, eof = [], offset, None, False
    seen = set()
    while True:
        file.stream.seek(position)
        block = file.stream.read(SEARCH_BLOCK + len(pattern) - 1)
        at = block.find(pattern)
        while at >= 0 and at < SEARCH_BLOCK:
            hit = position + at
            chain = list(_chain(file, hit))
            if chain:
                found, info = chain[-1][1], chain[-1][2]
                key = found.offset
                if key not in seen:
                    seen.add(key)
                    described = file.describe(found, info)
                    hits.append({
                        'offset': found.offset, 'match': hit,
                        'path': '/'.join(file.label(item, item_info) for
                                         _, item, item_info in chain),
                        'preview': described.get('preview') or
                        described.get('preview_hex')})
            else:
                hits.append({'offset': None, 'match': hit,
                             'path': '(no node)', 'preview': None})
            if len(hits) >= limit:
                return {'hits': hits, 'next_offset': hit + 1, 'eof': False,
                        'stopped': 'matches'}
            at = block.find(pattern, at + 1)
        if len(block) < SEARCH_BLOCK + len(pattern) - 1:
            position += len(block)
            eof = True
            break
        position += SEARCH_BLOCK
        if time.monotonic() > deadline:
            stopped = 'time'
            break
    return {'hits': hits, 'next_offset': position, 'eof': eof,
            'stopped': stopped}
