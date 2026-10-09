"""Contains the settings of the file viewer kept in rapo_viewer_config.

Two kinds of rows, the content JSON:

    GRAMMAR     by name: ASN.1 modules or a tag map, `{kind, files: [{name,
                text}], modules | entries}`
    DATASOURCE  by SOURCEID: `{layout, asn1: {grammar, top, start_offset,
                record_header, filler}}`, the delimiter (or fixed widths) and
                the ASN.1 decoding the viewer starts with for the files of the
                datasource

This module is the only code that knows the table. Every write is logged
with the value it replaces.
"""

import json
import re
import threading

import sqlalchemy as sa

from ..database import db
from ..logger import logger

from .asn1 import ber
from .asn1 import grammar as asn1_grammar
from .asn1 import tagmap
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
            'kind': row['content'].get('kind') or 'asn1',
            'entries': row['content'].get('entries'),
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
    return _grammar_row(name)[1]


def _grammar_row(name):
    """Get the kind and files of a grammar; 404 when none."""
    rows = _rows(GRAMMAR, name)
    if not rows:
        raise DatasourceError(f'There is no grammar {name}.', 404)
    content = rows[0]['content']
    return content.get('kind') or 'asn1', [
        (item['name'], item['text']) for item in content.get('files') or []]


def _load(kind, files):
    """Get the Grammar or TagMap of files."""
    if kind == 'tagmap':
        return tagmap.TagMap(tagmap.parse(files))
    return asn1_grammar.load(files)


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
        grammar = _load(*_grammar_row(name))
    except asn1_grammar.GrammarError as error:
        raise DatasourceError(f'The grammar {name} is not usable: {error}')
    with _loaded_lock:
        for old in [old for old in _loaded if old[0] == name]:
            del _loaded[old]
        _loaded[key] = grammar
    return grammar


_loaded = {}
_loaded_lock = threading.Lock()


def grammar(name):
    """Get a grammar with the texts of its files, for the editor."""
    rows = _rows(GRAMMAR, name)
    if not rows:
        raise DatasourceError(f'There is no grammar {name}.', 404)
    row, content = rows[0], rows[0]['content']
    return {'name': name, 'kind': content.get('kind') or 'asn1',
            'files': content.get('files') or [],
            'modules': content.get('modules') or [],
            'entries': content.get('entries'),
            'wrapped': content.get('wrapped') or [],
            'updated_date': row['updated_date'],
            'used_by': _grammar_usage().get(name, [])}


def save_grammar(name, files, replace=False, old_name=None):
    """Save a grammar of files `[{name, text}]`: ASN.1 modules, or a tag map
    (tagmap.py) when every file is one. Parsed first (400 naming the file
    and line); an existing name only with `replace` (else 409).

    With `old_name` it is an edit of that grammar (404 when it is gone); a
    different `name` renames it (409 when that name exists), and the
    datasources decoding with it follow the new name, in one transaction.

    Returns
    -------
    result : dict
        `{name, kind, modules, entries, tops, preferred, wrapped}`.
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
    maps = [tagmap.looks_like(text) for _, text in pairs]
    if any(maps) and not all(maps):
        raise DatasourceError('A grammar is ASN.1 modules or a tag map, not '
                              'both: upload them as two grammars.')
    kind = 'tagmap' if all(maps) else 'asn1'
    files = [{'name': file_name, 'text': text} for file_name, text in pairs]
    try:
        if kind == 'tagmap':
            parsed = tagmap.parse(pairs)
            content = {'kind': kind, 'files': files,
                       'entries': len(parsed['entries']), 'modules': [],
                       'wrapped': []}
        else:
            parsed = asn1_grammar.parse(pairs)
            content = {'kind': kind, 'files': files,
                       'modules': sorted(parsed['modules']),
                       'wrapped': parsed['wrapped']}
    except asn1_grammar.GrammarError as error:
        raise DatasourceError(f'The grammar can not be read: {error}')
    renamed = None
    if old_name:
        old = _rows(GRAMMAR, old_name)
        if not old:
            raise DatasourceError(f'There is no grammar {old_name}.', 404)
        if old_name != name:
            if _rows(GRAMMAR, name):
                raise DatasourceError(f'A grammar {name} exists already.',
                                      409)
            renamed = _rename_grammar(old_name, name)
    else:
        old = _rows(GRAMMAR, name)
        if old and not replace:
            raise DatasourceError(f'A grammar {name} exists already.', 409)
    _write(GRAMMAR, name, content, old[0] if old else None)
    tops, preferred = _load(kind, pairs).tops()
    what = f'{content["entries"]} tag map entries' if kind == 'tagmap' \
        else f'modules {", ".join(content["modules"])}'
    action = f'renamed from {old_name}' if renamed is not None else \
        'changed' if old else 'added'
    logger.info(f'ASN.1 grammar {action}: {name} '
                f'({", ".join(file_name for file_name, _ in pairs)}; {what})'
                + (f'; it had files '
                   f'{", ".join(f["name"] for f in old[0]["content"].get("files") or [])}'
                   if old else '')
                + (f'; datasources following it: '
                   f'{", ".join(map(str, renamed))}' if renamed else ''))
    return {'name': name, 'kind': kind, 'modules': content['modules'],
            'entries': content.get('entries'), 'tops': tops,
            'preferred': preferred, 'wrapped': content['wrapped']}


def _rename_grammar(old_name, name):
    """Rename a grammar's row and point the datasource settings decoding with
    it to the new name, in one transaction; get the datasources moved."""
    moved = [row for row in _rows(DATASOURCE)
             if (row['content'].get('asn1') or {}).get('grammar') == old_name]
    result, connection, transaction = db.execute(
        sa.text(f'update {TABLE} set config_name = :name, '
                f'updated_date = sysdate where config_type = :kind '
                f'and config_name = :old').bindparams(
                    kind=GRAMMAR, name=name, old=old_name),
        return_connection=True)
    try:
        for row in moved:
            content = dict(row['content'])
            content['asn1'] = {**content['asn1'], 'grammar': name}
            connection.execute(sa.text(
                f'update {TABLE} set content = :content, '
                f'updated_date = sysdate where config_type = :kind '
                f'and config_name = :sourceid').bindparams(
                    sa.bindparam('content', type_=sa.Text),
                    content=json.dumps(content, separators=(',', ':')),
                    kind=DATASOURCE, sourceid=row['config_name']))
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        connection.close()
    return [_source_id(row['config_name']) for row in moved]


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
    grammar = load_grammar(name)
    tops, preferred = grammar.tops()
    return {'name': name, 'kind': grammar.kind, 'tops': tops,
            'preferred': preferred}


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
    try:
        record_header = int(value.get('record_header') or 0)
    except (TypeError, ValueError):
        record_header = -1
    if not 0 <= record_header <= ber.MAX_RECORD_HEADER:
        raise DatasourceError(f'The record header is 0 to '
                              f'{ber.MAX_RECORD_HEADER} bytes.')
    result['record_header'] = record_header
    filler = value.get('filler') or '00ff'
    if filler not in ber.FILLERS:
        raise DatasourceError('The filler is 00ff, ff or none.')
    result['filler'] = filler
    name = value.get('grammar')
    if name:
        grammar = load_grammar(name)
        top = value.get('top')
        if top and grammar.kind == 'asn1':
            try:
                grammar.top_handle(top)
            except asn1_grammar.GrammarError as error:
                raise DatasourceError(str(error))
            result['top'] = top
        result['grammar'] = name
    return result
