"""Contains the settings of the file viewer kept in rapo_viewer_config.

Two kinds of rows, the content JSON:

    GRAMMAR     by name: an ASN.1 grammar, `{files: [{name, text}]}`
    DATASOURCE  by SOURCEID: `{layout, asn1: {grammar, top, start_offset}}`,
                the delimiter (or fixed widths) and the ASN.1 decoding the
                viewer starts with for the files of the datasource

This module is the only code that knows the table. Every write is logged
with the value it replaces.
"""

import json
import re
import threading

import sqlalchemy as sa

from ..database import db
from ..logger import logger

from .asn1 import grammar as asn1_grammar
from .files import number_option
from .store import DatasourceError

TABLE = 'rapo_viewer_config'
GRAMMAR = 'GRAMMAR'
DATASOURCE = 'DATASOURCE'
NAME_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,63}')
MAX_LAYOUT = 1000


def _rows(kind, name=None):
    where = 'config_type = :kind' + (' and config_name = :name'
                                     if name is not None else '')
    statement = sa.text(f'select config_name, content, created_date, '
                        f'updated_date from {TABLE} where {where} '
                        f'order by config_name')
    params = {'kind': kind}
    if name is not None:
        params['name'] = str(name)
    try:
        rows = db.execute(statement.bindparams(**params), as_table=True)
    except sa.exc.DatabaseError as error:
        _missing(error)
        raise
    for row in rows:
        content = row['content']
        if not isinstance(content, str) and content is not None:
            content = content.read()
        try:
            row['content'] = json.loads(content or '{}')
        except ValueError:
            row['content'] = {}
    return rows


def _missing(error):
    if 'ORA-00942' in str(error):
        raise DatasourceError(
            'The file viewer settings table is missing: run '
            'migrations/v0.8.6/upgrade.sql.', 503)


def _write(kind, name, content, old):
    """Insert or update a row (old: the row before, or None)."""
    text = json.dumps(content, separators=(',', ':'))
    if old is None:
        statement = sa.text(
            f'insert into {TABLE} (config_type, config_name, content) '
            f'values (:kind, :name, :content)')
    else:
        statement = sa.text(
            f'update {TABLE} set content = :content, updated_date = sysdate '
            f'where config_type = :kind and config_name = :name')
    statement = statement.bindparams(
        sa.bindparam('content', type_=sa.Text), kind=kind, name=str(name),
        content=text)
    try:
        db.execute(statement)
    except sa.exc.IntegrityError:
        raise DatasourceError(f'{name} was just saved by someone else.', 409)
    except sa.exc.DatabaseError as error:
        _missing(error)
        raise


def _delete(kind, name):
    statement = sa.text(f'delete from {TABLE} where config_type = :kind '
                        f'and config_name = :name')
    db.execute(statement.bindparams(kind=kind, name=str(name)))


# Grammars.

def grammars():
    """Get the grammars: name, files (name, size), modules, top types and
    the datasources decoding with each, without the texts."""
    usage = _grammar_usage()
    result = []
    for row in _rows(GRAMMAR):
        files = row['content'].get('files') or []
        result.append({
            'name': row['config_name'],
            'files': [{'name': item['name'], 'size': len(item['text'])}
                      for item in files],
            'modules': row['content'].get('modules') or [],
            'wrapped': row['content'].get('wrapped') or [],
            'created_date': row['created_date'],
            'updated_date': row['updated_date'],
            'used_by': usage.get(row['config_name'], [])})
    return result


def grammar_files(name):
    """Get the files `[(name, text)]` of a grammar; 404 when none."""
    rows = _rows(GRAMMAR, name)
    if not rows:
        raise DatasourceError(f'There is no grammar {name}.', 404)
    return [(item['name'], item['text'])
            for item in rows[0]['content'].get('files') or []]


def load_grammar(name):
    """Get the parsed Grammar of a name, kept while its row is unchanged
    (only its updated_date is read again)."""
    statement = sa.text(f'select updated_date from {TABLE} '
                        f'where config_type = :kind and config_name = :name')
    try:
        updated = db.execute(statement.bindparams(kind=GRAMMAR, name=name),
                             as_scalar=True)
    except sa.exc.DatabaseError as error:
        _missing(error)
        raise
    if updated is None:
        raise DatasourceError(f'There is no grammar {name}.', 404)
    key = (name, updated)
    with _loaded_lock:
        grammar = _loaded.get(key)
    if grammar is not None:
        return grammar
    try:
        grammar = asn1_grammar.load(grammar_files(name))
    except asn1_grammar.GrammarError as error:
        raise DatasourceError(f'The grammar {name} is not usable: {error}')
    with _loaded_lock:
        for old in [old for old in _loaded if old[0] == name]:
            del _loaded[old]
        _loaded[key] = grammar
    return grammar


_loaded = {}
_loaded_lock = threading.Lock()


