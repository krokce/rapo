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

import sqlalchemy as sa

from .database import db


TYPE_TABLE = 'racs_kpi_type'
CONFIG_TABLE = 'racs_kpi_config'


class Kpi:
    """Represents the KPI configuration of controls."""

    def __init__(self):
        self._available = None
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

    def validate_statement(self, statement):
        """Parse a KPI or alarm statement without executing it.

        Returns
        -------
        result : dict
            Whether the statement parses, and the columns it would return.
        """
        if not statement or not statement.strip():
            return {'valid': False, 'error': 'Statement is empty.'}
        if not self.available:
            return {'valid': False, 'error': 'KPI tables are not available.'}
        connection = db.engine.raw_connection()
        try:
            cursor = connection.cursor()
            # parse() checks syntax, names and privileges without running the
            # statement, so a KPI can be checked without touching its data.
            cursor.parse(self._query(statement))
            description = cursor.description or []
        except Exception as error:
            return {'valid': False, 'error': str(error).strip()}
        finally:
            connection.close()
        columns = [{'name': column[0], 'type': str(column[1]).split()[-1]
                    .rstrip('>').replace('DB_TYPE_', '')}
                   for column in description]
        result = {'valid': True, 'columns': columns}
        if not columns:
            result['warning'] = ('Statement returns no columns, so it can not '
                                 'produce a value.')
        elif len(columns) > 1:
            result['warning'] = (f'Statement returns {len(columns)} columns, '
                                 'only the first one is used.')
        elif columns[0]['type'] != 'NUMBER':
            result['warning'] = (f'Column {columns[0]["name"]} is '
                                 f'{columns[0]["type"]}, not a number.')
        return result

    def _query(self, statement):
        """Drop the trailing semicolon a query is often written with.

        Only for a query: in PL/SQL the last semicolon is part of the block.
        """
        statement = statement.strip()
        if statement.lower().startswith(('select', 'with')):
            statement = statement.rstrip(';')
        return statement

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


kpi = Kpi()
