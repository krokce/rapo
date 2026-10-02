"""Contains KPI configuration reader and writer.

KPI values are calculated after a control run by the Oracle package
RACS_KPI_PKG, which reads its definitions from two tables that belong to that
deployment and not to rapo itself:

    racs_kpi_type    the catalogue of KPI types and their default statements
    racs_kpi_config  one row per KPI of one control, linked by
                     rapo_config.control_name = racs_kpi_config.processname

A statement left NULL in racs_kpi_config means the type's default is used
(`coalesce(k.kpi_sql_statement, t.default_kpi_sql_statement)`), and a KPI whose
statement is NULL on both sides is not calculated at all.

Everything that knows about those tables lives here. They are optional: an
installation without them simply gets empty answers and no KPI tab in the web
UI.
"""

import re
import time

import sqlalchemy as sa

from .config import config
from . import options
from .core import sqlcheck
from .database import db


TYPE_TABLE = 'racs_kpi_type'
CONFIG_TABLE = 'racs_kpi_config'
HISTORY_TABLE = 'racs_kpi_runhistory_all'

# The binds RACS_KPI_PKG gives the KPI and the alarm statement.
KPI_BIND = 'v_processid'
ALARM_BIND = 'v_kpi_value'

CALCULATE_TIMEOUT = options.default('KPI', 'calculate_timeout')
LOG_TAIL = 4000


