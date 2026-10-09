"""Contains the ASN.1 grammars that name the nodes of a BER file.

A grammar is a set of ASN.1 modules (.asn files), parsed by asn1tools'
parse_string into plain dicts; only the parse is used, never its codecs, so a
file that does not follow the grammar is still read node by node. A node's
type is a *state*: a handle (module, type name, then the members `m:<name>`
and elements `e` down to an inline type) and the index of the tag layer the
node encodes. A type's layers are its tags from the outside in (X.690): an
explicit tag wraps the encoding of the type inside it, an implicit one
replaces its outer tag, an untagged CHOICE has none of its own and is matched
by the tag of an alternative. A tag the grammar does not expect leaves the
node unnamed, and its children too.
"""

import collections
import concurrent.futures
import hashlib
import json
import re
import threading

from .ber import UNIVERSAL_NAMES

CLASS_NUMBERS = {'UNIVERSAL': 0, 'APPLICATION': 1, 'PRIVATE': 3}
UNIVERSAL_NUMBERS = {name: number for number, name in UNIVERSAL_NAMES.items()}
UNIVERSAL_NUMBERS.update({'SEQUENCE OF': 16, 'SET OF': 17, 'T61String': 20,
                          'ISO646String': 26})
UNTAGGED = ('CHOICE', 'ANY', 'ANY DEFINED BY', 'OPEN TYPE', 'OpenType')
STRUCTURED = ('SEQUENCE', 'SET', 'CHOICE')
LISTS = ('SEQUENCE OF', 'SET OF')
# Parsed grammars kept, and seconds a parse may take.
GRAMMARS = 8
PARSE_SECONDS = 30
MAX_DEPTH = 32


class GrammarError(Exception):
    """A grammar that can not be parsed or used."""


class Layer(collections.namedtuple('Layer', 'cls number wrapper')):
    """One tag of a type: `wrapper` when its content is the next layer's
    encoding (an explicit tag), else the type's own content."""

    @property
    def tag(self):
        return self.cls, self.number


class Base(collections.namedtuple('Base', 'handle module typedef chain')):
    """What a type is under its tags: the handle and module of the type
    definition, the definition, and the names of the types passed to reach
    it (for the value decoders)."""


def parse(files, timeout=PARSE_SECONDS):
    """Parse the files of a grammar, `[(file name, text)]`, into modules.

    A file without a module header (only type assignments, as some copies of
    the GSMA TDs are) is read as a module named after the file with IMPLICIT
    TAGS. Raises GrammarError naming the file and line.

    Returns
    -------
    result : dict
        `{modules: {name: module dict}, wrapped: [file names]}`.
    """
    pool = concurrent.futures.ThreadPoolExecutor(1)
    future = pool.submit(_parse, files)
    pool.shutdown(wait=False)
    try:
        return future.result(timeout)
    except concurrent.futures.TimeoutError:
        raise GrammarError(f'The grammar took more than {timeout} seconds '
                           f'to parse.')


def _parse(files):
    import asn1tools
    modules, wrapped = {}, []
    for name, text in files:
        text = text.replace('\r\n', '\n').lstrip('\ufeff') + '\n'
        try:
            parsed = asn1tools.parse_string(text)
        except asn1tools.ParseError as error:
            if re.search(r'\bDEFINITIONS\b', _strip_comments(text)):
                raise GrammarError(f'{name}: {error}')
            module = _module_name(name)
            try:
                parsed = asn1tools.parse_string(
                    f'{module} DEFINITIONS IMPLICIT TAGS ::=\nBEGIN\n'
                    f'{text}\nEND\n')
            except asn1tools.ParseError as wrapped_error:
                message = str(wrapped_error)
                # The text starts 2 lines down in the wrapped module.
                message = re.sub(
                    r'line (\d+)',
                    lambda found: f'line {max(int(found.group(1)) - 2, 1)}',
                    message, count=1)
                raise GrammarError(f'{name}: {message}')
            wrapped.append(name)
        except Exception as error:
            raise GrammarError(f'{name}: {error}')
        for module, content in parsed.items():
            if module in modules:
                raise GrammarError(f'{name}: module {module} is defined '
                                   f'twice in the grammar.')
            modules[module] = content
    if not modules:
        raise GrammarError('The grammar has no modules.')
    return {'modules': modules, 'wrapped': wrapped}


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'--.*?(--|$)', ' ', text, flags=re.M)


