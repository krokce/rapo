"""Contains the reader and writer of the PDI Core datasource configuration.

Everything that knows pdi_core_ds_config, pdi_core_ds_tables and
pdi_core_file_log lives here. They are named without an owner in every
statement, so Oracle finds them in rapo's own schema or through a private or
public synonym to another one.

pdi_core_ds_config has no update stamp, and it is also edited by hand, so a
save is guarded by the row as the editor loaded it (the datasource and its
tables): a row changed since then is not overwritten. Every write rapo makes
is logged in the server log.
"""

import datetime as dt
import json
import re

import sqlalchemy as sa

from ..database import db
from ..logger import logger


CONFIG_TABLE = 'pdi_core_ds_config'
TABLES_TABLE = 'pdi_core_ds_tables'
LOG_TABLE = 'pdi_core_file_log'

DUP_HANDLING = ('PREVENT', 'PREVENTX', 'REPLACE', 'LOAD')

# The columns of pdi_core_ds_config in the order of its DDL: (name, kind,
# limit). A text limit is its length, a number's limit its highest value.
CONFIG_FIELDS = (
    ('id', 'int', 999999),
    ('sourcename', 'name', 50),
    ('input_directory', 'dirs', 2000),
    ('archive_directory', 'dir', 2000),
    ('error_directory', 'dir', 2000),
    ('duplicate_directory', 'dir', 2000),
    ('isactive', 'lane', 9),
    ('files_mask', 'mask', 4000),
    ('files_retention_days', 'int', 999999),
    ('files_max_per_cycle', 'int', 999999),
    ('files_dup_handling', 'dup', 10),
    ('leave_input_zipped', 'flag', 1),
    ('files_load_parallel', 'flag', 1),
    ('max_recordsreject', 'int', 999999),
    ('input_scan_subdirs', 'flag', 1),
    ('input_clean_files_mask', 'mask', 2000),
)
CONFIG_NAMES = tuple(name for name, kind, limit in CONFIG_FIELDS)
EDITABLE_NAMES = tuple(name for name in CONFIG_NAMES if name != 'id')
OPTIONAL_NAMES = ('input_clean_files_mask',)

LINK_NAMES = ('table_name', 'partition_key', 'partition_days_to_retain',
              'partition_days_in_advance')

# The file log columns a list shows; the log text is read one file at a time.
FILE_LOG_NAMES = ('id', 'inputfilename', 'inputfullfilename',
                  'outputfullfilename', 'filedate', 'filesize',
                  'startloaddate', 'endloaddate', 'runtime', 'sourcename',
                  'recordsread', 'recordswrite', 'recordsreject',
                  'filestatus', 'errorcount', 'md5', 'duplicate',
                  'outfiledeleted', 'server')
FILE_LOG_LIMIT = 20000

# SOURCENAME is also PDI_CORE_FILE_LOG.SOURCENAME, which holds 50 characters.
NAME_PATTERN = re.compile(r'^[A-Z0-9_]+$')
TABLE_PATTERN = re.compile(r'^[A-Z][A-Z0-9_$#]*$')


