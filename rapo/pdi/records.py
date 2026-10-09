"""Contains the records PDI Core loaded from a file into its tables.

The tables of a datasource (PDI_CORE_DS_TABLES) have FILE_ID, the ID of the
file log row a record came from, indexed. Only the tables linked to the
datasource of a file are read, by their name as linked (own schema or a
synonym), and only through a statement built here, so a request can never
name another table or carry its own SQL.
"""

import datetime as dt
import decimal
import re

import sqlalchemy as sa

from ..database import db

from .store import DatasourceError, pdi

PAGE_MAX = 500
TEXT_MAX = 4000
TABLE_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_$#]*(\.[A-Za-z][A-Za-z0-9_$#]*)?')
FILE_COLUMN = 'file_id'


def tables(file_id):
    """Get the tables a file's records were loaded into, with their counts.

    Returns
    -------
    result : dict
        `file`, the file log row with its record counts, and `tables`,
        `[{table_name, count, reason}]` in the order of the links; `count` is
        None and `reason` says why when a table can not be read (it does not
        exist, has no FILE_ID or is not readable).
    """
    file = _file(file_id)
    links = _links(file)
    result = []
    for name in links:
        count, reason = None, None
        try:
            count = db.execute(sa.text(
                f'select count(*) from {_name(name)} '
                f'where {FILE_COLUMN} = :id').bindparams(id=file['id']),
                as_scalar=True)
        except sa.exc.DatabaseError as error:
            reason = _reason(error)
        except DatasourceError as error:
            reason = str(error)
        result.append({'table_name': name, 'count': count, 'reason': reason})
    return {'file': file, 'tables': result}


def select(file_id, table):
    """Get the select of a file's records in one of its datasource's tables.

    Returns
    -------
    sql, file, table_name : str, dict, str
        The select (the file ID inline, no order: the index gives the rows
        in the order they were loaded), the file log row and the table's
        name as linked. Raises DatasourceError when the table is no table of
        the file's datasource.
    """
    file = _file(file_id)
    wanted = str(table or '').strip().upper()
    if wanted not in _links(file):
        raise DatasourceError(f'{wanted or "No table"} is no table of '
                              f'datasource {file["sourcename"]}.')
    sql = (f'select * from {_name(wanted)} '
           f'where {FILE_COLUMN} = {int(file["id"])}')
    return sql, file, wanted


def rows(file_id, table, search=None, offset=0, limit=200, count=False):
    """Get a page of a file's records in one of its datasource's tables.

    The records are in ROWID order, so the pages of one search follow each
    other; a search is a case-insensitive contains over every column as
    text, applied by the database.

    Returns
    -------
    page : dict
        `columns`, `[{name, kind}]`, `rows`, lists in column order,
        `offset` and, with `count`, `total`, the records of the search.
    """
    from ..analysis import datasets
    sql, file, table_name = select(file_id, table)
    offset = max(int(offset or 0), 0)
    limit = min(max(int(limit or 200), 1), PAGE_MAX)
    try:
        columns = datasets.describe(sql)
    except datasets.DatasetError as error:
        raise DatasourceError(str(error))
    condition = (datasets.search_condition(columns, search)
                 if search and search.strip() else None)
    where = f' where {condition}' if condition else ''
    inner = (f'select t.*, t.rowid rapo_rowid from {_name(table_name)} t '
             f'where t.{FILE_COLUMN} = {int(file["id"])}')
    names = [column['name'] for column in columns]
    listed = ', '.join(f'q."{name}"' for name in names)
    statement = (f'select {listed} from ({inner}) q{where} '
                 f'order by q.rapo_rowid offset {offset} rows '
                 f'fetch next {limit} rows only')
    try:
        records = db.execute(sa.text(statement), as_records=True)
        total = None
        if count:
            total = db.execute(sa.text(
                f'select count(*) from ({inner}) q{where}'), as_scalar=True)
    except sa.exc.DatabaseError as error:
        raise DatasourceError(_reason(error))
    return {'columns': columns, 'offset': offset, 'total': total,
            'rows': [[_value(value) for value in record]
                     for record in records]}


def _value(value):
    """A value as JSON takes it: whole numbers as int, datetimes without
    microseconds, LOBs read and cut."""
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(
            value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dt.datetime):
        return value.replace(microsecond=0).isoformat()
    if hasattr(value, 'read'):
        value = value.read()
    if isinstance(value, bytes):
        return value[:TEXT_MAX].hex()
    if isinstance(value, str) and len(value) > TEXT_MAX:
        return value[:TEXT_MAX]
    return value


def _file(file_id):
    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        raise DatasourceError('file_id must be a file ID.')
    file = pdi.read_file(file_id)
    if file is None:
        raise DatasourceError(f'File {file_id} is not in the file log.', 404)
    return file


def _links(file):
    datasource = pdi.read_datasource(file['sourceid'])
    if datasource is None:
        raise DatasourceError(f'Datasource {file["sourceid"]} of file '
                              f'{file["id"]} does not exist.', 404)
    return [str(link['table_name']).strip().upper()
            for link in datasource['links'] if link.get('table_name')]


def _name(name):
    if not TABLE_NAME.fullmatch(name):
        raise DatasourceError(f'{name} is no valid table name.')
    return name


def _reason(error):
    text = str(getattr(error, 'orig', error))
    if 'ORA-00942' in text:
        return 'does not exist'
    if 'ORA-00904' in text:
        return 'has no FILE_ID column'
    return text.strip().splitlines()[0] if text.strip() else 'not readable'