class Kpi:
    """Represents the KPI configuration of controls."""

    def __init__(self):
        self._available = None
        self._history = None
        self._tables = {}

    @property
    def available(self):
        """Check whether the KPI tables are deployed in this database."""
        if self._available is None:
            try:
                self._available = (db.exists(TYPE_TABLE)
                                   and db.exists(CONFIG_TABLE))
            except Exception:
                self._available = False
        return self._available

    @property
    def history_available(self):
        """Check whether the package's run history table is deployed."""
        if self._history is None:
            try:
                self._history = self.available and db.exists(HISTORY_TABLE)
            except Exception:
                self._history = False
        return self._history

    def table(self, name):
        """Get one of the KPI tables, reflected once and kept."""
        # db.table() reflects on every call, so the result is cached here.
        if name not in self._tables:
            self._tables[name] = db.table(name)
        return self._tables[name]

    def read_kpi_types(self):
        """Get the catalogue of KPI types, most important first."""
        if not self.available:
            return []
        table = self.table(TYPE_TABLE)
        select = table.select().order_by(table.c.kpi_priority.nulls_last(),
                                         table.c.kpi_type)
        return db.execute(select, as_table=True)

    def read_kpi_type_usage(self):
        """Get the controls that use each KPI type.

        The controls are outer-joined, so a configuration row naming a control
        that does not exist any more is still reported, only without an id.
        """
        if not self.available:
            return []
        config = self.table(CONFIG_TABLE)
        controls = db.tables.config
        select = (sa.select(config.c.kpi_type, config.c.processname,
                            controls.c.control_id)
                    .select_from(config.outerjoin(
                        controls,
                        controls.c.control_name == config.c.processname))
                    .order_by(config.c.kpi_type, config.c.processname))
        return db.execute(select, as_table=True)

    def save_kpi_type(self, record, previous=None):
        """Create, update or rename one KPI type.

        A rename is not an update: kpi_type is the primary key and
        racs_kpi_config references it, so the row is inserted under the new
        code, the configuration rows of the controls are moved over and the old
        row is deleted.
        """
        if not self.available:
            raise ValueError('KPI tables are not available.')
        table = self.table(TYPE_TABLE)
        values = self._type_values(record)
        previous = (previous or '').strip().upper() or None
        if previous != values['kpi_type'] and self._type_exists(
                values['kpi_type']):
            raise ValueError(f'KPI type {values["kpi_type"]} already exists.')
        if previous is None:
            return db.execute(table.insert().values(values))
        if previous == values['kpi_type']:
            update = (table.update()
                           .where(table.c.kpi_type == previous)
                           .values(values))
            return db.execute(update)
        return self._rename_kpi_type(previous, values)

    def delete_kpi_type(self, kpi_type):
        """Delete one KPI type, unless controls still use it.

        The foreign key of racs_kpi_config is NO ACTION, so this reports the
        controls instead of letting ORA-02292 out.
        """
        if not self.available:
            raise ValueError('KPI tables are not available.')
        kpi_type = self._code(kpi_type)
        names = self.read_kpi_type_controls(kpi_type)
        if names:
            raise ValueError(f'KPI type {kpi_type} is used by '
                             f'{len(names)} control(s): {", ".join(names)}.')
        table = self.table(TYPE_TABLE)
        return db.execute(table.delete().where(table.c.kpi_type == kpi_type))

    def read_kpi_type_controls(self, kpi_type):
        """Get the names of the controls that use one KPI type."""
        if not self.available:
            return []
        config = self.table(CONFIG_TABLE)
        select = (sa.select(config.c.processname)
                    .where(config.c.kpi_type == kpi_type)
                    .order_by(config.c.processname))
        return [record[0] for record in db.execute(select, as_records=True)]

    def _type_exists(self, kpi_type):
        """Check whether a KPI type of that code is in the catalogue."""
        table = self.table(TYPE_TABLE)
        select = (sa.select(sa.func.count())
                    .select_from(table)
                    .where(table.c.kpi_type == kpi_type))
        return bool(db.execute(select, as_scalar=True))

    def _rename_kpi_type(self, previous, values):
        """Move one KPI type to a new code, taking its controls along.

        db.execute commits each statement of its own, which is why the three
        statements of a rename run on one connection and are committed
        together: a failure anywhere leaves the catalogue exactly as it was,
        never with both codes.
        """
        table = self.table(TYPE_TABLE)
        config = self.table(CONFIG_TABLE)
        result, connection, transaction = db.execute(
            table.insert().values(values), return_connection=True)
        try:
            # The insert comes first, so the foreign key of racs_kpi_config
            # holds at every step.
            connection.execute(config.update()
                                     .where(config.c.kpi_type == previous)
                                     .values(kpi_type=values['kpi_type']))
            connection.execute(table.delete()
                                    .where(table.c.kpi_type == previous))
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            connection.close()
        return result

    def read_control_kpis(self, control_name):
        """Get the KPI configuration of one control, in type priority order."""
        if not self.available or not control_name:
            return []
        config = self.table(CONFIG_TABLE)
        types = self.table(TYPE_TABLE)
        select = (sa.select(config)
                    .select_from(config.join(
                        types, config.c.kpi_type == types.c.kpi_type))
                    .where(config.c.processname == control_name)
                    .order_by(types.c.kpi_priority.nulls_last(),
                              config.c.kpi_type))
        return db.execute(select, as_table=True)

    def save_control_kpis(self, control_name, records, old_name=None):
        """Replace the KPI configuration of one control.

        The rows of the control are deleted and written anew from the passed
        records, under old_name as well as control_name, so that a renamed
        control takes its KPIs with it and cannot collide with rows left behind
        by an earlier rename.
        """
        if not self.available:
            return
        table = self.table(CONFIG_TABLE)
        names = {name for name in (old_name, control_name) if name}
        db.execute(table.delete().where(table.c.processname.in_(names)))
        for record in records or []:
            insert = table.insert().values(
                processname=control_name,
                kpi_type=record['kpi_type'],
                kpi_sql_statement=self._text(record.get('kpi_sql_statement')),
                alarm_sql_statement=self._text(
                    record.get('alarm_sql_statement')),
                rerun_on_alarm_days_back=self._number(
                    record.get('rerun_on_alarm_days_back')),
                rerun_on_new_data_days_back=self._number(
                    record.get('rerun_on_new_data_days_back')))
            db.execute(insert)

    def read_orphan_kpis(self):
        """Get the KPI rows of no control.

        RACS_KPI_PKG finds a control's KPIs by its exact name, so a row whose
        processname matches no control_name is never calculated: its control
        was deleted, or renamed outside the application. `case_match` names a
        control the row matches only ignoring case. The values the package
        stored for it are counted from the run history.
        """
        if not self.available:
            return []
        config = self.table(CONFIG_TABLE)
        controls = db.tables.config
        select = (sa.select(config.c.processname, config.c.kpi_type,
                            sa.case((config.c.kpi_sql_statement.isnot(None),
                                     1), else_=0).label('has_kpi_sql'),
                            sa.case((config.c.alarm_sql_statement.isnot(None),
                                     1), else_=0).label('has_alarm_sql'))
                    .select_from(config.outerjoin(
                        controls,
                        controls.c.control_name == config.c.processname))
                    .where(controls.c.control_id.is_(None))
                    .order_by(config.c.processname, config.c.kpi_type))
        rows = db.execute(select, as_table=True)
        if not rows:
            return rows
        names = db.execute(sa.select(controls.c.control_name), as_records=True)
        by_upper = {}
        for (name,) in names:
            by_upper.setdefault((name or '').upper(), name)
        stored = {}
        if self.history_available:
            history = self.table(HISTORY_TABLE)
            processnames = sorted({row['processname'] for row in rows})
            select = (sa.select(history.c.processname, history.c.kpi_type,
                                sa.func.count().label('stored_runs'),
                                sa.func.max(history.c.created)
                                .label('last_stored'))
                        .where(history.c.processname.in_(processnames))
                        .group_by(history.c.processname, history.c.kpi_type))
            for item in db.execute(select, as_table=True):
                stored[(item['processname'], item['kpi_type'])] = item
        for row in rows:
            row['has_kpi_sql'] = bool(row['has_kpi_sql'])
            row['has_alarm_sql'] = bool(row['has_alarm_sql'])
            item = stored.get((row['processname'], row['kpi_type'])) or {}
            row['stored_runs'] = item.get('stored_runs') or 0
            row['last_stored'] = item.get('last_stored')
            row['case_match'] = by_upper.get(
                (row['processname'] or '').upper())
        return rows

    def delete_orphan_kpis(self, processname, kpi_type=None):
        """Delete the KPI rows of a name no control has, one type or all.

        Returns
        -------
        count : int
            The rows deleted.
        """
        if not self.available:
            raise ValueError('KPI tables are not available.')
        self._check_orphan(processname)
        config = self.table(CONFIG_TABLE)
        delete = config.delete().where(config.c.processname == processname)
        if kpi_type:
            delete = delete.where(config.c.kpi_type == self._code(kpi_type))
        return db.execute(delete).rowcount

    def reassign_orphan_kpi(self, processname, kpi_type, control_name):
        """Move one KPI row of a name no control has to an existing control."""
        if not self.available:
            raise ValueError('KPI tables are not available.')
        self._check_orphan(processname)
        kpi_type = self._code(kpi_type)
        controls = db.tables.config
        exists = db.execute(sa.select(sa.func.count())
                              .where(controls.c.control_name == control_name),
                            as_scalar=True)
        if not exists:
            raise ValueError(f'Control {control_name} does not exist.')
        config = self.table(CONFIG_TABLE)
        taken = db.execute(sa.select(sa.func.count())
                             .select_from(config)
                             .where(config.c.processname == control_name,
                                    config.c.kpi_type == kpi_type),
                           as_scalar=True)
        if taken:
            raise ValueError(f'Control {control_name} already has KPI '
                             f'{kpi_type}.')
        update = (config.update()
                        .where(config.c.processname == processname,
                               config.c.kpi_type == kpi_type)
                        .values(processname=control_name))
        if not db.execute(update).rowcount:
            raise ValueError(f'{processname} has no KPI {kpi_type}.')

    def move_control_kpis(self, old_name, new_name):
        """Move the KPIs of a renamed control, rewriting their table names.

        For a rename saved without a KPI configuration (the editor sends one
        and rewrites the statements itself). Rows already under the new name
        can only be orphans, since no other control has it, and are replaced,
        as save_control_kpis does. All on one connection, so a failure moves
        nothing.

        Returns
        -------
        moved : list of dict
            `{kpi_type, fields}` per moved KPI, `fields` naming the statements
            whose table references were rewritten.
        """
        if not self.available or not old_name or old_name == new_name:
            return []
        table = self.table(CONFIG_TABLE)
        rows = db.execute(table.select()
                               .where(table.c.processname == old_name),
                          as_table=True)
        if not rows:
            return []
        moved = []
        result, connection, transaction = db.execute(
            table.delete().where(table.c.processname == new_name),
            return_connection=True)
        try:
            for row in rows:
                values = {'processname': new_name}
                fields = []
                for field in ('kpi_sql_statement', 'alarm_sql_statement'):
                    text, count = rename_table_references(
                        _plain(row[field]), old_name, new_name)
                    if count:
                        values[field] = text
                        fields.append(field)
                connection.execute(table.update()
                                        .where(table.c.processname == old_name,
                                               table.c.kpi_type
                                               == row['kpi_type'])
                                        .values(values))
                moved.append({'kpi_type': row['kpi_type'], 'fields': fields})
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            connection.close()
        return moved

    def delete_control_kpis(self, control_name):
        """Delete the KPI rows of a control, giving the types deleted."""
        if not self.available or not control_name:
            return []
        types = [row['kpi_type'] for row in self.read_control_kpis(control_name)]
        if types:
            config = self.table(CONFIG_TABLE)
            db.execute(config.delete()
                             .where(config.c.processname == control_name))
        return types

    def _check_orphan(self, processname):
        """Refuse a name a control has: its KPIs are edited with it."""
        if not processname:
            raise ValueError('processname is required.')
        controls = db.tables.config
        exists = db.execute(sa.select(sa.func.count())
                              .where(controls.c.control_name == processname),
                            as_scalar=True)
        if exists:
            raise ValueError(f'Control {processname} exists: edit its KPIs '
                             'in the control editor.')

    def validate_statement(self, statement, kind='kpi'):
        """Parse a KPI or alarm statement without executing it.

        Parameters
        ----------
        statement : str
            The KPI or alarm statement.
        kind : str
            `kpi` or `alarm`. An alarm also gets the thresholds the dashboard
            reads from it.

        Returns
        -------
        result : dict
            Whether the statement parses, and the columns it would return.
        """
        if not statement or not statement.strip():
            return {'valid': False, 'error': 'Statement is empty.'}
        if not self.available:
            return {'valid': False, 'error': 'KPI tables are not available.'}
        problem = self.guard_query(statement)
        if problem:
            return {'valid': False, 'error': problem}
        result = sqlcheck.parse(sqlcheck.strip_query(statement))
        if not result['valid']:
            return result
        columns = result['columns']
        bind = ':v_kpi_value' if kind == 'alarm' else ':v_processid'
        warnings = [sqlcheck.number_warning(columns)]
        if bind not in statement.lower():
            warnings.append(f'{bind} is not used, so RACS_KPI_PKG fails to '
                            'bind it.')
        if kind == 'alarm':
            thresholds, problem = self.alarm_thresholds(statement)
            result['thresholds'] = thresholds
            warnings.append(problem)
        warnings = [warning for warning in warnings if warning]
        if warnings:
            result['warning'] = ' '.join(warnings)
        return result

    def guard_query(self, statement):
        """Tell why a statement may not be executed as a KPI preview.

        Only one plain query passes: no FOR UPDATE lock, no PL/SQL declared in
        a WITH clause and nothing after the first statement. The preview also
        runs it read only, so DML in the same transaction is refused by Oracle;
        a function with an autonomous transaction is the one thing neither
        check can stop.

        Returns
        -------
        problem : str or None
        """
        if sqlcheck.first_keyword(statement) not in sqlcheck.QUERY_KEYWORDS:
            return ('A KPI or alarm statement must be a query (select) '
                    'returning one number.')
        code = _code_only(sqlcheck.strip_query(statement))
        if re.match(r'[\s(]*with\s+(function|procedure)\b', code,
                    flags=re.I):
            return 'PL/SQL declared in a WITH clause is not allowed.'
        if ';' in code:
            return 'Only one statement is allowed.'
        if re.search(r'\bfor\s+update\b', code, flags=re.I):
            return 'FOR UPDATE is not allowed: it locks rows.'
        return None

    def calculate(self, process_id, kpi_type, kpi_sql_statement=None,
                  alarm_sql_statement=None, saved=False):
        """Calculate one KPI of one run without storing anything.

        Mirrors racs_kpi_pkg.run_rapo_control_kpi_calculation: the KPI
        statement gets :v_processid as text and gives the first column of its
        first row, 0 when there is no row; the alarm statement gets that value
        as :v_kpi_value. A blank statement means the type's default.

        Parameters
        ----------
        process_id : int
            The run.
        kpi_type : str
            The KPI type, which gives the defaults, unit and decimal places.
        kpi_sql_statement, alarm_sql_statement : str
            The statements as edited, ignored with `saved`.
        saved : bool
            Use the statements saved for the run's control.

        Returns
        -------
        result : dict
            The value, the alarm level and how they were reached. A statement
            that fails is reported in `error`, never raised.
        """
        if not self.available:
            raise ValueError('KPI tables are not available.')
        process_id = int(process_id)
        kpi_type = self._code(kpi_type)
        types = self.table(TYPE_TABLE)
        type_row = db.execute(types.select()
                                   .where(types.c.kpi_type == kpi_type),
                              as_dict=True)
        if not type_row:
            raise ValueError(f'KPI type {kpi_type} does not exist.')
        if saved:
            control_name = self._run_control_name(process_id)
            config_table = self.table(CONFIG_TABLE)
            row = db.execute(config_table.select().where(
                config_table.c.processname == control_name,
                config_table.c.kpi_type == kpi_type), as_dict=True)
            if not row:
                raise ValueError(f'Control {control_name} has no KPI '
                                 f'{kpi_type}.')
            kpi_sql_statement = row['kpi_sql_statement']
            alarm_sql_statement = row['alarm_sql_statement']
        own = 'saved' if saved else 'draft'
        kpi_sql = self._text(kpi_sql_statement)
        alarm_sql = self._text(alarm_sql_statement)
        result = {
            'kpi_type': kpi_type,
            'process_id': process_id,
            'kpi_value_unit': type_row['kpi_value_unit'],
            'kpi_decimal_places': type_row['kpi_decimal_places'],
            'kpi_source': own if kpi_sql else 'default',
            'alarm_source': own if alarm_sql else 'default',
            'kpi_sql': kpi_sql or self._text(
                type_row['default_kpi_sql_statement']),
            'alarm_sql': alarm_sql or self._text(
                type_row['default_alarm_sql_statement']),
            'value': 0, 'no_rows': False, 'alarm_level': 0,
            'kpi_ms': None, 'alarm_ms': None, 'error': None, 'stage': None}
        if not result['kpi_sql']:
            result['kpi_source'] = None
        if not result['alarm_sql']:
            result['alarm_source'] = None
        raw = 0
        if result['kpi_sql']:
            result['stage'] = 'kpi'
            try:
                row, result['kpi_ms'] = self._query(
                    result['kpi_sql'], KPI_BIND, str(process_id))
                if row is None:
                    result['no_rows'] = True
                else:
                    raw = self._number_of(row[0])
                    result['value'] = (None if raw is None
                                       else round(raw, 4))
            except Exception as error:
                result['error'] = str(error).strip()
                return result
        if result['alarm_sql']:
            result['stage'] = 'alarm'
            try:
                row, result['alarm_ms'] = self._query(
                    result['alarm_sql'], ALARM_BIND, raw)
                if row is not None:
                    result['alarm_level'] = self._number_of(row[0])
            except Exception as error:
                result['error'] = str(error).strip()
                return result
        result['stage'] = None
        return result

    def _query(self, statement, bind, value):
        """Run one KPI or alarm statement read only and get its first row.

        The connection is the pool's own driver connection, so its timeout
        is put back and the read-only transaction is always rolled back. A
        statement interrupted by the timeout leaves the connection unusable,
        so after any failure it is dropped from the pool.
        """
        problem = self.guard_query(statement)
        if problem:
            raise ValueError(problem)
        statement = sqlcheck.strip_query(statement)
        if not re.search(rf':{bind}\b', statement, flags=re.I):
            raise ValueError(f':{bind} is not used, so RACS_KPI_PKG fails '
                             'to bind it.')
        section = config.get('KPI') or {}
        timeout = section.get('calculate_timeout') or CALCULATE_TIMEOUT
        connection = db.engine.raw_connection()
        driver = (getattr(connection, 'dbapi_connection', None)
                  or connection.connection)
        previous = driver.call_timeout
        failed = False
        try:
            driver.rollback()
            driver.call_timeout = int(float(timeout) * 1000)
            cursor = driver.cursor()
            cursor.execute('set transaction read only')
            started = time.monotonic()
            cursor.execute(statement, {bind: value})
            row = cursor.fetchone()
            elapsed = round((time.monotonic() - started) * 1000)
            row = tuple(_plain(item) for item in row) if row else None
            return row, elapsed
        except Exception as error:
            failed = True
            if 'DPY-4024' in str(error):
                raise TimeoutError(f'Stopped after {timeout} s ([KPI] '
                                   'calculate_timeout).') from error
            raise
        finally:
            try:
                driver.rollback()
                driver.call_timeout = previous
            except Exception:
                failed = True
            if failed:
                connection.invalidate()
            connection.close()

    def _number_of(self, value):
        """Turn the first column into the number the package defines."""
        if value is None or isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).strip())
        except ValueError:
            raise ValueError(f'The statement returns "{value}", which is '
                             'not a number (ORA-06502 in RACS_KPI_PKG).')

    def _run_control_name(self, process_id):
        """Get the name of the control a run belongs to."""
        log, controls = db.tables.log, db.tables.config
        select = (sa.select(controls.c.control_name)
                    .select_from(log.join(
                        controls, log.c.control_id == controls.c.control_id))
                    .where(log.c.process_id == process_id))
        name = db.execute(select, as_scalar=True)
        if not name:
            raise ValueError(f'Run {process_id} does not exist.')
        return name

    def read_history(self, process_id):
        """Get the KPI values RACS_KPI_PKG stored for one run."""
        if not self.history_available:
            return []
        table = self.table(HISTORY_TABLE)
        log = sa.func.dbms_lob.substr(
            table.c.kpi_sql_log, LOG_TAIL,
            sa.func.greatest(
                sa.func.dbms_lob.getlength(table.c.kpi_sql_log)
                - LOG_TAIL + 1, 1))
        select = (sa.select(table.c.processname, table.c.kpi_type,
                            table.c.kpi_value, table.c.alarm_level,
                            table.c.status, table.c.created,
                            log.label('kpi_sql_log'))
                    .where(table.c.processid == str(int(process_id)))
                    .order_by(table.c.kpi_type))
        return db.execute(select, as_table=True)

    def read_kpi_runs(self, control_name, limit=50):
        """Get the latest runs of one control, newest first."""
        if not control_name:
            return []
        log, controls = db.tables.log, db.tables.config
        select = (sa.select(log.c.process_id, log.c.status, log.c.date_from,
                            log.c.date_to, log.c.start_date, log.c.added)
                    .select_from(log.join(
                        controls, log.c.control_id == controls.c.control_id))
                    .where(controls.c.control_name == control_name)
                    .order_by(log.c.process_id.desc())
                    .limit(max(1, min(int(limit), 500))))
        return db.execute(select, as_table=True)

    def reingest(self, process_id):
        """Calculate and store the KPIs of one run with RACS_KPI_PKG.

        Calls racs_kpi_pkg.ingest_rapo_control, which takes the environment
        snapshot, calculates the saved KPIs into RACS_KPI_RUNHISTORY_ALL and
        posts the run to the dashboard. The package skips runs not ending D
        and controls aliased TEST..., and logs its errors in its own table
        instead of raising them, which is why the stored rows are returned.
        """
        if not self.available:
            raise ValueError('KPI tables are not available.')
        process_id = int(process_id)
        log, controls = db.tables.log, db.tables.config
        select = (sa.select(log.c.status, controls.c.control_name,
                            controls.c.control_alias)
                    .select_from(log.join(
                        controls, log.c.control_id == controls.c.control_id))
                    .where(log.c.process_id == process_id))
        run = db.execute(select, as_dict=True)
        if not run:
            raise ValueError(f'Run {process_id} does not exist.')
        if run['status'] != 'D':
            raise ValueError(f'Run {process_id} did not end D, so '
                             'RACS_KPI_PKG would skip it.')
        if (run['control_alias'] or '').upper().startswith('TEST'):
            raise ValueError(f'Control {run["control_name"]} is aliased '
                             f'{run["control_alias"]}, so RACS_KPI_PKG '
                             'would skip it.')
        if not self.read_control_kpis(run['control_name']):
            raise ValueError(f'Control {run["control_name"]} has no KPIs.')
        try:
            db.execute(sa.text('begin racs_kpi_pkg.ingest_rapo_control(:pid);'
                               ' end;').bindparams(pid=process_id))
        except sa.exc.DBAPIError as error:
            raise ValueError(str(error.orig).strip()) from error
        return self.read_history(process_id)

    def alarm_thresholds(self, statement):
        """Get the thresholds the dashboard reads from an alarm statement.

        A line-for-line port of racs_kpi_pkg.get_kpi_thresholds_json, which
        turns the statement into conditions with plain regular expressions.

        Returns
        -------
        thresholds : list of dict
            `{condition, alarm}`, highest alarm first, as the package sorts.
        problem : str or None
            Why the dashboard would show wrong thresholds, if it would.
        """
        text = re.sub(r'--.*', '', statement)
        text = re.sub(r'(case|select|end|from|dual|\s)', '', text.lower())
        text = re.sub(r'/\*.*\*/', '', text)
        text = re.sub(r'then([0-9]{1})', r'(\1)', text)
        text = re.sub(r'else([0-9]{1})', r'|else (\1)', text)
        text = re.sub(r':v_kpi_value', 'KPI', text)
        text = re.sub(r'^when', '', text)
        text = re.sub(r'when', ',', text)
        text = re.sub(r'and', ' & ', text)
        text = text.replace('|else (0)', '')
        for level in '321':
            text = text.replace(f'({level})', f'|{level}')
        thresholds = []
        for part in text.split(','):
            tokens = [token for token in part.strip().split('|') if token]
            condition = tokens[0] if tokens else None
            alarm = tokens[1] if len(tokens) > 1 else None
            thresholds.append({'condition': condition, 'alarm': alarm})
        thresholds.sort(key=lambda item: item['alarm'] or '', reverse=True)
        problems = []
        for item in thresholds:
            condition, alarm = item['condition'], item['alarm']
            if alarm not in ('1', '2', '3'):
                problems.append(f'"{condition}" has no alarm level 1-3')
            elif not condition or 'KPI' not in condition:
                problems.append(f'level {alarm} has no condition on '
                                ':v_kpi_value')
            elif re.search(r'[a-z]', condition.replace('KPI', '')
                                                .replace('abs', '')):
                problems.append(f'"{condition}" is not a plain comparison')
        problem = None
        if problems:
            problem = ('The dashboard can not read the thresholds: '
                       + '; '.join(problems) + '. Keep the shape "case when '
                       ':v_kpi_value > N then 1..3 ... else 0 end from dual".')
        return thresholds, problem

    def _code(self, value):
        """Normalize a KPI type code, which is always stored upper case."""
        value = (self._text(value) or '').upper()
        if not value:
            raise ValueError('KPI code is required.')
        if len(value) > 20:
            raise ValueError(f'KPI code {value} is longer than 20 characters.')
        return value

    def _type_values(self, record):
        """Turn an edited KPI type into the values of its row."""
        unit = self._text(record.get('kpi_value_unit'))
        if unit:
            # The column holds 10 bytes, not 10 characters, and units like the
            # euro sign take three of them.
            length = len(unit.encode('utf-8'))
            if length > 10:
                raise ValueError(f'Unit {unit} takes {length} bytes, the '
                                 'column holds 10.')
        return {'kpi_type': self._code(record.get('kpi_type')),
                'kpi_type_desc': self._text(record.get('kpi_type_desc')),
                'kpi_value_unit': unit,
                'kpi_priority': self._number(record.get('kpi_priority')),
                'kpi_decimal_places': self._number(
                    record.get('kpi_decimal_places')),
                'default_kpi_sql_statement': self._text(
                    record.get('default_kpi_sql_statement')),
                'default_alarm_sql_statement': self._text(
                    record.get('default_alarm_sql_statement'))}

    def _text(self, value):
        """Turn a blank statement into NULL, so that it means the default."""
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    def _number(self, value):
        """Turn a blank number into NULL."""
        if value is None or value == '':
            return None
        return value


