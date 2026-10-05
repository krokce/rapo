"""Contains application data reader."""

import datetime as dt
import sqlalchemy as sa

from .database import db


# Prefix of the rapo_log.text_message lines that flag a run with a warning.
WARNING_PREFIX = 'Warning: '


class Reader:
    """Represents application data reader.

    Reader used to extract aplication data from database to user.
    """

    def read_scheduler_record(self):
        """Get scheduler record from DB table.

        Returns
        -------
        record : dict
            Ordinary dictionary with web API information from DB table.
        """
        table = db.tables.scheduler
        select = table.select()
        record = db.execute(select, as_dict=True)
        return record

    def read_web_api_record(self):
        """Get web API record from DB table.

        Returns
        -------
        record : dict
            Ordinary dictionary with web API information from DB table.
        """
        table = db.tables.web_api
        select = table.select()
        record = db.execute(select, as_dict=True)
        return record

    def read_control_name(self, process_id):
        """Get control name using passed process_id.

        Parameters
        ----------
        process_id : int
            Unique process ID used to load record from DB log.

        Returns
        -------
        control_name : str
            Name of the defined control.
        """
        log = db.tables.log
        config = db.tables.config
        join = log.join(config, log.c.control_id == config.c.control_id)
        select = (sa.select(config.c.control_name).select_from(join)
                    .where(log.c.process_id == process_id))
        result = db.execute(select, as_one=True)
        if not result:
            message = f'no control of process with ID {process_id} found'
            raise ValueError(message)
        control_name = result.control_name
        return control_name

    def read_control_config_by_id(self, control_id):
        """Get control configuration by control ID, {} if not found."""
        table = db.tables.config
        select = table.select().where(table.c.control_id == control_id)
        return db.execute(select, as_dict=True) or {}

    def read_control_name_by_id(self, control_id):
        """Get control name by control ID, None if it does not exist."""
        config = db.tables.config
        select = (sa.select(config.c.control_name)
                    .where(config.c.control_id == control_id))
        return db.execute(select, as_scalar=True)

    def read_control_stamp(self, control_id=None, control_name=None):
        """Get ID and last change of a control by ID or name, or None."""
        config = db.tables.config
        select = sa.select(config.c.control_id, config.c.updated_date,
                           config.c.updated_by)
        if control_id is not None:
            select = select.where(config.c.control_id == control_id)
        else:
            select = select.where(config.c.control_name == control_name)
        return db.execute(select, as_dict=True)

    def read_run_state(self, process_id):
        """Get the state a running control run is supervised by.

        Reads the few values needed to decide whether a run must be stopped
        in one query, instead of loading the whole control.

        Returns
        -------
        record : dict or None
            Status, initiation date, start date, data window and configured
            timeout of the run, and the name and type of its control.
        """
        log = db.tables.log
        config = db.tables.config
        join = log.join(config, log.c.control_id == config.c.control_id,
                        isouter=True)
        select = (sa.select(log.c.status, log.c.added, log.c.start_date,
                            log.c.date_from, log.c.date_to,
                            config.c.timeout, config.c.control_name,
                            config.c.control_type)
                    .select_from(join)
                    .where(log.c.process_id == process_id))
        return db.execute(select, as_dict=True)

    def read_run_counts(self, process_id):
        """Get the fetched record numbers of the given run.

        Used to read back what the PL-SQL engine wrote, since the procedure
        takes no OUT arguments.

        Returns
        -------
        record : dict or None
            Fetched numbers of both datasources.
        """
        log = db.tables.log
        select = (sa.select(log.c.fetched_number_a, log.c.fetched_number_b)
                    .where(log.c.process_id == process_id))
        return db.execute(select, as_dict=True)

    def read_control_result(self, process_id):
        """Get control result from DB log table.

        Parameters
        ----------
        process_id : int
            Unique process ID used to load record from DB log.

        Returns
        -------
        record : dict
            Ordinary dictionary with control result.
        """
        if process_id:
            table = db.tables.log
            select = table.select().where(table.c.process_id == process_id)
            record = db.execute(select, as_dict=True)
            if record:
                return record
            else:
                message = f'no process with ID {process_id} found'
                raise ValueError(message)
        else:
            return None

    def read_control_config(self, control_name):
        """Get dictionary with control configuration from DB.

        Parameters
        ----------
        control_name : str
            Unique control name used to load record from DB configuration.

        Returns
        -------
        record : dict
            Ordinary dictionary with control configuration.
        """
        table = db.tables.config
        select = table.select().where(table.c.control_name == control_name)
        record = db.execute(select, as_dict=True)
        if record:
            return record
        else:
            message = f'no control with name {control_name} found'
            raise ValueError(message)

    def read_control_logs(self, control_name, days=365, statuses=[],
                          order_by=True, limit=None):
        """Retrieve control run logs with given parameters.

        Parameters
        ----------
        control_name : str
            Unique control name used to load logs.
        days : int
            Number of days for which logs are to be received.
        status : list
            List of statuses with which logs are to be retrieved.
        order_by : bool
            Whether to sort logs by process_id.
        limit : int or None
            Maximum number of logs to read, None for no limit. Logs carry
            the whole text of their run, so a frequently run control can
            hold a lot of them.

        Returns
        -------
        records : list
            Ordinary list with control logs.
        """
        log = db.tables.log
        config = db.tables.config
        join = log.join(config, log.c.control_id == config.c.control_id)
        select = sa.select(*log.columns).select_from(join)\
                   .where(config.c.control_name == control_name)
        if days and isinstance(days, int):
            dateform = 'YYYY-MM-DD HH24:MI:SS'
            cut_off_date = dt.datetime.now()-dt.timedelta(days=days)
            cut_off_date = cut_off_date.strftime('%Y-%m-%d %H:%M:%S')
            cut_off_date = sa.func.to_date(cut_off_date, dateform)
            select = select.where(log.c.added > cut_off_date)
        if statuses:
            if all(isinstance(i, str) and len(i) == 1 for i in statuses):
                select = select.where(log.c.status.in_(statuses))
        if order_by:
            select = select.order_by(log.c.process_id.desc())
        if limit:
            select = select.limit(limit)
        answerset = db.execute(select, as_table=True)
        return answerset

    def read_control_recent_logs(self, control_name):
        """Retrieve logs of currently working control instances.

        Parameters
        ----------
        control_name : str
            Unique control name used to load logs.

        Returns
        -------
        records : list
            Ordinary list with currently running control run logs.
        """
        statuses = ['W', 'S', 'P', 'F']
        return self.read_control_logs(control_name, days=1, statuses=statuses)

    def read_running_controls(self):
        """Get list of running controls."""
        table = db.tables.log
        select = table.select().where(
            table.c.status.in_(['I', 'P', 'W', 'S', 'F']))
        answerset = db.execute(select, as_table=True)
        return answerset

    def read_control_config_all(self):
        """Get list of all controls in the config table."""
        config = db.tables.config
        select = config.select().order_by(config.c.updated_date.desc())
        answerset = db.execute(select, as_table=True)
        return answerset

    def read_control_config_versions(self, control_id):
        """Get an array  with all past control configurations from DB.

        rapo_config_bak has no key, and two saves in one second share their
        audit_date, so each version carries its ROWID as `version_id`.
        """
        table = db.tables.config_bak
        version_id = sa.literal_column('rowidtochar(rowid)').label('version_id')
        select = (sa.select(table, version_id)
                    .where(table.c.control_id == control_id)
                    .order_by(table.c.audit_date.desc()))
        answerset = db.execute(select, as_table=True)
        return answerset

    def delete_control_config_versions(self, control_id, version_ids=None,
                                       older_than_days=None, keep=0,
                                       dry_run=False):
        """Delete past versions of one control from rapo_config_bak.

        Either the versions given by their `version_id` (ROWID), or those
        older than `older_than_days` by the database clock (audit_date is
        stamped with it), apart from the newest `keep` versions.

        Returns
        -------
        result : int or list of str
            Number of versions deleted, or with `dry_run` the version_ids
            that would be.
        """
        if version_ids:
            where = 'rowid in :ids'
            params = [sa.bindparam('ids', [str(item) for item in version_ids],
                                   expanding=True)]
        elif older_than_days is not None:
            where = """audit_date < sysdate - :days
                   and rowid not in (
                     select rid from (
                       select rowid rid from rapo_config_bak
                        where control_id = :control_id
                        order by audit_date desc)
                      where rownum <= :keep)"""
            params = [sa.bindparam('days', older_than_days),
                      sa.bindparam('keep', keep)]
        else:
            return [] if dry_run else 0
        verb = 'select rowidtochar(rowid)' if dry_run else 'delete'
        statement = sa.text(f"""{verb} from rapo_config_bak
                                 where control_id = :control_id
                                   and {where}""")
        statement = statement.bindparams(
            sa.bindparam('control_id', control_id), *params)
        if dry_run:
            return [row[0] for row in db.execute(statement, as_records=True)]
        return db.execute(statement).rowcount

    def read_run_calendar(self, start, end):
        """Get the runs and runs in error per day in [start, end).

        A run counts on the day it started, or was added if it never started,
        as on Results; runs of deleted controls are left out as there.

        Returns
        -------
        days : dict
            By YYYY-MM-DD, `count` and `errors`, for the days with runs.
        """
        rows = db.execute(sa.text("""
            select to_char(trunc(nvl(l.start_date, l.added)), 'YYYY-MM-DD') day,
                   count(*) runs,
                   sum(case when l.status = 'E' then 1 else 0 end) errors
              from rapo_log l
              join rapo_config c on l.control_id = c.control_id
             where nvl(l.start_date, l.added) >= :day_from
               and nvl(l.start_date, l.added) < :day_to
             group by trunc(nvl(l.start_date, l.added))
        """).bindparams(day_from=start, day_to=end), as_table=True)
        return {row['day']: {'count': int(row['runs']),
                             'errors': int(row['errors'] or 0)}
                for row in rows}

    def read_control_results_for_day(self, day):
        """Get list of all control runs started on the passed day."""
        return self.read_control_runs(day=day)

    def read_control_runs(self, day=None, control_name=None, days=None):
        """Get the runs started on a day, or those of one control.

        Parameters
        ----------
        day : date or None
            Day the runs started on (a run that never started counts on the
            day it was added).
        control_name : str or None
            One control's runs of the last `days` days instead.
        days : int or None
            Days back, counted from now, for `control_name`.

        Returns
        -------
        runs : list
            Rows with the control, counters, trigger and dates, newest first.
        """
        select = f"""
                select
                    c.control_name,
                    c.control_id,
                    c.control_type,
                    l.process_id,
                    l.added,
                    nvl(l.start_date, l.added) start_date,
                    l.end_date,
                    l.date_from,
                    l.date_to,
                    l.status,
                    nvl(coalesce(success_number_a, success_number), 0) as success_number_a,
                    nvl(coalesce(success_number_b, 0), 0) as success_number_b,
                    nvl(coalesce(fetched_number_a, fetched_number), 0) as fetched_number_a,
                    nvl(coalesce(fetched_number_b, 0), 0) as fetched_number_b,
                    nvl(coalesce(error_number_a, error_number), 0) as error_number_a,
                    nvl(coalesce(error_number_b, 0), 0) as error_number_b,
                    nvl(coalesce(error_level_a, error_level), 0) as error_level_a,
                    nvl(coalesce(error_level_b, 0), 0) as error_level_b,
                    text_log,
                    nvl(text_error, text_message) text_error,
                    case when dbms_lob.instr(text_message, '{WARNING_PREFIX}') > 0
                         then 1 else 0 end as has_warning,
                    prerequisite_value,
                    nvl(round((l.end_date - nvl(l.start_date, l.added)) * 1440, 2), 0) duration_minutes,
                    e.trigger_type,
                    e.trigger_message,
                    e.scheduled_time
                from rapo_log l
                left join rapo_config c on l.control_id = c.control_id
                -- What started the run (rapo_scheduler_event, one row per process), null for a run the run
                -- manager did not start.
                left join (select process_id,
                                  max(trigger_type) trigger_type,
                                  max(message) trigger_message,
                                  max(scheduled_time) scheduled_time
                             from rapo_scheduler_event
                            where process_id is not null
                            group by process_id) e on e.process_id = l.process_id
                where 1=1
                    and c.control_name is not null
                    and {'c.control_name = :control_name' if control_name else '1=1'}
                    and ((l.start_date >= :day_start and l.start_date < :day_end)
                         or (l.start_date is null and l.added >= :day_start and l.added < :day_end))
                order by process_id desc
        """
        if control_name:
            # As read_control_logs counts days back: from now, on the app clock.
            day_end = dt.datetime.now()+dt.timedelta(days=1)
            day_start = dt.datetime.now()-dt.timedelta(days=days or 7)
            params = {'control_name': control_name}
        else:
            day_start = dt.datetime.combine(day, dt.time())
            day_end = day_start + dt.timedelta(days=1)
            params = {}
        select = sa.text(select).bindparams(day_start=day_start, day_end=day_end,
                                            **params)
        answerset = db.execute(select, as_table=True)
        return answerset

    def read_datasources(self, types=False):
        """Get list of all datasources in the DB.

        Names only, or with `types` [{name, type}], type TABLE or VIEW.
        """
        answerset = db.execute("select object_name, object_type from user_objects where object_type in ('VIEW', 'TABLE') order by 1", as_table=True)
        if types:
            return [{'name': record['object_name'],
                     'type': record['object_type']} for record in answerset]
        object_names = [record['object_name'] for record in answerset]
        return object_names

    def read_datasource_columns(self, datasource_name):
        """Get list of all column names of the passed datasource_name."""

        select = sa.text('select column_name, data_type from user_tab_cols '
                         'where table_name = :datasource_name '
                         'order by column_id')
        select = select.bindparams(datasource_name=datasource_name)
        answerset = db.execute(select, as_table=True)
        return answerset

    def read_schema_columns(self, tables, chunk=300):
        """Get the columns of many tables and views from the dictionary.

        Parameters
        ----------
        tables : iterable of tuple
            (owner, table_name) pairs, uppercase. owner None means the
            current schema.

        Returns
        -------
        columns : dict
            {(owner, table_name): [column, ...]} in column order, each column
            a dict like Executor._read_table_schema returns, plus the object
            type (TABLE or VIEW) under 'object_type'. A table that does not
            exist is absent. Invisible columns (no column_id) are left out,
            as SQLAlchemy's reflection and select * leave them out.
        """
        schema, user = db.execute(
            "select sys_context('userenv', 'current_schema'), user from dual",
            as_one=True)
        keys = sorted({(owner or schema, name) for owner, name in tables})
        found = {}
        # The tables of the own schema, i.e. every result table and most
        # datasources, are read from user_tab_columns: all_tab_columns has to
        # check privileges on the whole dictionary and takes several times
        # longer for the same rows.
        local = [name for owner, name in keys if owner == user == schema]
        keys = [key for key in keys if not (key[0] == user == schema)]
        for i in range(0, len(local), chunk):
            part = local[i:i + chunk]
            names = ', '.join(f':t{j}' for j in range(len(part)))
            params = {f't{j}': name for j, name in enumerate(part)}
            query = sa.text(
                'select c.table_name, lower(c.column_name) name, '
                'c.column_name, '
                'c.data_type, c.data_length, c.char_length, c.char_used, '
                'c.data_precision, c.data_scale, c.nullable, '
                "nvl2(t.table_name, 'TABLE', 'VIEW') object_type "
                'from user_tab_columns c '
                'left join user_tables t on t.table_name = c.table_name '
                f'where c.table_name in ({names}) '
                'and c.column_id is not null '
                'order by c.table_name, c.column_id'
            ).bindparams(**params)
            for row in db.execute(query, as_table=True):
                key = (schema, row.pop('table_name'))
                found.setdefault(key, []).append(row)
        for i in range(0, len(keys), chunk):
            part = keys[i:i + chunk]
            pairs = ', '.join(f'(:o{j}, :t{j})' for j in range(len(part)))
            params = {}
            for j, (owner, name) in enumerate(part):
                params[f'o{j}'], params[f't{j}'] = owner, name
            query = sa.text(
                'select c.owner, c.table_name, lower(c.column_name) name, '
                'c.column_name, '
                'c.data_type, c.data_length, c.char_length, c.char_used, '
                'c.data_precision, c.data_scale, c.nullable, '
                "nvl2(t.table_name, 'TABLE', 'VIEW') object_type "
                'from all_tab_columns c '
                'left join all_tables t '
                'on t.owner = c.owner and t.table_name = c.table_name '
                f'where (c.owner, c.table_name) in ({pairs}) '
                'and c.column_id is not null '
                'order by c.owner, c.table_name, c.column_id'
            ).bindparams(**params)
            for row in db.execute(query, as_table=True):
                key = (row.pop('owner'), row.pop('table_name'))
                found.setdefault(key, []).append(row)
        return {(None if owner == schema else owner, name): columns
                for (owner, name), columns in found.items()}

    def resolve_datasources(self, tables):
        """Tell what datasource names without dictionary columns stand for.

        Parameters
        ----------
        tables : iterable of tuple
            (owner, name) pairs, uppercase, as read_schema_columns takes them.

        Returns
        -------
        synonyms : dict
            {(owner, name): (table_owner, table_name, db_link)} for the names
            that are synonyms: a private one of the owner (the current schema
            for owner None) first, else a public one for an unqualified name.
        existing : set
            The other names that are an object Rapo's user can see, e.g. a
            view it cannot describe. A name in neither does not exist.
        """
        schema = db.execute("select sys_context('userenv', 'current_schema') "
                            "from dual", as_scalar=True)
        keys = sorted(set(tables), key=lambda key: (key[0] or '', key[1]))
        synonyms, existing = {}, set()
        if not keys:
            return synonyms, existing
        pairs = ', '.join(f'(:o{j}, :t{j})' for j in range(len(keys)))
        params = {}
        for j, (owner, name) in enumerate(keys):
            params[f'o{j}'], params[f't{j}'] = owner or schema, name
        public = ', '.join(f':t{j}' for j, (owner, _) in enumerate(keys)
                           if not owner) or 'null'
        query = sa.text(
            'select owner, synonym_name, table_owner, table_name, db_link '
            'from all_synonyms '
            f'where (owner, synonym_name) in ({pairs}) '
            f"or (owner = 'PUBLIC' and synonym_name in ({public}))"
        ).bindparams(**params)
        found = {}
        for row in db.execute(query, as_table=True):
            found[(row['owner'], row['synonym_name'])] = (
                row['table_owner'], row['table_name'], row['db_link'])
        for owner, name in keys:
            target = (found.get((owner or schema, name))
                      or (None if owner else found.get(('PUBLIC', name))))
            if target:
                synonyms[(owner, name)] = target
        rest = [key for key in keys if key not in synonyms]
        if rest:
            pairs = ', '.join(f'(:o{j}, :t{j})' for j in range(len(rest)))
            params = {}
            for j, (owner, name) in enumerate(rest):
                params[f'o{j}'], params[f't{j}'] = owner or schema, name
            query = sa.text(
                'select distinct owner, object_name from all_objects '
                f'where (owner, object_name) in ({pairs})'
            ).bindparams(**params)
            seen = {(row['owner'], row['object_name'])
                    for row in db.execute(query, as_table=True)}
            existing = {(owner, name) for owner, name in rest
                        if (owner or schema, name) in seen}
        return synonyms, existing

    def save_control(self, data):
        """Create or update control object in the config table with passed control data."""
        config = db.tables.config

        # Remove control object columns that are not in DB table
        for k in [i for i in set(data.keys()).difference(config.columns.keys())]:
          del data[k]

        data['updated_date'] = dt.datetime.now()

        if 'control_id' in data:
            data['created_date'] = dt.datetime.fromisoformat(data['created_date'])
            update = config.update().where(config.c.control_id == data['control_id']).values(data)
            result = db.execute(update)
        else:
            data['created_date'] = dt.datetime.now()
            insert = config.insert().values(data)
            result = db.execute(insert)
        return result

    def update_control(self, control_id, values):
        """Update the given columns of the control with the passed ID."""
        config = db.tables.config
        update = (config.update()
                        .where(config.c.control_id == control_id)
                        .values(**values, updated_date=dt.datetime.now()))
        return db.execute(update)

    def delete_control(self, control_id):
        """Delete control from the config table of the passed control_id."""
        config = db.tables.config
        delete = config.delete().where(config.c.control_id == control_id)
        result = db.execute(delete)
        return result


reader = Reader()