class DatasourceError(Exception):
    """A request about datasources that can not be done, with its HTTP code."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def split_directories(value):
    """Get the paths of an INPUT_DIRECTORY, which PDI Core separates by |."""
    return [part.strip() for part in str(value or '').split('|')
            if part.strip()]


def mask_error(mask):
    """Get why a mask is no valid regular expression, or None."""
    try:
        re.compile(mask)
    except (re.error, TypeError) as error:
        return str(error)
    return None


class Store:
    """Represents the datasources of PDI Core."""

    def __init__(self):
        self._probe = None

    def reset(self):
        """Forget what the probe found, e.g. after the schema changed."""
        self._probe = None

    @property
    def probe(self):
        """What rapo may do with the PDI tables, found out once.

        The statements change nothing (`where 1 = 0`), yet Oracle checks the
        privileges of each, granted directly or through a role.
        """
        if self._probe is None:
            self._probe = {name: self._try(statement)
                           for name, statement in self._probes()}
        return self._probe

    def _probes(self):
        yield 'read', (f'select 1 from {CONFIG_TABLE} where 1 = 0 union all '
                       f'select 1 from {TABLES_TABLE} where 1 = 0')
        yield 'insert', (f'insert into {TABLES_TABLE} '
                         f'select * from {TABLES_TABLE} where 1 = 0')
        yield 'update', (f'update {CONFIG_TABLE} set isactive = isactive '
                         'where 1 = 0')
        yield 'delete', (f'delete from {TABLES_TABLE} where 1 = 0')
        yield 'delete_config', (f'delete from {CONFIG_TABLE} where 1 = 0')
        yield 'log', f'select 1 from {LOG_TABLE} where 1 = 0'

    def _try(self, statement):
        try:
            db.execute(sa.text(statement), auto_commit=False)
        except Exception:
            return False
        return True

    @property
    def available(self):
        """Check whether the datasource tables can be read."""
        try:
            return self.probe['read']
        except Exception:
            return False

    @property
    def writable(self):
        """Check whether datasources can be created and changed."""
        return (self.available and self.probe['insert']
                and self.probe['update'])

    @property
    def deletable(self):
        """Check whether datasources and their tables can be deleted."""
        return (self.writable and self.probe['delete']
                and self.probe['delete_config'])

    @property
    def log_available(self):
        """Check whether the file log can be read."""
        return self.available and self.probe['log']

    def capabilities(self):
        """Get what the web UI may offer, for /info."""
        return {'datasources_available': self.available,
                'datasources_writable': self.writable,
                'datasources_deletable': self.deletable,
                'datasources_log': self.log_available}

    def check(self, write=False, delete=False):
        """Raise when the datasources can not be read, or changed."""
        if not self.available:
            raise DatasourceError('PDI Core datasource tables are not '
                                  'available.', 404)
        if write and not self.writable:
            raise DatasourceError('Datasources are read-only for this '
                                  'database user.', 403)
        if delete and not self.deletable:
            raise DatasourceError('This database user may not delete '
                                  'datasources or their tables.', 403)

    def read_datasources(self):
        """Get every datasource, with the names of its tables.

        Each row also has `tables` (the table names), `table_count` and
        `retention_count`, the tables with a partition key.
        """
        self.check()
        columns = ', '.join(CONFIG_NAMES)
        rows = db.execute(sa.text(f'select {columns} from {CONFIG_TABLE} '
                                  'order by sourcename'), as_table=True)
        links = self._read_links()
        for row in rows:
            own = links.get(row['id'], [])
            row['tables'] = [link['table_name'] for link in own]
            row['table_count'] = len(own)
            row['retention_count'] = len([link for link in own
                                          if link['partition_key']])
        return [self._normalize(row) for row in rows]

    def read_datasource(self, id, connection=None, lock=False):
        """Get one datasource and its tables, or None.

        With `connection` it reads within that transaction, and with `lock`
        the datasource row stays locked until the transaction ends.
        """
        columns = ', '.join(CONFIG_NAMES)
        statement = sa.text(f'select {columns} from {CONFIG_TABLE} '
                            f'where id = :id{" for update" if lock else ""}')
        statement = statement.bindparams(id=id)
        if connection is None:
            self.check()
            row = db.execute(statement, as_dict=True)
        else:
            row = connection.execute(statement).first()
            row = dict(row._mapping) if row else None
        if not row:
            return None
        row = self._normalize(row)
        row['links'] = self._read_links(id, connection).get(id, [])
        return row

    def _read_links(self, id=None, connection=None):
        """Get the tables of one or all datasources, by sourceid."""
        columns = ', '.join(('sourceid',) + LINK_NAMES)
        where = 'where sourceid = :id ' if id is not None else ''
        statement = sa.text(f'select {columns} from {TABLES_TABLE} {where}'
                            'order by table_name')
        if id is not None:
            statement = statement.bindparams(id=id)
        if connection is None:
            rows = db.execute(statement, as_table=True)
        else:
            rows = [dict(row._mapping) for row in connection.execute(statement)]
        links = {}
        for row in rows:
            link = {name: self._value(row[name]) for name in LINK_NAMES}
            links.setdefault(self._value(row['sourceid']), []).append(link)
        return links

    def save(self, payload, expected=None):
        """Create or update one datasource and replace its tables.

        Parameters
        ----------
        payload : dict
            The datasource's columns, and `links`, its tables. Without an
            `id` a datasource is created.
        expected : dict, optional
            The datasource and its tables as the editor loaded them. A row
            that differs from it now is not overwritten (409).

        Returns
        -------
        row : dict
            The datasource as saved, read back.
        """
        self.check(write=True)
        values = self.validate(payload)
        links = self.validate_links(payload.get('links') or [])
        id = payload.get('id')
        connection = db.connect()
        try:
            with connection.begin():
                if id:
                    current = self.read_datasource(id, connection, lock=True)
                    if current is None:
                        raise DatasourceError(f'Datasource {id} does not exist '
                                              'any more.', 404)
                    if expected is not None and not self.same(current,
                                                              expected):
                        raise DatasourceError(
                            f'Datasource {current["sourcename"]} was changed '
                            'by someone else since you opened it.', 409)
                    removed = self._removed_links(current['links'], links)
                    if removed and not self.deletable:
                        raise DatasourceError(
                            'This database user may not remove tables of a '
                            f'datasource: {", ".join(removed)}.', 403)
                    self._check_unique(connection, values['sourcename'], id)
                    assignments = ', '.join(f'{name} = :{name}'
                                            for name in EDITABLE_NAMES)
                    connection.execute(sa.text(
                        f'update {CONFIG_TABLE} set {assignments} '
                        'where id = :id').bindparams(id=id, **values))
                    action = 'UPDATE'
                else:
                    self._check_unique(connection, values['sourcename'], None)
                    names = ', '.join(EDITABLE_NAMES)
                    binds = ', '.join(f':{name}' for name in EDITABLE_NAMES)
                    # The ID is set by the trigger from PDI_CORE_DS_CONFIG_SEQ,
                    # so the row is found again by its unique name.
                    connection.execute(sa.text(
                        f'insert into {CONFIG_TABLE} ({names}) '
                        f'values ({binds})').bindparams(**values))
                    id = connection.execute(sa.text(
                        f'select id from {CONFIG_TABLE} '
                        'where sourcename = :name').bindparams(
                            name=values['sourcename'])).scalar()
                    action = 'INSERT'
                self._write_links(connection, id, links)
                saved = self.read_datasource(id, connection)
        except sa.exc.DatabaseError as error:
            raise DatasourceError(self._message(error)) from error
        finally:
            connection.close()
        self._log(saved, action)
        return saved

    def set_active(self, id, value, expected=None):
        """Move one datasource to another scheduler lane, or disable it.

        `expected` is the lane the caller saw; a datasource moved by someone
        else meanwhile is not moved again (409).
        """
        self.check(write=True)
        value = self._int(value, 'ISACTIVE', 0, 9)
        connection = db.connect()
        try:
            with connection.begin():
                current = self.read_datasource(id, connection, lock=True)
                if current is None:
                    raise DatasourceError(f'Datasource {id} does not exist.',
                                          404)
                if expected is not None and current['isactive'] != int(
                        expected):
                    raise DatasourceError(
                        f'Datasource {current["sourcename"]} was moved to '
                        f'ISACTIVE={current["isactive"]} by someone else.',
                        409)
                if current['isactive'] == value:
                    return current
                connection.execute(sa.text(
                    f'update {CONFIG_TABLE} set isactive = :value '
                    'where id = :id').bindparams(value=value, id=id))
                current['isactive'] = value
        except sa.exc.DatabaseError as error:
            raise DatasourceError(self._message(error)) from error
        finally:
            connection.close()
        self._log(current, 'UPDATE')
        return current

    def delete(self, id):
        """Delete one disabled datasource and its tables.

        The file log and the loaded tables are left alone. An active
        datasource (ISACTIVE other than 0) is refused, so that no scheduler
        of PDI Core loses a datasource it is processing.
        """
        self.check(delete=True)
        connection = db.connect()
        try:
            with connection.begin():
                current = self.read_datasource(id, connection, lock=True)
                if current is None:
                    raise DatasourceError(f'Datasource {id} does not exist.',
                                          404)
                if current['isactive'] != 0:
                    raise DatasourceError(
                        f'Datasource {current["sourcename"]} is active '
                        f'(ISACTIVE={current["isactive"]}): disable it first.')
                connection.execute(sa.text(
                    f'delete from {TABLES_TABLE} where sourceid = :id')
                    .bindparams(id=id))
                connection.execute(sa.text(
                    f'delete from {CONFIG_TABLE} where id = :id')
                    .bindparams(id=id))
        except sa.exc.DatabaseError as error:
            raise DatasourceError(self._message(error)) from error
        finally:
            connection.close()
        self._log(current, 'DELETE')
        return current

    def count_file_log(self, id):
        """Count the file log rows of one datasource."""
        self.check()
        if not self.log_available:
            return None
        statement = sa.text(f'select count(*) from {LOG_TABLE} '
                            'where sourceid = :id').bindparams(id=id)
        return db.execute(statement, as_scalar=True)

    def read_file_log(self, id, day):
        """Get the files of one datasource loaded on one day, newest first."""
        self.check()
        if not self.log_available:
            return {'files': [], 'truncated': False}
        columns = ', '.join(FILE_LOG_NAMES)
        start = dt.datetime.combine(day, dt.time())
        statement = sa.text(
            f'select {columns} from {LOG_TABLE} where sourceid = :id '
            'and startloaddate >= :day_from and startloaddate < :day_to '
            'order by startloaddate desc, id desc '
            f'fetch first {FILE_LOG_LIMIT + 1} rows only').bindparams(
                id=id, day_from=start, day_to=start + dt.timedelta(days=1))
        rows = db.execute(statement, as_table=True)
        return {'files': rows[:FILE_LOG_LIMIT],
                'truncated': len(rows) > FILE_LOG_LIMIT}

    def read_file_log_text(self, file_id):
        """Get the LOG text of one file of the file log."""
        self.check()
        if not self.log_available:
            raise DatasourceError('The file log is not available.', 404)
        statement = sa.text(f'select log from {LOG_TABLE} '
                            'where id = :id').bindparams(id=file_id)
        value = db.execute(statement, as_scalar=True)
        if hasattr(value, 'read'):
            value = value.read()
        return value

    def read_file_log_stats(self):
        """Get the loads of the last 24 hours of every datasource, by id.

        Only the last day's partitions of the file log are read.
        """
        if not self.log_available:
            return {}
        statement = sa.text(
            'select sourceid, max(startloaddate) last_load, count(*) files, '
            'sum(recordswrite) records, sum(recordsreject) rejected, '
            "sum(case when filestatus = 'ERROR' then 1 else 0 end) errors, "
            'sum(case when duplicate = 1 then 1 else 0 end) duplicates '
            f'from {LOG_TABLE} where startloaddate >= sysdate - 1 '
            'group by sourceid')
        stats = {}
        for row in db.execute(statement, as_table=True):
            id = self._value(row.pop('sourceid'))
            stats[id] = {key: self._value(value) for key, value in row.items()}
        return stats

    def read_database_time(self):
        """Get the database clock, which stamps the file log."""
        return db.execute(sa.text('select sysdate from dual'), as_scalar=True)

    def read_table_facts(self, tables):
        """Get what the dictionary says about the tables of datasources.

        Parameters
        ----------
        tables : list of str
            Table names, in rapo's own schema.

        Returns
        -------
        facts : dict
            By table name: `exists`, `partitioned`, `partitioning_type`,
            `interval`, `partition_keys`, `partition_count`, the high values
            of the first and last partition, and `partitioned_by`: the
            datasources configuring a partition key for it.
        """
        self.check()
        names = sorted({str(table).strip().upper() for table in tables
                        if table and str(table).strip()})
        if not names:
            return {}
        binds = {f'name{index}': name for index, name in enumerate(names)}
        in_list = ', '.join(f':{bind}' for bind in binds)
        facts = {name: {'exists': False, 'partitioned': False,
                        'partitioning_type': None, 'interval': None,
                        'partition_keys': [], 'partition_count': None,
                        'first_partition': None, 'last_partition': None,
                        'num_rows': None, 'partitioned_by': []}
                 for name in names}
        statement = sa.text('select table_name, num_rows, partitioned '
                            f'from user_tables where table_name in ({in_list})')
        for row in db.execute(statement.bindparams(**binds), as_table=True):
            fact = facts[row['table_name']]
            fact['exists'] = True
            fact['num_rows'] = row['num_rows']
            fact['partitioned'] = row['partitioned'] == 'YES'
        statement = sa.text('select table_name, partitioning_type, '
                            'partition_count, interval from user_part_tables '
                            f'where table_name in ({in_list})')
        for row in db.execute(statement.bindparams(**binds), as_table=True):
            fact = facts[row['table_name']]
            fact['partitioning_type'] = row['partitioning_type']
            fact['partition_count'] = row['partition_count']
            fact['interval'] = row['interval']
        statement = sa.text('select name, column_name '
                            'from user_part_key_columns '
                            f"where object_type = 'TABLE' and name in "
                            f'({in_list}) order by name, column_position')
        for row in db.execute(statement.bindparams(**binds), as_table=True):
            facts[row['name']]['partition_keys'].append(row['column_name'])
        # high_value is a LONG, which can be fetched but not used in SQL.
        statement = sa.text(
            'select table_name, partition_position, high_value '
            'from user_tab_partitions p '
            f'where table_name in ({in_list}) and (partition_position = 1 '
            'or partition_position = (select max(partition_position) '
            'from user_tab_partitions q where q.table_name = p.table_name))')
        for row in db.execute(statement.bindparams(**binds), as_table=True):
            fact = facts[row['table_name']]
            key = ('first_partition' if row['partition_position'] == 1
                   else 'last_partition')
            fact[key] = row['high_value']
            if fact['partition_count'] == 1:
                fact['last_partition'] = row['high_value']
        statement = sa.text(
            f'select t.table_name, c.id, c.sourcename from {TABLES_TABLE} t '
            f'join {CONFIG_TABLE} c on c.id = t.sourceid '
            f'where t.partition_key is not null and t.table_name in '
            f'({in_list}) order by c.sourcename')
        for row in db.execute(statement.bindparams(**binds), as_table=True):
            facts[row['table_name']]['partitioned_by'].append(
                {'id': self._value(row['id']),
                 'sourcename': row['sourcename']})
        return facts

    def signature(self):
        """Get a value that changes whenever a datasource or its tables do.

        ORA_ROWSCN changes with every commit to a block of the table, which is
        enough for a table of a few hundred rows.
        """
        if not self.available:
            return None
        statement = sa.text(
            f'select (select count(*) || \':\' || max(ora_rowscn) '
            f'from {CONFIG_TABLE}) || \'/\' || (select count(*) || \':\' || '
            f'max(ora_rowscn) from {TABLES_TABLE}) from dual')
        return db.execute(statement, as_scalar=True)

    def same(self, current, expected):
        """Check whether a datasource still is the way a caller saw it."""
        return self._key(current) == self._key(expected)

    def _key(self, row):
        row = row or {}
        values = {}
        for name, kind, limit in CONFIG_FIELDS:
            value = row.get(name)
            if kind in ('int', 'flag', 'lane'):
                try:
                    value = int(value) if value not in (None, '') else None
                except (TypeError, ValueError):
                    pass
            elif value == '':
                value = None
            values[name] = value
        links = []
        for link in row.get('links') or []:
            links.append(tuple(
                (int(link.get(name)) if name.startswith('partition_days')
                 and link.get(name) not in (None, '') else
                 (link.get(name) or None))
                for name in LINK_NAMES))
        values['links'] = sorted(links, key=lambda link: str(link[0]))
        return json.dumps(values, sort_keys=True, default=str)

    def validate(self, payload):
        """Turn an edited datasource into the values of its row.

        Raises DatasourceError naming the first value that is not valid.
        """
        values = {}
        for name, kind, limit in CONFIG_FIELDS:
            if name == 'id':
                continue
            label = name.upper()
            value = payload.get(name)
            if isinstance(value, str):
                value = value.strip()
            if value in (None, ''):
                if name in OPTIONAL_NAMES:
                    values[name] = None
                    continue
                raise DatasourceError(f'{label} is required.')
            if kind in ('int', 'flag', 'lane'):
                low = 1 if name == 'files_max_per_cycle' else 0
                values[name] = self._int(value, label, low, limit)
                continue
            value = str(value)
            if len(value) > limit:
                raise DatasourceError(f'{label} is longer than {limit} '
                                      'characters.')
            if kind == 'name':
                value = value.upper()
                if not NAME_PATTERN.match(value):
                    raise DatasourceError(
                        f'{label} {value} may only have letters, digits and '
                        'underscores.')
            elif kind == 'dirs':
                parts = split_directories(value)
                for part in parts:
                    self._check_path(part, label)
                value = '|'.join(parts)
            elif kind == 'dir':
                self._check_path(value, label)
            elif kind == 'mask':
                error = mask_error(value)
                if error:
                    raise DatasourceError(f'{label} is no valid regular '
                                          f'expression: {error}.')
                if name == 'input_clean_files_mask' and len(
                        value.encode('utf-8')) > limit:
                    raise DatasourceError(f'{label} is longer than {limit} '
                                          'bytes.')
            elif kind == 'dup':
                value = value.upper()
                if value not in DUP_HANDLING:
                    raise DatasourceError(f'{label} must be one of '
                                          f'{", ".join(DUP_HANDLING)}.')
            values[name] = value
        return values

    def validate_links(self, links):
        """Turn the edited tables of a datasource into rows."""
        rows = []
        seen = set()
        for link in links:
            table = str(link.get('table_name') or '').strip().upper()
            if not table:
                raise DatasourceError('Every table needs a TABLE_NAME.')
            if len(table) > 128 or not TABLE_PATTERN.match(table):
                raise DatasourceError(f'{table} is no valid table name.')
            if table in seen:
                raise DatasourceError(f'Table {table} is listed twice.')
            seen.add(table)
            key = str(link.get('partition_key') or '').strip().upper() or None
            retain = link.get('partition_days_to_retain')
            advance = link.get('partition_days_in_advance')
            retain = None if retain in (None, '') else retain
            advance = None if advance in (None, '') else advance
            if key is None:
                if retain is not None or advance is not None:
                    raise DatasourceError(f'Table {table} has partition days '
                                          'but no PARTITION_KEY.')
            else:
                if len(key) > 512 or not TABLE_PATTERN.match(key):
                    raise DatasourceError(f'{key} is no valid column name.')
                if retain is None:
                    raise DatasourceError(f'Table {table} needs '
                                          'PARTITION_DAYS_TO_RETAIN.')
                retain = self._int(retain, 'PARTITION_DAYS_TO_RETAIN', 1,
                                   99999999)
                advance = self._int(0 if advance is None else advance,
                                    'PARTITION_DAYS_IN_ADVANCE', 0, 99999999)
            rows.append({'table_name': table, 'partition_key': key,
                         'partition_days_to_retain': retain,
                         'partition_days_in_advance': advance})
        return rows

    def _check_path(self, path, label):
        if not path.startswith('/'):
            raise DatasourceError(f'{label} {path} is not an absolute path.')
        if '..' in path.split('/'):
            raise DatasourceError(f'{label} {path} may not contain "..".')

    def _check_unique(self, connection, name, id):
        statement = sa.text(f'select id from {CONFIG_TABLE} '
                            'where sourcename = :name').bindparams(name=name)
        other = connection.execute(statement).scalar()
        if other is not None and (id is None or int(other) != int(id)):
            raise DatasourceError(f'Datasource {name} already exists '
                                  f'(ID {other}).')

    def _removed_links(self, current, links):
        names = {link['table_name'] for link in links}
        return [link['table_name'] for link in current
                if link['table_name'] not in names]

    def _write_links(self, connection, id, links):
        """Replace the tables of one datasource."""
        connection.execute(sa.text(f'delete from {TABLES_TABLE} '
                                   'where sourceid = :id').bindparams(id=id))
        for link in links:
            connection.execute(sa.text(
                f'insert into {TABLES_TABLE} (sourceid, table_name, '
                'partition_key, partition_days_to_retain, '
                'partition_days_in_advance) values (:id, :table_name, '
                ':partition_key, :partition_days_to_retain, '
                ':partition_days_in_advance)').bindparams(id=id, **link))

    def _log(self, row, action):
        """Write one change of a datasource to the server log."""
        verb = {'INSERT': 'created', 'UPDATE': 'updated',
                'DELETE': 'deleted'}[action]
        logger.info(f'Datasource {row["sourcename"]} ({row["id"]}) {verb}')

    def _normalize(self, row):
        return {key: self._value(value) for key, value in row.items()}

    def _value(self, value):
        """Numbers of the PDI tables come as whole numbers or Decimals."""
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if hasattr(value, 'as_integer_ratio') and not isinstance(
                value, (int, float)):
            return int(value) if value == int(value) else float(value)
        return value

    def _int(self, value, label, low, high):
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            raise DatasourceError(f'{label} must be a whole number.')
        if number < low or number > high:
            raise DatasourceError(f'{label} must be between {low} and {high}.')
        return number

    def _message(self, error):
        """Turn an Oracle error into what a user can act on."""
        text = str(getattr(error, 'orig', error)).strip()
        return text.splitlines()[0] if text else 'Database error.'


pdi = Store()