def rename_table_references(text, old_name, new_name):
    """Point the result table names of a control in a statement to its new
    name.

    Whole RAPO_REST_/RAPO_RESA_/RAPO_RESB_<old_name> names are replaced, in
    any case, quoted or owner-qualified; a longer name that merely starts
    with it is not. The prefix keeps its case and the new name is written
    lower case where the old one was, unless quoted. Mirrored by renameTableReferences in
    rapo-ui/src/utils/kpi.js, which the editor applies live: keep both in
    step.

    Returns
    -------
    text : str
    count : int
        The references replaced.
    """
    if not text or not old_name or not new_name:
        return text, 0
    pattern = re.compile(r'(?<![\w$#])("?)(RAPO_RES[TAB]_)('
                         + re.escape(old_name) + r')\1(?![\w$#])', re.I)

    def replace(match):
        quote, prefix, name = match.groups()
        if not quote and name == name.lower():
            name = new_name.lower()
        else:
            name = new_name
        return f'{quote}{prefix}{name}{quote}'

    return pattern.subn(replace, text)


def _code_only(statement):
    """Drop comments and string literals, which may hold any word."""
    text = re.sub(r'/\*.*?\*/', ' ', statement, flags=re.S)
    text = re.sub(r'--[^\n]*', ' ', text)
    return re.sub(r"'(?:[^']|'')*'", "''", text)


def _plain(value):
    """Read a LOB the first column may be."""
    read = getattr(value, 'read', None)
    return read() if read else value


kpi = Kpi()
