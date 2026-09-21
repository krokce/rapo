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