def _module_name(file_name):
    stem = re.sub(r'\.[^.]*$', '', file_name)
    stem = re.sub(r'[^A-Za-z0-9-]+', '-', stem).strip('-') or 'Grammar'
    stem = re.sub(r'-{2,}', '-', stem)
    if not stem[0].isalpha():
        stem = f'M-{stem}'
    return stem[0].upper() + stem[1:]


_grammars = collections.OrderedDict()
_grammars_lock = threading.Lock()


def load(files):
    """Get the Grammar of files `[(name, text)]`, parsed once per content
    for the GRAMMARS used last."""
    digest = hashlib.sha1(json.dumps(files).encode()).hexdigest()
    with _grammars_lock:
        grammar = _grammars.pop(digest, None)
        if grammar is not None:
            _grammars[digest] = grammar
            return grammar
    grammar = Grammar(parse(files)['modules'])
    with _grammars_lock:
        _grammars[digest] = grammar
        while len(_grammars) > GRAMMARS:
            _grammars.popitem(last=False)
    return grammar


class Grammar:
    """Parsed modules, and how they name the nodes of a BER encoding."""

    kind = 'asn1'

    def __init__(self, modules):
        self.modules = modules
        self.layer_cache = {}
        self.lock = threading.Lock()

    # Types and handles.

    def typedef(self, handle):
        module, name, *steps = handle
        typedef = self.modules[module]['types'][name]
        for step in steps:
            if step == 'e':
                typedef = typedef['element']
            else:
                typedef = dict(self.members(module, typedef))[step[2:]]
        return typedef

    def find(self, module, name):
        """Get the handle of a type named in a module: its own, imported, or
        in another module of the grammar; None when not defined."""
        if '.' in name and name.split('.', 1)[0] in self.modules:
            module, name = name.split('.', 1)
        content = self.modules.get(module)
        if content and name in content['types']:
            return module, name
        if content:
            for source, names in (content.get('imports') or {}).items():
                if name in names and source in self.modules and \
                        name in self.modules[source]['types']:
                    return source, name
        for other, content in self.modules.items():
            if name in content['types']:
                return other, name
        return None

    def members(self, module, typedef, depth=0):
        """Get `[(name, member typedef)]` of a SEQUENCE, SET or CHOICE, with
        COMPONENTS OF expanded and automatic tags given."""
        found = []
        for member in typedef.get('members') or []:
            if member is None:
                continue
            if 'components-of' in member:
                handle = self.find(module, member['components-of'])
                if handle is not None and depth < MAX_DEPTH:
                    found.extend(self.members(
                        handle[0], self.typedef(handle), depth + 1))
                continue
            if member.get('name'):
                found.append((member['name'], member))
        if self.modules[module].get('tags') == 'AUTOMATIC' and \
                not any('tag' in member for _, member in found):
            found = [(name, {**member, 'tag': {'number': index}})
                     for index, (name, member) in enumerate(found)]
        return found

    def default_kind(self, module):
        tags = self.modules[module].get('tags')
        return 'EXPLICIT' if tags in (None, 'EXPLICIT') else 'IMPLICIT'

    # Layers.

    def layers(self, handle):
        """Get the tag Layers of a type and its Base (None: not defined)."""
        key = tuple(handle)
        with self.lock:
            cached = self.layer_cache.get(key)
        if cached is None:
            cached = self._layers(handle[0], self.typedef(handle), handle,
                                  (), 0)
            with self.lock:
                self.layer_cache[key] = cached
        return cached

    def _layers(self, module, typedef, handle, chain, depth):
        if depth > MAX_DEPTH:
            return [], None
        tag = typedef.get('tag')
        if tag:
            untagged = {key: value for key, value in typedef.items()
                        if key != 'tag'}
            inner, base = self._layers(module, untagged, handle, chain,
                                       depth + 1)
            cls = CLASS_NUMBERS.get(tag.get('class'), 2)
            kind = tag.get('kind') or self.default_kind(module)
            if kind == 'EXPLICIT' or not inner:
                return [Layer(cls, tag['number'], True)] + inner, base
            return [Layer(cls, tag['number'], inner[0].wrapper)] + \
                inner[1:], base
        name = typedef.get('type')
        if name in UNTAGGED:
            return [], Base(handle, module, typedef, chain + (name,))
        if name in UNIVERSAL_NUMBERS:
            return [Layer(0, UNIVERSAL_NUMBERS[name], False)], Base(
                handle, module, typedef, chain + (name,))
        if name and '.&' in name:
            field = self.class_field(module, name)
            if field is None:
                return [], None
            return self._layers(module, field, handle, chain + (name,),
                                depth + 1)
        found = self.find(module, name) if name else None
        if found is None:
            return [], None
        return self._layers(found[0], self.typedef(found), found,
                            chain + (name,), depth + 1)

    def class_field(self, module, name):
        """Get the type of an information object class field (CLASS.&field,
        an open type when it is a type field), or None."""
        class_name, field = name.split('.', 1)
        modules = [module] + [source for source, names in (
            self.modules[module].get('imports') or {}).items()
            if class_name in names] + list(self.modules)
        for candidate in modules:
            classes = (self.modules.get(candidate) or {}).get(
                'object-classes') or {}
            if class_name in classes:
                for member in classes[class_name].get('members') or []:
                    if member and member.get('name') == field:
                        return {'type': member.get('type') or 'OpenType'}
                return None
        return None

    # Matching tags.

    def match(self, handle, layer, tag, depth=0):
        """Match a TLV tag against a type from a layer: get `(handle, layer,
        alternatives)` (the CHOICE alternatives passed) or None."""
        layers, base = self.layers(handle)
        if layer < len(layers):
            return (handle, layer, []) if layers[layer].tag == tag else None
        if base is None or depth > MAX_DEPTH or \
                base.typedef.get('type') != 'CHOICE':
            return None
        for name, _ in self.members(base.module, base.typedef):
            alternative = tuple(base.handle) + (f'm:{name}',)
            found = self.match(alternative, 0, tag, depth + 1)
            if found is not None:
                return found[0], found[1], [name] + found[2]
        return None

    def child(self, state, tag):
        """Get what a child TLV with a tag is inside a node of a state:
        `{name, alternatives, state}`, or None when not expected."""
        handle, layer = state
        layers, base = self.layers(handle)
        if layer < len(layers) and layers[layer].wrapper:
            found = self.match(handle, layer + 1, tag)
            return None if found is None else {
                'name': None, 'alternatives': found[2],
                'state': (found[0], found[1])}
        if base is None:
            return None
        kind = base.typedef.get('type')
        if kind in ('SEQUENCE', 'SET'):
            for name, _ in self.members(base.module, base.typedef):
                member = tuple(base.handle) + (f'm:{name}',)
                found = self.match(member, 0, tag)
                if found is not None:
                    return {'name': name, 'alternatives': found[2],
                            'state': (found[0], found[1])}
            return None
        if kind in LISTS:
            found = self.match(tuple(base.handle) + ('e',), 0, tag)
            return None if found is None else {
                'name': None, 'alternatives': found[2],
                'state': (found[0], found[1])}
        return None

    def top(self, name, tag):
        """Match a root TLV against the top type `Module.Type`."""
        handle = self.top_handle(name)
        found = self.match(handle, 0, tag)
        return None if found is None else {
            'name': None, 'alternatives': found[2],
            'state': (found[0], found[1])}

    def top_handle(self, name):
        module, _, type_name = (name or '').partition('.')
        if module not in self.modules or \
                type_name not in self.modules[module]['types']:
            raise GrammarError(f'The grammar has no type {name}.')
        return module, type_name

    # What a state is.

    def describe(self, state):
        """Get the type name to show of a node of a state and what decodes
        its value: `{type, chain, named_numbers, named_bits, constructed}`."""
        handle, layer = state
        layers, base = self.layers(handle)
        typedef = self.typedef(handle)
        declared = handle[1] if len(handle) == 2 else typedef.get('type')
        if declared in LISTS:
            element = typedef.get('element') or {}
            declared = f'{declared} {element.get("type", "")}'.strip()
        info = {'type': declared, 'chain': [], 'named_numbers': None,
                'named_bits': None}
        if layer < len(layers) and layers[layer].wrapper:
            info['wrapper'] = True
            return info
        if base is None:
            return info
        info['chain'] = list(base.chain)
        definitions = [typedef] + self._chain_typedefs(handle)
        for definition in definitions:
            if info['named_numbers'] is None:
                if definition.get('named-numbers'):
                    info['named_numbers'] = {
                        int(value): name for name, value in
                        definition['named-numbers'].items()
                        if _is_int(value)}
                elif definition.get('values'):
                    info['named_numbers'] = {
                        int(item[1]): item[0]
                        for item in definition['values']
                        if item and _is_int(item[1])}
            if info['named_bits'] is None and definition.get('named-bits'):
                info['named_bits'] = {
                    int(bit): name for name, bit in definition['named-bits']
                    if _is_int(bit)}
        return info

    def _chain_typedefs(self, handle):
        """Get the definitions a type refers to, outside in."""
        found = []
        module, typedef = handle[0], self.typedef(handle)
        for _ in range(MAX_DEPTH):
            name = typedef.get('type')
            if not name or name in UNIVERSAL_NUMBERS or name in UNTAGGED:
                break
            target = self.find(module, name)
            if target is None:
                break
            module, typedef = target[0], self.typedef(target)
            found.append(typedef)
        return found

    # Listing.

    def tops(self):
        """Get the types worth decoding a file with, as `Module.Type`: the
        structured types no other type refers to first, then the other
        structured types, then the rest, each by name."""
        referred = set()
        for module, content in self.modules.items():
            for typedef in content['types'].values():
                _collect_refs(typedef, referred)
        first, second, rest = [], [], []
        for module, content in self.modules.items():
            for name, typedef in content['types'].items():
                full = f'{module}.{name}'
                base = self.layers((module, name))[1]
                structured = base is not None and \
                    base.typedef.get('type') in STRUCTURED + LISTS
                if structured and name not in referred:
                    first.append(full)
                elif structured:
                    second.append(full)
                else:
                    rest.append(full)
        return sorted(first) + sorted(second) + sorted(rest), len(first)

    def dump_state(self, state):
        return dump_state(state)

    def load_state(self, text):
        return load_state(self, text)

    def guess_top(self, tag):
        """Get the first of `tops()` a root TLV with a tag matches, or
        None."""
        for name in self.tops()[0]:
            handle = self.top_handle(name)
            if self.match(handle, 0, tag) is not None:
                return name
        return None


def _collect_refs(typedef, found):
    if isinstance(typedef, dict):
        name = typedef.get('type')
        if isinstance(name, str) and name not in UNIVERSAL_NUMBERS and \
                name not in UNTAGGED:
            found.add(name.split('.')[-1])
        if 'components-of' in typedef:
            found.add(typedef['components-of'])
        for value in typedef.values():
            if isinstance(value, (dict, list)):
                _collect_refs(value, found)
    elif isinstance(typedef, list):
        for value in typedef:
            _collect_refs(value, found)


def _is_int(value):
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def dump_state(state):
    """Get a state as the text a client sends back."""
    if state is None:
        return None
    handle, layer = state
    return json.dumps(list(handle) + [layer], separators=(',', ':'))


def load_state(grammar, text):
    """Get a state from its text, or None when it is none of the grammar."""
    if not text:
        return None
    try:
        value = json.loads(text)
        handle, layer = tuple(value[:-1]), int(value[-1])
        grammar.typedef(handle)
        return handle, layer
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