def save_grammar(name, files, replace=False):
    """Save a grammar of files `[{name, text}]`, parsed first (400 naming the
    file and line); an existing name only with `replace` (else 409).

    Returns
    -------
    result : dict
        `{name, modules, tops, preferred, wrapped}`.
    """
    name = (name or '').strip()
    if not NAME_PATTERN.fullmatch(name):
        raise DatasourceError('A grammar name has 1 to 64 letters, digits, '
                              'spaces and ._()+- and starts with a letter '
                              'or digit.')
    if not files or not isinstance(files, list):
        raise DatasourceError('Give the .asn files of the grammar.')
    pairs = []
    for item in files:
        if not isinstance(item, dict) or not item.get('name') or \
                not isinstance(item.get('text'), str):
            raise DatasourceError('Each file needs a name and its text.')
        pairs.append((str(item['name']), item['text']))
    if len({file_name for file_name, _ in pairs}) != len(pairs):
        raise DatasourceError('Two files have the same name.')
    size = sum(len(text.encode('utf-8')) for _, text in pairs)
    limit = number_option('asn1_grammar_max_kb') * 1024
    if size > limit:
        raise DatasourceError(f'The grammar has {size // 1024} KB; at most '
                              f'{limit // 1024} KB are allowed '
                              f'([DATASOURCES] asn1_grammar_max_kb).', 413)
    try:
        parsed = asn1_grammar.parse(pairs)
    except asn1_grammar.GrammarError as error:
        raise DatasourceError(f'The grammar can not be read: {error}')
    old = _rows(GRAMMAR, name)
    if old and not replace:
        raise DatasourceError(f'A grammar {name} exists already.', 409)
    content = {'files': [{'name': file_name, 'text': text}
                         for file_name, text in pairs],
               'modules': sorted(parsed['modules']),
               'wrapped': parsed['wrapped']}
    _write(GRAMMAR, name, content, old[0] if old else None)
    loaded = asn1_grammar.load(pairs)
    tops, preferred = loaded.tops()
    logger.info(f'ASN.1 grammar {"replaced" if old else "added"}: {name} '
                f'({", ".join(file_name for file_name, _ in pairs)}; '
                f'modules {", ".join(content["modules"])})'
                + (f'; it had files '
                   f'{", ".join(f["name"] for f in old[0]["content"].get("files") or [])}'
                   if old else ''))
    return {'name': name, 'modules': content['modules'], 'tops': tops,
            'preferred': preferred, 'wrapped': parsed['wrapped']}


def delete_grammar(name):
    """Delete a grammar no datasource decodes with (else 409)."""
    old = _rows(GRAMMAR, name)
    if not old:
        raise DatasourceError(f'There is no grammar {name}.', 404)
    used = _grammar_usage().get(name)
    if used:
        raise DatasourceError(
            f'The grammar {name} is used by datasource'
            f'{"s" if len(used) > 1 else ""} '
            f'{", ".join(map(str, used))}.', 409)
    _delete(GRAMMAR, name)
    files = old[0]['content'].get('files') or []
    logger.info(f'ASN.1 grammar deleted: {name} '
                f'({", ".join(item["name"] for item in files)})')


def grammar_types(name):
    """Get the types of a grammar to decode a file with: `{tops, preferred}`
    (the first `preferred` are those no other type refers to)."""
    tops, preferred = load_grammar(name).tops()
    return {'name': name, 'tops': tops, 'preferred': preferred}


def _grammar_usage():
    usage = {}
    for row in _rows(DATASOURCE):
        asn1 = row['content'].get('asn1') or {}
        if asn1.get('grammar'):
            usage.setdefault(asn1['grammar'], []).append(
                _source_id(row['config_name']))
    return usage


def _source_id(name):
    try:
        return int(name)
    except ValueError:
        return name


# Datasource settings.

def settings(sourceid):
    """Get the viewer settings of a datasource (`{}` when none)."""
    if sourceid is None:
        return {}
    rows = _rows(DATASOURCE, int(sourceid))
    return rows[0]['content'] if rows else {}


def save_settings(sourceid, values):
    """Save viewer settings of a datasource: the keys given replace theirs
    (`layout`: text or None; `asn1`: `{grammar, top, start_offset}` or
    None), the others are kept."""
    try:
        sourceid = int(sourceid)
    except (TypeError, ValueError):
        raise DatasourceError('Give the datasource ID.')
    if not isinstance(values, dict):
        raise DatasourceError('Give the settings as an object.')
    old = _rows(DATASOURCE, sourceid)
    content = dict(old[0]['content']) if old else {}
    if 'layout' in values:
        layout = values['layout']
        if layout is not None and (not isinstance(layout, str) or
                                   len(layout) > MAX_LAYOUT):
            raise DatasourceError('The delimiter is a text of at most '
                                  f'{MAX_LAYOUT} characters.')
        content['layout'] = layout
    if 'asn1' in values:
        content['asn1'] = _check_asn1(values['asn1'])
    content = {key: value for key, value in content.items()
               if value is not None}
    if old and old[0]['content'] == content:
        return content
    if not content:
        if old:
            _delete(DATASOURCE, sourceid)
    else:
        _write(DATASOURCE, sourceid, content, old[0] if old else None)
    logger.info(f'File viewer settings of datasource {sourceid} saved: '
                f'{json.dumps(content)}'
                + (f'; they were {json.dumps(old[0]["content"])}'
                   if old else ''))
    return content


def _check_asn1(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DatasourceError('The ASN.1 decoding is an object.')
    result = {}
    try:
        offset = int(value.get('start_offset') or 0)
    except (TypeError, ValueError):
        raise DatasourceError('The start offset is a number of bytes.')
    if offset < 0:
        raise DatasourceError('The start offset is a number of bytes.')
    result['start_offset'] = offset
    name = value.get('grammar')
    if name:
        grammar = load_grammar(name)
        top = value.get('top')
        if top:
            try:
                grammar.top_handle(top)
            except asn1_grammar.GrammarError as error:
                raise DatasourceError(str(error))
            result['top'] = top
        result['grammar'] = name
    return result
