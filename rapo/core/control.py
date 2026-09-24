"""Contains RAPO control interface."""

import sys
import traceback as tb
import threading as th
import multiprocessing as mp

import re
import json
import uuid
import time as tm
import datetime as dt

import sqlalchemy as sa

from ..database import db
from ..logger import logger
from ..reader import reader
from ..utils import utils

from ..config import get_algorithm_setting

from . import mailer
from .fields import (
    RESULT_KEY, RESULT_VALUE, RESULT_TYPE, DISCREPANCY_ID,
    DISCREPANCY_DESCRIPTION
)
from .case import (
    NORMAL, INFO, ERROR, WARNING, INCIDENT, DISCREPANCY,
    SUCCESS, LOSS, DUPLICATE
)


class Control:
    """Represents a control and acts like its API.

    Parameters
    ----------
    name : str, optional
        Name of the control from configuration table.
    timestamp : float or None
        Timestamp of this process.
    date_from : str or datetime, optional
        Data source date lower bound.
    date_to : str or datetime, optional
        Data source date upper bound.
    config : dict, optional
        Configuration to use instead of the stored one, e.g. an unsaved one
        whose result table schema is being checked. Never run it.

    Attributes
    ----------
    name : str
        Name of the control from configuration table.
    timestamp : float or None
        Timestamp of this process.
    parser : rapo.Parser
        Parser instance for this control.
    executor : rapo.Executor
        Executor instance for this control.
    log : sqlalchemy.Table
        RAPO_LOG table object.
    config : sqlalchemy.RowProxy
        configuration table record for this control.
    id : int
        ID of the control from configuration table.
    group : str or None
        Group of the control from configuration table.
    type : str or None
        Type of the control from configuration table. See reference types
        table.
    engine : str or None
        Engine of the control from configuration table. See reference engines
        table.
    process_id : int or None
        Process id from RAPO_LOG.
    pid : int or None
        Process id from RAPO_LOG.
    source_name: str or None
        Data source name.
    source_date_field :
        Data source date field.
    source_name_a : str or None
        Data source A name.
    source_date_field_a :
        Data source A date field.
    source_name_b : str or None
        Data source B name.
    source_date_field_b :
        Data source B date field.
    updated : datetime or None
        Date when process RAPO_LOG record was last updated.
    start_date : datetime or None
        Date when process started.
    end_date : datetime or None
        Date when process finished.
    status : bool or None
        Current process status.
    select : sqlalchemy.Select
        SQL statement to fetch data from data source.
    select_a : sqlalchemy.Select
        SQL statement to fetch data from data source A.
    select_b : sqlalchemy.Select
        SQL statement to fetch data from data source B.
    rule_config : list
        Configuration defining success result.
    error_definition : list
        Configuration defining error result.
    output_columns : list or None
        Output column configuration.
    output_columns_a : list or None
        Output A column configuration.
    output_columns_b : list or None
        Output B column configuration.
    need_a : bool or None
        Flag to define whether save output A or not.
    need_b : bool or None
        Flag to define whether save output B or not.
    need_prerun_hook : bool or None
        Flag to define whether run database prerun hook function or not.
    need_hook : bool or None
        Flag to define whether run database hook procedure or not.
    source_table : sqlalchemy.Table
        Proxy object reflecting data source table.
    source_table_a : sqlalchemy.Table
        Proxy object reflecting data source A table.
    source_table_b : sqlalchemy.Table
        Proxy object reflecting data source B table.
    input_table : sqlalchemy.Table
        Proxy object reflecting table with fetched records from data source.
    input_table_a : sqlalchemy.Table
        Proxy object reflecting table with fetched records from data source A.
    input_table_b : sqlalchemy.Table
        Proxy object reflecting table with fetched records from data source B.
    stage_table : sqlalchemy.Table
        Proxy object reflecting table with found matches.
    error_table : sqlalchemy.Table
        Proxy object reflecting table with found discrapancies.
    error_table_a : sqlalchemy.Table
        Proxy object reflecting table with found discrapancies from A.
    error_table_b : sqlalchemy.Table
        Proxy object reflecting table with found discrapancies from B.
    fetched_number : int or None
        Number of fetched records from data source.
    success_number : int or None
        Number of success results.
    error_number : int or None
        Number of discrapancies.
    error_level : float or None
        Indicator presenting the percentage of discrapancies among the fetched
        records.
    fetched_number_a : int or None
        Number of fetched records from data source A.
    fetched_number_b : int or None
        Number of fetched records from data source B.
    success_number_a : int or None
        Number of success results in A.
    success_number_b : int or None
        Number of success results in B.
    error_number_a : int or None
        Number of discrapancies in A.
    error_number_b : int or None
        Number of discrapancies in B.
    error_level_a : float or None
        Indicator presenting the percentage of discrapancies among the fetched
        records from A.
    error_level_b : float or None
        Indicator presenting the percentage of discrapancies among the fetched
        records from B.
    date_from : datetime
        Data source date lower bound.
    date_from : datetime
        Data source date upper bound.
    """

    def __init__(self, name=None, timestamp=None, process_id=None,
                 iteration_id=None, date=None, date_from=None, date_to=None,
                 debug_mode=False, config=None):
        self.name = name or reader.read_control_name(process_id)
        # An unsaved configuration (the editor's form), used only to inspect
        # what the control would do, e.g. the schema of its result tables.
        self.config = config or reader.read_control_config(self.name)
        self.result = reader.read_control_result(process_id)
        self.id = int(self.config['control_id'])
        self.group = self.config['control_group']
        self.type = self.config['control_type']
        self.engine = self.config['control_engine']
        self.debug_mode = debug_mode

        self.parser = Parser(self)
        self.executor = Executor(self)

        self.process = None
        self.handler = None

        # Optional callable taking this control, called once the control is
        # initiated. Iterations and cascades inherit it, so the run manager
        # can follow every run performed in one control process.
        self.observer = None
        self.trigger = None

        self.process_id = process_id
        if self.result:
            self.start_date = self.result['start_date']
            self.end_date = self.result['end_date']
            self.updated = self.result['updated']
            self.status = self.result['status']

            self.iteration_id = None
            self.timestamp = None
            self.scheduled = False
            self.date_from = self.result['date_from']
            self.date_to = self.result['date_to']

            self.fetched_number = self.result['fetched_number']
            self.success_number = self.result['success_number']
            self.error_number = self.result['error_number']

            self.fetched_number_a = self.result['fetched_number_a']
            self.fetched_number_b = self.result['fetched_number_b']
            self.success_number_a = self.result['success_number_a']
            self.success_number_b = self.result['success_number_b']
            self.error_number_a = self.result['error_number_a']
            self.error_number_b = self.result['error_number_b']
        else:
            self.start_date = None
            self.end_date = None
            self.updated = None
            self.status = None

            self.iteration_id = iteration_id
            if self.iteration_id:
                iteration_config = utils.get_config(self.iteration_id,
                                                    self.iteration_config)
                self.period_back = iteration_config['period_back']
                self.period_number = iteration_config['period_number']
                self.period_type = iteration_config['period_type']
            else:
                self.period_back = self.config['period_back']
                self.period_number = self.config['period_number']
                self.period_type = self.config['period_type']

            self.timestamp = timestamp
            # Whether the timestamp is a moment the run was really fired at.
            # A manual run has its own reconstructed for the iterations.
            self.scheduled = bool(timestamp)
            if self.timestamp:
                self.date_from, self.date_to = self.parser.parse_dates()
            elif date:
                self.date_from = self.parser.parse_date(date, 0, 0, 0)
                self.date_to = self.parser.parse_date(date, 23, 59, 59)
            else:
                self.date_from = self.parser.parse_date(date_from)
                self.date_to = self.parser.parse_date(date_to)

            self.fetched_number = None
            self.success_number = None
            self.error_number = None

            self.fetched_number_a = None
            self.success_number_a = None
            self.error_number_a = None

            self.fetched_number_b = None
            self.success_number_b = None
            self.error_number_b = None

        self.source_table = None
        self.source_table_a = None
        self.source_table_b = None

        self.input_table = None
        self.input_table_a = None
        self.input_table_b = None

        self.stage_table = None
        self.error_table = None
        self.error_table_a = None
        self.error_table_b = None
        self.stage_table_a = None
        self.stage_table_b = None

        self.output_table = None
        self.output_table_a = None
        self.output_table_b = None

        self._all_errors = []
        self._with_error = False
        self._pending_error = None

        self._all_messages = []
        if self.result:
            if self.result['text_message']:
                text_messages = self.result['text_message'].splitlines()
                self._all_messages.extend(text_messages)

    def __str__(self):
        return self.label

    def __repr__(self):
        return self.label

    @property
    def name(self):
        """Get control name."""
        return self._name

    @name.setter
    def name(self, value):
        if isinstance(value, str) or value is None:
            self._name = value
        else:
            type = value.__class__.__name__
            message = f'name must be str or None, not {type}'
            raise TypeError(message)

    @property
    def label(self):
        """Represent control as a simple string with or withoud process id."""
        if not self.process_id:
            return f'[{self.name}]'
        return f'[{self.name}:{self.process_id}]'

    @property
    def date(self):
        """Get control date if relevant."""
        if self.date_from.date() == self.date_to.date():
            return self.date_from.date()

    @property
    def process_id(self):
        """Get control run process ID."""
        return self._process_id

    @process_id.setter
    def process_id(self, value):
        if isinstance(value, int) or value is None:
            self._process_id = value
        else:
            type = value.__class__.__name__
            message = f'process_id must be int or None, not {type}'
            raise TypeError(message)

    @property
    def pid(self):
        """Shortcut for process_id."""
        return self._process_id

    @property
    def is_analysis(self):
        """Identify whether control is analysis or not."""
        return True if self.type == 'ANL' else False

    @property
    def is_reconciliation(self):
        """Identify whether control is reconciliation or not."""
        return True if self.type == 'REC' else False

    @property
    def is_comparison(self):
        """Identify whether control is comparison or not."""
        return True if self.type == 'CMP' else False

    @property
    def is_plsql_engine(self):
        """Identify whether control runs through the Oracle-side procedure."""
        return True if self.engine == 'PL' else False

    @property
    def is_database_engine(self):
        """Identify whether control results are produced in the database.

        True for both SQL engines. The fetch and index steps still branch on
        the engine code itself, because the PL-SQL engine performs them inside
        the procedure, but anything that merely reads a produced table applies
        to both.
        """
        return True if self.engine in ('DB', 'PL') else False

    @property
    def is_report(self):
        """Identify whether control is report or not."""
        return True if self.type == 'REP' else False

    @property
    def status(self):
        """Get control run status."""
        return self._status

    @status.setter
    def status(self, value):
        """Set control run status."""
        if isinstance(value, str) and len(value) == 1:
            if hasattr(self, '_status'):
                self._status = value
                self.updated = dt.datetime.now()
                logger.info(f'{self} Status changed to {self._status}')
            else:
                self._status = value
        elif value is None:
            self._status = None
        else:
            message = f'incorrect status: {value}'
            raise ValueError(message)

    @property
    def duration(self):
        """Get control duration."""
        if self.start_date and self.end_date:
            return int((self.end_date-self.start_date).total_seconds())
        elif self.start_date:
            current_date = dt.datetime.now()
            return int((current_date-self.start_date).total_seconds())
        else:
            return 0

    @property
    def initiated(self):
        """Check if control is initiated."""
        if self.status == 'I':
            return True
        return False

    @property
    def waiting(self):
        """Check if control is waiting to start."""
        if self.status == 'W':
            return True
        return False

    @property
    def working(self):
        """Check if control is working."""
        if self.status in ('S', 'P', 'F'):
            return True
        return False

    @property
    def timeout(self):
        """Check if control time limit is reached."""
        time_limit = self.config['timeout']
        if isinstance(time_limit, int) and self.duration > time_limit:
            return True
        return False

    @property
    def blocked(self):
        """Check if control has exceeded instance limit."""
        instance_list = reader.read_control_recent_logs(self.name)
        instance_number = len(instance_list)
        instance_limit = self.config['instance_limit']
        if instance_number >= instance_limit:
            return True
        return False

    @property
    def error_level(self):
        """Calculate control error level."""
        if self.is_analysis:
            if self.fetched_number and self.fetched_number > 0:
                return (self.error_number/self.fetched_number)*100
        elif self.is_comparison:
            total_number = self.success_number+self.error_number
            if total_number and total_number > 0:
                return (self.error_number/total_number)*100

    @property
    def error_level_a(self):
        """Calculate control error level A."""
        if self.is_reconciliation:
            if self.need_a and (self.fetched_number_a or 0) > 0:
                if self.error_number_a is not None:
                    return (self.error_number_a/self.fetched_number_a)*100

    @property
    def error_level_b(self):
        """Calculate control error level B."""
        if self.is_reconciliation:
            if self.need_b and (self.fetched_number_b or 0) > 0:
                if self.error_number_b is not None:
                    return (self.error_number_b/self.fetched_number_b)*100

    @property
    def text_error(self):
        """Get textual error representation of current control run."""
        errors = self._all_errors.copy()
        texts = [''.join(tb.format_exception(*error)) for error in errors]
        text = f'{str():->40}\n'.join(texts)
        return text

    @property
    def text_message(self):
        """Get textual message describing current control run."""
        text = '\n'.join(self._all_messages)
        return text

    @property
    def source_name(self):
        """Get control data source name."""
        return self.parser.parse_source_name()

    @property
    def source_filter(self):
        """Get control data source filter clause."""
        return self.parser.parse_filter()

    @property
    def source_date_field(self):
        """Get control data source date field."""
        return utils.to_lower(self.config['source_date_field'])

    @property
    def source_name_a(self):
        """Get control data source A name."""
        return self.parser.parse_source_name_a()

    @property
    def source_filter_a(self):
        """Get control data source A filter clause."""
        return self.parser.parse_filter_a()

    @property
    def source_date_field_a(self):
        """Get control data source A date field."""
        return utils.to_lower(self.config['source_date_field_a'])

    @property
    def source_key_field_a(self):
        """Get control data source A key field."""
        return utils.to_lower(self.config['source_key_field_a'])

    @property
    def source_name_b(self):
        """Get control data source B name."""
        return self.parser.parse_source_name_b()

    @property
    def source_filter_b(self):
        """Get control data source B filter clause."""
        return self.parser.parse_filter_b()

    @property
    def source_date_field_b(self):
        """Get control data source B date field."""
        return utils.to_lower(self.config['source_date_field_b'])

    @property
    def source_key_field_b(self):
        """Get control data source B key field."""
        return utils.to_lower(self.config['source_key_field_b'])

    @property
    def result_columns(self):
        """Get object representing result columns."""
        return self.parser.parse_result_columns()

    @property
    def key_column(self):
        """Get process identification column."""
        return self.parser.parse_key_column()

    @property
    def select(self):
        """Get SQL statement to fetch data from data source."""
        return self.parser.parse_select()

    @property
    def select_a(self):
        """Get SQL statement to fetch data from data source A."""
        return self.parser.parse_select_a()

    @property
    def select_b(self):
        """Get SQL statement to fetch data from data source B."""
        return self.parser.parse_select_b()

    @property
    def output_names(self):
        """Get output table names."""
        return self.parser.parse_output_names()

    @property
    def written_output_names(self):
        """Get the result tables a run of this configuration writes."""
        return self.parser.parse_written_output_names()

    @property
    def orphan_output_names(self):
        """Get existing result tables of this control that runs no longer write."""
        written = self.written_output_names
        return [name for name in output_table_names(self.name)
                if name not in written and db.exists(name)]

    @property
    def output_tables(self):
        """Get output tables."""
        return self.parser.parse_output_tables()

    @property
    def output_name(self):
        """Get control result table name."""
        if self.is_analysis or self.is_comparison or self.is_report:
            return f'rapo_rest_{self.name}'.lower()

    @property
    def output_name_a(self):
        """Get control result table A name."""
        if self.is_reconciliation:
            return f'rapo_resa_{self.name}'.lower()

    @property
    def output_name_b(self):
        """Get control result table B name."""
        if self.is_reconciliation:
            return f'rapo_resb_{self.name}'.lower()

    @property
    def temporary_names(self):
        """Get temporary table names."""
        return self.parser.parse_temporary_names()

    @property
    def temporary_tables(self):
        """Get temporary tables."""
        return self.parser.parse_temporary_tables()

    @property
    def rule_config(self):
        """Get control match configuration."""
        if self.is_analysis:
            return []
        elif self.is_reconciliation:
            return self.parser.parse_reconciliation_rule_config()
        elif self.is_comparison:
            return self.parser.parse_comparison_rule_config()
        elif self.is_report:
            return []

    @property
    def case_config(self):
        """Get control case configuration."""
        return self.parser.parse_case_config()

    @property
    def case_definition(self):
        """Get control result definition."""
        return self.parser.parse_case_definition()

    @property
    def error_definition(self):
        """Get control error definition."""
        if self.is_analysis:
            return self.parser.parse_analyze_error_definition()
        elif self.is_reconciliation:
            return []
        elif self.is_comparison:
            return self.parser.parse_comparison_error_definition()
        elif self.is_report:
            return []

    @property
    def error_sql(self):
        """Get control error SQL expression."""
        if self.is_analysis:
            return self.parser.parse_analyze_error_sql()

    @property
    def iteration_config(self):
        """Get control iteration configuration."""
        return self.parser.parse_iteration_config()

    @property
    def cascade_config(self):
        """Get control cascade configuration."""
        return self.parser.parse_cascade_config()

    @property
    def output_columns(self):
        """Get control output column configuration."""
        return self.parser.parse_output_columns()

    @property
    def output_columns_a(self):
        """Get control output A column configuration."""
        return self.parser.parse_output_columns_a()

    @property
    def output_columns_b(self):
        """Get control output B column configuration."""
        return self.parser.parse_output_columns_b()

    @property
    def mandatory_columns(self):
        """Get control mandatory output columns configuration."""
        return self.parser.parse_mandatory_columns()

    @property
    def parallelism(self):
        """Get parameter describing execution parallelism."""
        return self.config['parallelism']

    @property
    def need_a(self):
        """Get parameter defining necessity of data source A saving."""
        return self.parser.parse_boolean('need_a')

    @property
    def need_b(self):
        """Get parameter defining necessity of data source B saving."""
        return self.parser.parse_boolean('need_b')

    @property
    def with_deletion(self):
        """Get parameter to clear output table before usage."""
        return self.parser.parse_boolean('with_deletion')

    @property
    def with_drop(self):
        """Get parameter to drop output table before usage."""
        return self.parser.parse_boolean('with_drop')

    @property
    def need_hook(self):
        """Get parameter defining necessity of hook execution."""
        return self.parser.parse_boolean('need_hook')

    @property
    def need_prerun_hook(self):
        """Get parameter defining necessity of prerun hook execution."""
        return self.parser.parse_boolean('need_prerun_hook')

    @property
    def need_postrun_hook(self):
        """Get parameter defining necessity of postrun hook execution."""
        return self.parser.parse_boolean('need_postrun_hook')

    @property
    def has_cases(self):
        """Identify whether control is case-configured or not."""
        if self.config['case_config'] and self.config['case_definition']:
            return True
        return False

    @property
    def has_iterations(self):
        """Identify whether control is iteration-configured or not."""
        if self.config['iteration_config']:
            return True
        return False

    @property
    def variables(self):
        """Get control variables."""
        return self.parser.parse_variables()

    def run(self):
        """Run control in an ordinary way."""
        logger.debug(f'{self} Running control...')
        if self._initiate():
            if self._throttle():
                self._resume()

    def launch(self):
        """Run control as a separate accompanied stoppable process."""
        logger.debug(f'{self} Running control...')
        if self._initiate():
            self._spawn()

    def _cascade_dates(self):
        """Get the date parameters a cascaded run inherits from this one.

        A scheduled run passes its timestamp down, so that every control of
        the cascade derives its own window from its own period configuration.
        A manual run has no timestamp, so it passes its window itself and the
        whole cascade runs for the dates that were requested.
        """
        if self.timestamp:
            return {'timestamp': self.timestamp}
        return {'date_from': self.date_from, 'date_to': self.date_to}

    def _iteration_dates(self):
        """Get the date parameters an iteration of this run derives from.

        An iteration differs from its run only by its period configuration,
        so it needs the moment that configuration is counted back from. A
        scheduled run has it, and a manual run has its window reconstructed
        into one, so that the iterations of a manual run keep their offsets
        relative to the dates that were requested instead of repeating them.
        """
        if self.timestamp:
            return {'timestamp': self.timestamp}
        return {'timestamp': self.parser.parse_timestamp()}

    @property
    def _chain_moment(self):
        """Get the moment a chained run is labeled with in the log."""
        if self.timestamp:
            return self.timestamp
        return f'{self.date_from} - {self.date_to}'

    def iterate(self):
        """Run all additional control iterations."""
        for case in self.iteration_config:
            iteration_id = case['iteration_id']
            iteration_status = case['status']
            if iteration_status:
                logger.info(f'{self} Iterating control '
                            f'using configuration {case}')
                control = self.__class__(name=self.name,
                                         iteration_id=iteration_id,
                                         debug_mode=self.debug_mode,
                                         **self._iteration_dates())
                control.scheduled = self.scheduled
                control.observer = self.observer
                control.trigger = 'ITERATION'
                control.run()

    def cascade(self):
        """Run following controls in cascade."""
        source_label = f'{self.name}[{self._chain_moment}]'
        for case in self.cascade_config:
            control_name = case['control_name']
            control_status = case['control_status']
            control_parameters = case['control_parameters']
            target_label = f'{control_name}[{self._chain_moment}]'
            if control_status:
                control = self.__class__(name=control_name,
                                         **self._cascade_dates(),
                                         **control_parameters)
                control.scheduled = self.scheduled
                control.observer = self.observer
                control.trigger = 'CASCADE'
                logger.info(f'Initiating control {target_label}] '
                            f'from control {source_label}...')
                control.run()
                logger.info(f'Control {target_label} performed')

    def prerequisite(self):
        """Get the result of the prerequisite statement."""
        return self._prerequisite()

    def prepare(self):
        """Execute control preparation SQL scripts."""
        self._prepare()

    def resume(self):
        """Resume initiated control run."""
        self._resume()

    def wait(self):
        """Wait untill control finishes."""
        return self._wait()

    def cancel(self):
        """Cancel control run."""
        if self.working or self.initiated or self.waiting:
            self._deinitiate()

    def delete(self):
        """Delete control results."""
        self._delete()

    def revoke(self):
        """Revoke control results."""
        self._revoke()

    def clean(self):
        """Clean control results."""
        self._clean()

    def _initiate(self):
        logger.info(f'{self} Initiating control...')
        try:
            self.status = 'I'
            logger.debug(f'{self} Creating new record in {db.tables.log}')
            insert = db.tables.log.insert()
            insert = insert.values(control_id=self.id,
                                   added=dt.datetime.now(),
                                   status=self.status,
                                   date_from=self.date_from,
                                   date_to=self.date_to)
            result = db.execute(insert)
            self.process_id = int(result.inserted_primary_key[0])
        except Exception:
            logger.error()
            return self._escape()
        else:
            logger.debug(f'{self} New record in {db.tables.log} created')
            logger.info(f'{self} Control owns process ID {self.process_id}')
            logger.info(f'{self} Control initiated')
            if self.observer:
                try:
                    self.observer(self)
                except Exception:
                    logger.error()
            return self._continue()

    def _deinitiate(self):
        logger.info(f'{self} Deinitiating control...')
        try:
            self._set_as_void()
        except Exception:
            logger.error()
        else:
            logger.info(f'{self} Control deinitiated')

    def _prerequisite(self):
        statement = self.parser.parse_prerequisite_statement()
        if statement:
            logger.info(f'{self} Checking control prerequisite statement...')
            try:
                prerequisite_value = db.execute(statement, as_scalar=True)
                self._save_prerequisite_value(prerequisite_value)
                logger.info(f'{self} Control prerequisite statement '
                            f'returns {self.prerequisite_value}')
                if not self.prerequisite_value:
                    self._cancel()
                    return False
            except Exception:
                logger.error()
                return self._escape()
            else:
                return self._continue()
        return self._continue()

    def _prepare(self):
        if self.is_plsql_engine and not self.is_reconciliation:
            # Raised and caught so that _escape() records a real traceback,
            # the way every other failure in this class reports itself.
            try:
                raise ValueError('The PL-SQL engine implements reconciliation '
                                 f'only, not {self.type}')
            except ValueError:
                logger.error()
                return self._escape()
        statement = self.parser.parse_preparation_statement()
        if statement:
            logger.info(f'{self} Running control preparation SQL scripts...')
            try:
                result = db.execute(statement)
                rowcount = result.rowcount
                logger.info(f'{self} Control preparation SQL scripts '
                            f'successfully performed returning {rowcount}')
            except Exception:
                logger.error()
                return self._escape()
            else:
                return self._continue()
        return self._continue()

    def _throttle(self):
        logger.info(f'{self} Attempting to start from initiation queue...')
        backoff_time = 1
        max_wait_time = 15
        while True:
            try:
                with self.executor.lock():
                    if not self.blocked:
                        logger.info(f'{self} Initiation queue passed, '
                                    'waiting to start...')
                        self._set_as_waiting()
                        return self._continue()
            except TimeoutError:
                logger.error()
                return self._escape()
            tm.sleep(backoff_time)
            backoff_time = min(backoff_time*2, max_wait_time)

    def _resume(self):
        if self.initiated or self.waiting:
            if self._start():
                if self._prepare():
                    if self._prerequisite():
                        if self._prerun_hook():
                            if self._progress():
                                if self._finish():
                                    if self._complete():
                                        if self._done():
                                            self._email()
                                            self._postrun_hook()
                    else:
                        self._do_not_resume()
                else:
                    self._can_not_prepare()

    def _do_not_resume(self):
        if not self.prerequisite_value:
            logger.info(f'{self} Control will not be resumed '
                        'due to a prerequisite check')
            message = ('Control execution stopped because the '
                       'PREREQUISITE check not passed.')
            self._save_text_message(message)

    def _can_not_prepare(self):
        logger.info(f'{self} Control will not be resumed '
                    'due to a preparation failure')
        message = ('Control execution stopped because the PREPARATION failed.')
        self._save_text_message(message)

    def _spawn(self):
        logger.debug(f'{self} Spawning new process for the control...')
        context = mp.get_context('spawn')
        self.process = context.Process(name=self.name, target=self._operate)
        self.process.start()
        self.handler = th.Thread(name=f'{self}-Handler', target=self._handle)
        self.handler.start()
        logger.info(f'{self} Running as process on PID {self.process.pid}')

    def _operate(self):
        if self._throttle():
            self._resume()

    def _handle(self):
        process = self.process
        while process.is_alive():
            control = Control(process_id=self.process_id)
            if not control.status:
                logger.info(f'{self} Control cancelation request received')
                self.process = process
                self._terminate()
                self._cancel_as_request()
            elif control.timeout:
                logger.info(f'{self} Control cancelation with timeout ')
                self.process = process
                self._terminate()
                self._cancel_as_timeout()
            tm.sleep(5)
            self.__dict__.update(control.__dict__)

    def _wait(self):
        process = self.process
        pid = process.pid
        logger.debug(f'{self} Waiting for process at PID {pid}...')
        while process.is_alive():
            tm.sleep(1)
        result_code = process.exitcode
        logger.debug(f'{self} Process at PID {pid} returns {result_code}')

    def _terminate(self):
        process = self.process
        pid = process.pid
        logger.info(f'{self} Terminating process at PID {pid}...')
        process.terminate()
        logger.info(f'{self} Process at PID {pid} terminated')

    def _start(self):
        logger.info(f'{self} Starting control...')
        try:
            self._set_as_started()
            if self.debug_mode:
                self._save_debug_message()
        except Exception:
            logger.error()
            return self._escape()
        else:
            logger.info(f'{self} Control started at {self.start_date}')
            return self._continue()

    def _progress(self):
        try:
            self._set_as_running()
            self._fetch()
            self._execute()
            self._save()
        except Exception:
            logger.error()
            return self._escape()
        else:
            return self._continue()

    def _finish(self):
        logger.info(f'{self} Finishing control...')
        try:
            self._set_as_finished()
            if not self.debug_mode:
                self._delete_temporary_tables()
        except Exception:
            logger.error()
            return self._escape()
        else:
            logger.info(f'{self} Control finished')
            return self._continue()

    def _complete(self):
        statement = self.parser.parse_completion_statement()
        if statement:
            logger.info(f'{self} Running control completion SQL scripts...')
            try:
                result = db.execute(statement)
                rowcount = result.rowcount
                logger.info(f'{self} Control completion SQL scripts '
                            f'successfully performed returning {rowcount}')
            except Exception:
                logger.error()
                return self._escape()
            else:
                return self._continue()
        return self._continue()

    def _cancel(self):
        logger.info(f'{self} Canceling control...')
        try:
            self._set_as_canceled()
            self.executor.release_lock()
            self.executor.delete_temporary_tables()
            self.executor.delete_output_records()
        except Exception:
            logger.error()
        else:
            logger.info(f'{self} Control canceled')

    def _done(self):
        try:
            self._set_as_done()
        except Exception:
            logger.error()
            return self._escape()
        else:
            logger.info(f'{self} ended at {self.end_date}')
            return self._continue()

    def _error(self):
        try:
            self._set_as_error()
        except Exception:
            logger.error()
        else:
            logger.info(f'{self} ended with error at {self.end_date}')
            self._email()

    def _continue(self):
        return True

    def _escape(self):
        self._with_error = True
        self._all_errors.append(sys.exc_info())
        self._save_text_error(self.text_error)
        return self._error()

    def _fetch(self):
        logger.info(f'{self} Fetching records...')
        if self.is_analysis or self.is_report:
            logger.info(f'{self} Fetching {self.source_name}...')
            self.source_table = self.parser.parse_source_table()
            self.input_table = self.executor.fetch_records()
            self.fetched_number = self.executor.count_fetched()
            logger.info(f'{self} Records fetched: {self.fetched_number}')
            self._save_metrics(fetched_number=self.fetched_number)
        elif self.is_reconciliation and self.is_plsql_engine:
            # The procedure opens its own cursors against the datasources and
            # reports the counts itself: no CTAS, no index, no count here.
            # The tables are still reflected: the output table is built from
            # their columns, and a missing source must fail now, not later.
            self.source_table_a = self.parser.parse_source_table_a()
            self.source_table_b = self.parser.parse_source_table_b()
            logger.info(f'{self} Fetching is performed by the PL-SQL engine')
        elif self.is_reconciliation or self.is_comparison:
            self.source_table_a = self.parser.parse_source_table_a()
            self.source_table_b = self.parser.parse_source_table_b()
            threads = []
            current = th.current_thread()
            for s in ['a', 'b']:
                name = f'{current.name}(fetch_{s})'
                func = getattr(self, f'_fetch_{s}')
                thread = th.Thread(target=func, name=name, daemon=True)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
                if self._pending_error is not None:
                    raise self._pending_error
            self._save_metrics(fetched_number_a=self.fetched_number_a,
                               fetched_number_b=self.fetched_number_b)

    def _fetch_a(self):
        try:
            self.__fetch_a()
            if self.is_reconciliation:
                self.__index_a()
        except Exception as error:
            self._pending_error = error

    def __fetch_a(self):
        logger.info(f'{self} Fetching {self.source_name_a}...')
        self.input_table_a = self.executor.fetch_records_a()
        self.fetched_number_a = self.executor.count_fetched_a()
        logger.info(f'{self} Records fetched A: {self.fetched_number_a}')

    def _fetch_b(self):
        try:
            self.__fetch_b()
            if self.is_reconciliation:
                self.__index_b()
        except Exception as error:
            self._pending_error = error

    def __fetch_b(self):
        logger.info(f'{self} Fetching {self.source_name_b}...')
        self.input_table_b = self.executor.fetch_records_b()
        self.fetched_number_b = self.executor.count_fetched_b()
        logger.info(f'{self} Records fetched B: {self.fetched_number_b}')

    def __index_a(self):
        logger.info(f'{self} Indexing data from {self.source_name_a}...')
        self.executor.index_records_a()
        logger.info(f'{self} Data from {self.source_name_a} indexed')

    def __index_b(self):
        logger.info(f'{self} Indexing data from {self.source_name_b}...')
        self.executor.index_records_b()
        logger.info(f'{self} Data from {self.source_name_b} indexed')

    def _execute(self):
        logger.info(f'{self} Executing control...')
        if self.is_analysis:
            if (self.fetched_number or 0) > 0:
                self.error_table = self.executor.analyze()
                self.error_number = self.executor.count_errors()
                self.success_number = self.fetched_number-self.error_number
                self._save_metrics(success_number=self.success_number,
                                   error_number=self.error_number,
                                   error_level=self.error_level)
        elif self.is_reconciliation:
            if self.is_plsql_engine:
                self.executor.reconsolidate_external()
                self._save_metrics(fetched_number_a=self.fetched_number_a,
                                   fetched_number_b=self.fetched_number_b)
            if (
                (self.fetched_number_a or 0) > 0 or
                (self.fetched_number_b or 0) > 0
            ):
                if not self.is_plsql_engine:
                    self.executor.reconsolidate()
                error_tables = self.parser.parse_error_tables()
                stage_tables = self.parser.parse_stage_tables()
                self.error_table_a, self.error_table_b = error_tables
                self.stage_table_a, self.stage_table_b = stage_tables
                if self.need_a:
                    self.error_number_a = self.executor.count_errors_a()
                    if self.error_number_a is not None:
                        calc_number = self.fetched_number_a-self.error_number_a
                        self.success_number_a = calc_number
                if self.need_b:
                    self.error_number_b = self.executor.count_errors_b()
                    if self.error_number_b is not None:
                        calc_number = self.fetched_number_b-self.error_number_b
                        self.success_number_b = calc_number
                self._save_metrics(success_number_a=self.success_number_a,
                                   success_number_b=self.success_number_b,
                                   error_number_a=self.error_number_a,
                                   error_number_b=self.error_number_b,
                                   error_level_a=self.error_level_a,
                                   error_level_b=self.error_level_b)
        elif self.is_comparison:
            threads = []
            current = th.current_thread()
            for action in ('match', 'mismatch'):
                name = f'{current.name}({action})'
                func = getattr(self, f'_{action}')
                thread = th.Thread(target=func, name=name, daemon=True)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
                if self._pending_error is not None:
                    raise self._pending_error
            self._save_metrics(success_number=self.success_number,
                               error_number=self.error_number,
                               error_level=self.error_level)
        elif self.is_report:
            if (self.fetched_number or 0) > 0:
                self.error_table = self.executor.analyze()
        logger.info(f'{self} Control executed')

    def _match(self):
        try:
            self.__match()
        except Exception as error:
            self._pending_error = error

    def __match(self):
        self.stage_table = self.executor.match()
        self.success_number = self.executor.count_matched()

    def _mismatch(self):
        try:
            self.__mismatch()
        except Exception as error:
            self._pending_error = error

    def __mismatch(self):
        self.error_table = self.executor.mismatch()
        self.error_number = self.executor.count_mismatched()

    def _save(self):
        logger.info(f'{self} Saving results...')
        if self.is_analysis:
            self.executor.save_errors()
        elif self.is_reconciliation:
            if self.need_a:
                self.executor.save_reconciliation_output_a()
            if self.need_b:
                self.executor.save_reconciliation_output_b()
        elif self.is_comparison:
            self.executor.save_mismatches()
        elif self.is_report:
            self.executor.save_errors()
        logger.info(f'{self} Results saved')

    def _delete(self):
        logger.info(f'{self} Deleting results...')
        self.executor.delete_output_records()
        logger.info(f'{self} Results deleted')

    def _revoke(self):
        try:
            logger.info(f'{self} Revoking control...')
            self._set_as_revoked()
            self._delete()
        except Exception:
            logger.error()
        else:
            logger.info(f'{self} Control revoked')

    def _clean(self):
        logger.info(f'{self} Cleaning control results...')
        days_retention = self.config['days_retention']
        if days_retention == 0:
            for table in self.output_tables:
                repr = f'[{self.name}]'
                logger.info(f'{repr} Deleting all results in {table}...')
                db.truncate(table.name)
                logger.info(f'{repr} Results in {table} deleted')
        else:
            outdated_results = list(self.parser.parse_outdated_results())
            if outdated_results:
                for table, process_ids in outdated_results:
                    for process_id in process_ids:
                        repr = f'[{self.name}:{process_id}]'
                        logger.info(f'{repr} Deleting results in {table}...')
                        id = table.c.rapo_process_id
                        query = table.delete().where(id == process_id)
                        text = db.formatter.document(query)
                        logger.debug(f'{self} Deleting from {table} '
                                     f'with query:\n{text}')
                        db.execute(query)
                        logger.info(f'{repr} Results in {table} deleted')
                logger.info(f'{self} Control results cleaned')
            else:
                logger.info(f'{self} No control results to clean')

    def _prerun_hook(self):
        if self.need_hook and self.need_prerun_hook:
            hook_result, hook_code = self.executor.prerun_hook()
            if not hook_result:
                self._cancel()
                message = ('Control execution stopped because PRERUN HOOK '
                           f'function evaluated as NOT OK [{hook_code}].')
                self._save_text_message(message)
                return False
        return True

    def _email(self):
        try:
            mailer.send_run_email(self)
        except Exception:
            logger.error()

    def _postrun_hook(self):
        if self.need_hook and self.need_postrun_hook:
            self.executor.postrun_hook()

    def _update_process_log(self, **kwargs):
        logger.debug(f'{self} Updating {db.tables.log} with {kwargs}')
        update = db.tables.log.update()
        update = update.values(**kwargs, updated=dt.datetime.now())
        update = update.where(db.tables.log.c.process_id == self.process_id)
        db.execute(update)
        logger.debug(f'{self} {db.tables.log} updated')

    def _set_as_waiting(self):
        self.status = 'W'
        self._update_process_log(status=self.status)

    def _set_as_started(self):
        self.status = 'S'
        self.start_date = dt.datetime.now()
        self._update_process_log(status=self.status,
                                 start_date=self.start_date)

    def _set_as_running(self):
        self.status = 'P'
        self._update_process_log(status=self.status)

    def _set_as_finished(self):
        self.status = 'F'
        self._update_process_log(status=self.status)

    def _set_as_done(self):
        self.status = 'D'
        self.end_date = dt.datetime.now()
        self._update_process_log(status=self.status,
                                 end_date=self.end_date)

    def _set_as_error(self):
        self.status = 'E'
        self.end_date = dt.datetime.now()
        self._update_process_log(status=self.status,
                                 end_date=self.end_date)

    def _set_as_canceled(self):
        self.status = 'C'
        if not self.end_date:
            self.end_date = dt.datetime.now()
        self._update_process_log(status=self.status,
                                 end_date=self.end_date)

    def _set_as_revoked(self):
        self.status = 'X'
        self._update_process_log(status=self.status)

    def _set_as_void(self):
        self.status = None
        self._update_process_log(status=self.status)

    def _save_prerequisite_value(self, prerequisite_value):
        self.prerequisite_value = prerequisite_value
        self._update_process_log(prerequisite_value=prerequisite_value)

    def _save_text_message(self, text_message):
        new_record = f'{dt.datetime.now():%Y-%m-%d %H:%M:%S} - {text_message}'
        self._all_messages.append(new_record)
        # Appended in the database, because the supervising server and the
        # control process itself both write messages of the same run. A CASE
        # can not be used here, its branches would mix CHAR with CLOB.
        column = db.tables.log.c.text_message
        separator = sa.func.nvl2(column, sa.func.chr(10), sa.null(),
                                 type_=sa.Text)
        appended = column+separator+sa.literal(new_record, type_=sa.Text)
        self._update_process_log(text_message=appended)

    def _save_text_error(self, text_error):
        self._update_process_log(text_error=text_error)

    def _save_metrics(self, **kwargs):
        self._update_process_log(**kwargs)

    def _save_debug_message(self):
        self._save_text_message('Control execution in debug mode.')

    def _cancel_as_request(self):
        message = 'Control execution stopped because of the request.'
        self._save_text_message(message)
        self._cancel()

    def _cancel_as_timeout(self):
        message = 'Control execution stopped because of the timeout.'
        self._save_text_message(message)
        self._cancel()

    def _delete_temporary_tables(self):
        self.executor.delete_temporary_tables()


class Parser:
    """Represents control parser."""

    def __init__(self, owner):
        self.__owner = owner

    @property
    def control(self):
        """Get owning control instance."""
        return self.__owner

    @property
    def c(self):
        """Shortcut for control."""
        return self.__owner

    def parse_boolean(self, name):
        """Prepare a boolean value of the parameter by name.

        Parameters
        ----------
        name : str
            Name of the parameter from the configuration table.

        Returns
        -------
        value : bool
            Parameter value represented as boolean.
        """
        return True if self.control.config[name] == 'Y' else False

    def parse_date(self, value, hour=None, minute=None, second=None):
        """Get date from initial raw value."""
        return self._parse_date(value, hour=hour, minute=minute, second=second)

    def _parse_date(self, value, hour=None, minute=None, second=None):
        date = utils.to_date(value)
        if hour is not None or minute is not None or second is not None:
            kwargs = {'hour': hour, 'minute': minute, 'second': second}
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            date = date.replace(**kwargs)
        return date

    def parse_dates(self):
        """Parse control dates according to configuration."""
        return (self.parse_date_from(), self.parse_date_to())

    def _parse_period_count(self, value, default, minimum=0):
        """Get whole number of periods from a raw configuration value."""
        if value is None:
            return max(default, minimum)
        try:
            value = int(value)
        except (TypeError, ValueError):
            message = f'incorrect number of periods: {value}'
            raise ValueError(message)
        return max(value, minimum)

    def _parse_period_type(self, period_type):
        """Get period type, raising when it is not one of the known ones."""
        if period_type not in ('D', 'W', 'M'):
            message = f'incorrect period type: {period_type}'
            raise ValueError(message)
        return period_type

    def parse_timestamp(self):
        """Get the moment this control run would have been fired at.

        The window of a run is counted back from the moment it was fired at
        using the period configuration, so a run started for an explicit
        window is reconstructed by counting the same periods forward from
        its lower bound. The iterations of a manual run are then derived the
        way they are derived on a scheduled one.

        Returns
        -------
        timestamp : float
            POSIX timestamp the period configuration is counted back from.
        """
        if self.control.timestamp:
            return self.control.timestamp
        period_back = self._parse_period_count(self.control.period_back, 0)
        period_type = self._parse_period_type(self.control.period_type)
        target_date = self._parse_date(self.control.date_from, 0, 0, 0)
        if period_type == 'D':
            target_date = target_date+dt.timedelta(days=period_back)
        elif period_type == 'W':
            target_date = target_date+dt.timedelta(weeks=period_back)
        elif period_type == 'M':
            for _ in range(period_back):
                target_date = utils.get_month_date_to(target_date)
                target_date = target_date+dt.timedelta(days=1)
            target_date = self._parse_date(target_date, 0, 0, 0)
        return target_date.timestamp()

    def parse_date_from(self):
        """Get data source date lower bound.

        Returns
        -------
        date_from : datetime or None
            Fetched records from data source should begin from this date.
        """
        timestamp = self.control.timestamp
        period_back = self._parse_period_count(self.control.period_back, 0)
        period_type = self._parse_period_type(self.control.period_type)
        current_date = self._parse_date(timestamp, 0, 0, 0)
        if period_type == 'D':
            target_date = current_date-dt.timedelta(days=period_back)
        elif period_type == 'M':
            calculated_date = utils.get_month_date_from(current_date)
            for _ in range(period_back):
                calculated_date = calculated_date-dt.timedelta(days=1)
                calculated_date = utils.get_month_date_from(calculated_date)
            target_date = calculated_date
        elif period_type == 'W':
            target_date = current_date-dt.timedelta(weeks=period_back)
        return target_date

    def parse_date_to(self):
        """Get data source date upper bound.

        date_to : datetime or None
            Fetched records from data source should end with this date.
        """
        period_number = self._parse_period_count(self.control.period_number,
                                                 1, minimum=1)
        period_type = self._parse_period_type(self.control.period_type)
        current_date = self._parse_date(self.parse_date_from(), 23, 59, 59)
        if period_type == 'D':
            target_date = current_date+dt.timedelta(days=period_number-1)
        elif period_type == 'M':
            calculated_date = utils.get_month_date_to(current_date)
            for _ in range(period_number-1):
                calculated_date = calculated_date+dt.timedelta(days=1)
                calculated_date = utils.get_month_date_to(calculated_date)
            target_date = calculated_date
        elif period_type == 'W':
            calculated_date = current_date+dt.timedelta(weeks=period_number)
            target_date = calculated_date-dt.timedelta(days=1)
        return target_date

    def parse_source_name(self):
        """Get data source name."""
        return self._parse_source_name('source_name')

    def parse_source_name_a(self):
        """Get data source A name."""
        return self._parse_source_name('source_name_a')

    def parse_source_name_b(self):
        """Get data source B name."""
        return self._parse_source_name('source_name_b')

    def _parse_source_name(self, source_name):
        custom_name = self.control.config[source_name]
        if custom_name:
            custom_name = custom_name.format(**self.c.variables)
            final_name = utils.to_lower(custom_name)
            return final_name

    def parse_source_table(self):
        """Get data source table.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting data source table.
        """
        name = self.control.source_name
        table = self._parse_source_table(name)
        return table

    def parse_source_table_a(self):
        """Get data source A table.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting data source A table.
        """
        name = self.control.source_name_a
        table = self._parse_source_table(name)
        return table

    def parse_source_table_b(self):
        """Get data source B table.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting data source B table.
        """
        name = self.control.source_name_b
        table = self._parse_source_table(name)
        return table

    def _parse_source_table(self, name):
        logger.debug(f'{self.c} Parsing source table {name}...')
        if isinstance(name, str) is True or name is None:
            table = db.table(name) if isinstance(name, str) is True else None
            if table is None:
                message = f'Source table {name} is not defined'
                raise AttributeError(message)
            else:
                logger.debug(f'{self.c} Source table {name} parsed')
                return table
        else:
            type = name.__class__.__name__
            message = f'source name must be str or None not {type}'
            raise TypeError(message)

    def parse_select(self):
        """Get SQL statement to fetch data from data source.

        Returns
        -------
        select : sqlalchemy.Select
        """
        table = self.control.source_table
        literals = self.control.result_columns
        where = self.control.source_filter
        date_field = self.control.source_date_field
        select = self._parse_select(table, literals=literals, where=where,
                                    date_field=date_field)
        return select

    def parse_select_a(self):
        """Get SQL statement to fetch data from data source A.

        Returns
        -------
        select : sqlalchemy.Select
        """
        table = self.control.source_table_a
        where = self.control.source_filter_a
        date_field = self.control.source_date_field_a
        key_field = self.control.source_key_field_a
        shift_from_sec, shift_to_sec = self._parse_time_shift_delta()
        not_null_fields = self._parse_not_null_fields_a()
        select = self._parse_select(table, alias='a', where=where,
                                    not_null_fields=not_null_fields,
                                    date_field=date_field,
                                    key_field=key_field,
                                    shift_from_sec=shift_from_sec,
                                    shift_to_sec=shift_to_sec)
        return select

    def parse_select_b(self):
        """Get SQL statement to fetch data from data source B.

        Returns
        -------
        select : sqlalchemy.Select
        """
        table = self.control.source_table_b
        where = self.control.source_filter_b
        date_field = self.control.source_date_field_b
        key_field = self.control.source_key_field_b
        shift_from_sec, shift_to_sec = self._parse_time_shift_delta()
        not_null_fields = self._parse_not_null_fields_b()
        select = self._parse_select(table, alias='b', where=where,
                                    not_null_fields=not_null_fields,
                                    date_field=date_field,
                                    key_field=key_field,
                                    shift_from_sec=shift_from_sec,
                                    shift_to_sec=shift_to_sec)
        return select

    def _parse_select(self, table, alias='s', literals=None, where=None,
                      not_null_fields=None, date_field=None,
                      key_field=None, shift_from_sec=0, shift_to_sec=0):
        logger.debug(f'{self.c} Parsing {table} select...')
        columns = db.normalize(table.columns, date_fields=[date_field])

        if key_field:
            if db.is_table(table) and not db.is_column(key_field, table):
                key_column = db.get_rowid(key_field)
                columns.append(key_column)
        source, columns = db.remap(table, columns, alias)
        literals = literals if isinstance(literals, list) else []

        if date_field and isinstance(date_field, str):
            date_column = source.columns[date_field]
            if db.is_timestamp(table, date_column):
                date_column = sa.cast(date_column, sa.DATE).label(date_field)
                columns = [
                    date_column if col.name == date_field else col
                    for col in columns
                ]

        select = sa.select(*columns, *literals)
        if where and isinstance(where, str):
            custom_where = utils.concat('(', where, ')')
            select = select.where(sa.text(custom_where))
        if not_null_fields and isinstance(not_null_fields, list):
            for not_null_field in not_null_fields:
                if not_null_field in table.columns:
                    not_null_column = source.columns[not_null_field]
                else:
                    not_null_column = sa.literal_column(not_null_field)
                select = select.where(not_null_column.is_not(None))

        if date_field and isinstance(date_field, str):
            date_from = self.control.date_from
            date_to = self.control.date_to
            if shift_from_sec or shift_to_sec:
                if shift_from_sec:
                    date_from = date_from+dt.timedelta(seconds=shift_from_sec)
                if shift_to_sec:
                    date_to = date_to+dt.timedelta(seconds=shift_to_sec)

            datefmt = '%Y-%m-%d %H:%M:%S'
            date_from = date_from.strftime(datefmt)
            date_to = date_to.strftime(datefmt)

            datefmt = 'YYYY-MM-DD HH24:MI:SS'
            date_from = sa.func.to_date(date_from, datefmt)
            date_to = sa.func.to_date(date_to, datefmt)

            select = select.where(date_column.between(date_from, date_to))

        logger.debug(f'{self.c} {table} select parsed')
        return select

    def parse_filter(self):
        """Get SQL-like expression used to filter the data source.
        """
        return self._parse_filter('source_filter')

    def parse_filter_a(self):
        """Get SQL-like expression used to filter the data source A.
        """
        return self._parse_filter('source_filter_a')

    def parse_filter_b(self):
        """Get SQL-like expression used to filter the data source B.
        """
        return self._parse_filter('source_filter_b')

    def _parse_filter(self, filter_name):
        # {variables} are rendered from the raw config on every call, so a
        # rendered text is never rendered again; other braces stay as they are.
        custom_filter = self.control.config[filter_name]
        if custom_filter:
            return utils.render(custom_filter, self.c.variables)
        return custom_filter

    def _parse_time_shift_delta(self):
        shift_from_sec, shift_to_sec = 0, 0
        if self.control.is_reconciliation:
            shift_from_sec = self.control.rule_config['time_shift_from']
            shift_to_sec = self.control.rule_config['time_shift_to']
        return shift_from_sec, shift_to_sec

    def _parse_not_null_fields_a(self):
        not_full_fields = []
        if self.control.is_reconciliation:
            for case in self.control.rule_config['correlation_config']:
                field_a = case['field_a']
                allow_null = case['allow_null']
                if not allow_null:
                    not_full_fields.append(field_a)
        return not_full_fields

    def _parse_not_null_fields_b(self):
        not_full_fields = []
        if self.control.is_reconciliation:
            for case in self.control.rule_config['correlation_config']:
                field_b = case['field_b']
                allow_null = case['allow_null']
                if not allow_null:
                    not_full_fields.append(field_b)
        return not_full_fields

    def parse_stage_tables(self):
        """Get control run stage tables."""
        if self.control.is_reconciliation:
            table_name_a = f'rapo_temp_stage_a_{self.control.process_id}'
            table_name_b = f'rapo_temp_stage_b_{self.control.process_id}'
            return self._parse_tables(table_name_a, table_name_b)

    def parse_error_tables(self):
        """Get control run error tables."""
        if self.control.is_reconciliation:
            table_name_a = f'rapo_temp_error_a_{self.control.process_id}'
            table_name_b = f'rapo_temp_error_b_{self.control.process_id}'
            return self._parse_tables(table_name_a, table_name_b)

    def _parse_tables(self, *table_names):
        tables = []
        for table_name in table_names:
            table = self._parse_table(table_name)
            tables.append(table)
        return tables

    def _parse_table(self, table_name):
        if db.exists(table_name):
            return db.table(table_name)

    def parse_output_names(self):
        """Get list with necessary output table names.

        Returns
        -------
        names : list
            List necessary output names.
        """
        names = []
        if self.control.type in ['ANL', 'CMP', 'REP']:
            name = f'rapo_rest_{self.control.name}'.lower()
            names.append(name)
        if self.control.type == 'REC':
            for s in ['a', 'b']:
                name = f'rapo_res{s}_{self.control.name}'.lower()
                names.append(name)
        return names

    def parse_written_output_names(self):
        """Get the result tables a run writes.

        A reconciliation saves side A only with need_a and side B only with
        need_b (Control._save), so only those tables are created and kept in
        line with the configuration.
        """
        if self.control.type in ['ANL', 'CMP', 'REP']:
            return [f'rapo_rest_{self.control.name}'.lower()]
        names = []
        if self.control.type == 'REC':
            if self.control.need_a:
                names.append(f'rapo_resa_{self.control.name}'.lower())
            if self.control.need_b:
                names.append(f'rapo_resb_{self.control.name}'.lower())
        return names

    def parse_output_tables(self):
        """Get list with existing output tables.

        Returns
        -------
        tables : list
            List of sqlalchemy.Table objects.
        """
        tables = []
        for name in self.control.output_names:
            if db.exists(name):
                table = db.table(name)
                tables.append(table)
        return tables

    def parse_temporary_names(self):
        """Get list with necessary temporary table names.

        Returns
        -------
        names : list
            List necessary temporary names.
        """
        names = []
        src = f'rapo_temp_source_{self.control.process_id}'
        src_a = f'rapo_temp_source_a_{self.control.process_id}'
        src_b = f'rapo_temp_source_b_{self.control.process_id}'
        stg_a = f'rapo_temp_stage_a_{self.control.process_id}'
        stg_b = f'rapo_temp_stage_b_{self.control.process_id}'
        err = f'rapo_temp_error_{self.control.process_id}'
        err_a = f'rapo_temp_error_a_{self.control.process_id}'
        err_b = f'rapo_temp_error_b_{self.control.process_id}'
        if self.control.is_analysis:
            names.extend([src, err])
        elif self.control.is_reconciliation:
            mod = f'rapo_temp_t01_mod_{self.control.process_id}'
            org_a = f'rapo_temp_t02_org_a_{self.control.process_id}'
            org_b = f'rapo_temp_t02_org_b_{self.control.process_id}'
            dup_a = f'rapo_temp_t03_dup_a_{self.control.process_id}'
            dup_b = f'rapo_temp_t03_dup_b_{self.control.process_id}'
            dup = f'rapo_temp_t04_dup_{self.control.process_id}'
            mac = f'rapo_temp_t05_mac_{self.control.process_id}'
            vrd_a = f'rapo_temp_verdict_a_{self.control.process_id}'
            vrd_b = f'rapo_temp_verdict_b_{self.control.process_id}'
            srcs = [src_a, src_b]
            orgs = [org_a, org_b]
            dups = [dup, dup_a, dup_b]
            stgs = [stg_a, stg_b]
            errs = [err_a, err_b]
            vrds = [vrd_a, vrd_b]
            # The PL-SQL engine creates only some of these; the deletion step
            # checks each one exists, so listing them all is safe.
            names.extend([*srcs, mod, *orgs, *dups, mac, *vrds, *errs, *stgs])
        elif self.control.is_comparison:
            md = f'rapo_temp_md_{self.control.process_id}'
            nmd = f'rapo_temp_nmd_{self.control.process_id}'
            names.extend([src_a, src_b, md, nmd])
        elif self.control.is_report:
            names.append(src)
        return names

    def parse_temporary_tables(self):
        """Get list with existing temporary tables.

        Returns
        -------
        tables : list
            List of sqlalchemy.Table objects.
        """
        tables = []
        for name in self.control.temporary_names:
            if db.exists(name):
                table = db.table(name)
                tables.append(table)
        return tables

    def parse_prerequisite_statement(self):
        """Prepare prerequisite statement taken from the configuration table.

        Returns
        -------
        final_statement : str or None
            Formatted SQL query representing prerequisite statement.
        """
        return self._parse_statement('prerequisite_sql')

    def parse_preparation_statement(self):
        """Get preparation statement taken from the configuration table.

        Returns
        -------
        final_statement : str or None
            Formatted SQL query that must be performed before the control.
        """
        return self._parse_statement('preparation_sql')

    def parse_completion_statement(self):
        """Get completion statement taken from the configuration table.

        Returns
        -------
        final_statement : str or None
            Formatted SQL query that must be performed after the control.
        """
        return self._parse_statement('completion_sql')

    def _parse_statement(self, statement_name):
        custom_statement = self.control.config[statement_name]
        if custom_statement:
            custom_statement = custom_statement.format(**self.c.variables)
            final_statement = db.formatter(custom_statement)
            return final_statement

    def parse_case_config(self):
        """Get case mapping taken from the configuration table.

        Returns
        -------
        config : dict or None
            Dictionary with case mapping.
        """
        logger.debug(f'{self.c} Parsing case configuration...')
        string = self.control.config['case_config']
        if string:
            case_list = [NORMAL, INFO, ERROR, WARNING, INCIDENT, DISCREPANCY,
                         SUCCESS, LOSS, DUPLICATE]
            custom_config = json.loads(string)
            final_config = {}
            for custom_record in custom_config:
                i = custom_record['case_id']
                case_id = custom_record['case_id']
                case_value = custom_record['case_value']
                case_type = custom_record.get('case_type')
                case_description = custom_record.get('case_description')
                final_record = {
                    'case_id': case_id,
                    'case_value': case_value,
                    'case_type': case_type if case_type in case_list else None,
                    'case_description': case_description
                }
                final_config[i] = final_record
            logger.debug(f'{self.c} Case configuration parsed')
            return final_config
        else:
            logger.debug(f'{self.c} Case configuration not found')

    def parse_case_definition(self):
        """Get main case statement taken from the configuration table.

        Returns
        -------
        config : str or None
            SQL-like logical expression with a case mapping.
        """
        logger.debug(f'{self.c} Parsing case definition...')
        string = self.control.config['case_definition']
        if string:
            custom_config = self.control.config['case_definition']
            final_config = db.formatter(custom_config)
            logger.debug(f'{self.c} Case definition parsed')
            return final_config
        else:
            logger.debug(f'{self.c} Case definition not found')

    def parse_analyze_error_definition(self):
        """Get analyze error definition.

        Returns
        -------
        config : list or None
            List with dictionaries where presented all keys for discrapancies.
        """
        logger.debug(f'{self.c} Parsing error definition...')
        string = self.control.config['error_definition']
        if utils.is_json(string):
            config = self._parse_json_filter(string)
            logger.debug(f'{self.c} Error definition parsed')
            return config
        else:
            logger.debug(f'{self.c} Error definition not found')

    def parse_analyze_error_sql(self):
        """Prepare analyze error SQL expression.

        Returns
        -------
        expression : str or None
            String with SQL expression to select discrapancies.
        """
        logger.debug(f'{self.c} Parsing error SQL...')
        string = self.control.config['error_definition']
        if utils.is_json(string):
            table = self.control.input_table
            expressions = []
            config = self.parse_analyze_error_definition()
            for i in config:
                expression = []
                connexion = i['connexion']
                if len(expressions) > 0:
                    expression.append(connexion)
                column = str(table.c[i['column']])
                expression.append(column)
                relation = i['relation']
                expression.append(relation)
                value = i['value']
                is_column = i['is_column']
                if is_column:
                    value = str(table.c[value])
                elif isinstance(value, str):
                    value = utils.render(value, self.c.variables)
                expression.append(value)
                expression = ' '.join(expression)
                expressions.append(expression)
            expression = '\n'.join(expressions)
            logger.debug(f'{self.c} Error SQL parsed using configuration')
            return expression
        elif utils.is_sql(string):
            expression = self._parse_sql_filter(string)
            logger.debug(f'{self.c} Error SQL parsed')
            return expression
        elif not string and self.control.has_cases:
            table = self.control.input_table
            result_type = table.c.rapo_result_type
            target_types = [INFO, ERROR, WARNING, INCIDENT, DISCREPANCY]
            clause = sa.or_(result_type.in_(target_types),
                            result_type.is_(None))
            statement = db.compile(clause)
            expression = statement.string
            return expression
        else:
            logger.debug(f'{self.c} Error SQL not found')
            return ''

    def parse_reconciliation_rule_config(self):
        """Get reconciliation rule configuration.

        Returns
        -------
        config : dict
            Dictionary with reconciliation parameters.
        """
        logger.debug(f'{self.c} Parsing rule configuration...')

        string = self.control.config['rule_config']
        input_config = json.loads(string or '{}')
        output_config = {}
        need_recons_a = input_config.get('need_recons_a', False)
        need_recons_b = input_config.get('need_recons_b', False)
        need_issues_a = input_config.get('need_issues_a', False)
        need_issues_b = input_config.get('need_issues_b', False)
        allow_duplicates = input_config.get('allow_duplicates', False)
        time_shift_from = input_config.get('time_shift_from', 0)
        time_shift_to = input_config.get('time_shift_to', 0)
        time_tolerance_from = input_config.get('time_tolerance_from', 0)
        time_tolerance_to = input_config.get('time_tolerance_to', 0)
        output_limit_a = input_config.get('output_limit_a')
        output_limit_b = input_config.get('output_limit_b')
        correlation_limit = input_config.get('correlation_limit', False)
        # PL engine only: the per-row fan-out cap. Left unset here so the
        # procedure applies its own default, the way the other PL-side knobs
        # fall back; without it the WARNING the procedure logs would tell the
        # user to raise a setting that never reaches it.
        max_candidates = input_config.get('max_candidates')

        fuzzy_optimization = input_config.get('fuzzy_optimization')
        fuzzy_optimization = utils.coalesce(
            fuzzy_optimization,
            get_algorithm_setting('fuzzy_optimization'),
            True)

        normalization_type = input_config.get('normalization_type')
        normalization_type = utils.coalesce(
            normalization_type,
            get_algorithm_setting('normalization_type'),
            'default')

        discrepancy_matching = input_config.get('discrepancy_matching')
        discrepancy_matching = utils.coalesce(
            discrepancy_matching,
            get_algorithm_setting('discrepancy_matching'),
            False)

        correlation_config = []
        for item_config in input_config.get('correlation_config', {}):
            field_a = item_config['field_a']
            field_b = item_config['field_b']
            allow_null = item_config.get('allow_null', False)
            formula_mode = item_config.get('formula_mode', False)
            if not formula_mode:
                field_a, field_b = field_a.lower(), field_b.lower()
            add_config = {
                'field_a': field_a,
                'field_b': field_b,
                'allow_null': allow_null,
                'formula_mode': formula_mode
            }
            correlation_config.append(add_config)

        discrepancy_config = []
        for item_config in input_config.get('discrepancy_config', {}):
            field_a = item_config['field_a']
            field_b = item_config['field_b']
            numeric_tolerance_from = item_config.get('numeric_tolerance_from')
            numeric_tolerance_to = item_config.get('numeric_tolerance_to')
            percentage_mode = item_config.get('percentage_mode', False)
            formula_mode = item_config.get('formula_mode', False)
            formula_alias = item_config.get('formula_alias')
            if not formula_mode:
                field_a, field_b = field_a.lower(), field_b.lower()
            add_config = {
                'field_a': field_a,
                'field_b': field_b,
                'numeric_tolerance_from': numeric_tolerance_from or 0,
                'numeric_tolerance_to': numeric_tolerance_to or 0,
                'percentage_mode': percentage_mode,
                'formula_mode': formula_mode,
                'formula_alias': formula_alias
            }
            discrepancy_config.append(add_config)

        output_config = {
            'need_recons_a': need_recons_a,
            'need_recons_b': need_recons_b,
            'need_issues_a': need_issues_a,
            'need_issues_b': need_issues_b,
            'allow_duplicates': allow_duplicates,
            'fuzzy_optimization': fuzzy_optimization,
            'normalization_type': normalization_type,
            'discrepancy_matching': discrepancy_matching,
            'time_shift_from': time_shift_from,
            'time_shift_to': time_shift_to,
            'time_tolerance_from': time_tolerance_from,
            'time_tolerance_to': time_tolerance_to,
            'output_limit_a': output_limit_a,
            'output_limit_b': output_limit_b,
            'correlation_limit': correlation_limit,
            'max_candidates': max_candidates,
            'correlation_config': correlation_config,
            'discrepancy_config': discrepancy_config
        }

        logger.debug(f'{self.c} Rule configuration parsed')
        return output_config

    def parse_procedure_payload(self):
        """Build the JSON payload of the Oracle-side PL-SQL engine.

        The payload is the procedure's only input and its whole truth: it never
        reads rapo_config. Every [ALGORITHM] fallback is resolved here
        by parse_reconciliation_rule_config, so the procedure applies no
        defaults of its own.

        Returns
        -------
        payload : dict
            Dictionary serialized to JSON for rapo_usage_rule.
        """
        control = self.control
        date_format = '%Y-%m-%d %H:%M:%S'
        return {
            'process_id': control.process_id,
            'control_name': control.name,
            'date_from': control.date_from.strftime(date_format),
            'date_to': control.date_to.strftime(date_format),
            'debug_mode': bool(control.debug_mode),
            'parallelism': control.parallelism or 0,
            'need_a': bool(control.need_a),
            'need_b': bool(control.need_b),
            'source_a': {
                'name': control.source_name_a,
                'filter': control.source_filter_a,
                'date_field': control.source_date_field_a,
                'key_field': control.source_key_field_a
            },
            'source_b': {
                'name': control.source_name_b,
                'filter': control.source_filter_b,
                'date_field': control.source_date_field_b,
                'key_field': control.source_key_field_b
            },
            'rule_config': control.rule_config
        }

    def parse_comparison_rule_config(self):
        """Get comparison rule configuration.

        Returns
        -------
        config : list
            List with dictionaries where presented all keys for rule.
        """
        logger.debug(f'{self.c} Parsing rule configuration...')
        raw = self.control.config['rule_config']
        config = []
        for item in json.loads(raw or '[]'):
            column_a = item['column_a'].lower()
            column_b = item['column_b'].lower()

            new = {'column_a': column_a, 'column_b': column_b}
            config.append(new)
        logger.debug(f'{self.c} Rule configuration parsed')
        return config

    def parse_comparison_error_definition(self):
        """Get comparison error definition.

        Returns
        -------
        config : list
            List with dictionaries where presented all keys for mismatching.
        """
        logger.debug(f'{self.c} Parsing error definition...')
        raw = self.control.config['error_definition']
        config = []
        for item in json.loads(raw or '[]'):
            column_a = item['column_a'].lower()
            column_b = item['column_b'].lower()

            new = {'column_a': column_a, 'column_b': column_b}
            config.append(new)
        logger.debug(f'{self.c} Error definition parsed')
        return config

    def _parse_json_filter(self, string):
        config = []
        for item in json.loads(string or '[]'):
            connexion = item.get('connexion', 'and').upper()
            column = item.get('column', '').lower()
            column_a = item.get('column_a', '').lower()
            column_b = item.get('column_b', '').lower()
            relation = item.get('relation', '<>').upper()
            value = item.get('value')
            is_column = item.get('is_column', False)

            config.append(
                {'connexion': connexion,
                 'column': column or None,
                 'column_a': column_a or None,
                 'column_b': column_b or None,
                 'relation': relation,
                 'value': value.lower() if is_column is True else value,
                 'is_column': is_column})
        return config

    def _parse_sql_filter(self, string):
        return utils.render(string, self.c.variables)

    def parse_output_columns(self):
        """Get control output columns.

        Returns
        -------
        columns : list or None
            List with dictionaries where output columns configuration is
            presented.
            Will be None if parameter is not filled in configuration table.
        """
        config = self.control.config['output_table']
        columns = self._parse_output_columns(config)
        return columns

    def parse_output_columns_a(self):
        """Get control output columns A.

        Returns
        -------
        columns : list or None
            List with dictionaries where output A columns configuration is
            presented.
            Will be None if parameter is not filled in configuration table.
        """
        config = self.control.config['output_table_a']
        columns = self._parse_output_columns(config)
        return columns

    def parse_output_columns_b(self):
        """Get control output columns B.

        Returns
        -------
        columns : list or None
            List with dictionaries where output B columns configuration is
            presented.
            Will be None if parameter is not filled in configuration table.
        """
        config = self.control.config['output_table_b']
        columns = self._parse_output_columns(config)
        return columns

    def _parse_output_columns(self, config):
        logger.debug(f'{self.c} Parsing output columns...')
        config = json.loads(config) if isinstance(config, str) else None
        if not config:
            logger.debug(f'{self.c} Output was not configured')
            return []
        else:
            column = dict.fromkeys(['column', 'column_a', 'column_b'])
            columns = []
            for value in config.get('columns', []):
                new = column.copy()
                if isinstance(value, str):
                    new['column'] = value.lower()
                if isinstance(value, dict):
                    for key in new.keys():
                        raw = value.get(key)
                        if isinstance(raw, str):
                            new[key] = raw.lower()
                columns.append(new)
            if columns:
                logger.debug(f'{self.c} Output columns parsed')
                return columns
            else:
                logger.debug(f'{self.c} Output columns was not configured')
                return columns

    def parse_mandatory_columns(self):
        """Get control mandatory columns."""
        logger.debug(f'{self.c} Parsing mandatory columns...')
        columns = []
        if self.control.is_analysis:
            columns = [RESULT_KEY, RESULT_VALUE, RESULT_TYPE]
        elif self.control.is_reconciliation:
            columns = [RESULT_TYPE, DISCREPANCY_ID, DISCREPANCY_DESCRIPTION]
        logger.debug(f'{self.c} Mandatory columns parsed')
        return columns

    def parse_result_columns(self):
        """Get result columns based on result statement and case configuration.

        Returns
        -------
        columns : List of sqlalchemy columns or None
            Object representing result column.
        """
        logger.debug(f'{self.c} Parsing result columns...')
        custom_statement = self.control.config['case_definition']
        if self.control.is_analysis and custom_statement:
            columns = []
            case_config = self.parse_case_config()

            replaces = []
            pattern = r'THEN\s+\d+|ELSE\s+\d+'
            matches = re.findall(pattern, custom_statement, re.IGNORECASE)
            for match in matches:
                keyword, result = re.split(r'\s+', match)
                case_id = int(result)
                case_value = case_config[case_id]['case_value']
                case_type = case_config[case_id]['case_type']

                replace = [match, {}]
                replace[1]['key'] = f'{keyword} {case_id}'
                replace[1]['value'] = f'{keyword} \'{case_value}\''
                replace[1]['type'] = f'{keyword} \'{case_type}\''
                replaces.append(replace)

            columns = []
            for field in ['key', 'value', 'type']:
                field_name = f'rapo_result_{field}'
                final_statement = custom_statement
                for replace in replaces:
                    old = replace[0]+r'\s'
                    new = replace[1][field]+r'\n'
                    final_statement = re.sub(old, new, final_statement)
                final_statement = db.formatter(final_statement)
                column = sa.literal_column(final_statement).label(field_name)
                columns.append(column)
            logger.debug(f'{self.c} Result columns parsed')
            return columns
        elif self.control.is_analysis and not custom_statement:
            columns = []
            fields = [RESULT_KEY, RESULT_VALUE, RESULT_TYPE]
            for field in fields:
                column = field.null
                columns.append(column)
            logger.debug(f'{self.c} Result columns not configured')
            return columns
        else:
            logger.debug(f'{self.c} Result columns not parsed')

    def parse_key_column(self):
        """Get process identification and description column.

        Returns
        -------
        column : sqlalchemy column
            Object representing process identification column.
        """
        column = sa.literal(self.control.process_id).label('rapo_process_id')
        return column

    def parse_iteration_config(self):
        """Get appropriate period parameters for this control iteration."""
        input_string = self.control.config['iteration_config'] or '[]'
        input_config = json.loads(input_string)
        output_config = []
        for item_config in input_config:
            iteration_id = item_config['iteration_id']
            iteration_description = item_config.get('iteration_description')
            period_back = item_config['period_back']
            period_number = item_config['period_number']
            period_type = item_config['period_type']
            status = True if item_config['status'] == 'Y' else False

            add_config = {
                'iteration_id': iteration_id,
                'iteration_description': iteration_description,
                'period_back': period_back,
                'period_number': period_number,
                'period_type': period_type,
                'status': status
            }
            output_config.append(add_config)
        return output_config

    def parse_cascade_config(self):
        config = db.tables.config
        select = config.select().order_by(config.c.control_id)
        answerset = db.execute(select, as_records=True)
        output_config = []
        for record in answerset:
            try:
                control_id = record.control_id
                control_name = record.control_name
                control_status = True if record.status == 'Y' else False
                control_parameters = {
                    'debug_mode': self.control.debug_mode
                }
                if record.schedule_config:
                    schedule_config = json.loads(record.schedule_config)
                    trigger_id = schedule_config.get('trigger_id')
                    if trigger_id and trigger_id == self.control.id:
                        add_config = {
                            'control_id': control_id,
                            'control_name': control_name,
                            'control_status': control_status,
                            'control_parameters': control_parameters
                        }
                        output_config.append(add_config)
            except Exception:
                logger.warning()
                continue
        return output_config

    def parse_parallelism_hint(self):
        """Get SQL expression with parallelism hint.

        Returns
        -------
        expression : string
            String with SQL expression with parallelism hint.
        """
        degree_of_parallelism = self.control.parallelism
        if degree_of_parallelism:
            expression = f'/*+ parallel({degree_of_parallelism}) */'
        else:
            expression = ''
        return expression

    def parse_variables(self):
        """Get control variables.

        Returns
        -------
        variables : dict
            Dictionary with control variables.
        """
        control = self.control
        variables = dict(control_name=control.name,
                         control_date=control.date,
                         control_date_from=control.date_from,
                         control_date_to=control.date_to,
                         process_id=control.process_id)
        return variables

    def parse_outdated_results(self):
        """Create list with tables and IDs of outdated control results."""
        log = db.tables.log
        control_id = self.control.id
        days_retention = self.control.config['days_retention']
        today = dt.date.today().strftime(r'%Y-%m-%d')
        current_date = sa.func.to_date(today, 'YYYY-MM-DD')
        target_date = current_date-days_retention
        for table in self.parse_output_tables():
            select = sa.select(log.c.process_id)
            subq = sa.select(table.c.rapo_process_id)
            query = (select.where(log.c.control_id == control_id)
                           .where(log.c.added < target_date)
                           .where(log.c.process_id.in_(subq))
                           .order_by(log.c.process_id))
            text = db.formatter.document(query)
            logger.debug(f'{self.c} Searching outdated results in {table} '
                         f'with query:\n{text}')
            answerset = db.execute(query, as_table=True)
            pids = [record['process_id'] for record in answerset]
            logger.debug(f'{self.c} Outdated results in {table}: {pids}')
            if pids:
                yield (table, pids)


class Executor:
    """Represents control executor."""

    def __init__(self, bind):
        self.__bind = bind

    @property
    def control(self):
        """Get binded control instance."""
        return self.__bind

    @property
    def c(self):
        """Get binded control instance. Same as control property."""
        return self.__bind

    def fetch_records(self):
        """Fetch data source.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting table with fetched data in case if DB is chosen
            engine.
        """
        select = self.control.select
        if self.control.engine == 'DB':
            table_name = f'rapo_temp_source_{self.control.process_id}'
            table = self._fetch_records_to_table(select, table_name)
            return table

    def fetch_records_a(self):
        """Fetch data source A.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting table with fetched data in case if DB is chosen
            engine.
        """
        select = self.control.select_a
        if self.control.engine == 'DB':
            table_name = f'rapo_temp_source_a_{self.control.process_id}'
            table = self._fetch_records_to_table(select, table_name)
            return table

    def fetch_records_b(self):
        """Fetch data source B.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting table with fetched data in case if DB is chosen
            engine.
        """
        select = self.control.select_b
        if self.control.engine == 'DB':
            table_name = f'rapo_temp_source_b_{self.control.process_id}'
            table = self._fetch_records_to_table(select, table_name)
            return table

    def index_records_a(self):
        """Create indexes for data from source A."""
        if self.control.engine == 'DB':
            table_name = f'rapo_temp_source_a_{self.control.process_id}'
            key_field_name = self.control.source_key_field_a
            self._index_table(table_name, key_field_name)

    def index_records_b(self):
        """Create indexes for data from source B."""
        if self.control.engine == 'DB':
            table_name = f'rapo_temp_source_b_{self.control.process_id}'
            key_field_name = self.control.source_key_field_b
            self._index_table(table_name, key_field_name)

    def analyze(self):
        """Run data analysis control.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting table with found discrepancies in case if DB is
            chosen engine.
        """
        logger.debug(f'{self.c} Analyzing...')
        input_table = self.control.input_table
        output_columns = self.control.output_columns
        mandatory_columns = self.control.mandatory_columns
        if output_columns is None or len(output_columns) == 0:
            select = input_table.select()
        else:
            columns = []
            for output_column in output_columns:
                name = output_column['column']
                column = input_table.c[name]
                columns.append(column)
            for mandatory_column in mandatory_columns:
                name = mandatory_column.column_name
                column = input_table.c[name]
                columns.append(column)
            select = sa.select(*columns)

        table_name = f'rapo_temp_error_{self.control.process_id}'
        clause = sa.text(self.control.error_sql or '')
        select = select.where(clause)
        select = db.compile(select)
        ctas = sa.text(f'CREATE TABLE {table_name} AS\n{select}')
        text = db.formatter.document(ctas)
        logger.info(f'{self.c} Creating {table_name} with query:\n{text}')
        db.execute(ctas)
        logger.debug(f'{self.c} {table_name} created')

        table = db.table(table_name)
        logger.debug(f'{self.c} Analyzing done')
        return table

    def _drain_engine_log(self):
        """Copy the PL-SQL engine's log lines into this run's log file.

        The procedure cannot write to the log file: it may not even run on the
        host that keeps it. It appends to rapo_engine_log instead, and this
        drains those rows, deleting what it has taken so the table stays a
        transport buffer rather than a second log.

        Returns
        -------
        stop : callable
            Stops the thread and performs one last drain.
        """
        process_id = self.control.process_id
        levels = {'DEBUG': logger.debug, 'WARNING': logger.warning,
                  'ERROR': logger.error, 'INFO': logger.info}
        finished = th.Event()
        state = {'last': 0}
        # reflected once: db.table() autoloads, and this runs every two seconds
        table = db.table('rapo_engine_log')

        def drain_once():
            select = (sa.select(table.c.record_number, table.c.log_level,
                                table.c.message)
                        .where(table.c.process_id == process_id)
                        .where(table.c.record_number > state['last'])
                        .order_by(table.c.record_number))
            records = db.execute(select, as_records=True)
            for record in records:
                write = levels.get(record.log_level, logger.info)
                message = record.message
                if not isinstance(message, str):
                    message = message.read() if message is not None else ''
                write(f'{self.c} [engine] {message}')
                state['last'] = record.record_number
            if records:
                delete = (table.delete()
                               .where(table.c.process_id == process_id)
                               .where(table.c.record_number <= state['last']))
                db.execute(delete)
                # The procedure publishes its running counts but leaves
                # rapo_log.updated alone, because that column is stamped with
                # the application clock. Writing them back from here moves it
                # on, which is also what tells the live-event watcher that a
                # long run is still alive.
                counts = reader.read_run_counts(process_id)
                self.control._save_metrics(
                    fetched_number_a=counts['fetched_number_a'],
                    fetched_number_b=counts['fetched_number_b'])

        def loop():
            while not finished.wait(2):
                try:
                    drain_once()
                except Exception:
                    logger.warning()

        name = f'{th.current_thread().name}(engine-log)'
        thread = th.Thread(target=loop, name=name, daemon=True)
        thread.start()

        def stop():
            finished.set()
            thread.join(timeout=10)
            try:
                drain_once()
            except Exception:
                logger.warning()

        return stop

    def reconsolidate_external(self):
        """Run data reconciliation through the Oracle-side PL-SQL engine.

        Hands the whole s01-s09 pipeline to RAPO_USAGE_RULE, which fetches from
        the datasources itself and leaves rapo_temp_error_* and
        rapo_temp_stage_* behind for the ordinary save path. The counts
        it wrote to rapo_log are read back: the procedure has no OUT args.
        """
        payload = self.control.parser.parse_procedure_payload()
        document = json.dumps(payload)
        logger.info(f'{self.c} Running PL-SQL engine with payload:\n'
                    f'{json.dumps(payload, indent=2)}')
        statement = sa.text('begin rapo_usage_rule(:payload); end;')
        statement = statement.bindparams(
            sa.bindparam('payload', value=document, type_=sa.CLOB))
        # The procedure logs into rapo_engine_log as it goes. Draining it in a
        # thread puts those lines into this run's log file while the run is
        # still going, and the final drain runs even when the call raises, so
        # the failure keeps the context that led to it.
        drain = self._drain_engine_log()
        try:
            db.execute(statement)
        finally:
            drain()
        counts = reader.read_run_counts(self.control.process_id)
        self.control.fetched_number_a = counts['fetched_number_a']
        self.control.fetched_number_b = counts['fetched_number_b']
        logger.info(f'{self.c} PL-SQL engine fetched '
                    f'{self.control.fetched_number_a}/'
                    f'{self.control.fetched_number_b} records')

    def reconsolidate(self):
        """Run data reconciliation control.

        Returns
        -------
        tables : list of sqlalchemy.Table
            List of objects reflecting tables with found issues.
        """

        SQL_DIRECTORY = 'algorithms/reconciliation'

        def execute(*scripts):
            if scripts and len(scripts) == 1:
                db.execute(scripts[0], output=logger.info, tag=self.c.label)
            elif scripts:
                db.parallelize(*scripts, output=logger.info, tag=self.c.label)

        def read_script(script_name):
            return utils.read_sql(f'{SQL_DIRECTORY}/{script_name}')

        def read_expression(script_name):
            return utils.read_sql(f'{SQL_DIRECTORY}/exps/{script_name}')

        def prepare_paralell(name, script):
            statements = script if is_sequence(script) else [script]
            return {'name': name, 'statements': statements}

        def prepare_save(name, need_base, need_issues, need_recons,
                         save_error_script, save_stage_script):
            save_scripts = []
            if need_base:
                if need_issues in [True, False]:
                    save_scripts.append(save_error_script)
                if need_recons:
                    save_scripts.append(save_stage_script)
            return prepare_paralell(name, save_scripts)

        def is_sequence(obj):
            return isinstance(obj, (list, tuple, set, frozenset))

        correlate = read_script('s01_correlate')
        organize_a = read_script('s02_organize_a')
        organize_b = read_script('s02_organize_b')
        prepare_duplicates_a = read_script('s03_prepare_duplicates_a')
        prepare_duplicates_b = read_script('s03_prepare_duplicates_b')
        process_duplicates = read_script('s04_process_duplicates')
        match_duplicates_a = read_script('s05_match_duplicates_a')
        match_duplicates_b = read_script('s05_match_duplicates_b')
        match_duplicates = read_script('s05_match_duplicates')
        prepare_conflicts = read_script('s06_prepare_conflicts')
        match_conflicts = read_script('s07_match_conflicts')
        save_error_a = read_script('s08_save_error_a')
        save_error_b = read_script('s08_save_error_b')
        save_stage_a = read_script('s09_save_stage_a')
        save_stage_b = read_script('s09_save_stage_b')

        discrepancy_rule_form = read_expression('discrepancy_rule')
        discrepancy_formula_form = read_expression('discrepancy_formula')
        discrepancy_field_form = read_expression('discrepancy_field')
        discrepancy_percentage_form = read_expression('discrepancy_percentage')
        discrepancy_description_form = read_expression('discrepancy_desc')
        discrepancy_filter_form = read_expression('discrepancy_filter')

        distance_formula_none = read_expression('distance_formula_none')
        distance_formula_minmax = read_expression('distance_formula_minmax')
        distance_formula_rank = read_expression('distance_formula_rank')
        distance_formula_z_norm = read_expression('distance_formula_z_norm')
        distance_formula_srd = read_expression('distance_formula_srd')

        parallelism = self.control.parser.parse_parallelism_hint()
        rule_config = self.control.rule_config

        key_field_a = f'a.{self.control.source_key_field_a}'
        date_field_a = f'a.{self.control.source_date_field_a}'

        key_field_b = f'b.{self.control.source_key_field_b}'
        date_field_b = f'b.{self.control.source_date_field_b}'

        date_from = self.control.date_from
        date_to = self.control.date_to
        time_shift_from = rule_config['time_shift_from']
        time_shift_to = rule_config['time_shift_to']
        time_tolerance_from = rule_config['time_tolerance_from']
        time_tolerance_to = rule_config['time_tolerance_to']

        need_issues_a = rule_config['need_issues_a']
        need_issues_b = rule_config['need_issues_b']
        need_recons_a = rule_config['need_recons_a']
        need_recons_b = rule_config['need_recons_b']
        allow_duplicates = rule_config['allow_duplicates']
        fuzzy_optimization = rule_config['fuzzy_optimization']
        normalization_type = rule_config['normalization_type']
        discrepancy_matching = rule_config['discrepancy_matching']
        correlation_limit = rule_config.get('correlation_limit')

        key_fields_a = []
        key_fields_b = []
        key_combinations = []
        for case in rule_config['correlation_config']:
            field_a = case['field_a']
            field_b = case['field_b']
            formula_mode = case['formula_mode']

            if not formula_mode:
                expression_a, expression_b = f'a.{field_a}', f'b.{field_b}'
            else:
                expression_a, expression_b = field_a, field_b
            key_combination = [expression_a, expression_b]
            key_fields_a.append(expression_a)
            key_fields_b.append(expression_b)
            key_combinations.append(key_combination)

        key_rules = []
        hash_fields = []
        for field_a, field_b in key_combinations:
            key_rule = f'{field_a} = {field_b}'
            key_rules.append(key_rule)
            hash_field = f'coalesce({field_a}, {field_b})'
            hash_fields.append(hash_field)

        if time_shift_from == time_shift_to == 0:
            date_rule = [date_field_a, '=', date_field_b]
        else:
            range_from = f'{date_field_b}+({time_shift_from}/86400)'
            range_to = f'{date_field_b}+({time_shift_to}/86400)'
            date_rule = [date_field_a, 'between', range_from, 'and', range_to]
        date_field_name_a = date_field_a[2:].upper()
        date_field_name_b = date_field_b[2:].upper()

        discrepancy_fields_a = []
        discrepancy_fields_b = []
        discrepancy_combinations = []
        for case in rule_config['discrepancy_config']:
            field_a = case['field_a']
            field_b = case['field_b']
            tolerance_from = case['numeric_tolerance_from']
            tolerance_to = case['numeric_tolerance_to']
            percentage_mode = case['percentage_mode']
            formula_mode = case['formula_mode']
            formula_alias = case['formula_alias']

            if not formula_mode:
                expression_a, expression_b = f'a.{field_a}', f'b.{field_b}'
            else:
                expression_a, expression_b = field_a, field_b
            discrepancy_combination = [expression_a, expression_b,
                                       tolerance_from, tolerance_to,
                                       percentage_mode,
                                       formula_mode,
                                       formula_alias]
            discrepancy_fields_a.append(expression_a)
            discrepancy_fields_b.append(expression_b)
            discrepancy_combinations.append(discrepancy_combination)

        discrepancy_rules = []
        discrepancy_formulas = []
        discrepancy_fields = []
        discrepancy_sums = []
        discrepancy_descriptions_a = []
        discrepancy_descriptions_b = []
        discrepancy_filters_a = []
        discrepancy_filters_b = []
        discrepancy_number = 0
        for field_a, field_b, *params in discrepancy_combinations:
            discrepancy_number += 1
            tolerance_from, tolerance_to = params[0], params[1]
            percentage_mode = params[2]
            formula_mode = params[3]
            formula_alias = params[4]

            percentage_formula = discrepancy_percentage_form.format(
                field_a=field_a,
                field_b=field_b
            ) if percentage_mode else ''

            if formula_mode:
                if formula_alias:
                    field_desc_a = field_desc_b = formula_alias
                else:
                    field_desc_a, field_desc_b = field_a, field_b
            else:
                field_desc_a = field_a[2:].upper()
                field_desc_b = field_b[2:].upper()
            discrepancy_rule = discrepancy_rule_form.format(
                field_a=field_a,
                field_b=field_b,
                field_desc_a=field_desc_a,
                field_desc_b=field_desc_b,
                tolerance_from=tolerance_from,
                tolerance_to=tolerance_to,
                percentage_formula=percentage_formula,
                discrepancy_number=discrepancy_number
            )
            discrepancy_rules.append(discrepancy_rule)

            discrepancy_formula = discrepancy_formula_form.format(
                discrepancy_number=discrepancy_number
            )
            discrepancy_formulas.append(discrepancy_formula)

            discrepancy_field = discrepancy_field_form.format(
                discrepancy_number=discrepancy_number
            )
            discrepancy_fields.append(discrepancy_field)

            discrepancy_sum = f'abs(discrepancy_{discrepancy_number}_value)'
            discrepancy_sums.append(discrepancy_sum)

            discrepancy_description_a = discrepancy_description_form.format(
                discrepancy_number=discrepancy_number, datasource='a')
            discrepancy_descriptions_a.append(discrepancy_description_a)
            discrepancy_filter_a = discrepancy_filter_form.format(
                discrepancy_number=discrepancy_number, datasource='a')
            discrepancy_filters_a.append(discrepancy_filter_a)

            discrepancy_description_b = discrepancy_description_form.format(
                discrepancy_number=discrepancy_number, datasource='b')
            discrepancy_descriptions_b.append(discrepancy_description_b)
            discrepancy_filter_b = discrepancy_filter_form.format(
                discrepancy_number=discrepancy_number, datasource='b')
            discrepancy_filters_b.append(discrepancy_filter_b)

        keys_a = ', '.join(key_fields_a)
        keys_b = ', '.join(key_fields_b)
        key_rules = ' and '.join(key_rules)
        date_rule = ' '.join(date_rule)
        hash_value = '||\'|\'||'.join(hash_fields)

        discrepancy_rules = ''.join(discrepancy_rules)
        discrepancy_formulas = ''.join(discrepancy_formulas)
        discrepancy_fields = ''.join(discrepancy_fields)
        discrepancy_order_a = '+'.join(discrepancy_sums) or 'b_id'
        discrepancy_order_b = '+'.join(discrepancy_sums) or 'a_id'
        discrepancy_descriptions_a = ''.join(discrepancy_descriptions_a)
        discrepancy_descriptions_b = ''.join(discrepancy_descriptions_b)
        discrepancy_filters_a = ''.join(discrepancy_filters_a)
        discrepancy_filters_b = ''.join(discrepancy_filters_b)

        distance_formulas_a = []
        distance_formulas_b = []
        distance_type_names = [
            'time', *[str(i) for i in range(1, discrepancy_number+1)]
        ]
        if normalization_type in ['default', 'none', None]:
            distance_formula_form = distance_formula_none
        elif normalization_type == 'minmax':
            distance_formula_form = distance_formula_minmax
        elif normalization_type == 'rank':
            distance_formula_form = distance_formula_rank
        elif normalization_type == 'z_norm':
            distance_formula_form = distance_formula_z_norm
        elif normalization_type == 'srd':
            distance_formula_form = distance_formula_srd
        for distance_type_name in distance_type_names:
            distance_formula_a = distance_formula_form.format(
                field_name=f'discrepancy_{distance_type_name}_value',
                key_field='a_id',
                tolerance_from=(
                    time_tolerance_from if distance_type_name == 'time'
                    else discrepancy_combinations[int(distance_type_name)-1][2]
                ),
                tolerance_to=(
                    time_tolerance_to if distance_type_name == 'time'
                    else discrepancy_combinations[int(distance_type_name)-1][3]
                )
            )
            distance_formula_b = distance_formula_form.format(
                field_name=f'discrepancy_{distance_type_name}_value',
                key_field='b_id',
                tolerance_from=(
                    time_tolerance_from if distance_type_name == 'time'
                    else discrepancy_combinations[int(distance_type_name)-1][2]
                ),
                tolerance_to=(
                    time_tolerance_to if distance_type_name == 'time'
                    else discrepancy_combinations[int(distance_type_name)-1][3]
                )
            )

            distance_formulas_a.append(distance_formula_a)
            distance_formulas_b.append(distance_formula_b)
        distance_formulas_a = '+'.join(distance_formulas_a)
        distance_formulas_b = '+'.join(distance_formulas_b)

        numerics_a = []
        for discrepancy_field_a in discrepancy_fields_a:
            numeric_a = f'abs({discrepancy_field_a})'
            numerics_a.append(numeric_a)
        numerics_b = []
        for discrepancy_field_b in discrepancy_fields_b:
            numeric_b = f'abs({discrepancy_field_b})'
            numerics_b.append(numeric_b)

        epoch_date = 'to_date(\'1970-01-01\', \'YYYY-MM-DD\')'
        numeric_date_a = f'86400*({date_field_a}-{epoch_date})'
        numeric_date_b = f'86400*({date_field_b}-{epoch_date})'
        numeric_formula_a = (
            numeric_date_a
            + ('+' if numerics_a else '')
            + ('+'.join(numerics_a))
        )
        numeric_formula_b = (
            numeric_date_b
            + ('+' if numerics_b else '')
            + ('+'.join(numerics_b))
        )

        if fuzzy_optimization:
            conflict_types = '(\'A\', \'B\', \'M\')'
        else:
            conflict_types = '(\'F\', \'A\', \'B\', \'M\')'

        discrepancy_matching
        if discrepancy_matching:
            discrepancy_matching_exp = '1 = 1'
        else:
            discrepancy_matching_exp = '1 = 0'

        target_error_types_a = ['Loss', 'Discrepancy']
        if not allow_duplicates:
            target_error_types_a.append('Duplicate')

        target_error_types_b = ['Loss', 'Discrepancy']
        if not allow_duplicates:
            target_error_types_b.append('Duplicate')

        target_error_types_a = [f'\'{et}\'' for et in target_error_types_a]
        target_error_types_a = ', '.join(target_error_types_a)

        target_error_types_b = [f'\'{et}\'' for et in target_error_types_b]
        target_error_types_b = ', '.join(target_error_types_b)

        fetch_limit, fetch_limit_expression = 0, ''
        if correlation_limit:
            if isinstance(correlation_limit, bool) and correlation_limit:
                multiplier = 2.5
                fetch_number = max(self.control.fetched_number_a,
                                   self.control.fetched_number_b)
                fetch_limit = int(fetch_number*multiplier)
            elif isinstance(correlation_limit, int) and correlation_limit > 0:
                fetch_limit = correlation_limit
        if fetch_limit:
            fetch_limit_expression = f'where rownum <= {fetch_limit}'

        correlate = correlate.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_a=key_field_a,
            key_field_b=key_field_b,
            key_rules=key_rules,
            hash_value=hash_value,
            date_rule=date_rule,
            date_field_a=date_field_a,
            date_field_b=date_field_b,
            date_field_name_a=date_field_name_a,
            date_field_name_b=date_field_name_b,
            time_shift_from=time_shift_from,
            time_shift_to=time_shift_to,
            time_tolerance_from=time_tolerance_from,
            time_tolerance_to=time_tolerance_to,
            discrepancy_rules=discrepancy_rules,
            discrepancy_fields=discrepancy_fields,
            discrepancy_formulas=discrepancy_formulas,
            discrepancy_order_a=discrepancy_order_a,
            discrepancy_order_b=discrepancy_order_b,
            distance_formulas_a=distance_formulas_a,
            distance_formulas_b=distance_formulas_b,
            fetch_limit_expression=fetch_limit_expression
        )
        organize_a = organize_a.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_a=key_field_a,
            numeric_formula_a=numeric_formula_a
        )
        organize_b = organize_b.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_b=key_field_b,
            numeric_formula_b=numeric_formula_b
        )
        prepare_duplicates_a = prepare_duplicates_a.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            keys_a=keys_a,
            key_field_a=key_field_a,
            date_field_a=date_field_a
        )
        prepare_duplicates_b = prepare_duplicates_b.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            keys_b=keys_b,
            key_field_b=key_field_b,
            date_field_b=date_field_b
        )
        process_duplicates = process_duplicates.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_a=key_field_a,
            key_field_b=key_field_b,
            key_rules=key_rules,
            date_field_a=date_field_a,
            date_field_b=date_field_b,
            time_shift_from=time_shift_from,
            time_shift_to=time_shift_to
        )
        match_duplicates_a = match_duplicates_a.format(
            process_id=self.control.process_id,
            parallelism=parallelism
        )
        match_duplicates_b = match_duplicates_b.format(
            process_id=self.control.process_id,
            parallelism=parallelism
        )
        match_duplicates = match_duplicates.format(
            process_id=self.control.process_id,
            parallelism=parallelism
        )
        prepare_conflicts = prepare_conflicts.format(
            process_id=self.control.process_id,
            conflict_types=conflict_types,
            parallelism=parallelism
        )
        match_conflicts = match_conflicts.format(
            process_id=self.control.process_id,
            parallelism=parallelism
        )
        save_error_a = save_error_a.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_a=key_field_a,
            date_field_a=date_field_a,
            date_from=date_from,
            date_to=date_to,
            discrepancy_descriptions_a=discrepancy_descriptions_a,
            discrepancy_filters_a=discrepancy_filters_a,
            target_error_types_a=target_error_types_a,
            discrepancy_matching_exp=discrepancy_matching_exp
        )
        save_error_b = save_error_b.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_b=key_field_b,
            date_field_b=date_field_b,
            date_from=date_from,
            date_to=date_to,
            discrepancy_descriptions_b=discrepancy_descriptions_b,
            discrepancy_filters_b=discrepancy_filters_b,
            target_error_types_b=target_error_types_b,
            discrepancy_matching_exp=discrepancy_matching_exp
        )
        save_stage_a = save_stage_a.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_a=key_field_a,
            key_field_name_a=key_field_a[2:],
            date_field_a=date_field_a,
            date_from=date_from,
            date_to=date_to
        )
        save_stage_b = save_stage_b.format(
            process_id=self.control.process_id,
            parallelism=parallelism,
            key_field_b=key_field_b,
            key_field_name_b=key_field_b[2:],
            date_field_b=date_field_b,
            date_from=date_from,
            date_to=date_to
        )

        execute(correlate)

        organize_a = prepare_paralell('organize_a', organize_a)
        organize_b = prepare_paralell('organize_b', organize_b)
        execute(organize_a, organize_b)

        if fuzzy_optimization:
            prepare_duplicates_a = prepare_paralell(
                'prepare_duplicates_a', prepare_duplicates_a)
            prepare_duplicates_b = prepare_paralell(
                'prepare_duplicates_b', prepare_duplicates_b)
            execute(prepare_duplicates_a, prepare_duplicates_b)
            execute(process_duplicates)

            match_duplicates_a = prepare_paralell(
                'match_duplicates_a', match_duplicates_a)
            match_duplicates_b = prepare_paralell(
                'match_duplicates_b', match_duplicates_b)
            match_duplicates = prepare_paralell(
                'match_duplicates', match_duplicates)
            execute(match_duplicates_a, match_duplicates_b, match_duplicates)

        execute(prepare_conflicts)
        execute(match_conflicts)

        save_a = prepare_save(
            'save_a', self.control.need_a, need_issues_a, need_recons_a,
            save_error_a, save_stage_a
        )
        save_b = prepare_save(
            'save_b', self.control.need_b, need_issues_b, need_recons_b,
            save_error_b, save_stage_b
        )
        execute(save_a, save_b)

    def match(self):
        """Run data matching for comparison control.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting table with matched data in case if DB is chosen
            engine.
        """
        logger.debug(f'{self.c} Defining matches...')

        table_a = self.control.input_table_a
        table_b = self.control.input_table_b

        columns = []
        output_columns = self.control.output_columns
        if output_columns is None or len(output_columns) == 0:
            # Named the way _prepare_output_columns names the result columns.
            columns.extend(column.label(f'a_{column.name}')
                           for column in table_a.columns)
            columns.extend(column.label(f'b_{column.name}')
                           for column in table_b.columns)
        else:
            for output_column in output_columns:
                name = output_column['column']

                column_a = output_column['column_a']
                column_a = table_a.c[column_a] if column_a else None

                column_b = output_column['column_b']
                column_b = table_b.c[column_b] if column_b else None

                if column_a is not None and column_b is not None:
                    column = sa.func.coalesce(column_a, column_b)
                elif column_a is not None:
                    column = column_a
                elif column_b is not None:
                    column = column_b

                column = column.label(name) if name else column
                columns.append(column)

        keys = []
        for rule in self.control.rule_config:
            column_a = table_a.c[rule['column_a']]
            column_b = table_b.c[rule['column_b']]
            keys.append(column_a == column_b)
        join = table_a.join(table_b, *keys)
        select = sa.select(*columns).select_from(join)

        keys = []
        for error in self.control.error_definition:
            column_a = table_a.c[error['column_a']]
            column_b = table_b.c[error['column_b']]
            select = select.where(column_a == column_b)

        table_name = f'rapo_temp_md_{self.control.process_id}'
        select = db.compile(select)
        ctas = sa.text(f'CREATE TABLE {table_name} AS\n{select}')
        text = db.formatter.document(ctas)
        logger.info(f'{self.c} Creating {table_name} with query:\n{text}')
        db.execute(ctas)
        logger.debug(f'{self.c} {table_name} created')

        table = db.table(table_name)
        logger.debug(f'{self.c} Matches defined')
        return table

    def mismatch(self):
        """Run data mismatching for comparison control.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting table with mismatched data in case if DB is
            chosen engine.
        """
        logger.debug(f'{self.c} Defining mismatches...')

        table_a = self.control.input_table_a
        table_b = self.control.input_table_b

        columns = []
        output_columns = self.control.output_columns
        if output_columns is None or len(output_columns) == 0:
            # Named the way _prepare_output_columns names the result columns.
            columns.extend(column.label(f'a_{column.name}')
                           for column in table_a.columns)
            columns.extend(column.label(f'b_{column.name}')
                           for column in table_b.columns)
        else:
            for output_column in output_columns:
                name = output_column['column']

                column_a = output_column['column_a']
                column_a = table_a.c[column_a] if column_a else None

                column_b = output_column['column_b']
                column_b = table_b.c[column_b] if column_b else None

                if column_a is not None and column_b is not None:
                    column = sa.func.coalesce(column_a, column_b)
                elif column_a is not None:
                    column = column_a
                elif column_b is not None:
                    column = column_b

                column = column.label(name) if name else column
                columns.append(column)

        keys = None
        for rule in self.control.rule_config:
            column_a = table_a.c[rule['column_a']]
            column_b = table_b.c[rule['column_b']]
            if keys is None:
                keys = (column_a == column_b)
            else:
                keys &= (column_a == column_b)
        join = table_a.join(table_b, keys)
        select = sa.select(*columns).select_from(join)

        for error in self.control.error_definition:
            column_a = table_a.c[error['column_a']]
            column_b = table_b.c[error['column_b']]
            select = select.where(column_a != column_b)

        table_name = f'rapo_temp_nmd_{self.control.process_id}'
        select = db.compile(select)
        ctas = sa.text(f'CREATE TABLE {table_name} AS\n{select}')
        text = db.formatter.document(ctas)
        logger.info(f'{self.c} Creating {table_name} with query:\n{text}')
        db.execute(ctas)
        logger.debug(f'{self.c} {table_name} created')

        table = db.table(table_name)
        logger.debug(f'{self.c} Mismatches defined')
        return table

    def count_fetched(self):
        """Count fetched records in data source."""
        if self.control.engine == 'DB':
            table = self.control.input_table
            fetched = self._count_fetched_to_table(table)
        return fetched

    def count_fetched_a(self):
        """Count fetched records in data source A."""
        if self.control.engine == 'DB':
            table = self.control.input_table_a
            fetched_a = self._count_fetched_to_table(table)
        return fetched_a

    def count_fetched_b(self):
        """Count fetched records in data source B."""
        if self.control.engine == 'DB':
            table = self.control.input_table_b
            fetched_b = self._count_fetched_to_table(table)
        return fetched_b

    def count_errors(self):
        """Count found errors in control.

        Returns
        -------
        errors : int
            Number of found errors in control.
        """
        if self.control.error_table is not None:
            return self._count_errors(self.control.error_table)

    def count_errors_a(self):
        """Count found errors in control for side A.

        Returns
        -------
        error_number : list of int
            Number of found errors in control from side A.
        """
        if self.control.need_a:
            if self.control.error_table_a is not None:
                rule_config = self.control.rule_config
                need_issues_a = rule_config['need_issues_a']
                need_recons_a = rule_config['need_recons_a']
                if need_issues_a or need_recons_a:
                    return self._count_errors(self.control.error_table_a)

    def count_errors_b(self):
        """Count found errors in control for side B.

        Returns
        -------
        error_number : list of int
            Number of found errors in control from side B.
        """
        if self.control.need_b:
            if self.control.error_table_b is not None:
                rule_config = self.control.rule_config
                need_issues_b = rule_config['need_issues_b']
                need_recons_b = rule_config['need_recons_b']
                if need_issues_b or need_recons_b:
                    return self._count_errors(self.control.error_table_b)

    def _count_errors(self, table):
        logger.debug(f'{self.c} Counting errors from {table.name}...')
        error_number = None
        if self.control.is_database_engine:
            count = sa.select(sa.func.count()).select_from(table)
            error_number = db.execute(count, as_scalar=True)
        logger.debug(f'{self.c} Errors from {table.name} counted')
        return error_number

    def count_results_a(self):
        """Count found results in control for side A."""
        if self.control.need_a and self.control.stage_table_a:
            return self._count_results(self.control.stage_table_a)

    def count_results_b(self):
        """Count found results in control for side B."""
        if self.control.need_b and self.control.stage_table_b:
            return self._count_results(self.control.stage_table_b)

    def _count_results(self, table):
        logger.debug(f'{self.c} Counting results from {table.name}...')
        result_number = None
        if self.control.is_database_engine:
            count = sa.select(sa.func.count()).select_from(table)
            result_number = db.execute(count, as_scalar=True)
        logger.debug(f'{self.c} Results from {table.name} counted')
        return result_number

    def count_matched(self):
        """Count records that were matched.

        Returns
        -------
        matched : int
            Number of found discrepancies.
        """
        logger.debug(f'{self.c} Counting matched...')
        if self.control.is_database_engine:
            table = self.control.stage_table
            count = sa.select(sa.func.count()).select_from(table)
            matched = db.execute(count, as_scalar=True)
        logger.debug(f'{self.c} Matched counted')
        return matched

    def count_mismatched(self):
        """Count records that were not matched.

        Returns
        -------
        mismatched : int
            Number of found discrepancies.
        """
        logger.debug(f'{self.c} Counting mismatched')
        if self.control.is_database_engine:
            table = self.control.error_table
            count = sa.select(sa.func.count()).select_from(table)
            mismatched = db.execute(count, as_scalar=True)
        logger.debug(f'{self.c} Mismatched counted')
        return mismatched

    def save_results(self):
        """Save defined results as output records."""
        logger.debug(f'{self.c} Start saving...')
        input_table = self.control.stage_table
        output_table = self.prepare_output_table()
        if input_table is not None:
            output_columns, select = self._select_output(input_table,
                                                         output_table)
            select = self._limit_output(select)
            insert = output_table.insert().from_select(output_columns, select)
            db.execute(insert)
            logger.debug(f'{self.c} Saving done')

    def save_errors(self):
        """Save defined errors as output records."""
        logger.debug(f'{self.c} Start saving...')
        input_table = self.control.error_table
        output_table = self.prepare_output_table()
        if input_table is not None:
            output_columns, select = self._select_output(input_table,
                                                         output_table)
            select = self._limit_output(select)
            insert = output_table.insert().from_select(output_columns, select)
            db.execute(insert)
            logger.debug(f'{self.c} Saving done')

    def _select_output(self, input_table, output_table):
        """Match the result table columns with the input table by name.

        The result table may have columns the run does not fill (added by an
        older configuration) or in another order (added by a schema update).
        """
        output_columns = []
        input_columns = []
        for output_column in output_table.columns:
            if output_column.name == 'rapo_process_id':
                continue
            if output_column.name in input_table.columns:
                output_columns.append(output_column)
                input_columns.append(input_table.c[output_column.name])
        output_columns.append(output_table.c.rapo_process_id)
        select = sa.select(*input_columns, self.control.key_column)
        return output_columns, select

    def _limit_output(self, select):
        """Apply output_limit to the select of an ANL/REP/CMP result save.

        NULL or 0 means no limit. The run's counts stay the full ones.
        """
        output_limit = self.control.config['output_limit']
        if not output_limit or int(output_limit) <= 0:
            return select
        output_limit = int(output_limit)
        error_number = self.control.error_number
        if error_number is not None and error_number > output_limit:
            logger.info(f'{self.c} Output limited to {output_limit} '
                        f'of {error_number} records')
        return select.limit(output_limit)

    def save_matches(self):
        """Save found matches as RAPO results."""
        return self.save_results()

    def save_mismatches(self):
        """Save found mismatches as RAPO results."""
        return self.save_errors()

    def save_reconciliation_output_a(self):
        """Save reconciliation results from side A as output records."""
        logger.debug(f'{self.c} Start saving reconciliation output A...')
        rule_config = self.control.rule_config
        need_issues_a = rule_config['need_issues_a']
        need_recons_a = rule_config['need_recons_a']
        output_table = self.prepare_output_table_a()
        output_columns = output_table.columns
        output_limit = self.control.config['output_limit']
        if not output_limit:
            output_limit = rule_config['output_limit_a']
        process_id = self.control.key_column
        input_tables = []
        if need_issues_a:
            if self.control.error_table_a is not None:
                input_tables.append(self.control.error_table_a)
        if need_recons_a:
            if self.control.stage_table_a is not None:
                input_tables.append(self.control.stage_table_a)
        for input_table in input_tables:
            input_columns = []
            for output_column in output_columns:
                if output_column.name in input_table.columns:
                    input_column = input_table.c[output_column.name]
                    input_columns.append(input_column)
            select = sa.select(*input_columns, process_id)
            if isinstance(output_limit, int) and output_limit >= 0:
                select = select.limit(output_limit)
            insert = output_table.insert().from_select(output_columns, select)
            db.execute(insert)
        logger.debug(f'{self.c} Reconciliation output A saved')

    def save_reconciliation_output_b(self):
        """Save reconciliation results from side B as output records."""
        logger.debug(f'{self.c} Start saving reconciliation output B...')
        rule_config = self.control.rule_config
        need_issues_b = rule_config['need_issues_b']
        need_recons_b = rule_config['need_recons_b']
        output_table = self.prepare_output_table_b()
        output_columns = output_table.columns
        output_limit = self.control.config['output_limit']
        if not output_limit:
            output_limit = rule_config['output_limit_b']
        process_id = self.control.key_column
        input_tables = []
        if need_issues_b:
            if self.control.error_table_b is not None:
                input_tables.append(self.control.error_table_b)
        if need_recons_b:
            if self.control.stage_table_b is not None:
                input_tables.append(self.control.stage_table_b)
        for input_table in input_tables:
            input_columns = []
            for output_column in output_columns:
                if output_column.name in input_table.columns:
                    input_column = input_table.c[output_column.name]
                    input_columns.append(input_column)
            select = sa.select(*input_columns, process_id)
            if isinstance(output_limit, int) and output_limit >= 0:
                select = select.limit(output_limit)
            insert = output_table.insert().from_select(output_columns, select)
            db.execute(insert)
        logger.debug(f'{self.c} Reconciliation output B saved')

    def prepare_output_table(self):
        """Check result table and create it if initial control run.

        Returns
        -------
        table : sqlalchemy.Table
            Object reflecting result table.
        """
        return self._prepare_output_table(self.control.output_name)

    def prepare_output_table_a(self):
        """Prepare output table A."""
        return self._prepare_output_table(self.control.output_name_a)

    def prepare_output_table_b(self):
        """Prepare output table B."""
        return self._prepare_output_table(self.control.output_name_b)

    def _prepare_output_table(self, table_name):
        if self.control.with_deletion or self.control.with_drop:
            if self.control.with_deletion:
                self._clean_output_table(table_name)
            elif self.control.with_drop:
                self._delete_output_table(table_name)
        if not db.exists(table_name):
            self._create_output_table(table_name)
        else:
            self.sync_output_table(table_name, heal=True)
        table = db.table(table_name)
        return table

    def _create_output_table(self, table_name):
        logger.debug(f'{self.c} Table {table_name} will be created')
        select = self._select_output_columns(table_name)
        ctas = f'CREATE TABLE {table_name} AS\n{select}'
        index = (f'CREATE INDEX {table_name}_rapo_process_id_ix '
                 f'ON {table_name}(rapo_process_id) COMPRESS')
        compress = (f'ALTER TABLE {table_name} '
                    'MOVE ROW STORE COMPRESS ADVANCED')
        text = db.formatter.document(ctas, index, compress)
        logger.debug(f'{self.c} Creating table {table_name} '
                     f'with query:\n{text}')
        db.execute(ctas)
        db.execute(index)
        db.execute(compress)
        logger.debug(f'{self.c} {table_name} created')

    def _select_output_columns(self, table_name):
        """Compile the empty select a result table is created from."""
        columns = self._prepare_output_columns(table_name)
        if self.control.process_id is None:
            # Outside a run the process ID literal is a NULL, which has no
            # type, while a run's number makes it a NUMBER column.
            columns = [sa.literal(0).label(column.name)
                       if column.name == 'rapo_process_id' else column
                       for column in columns]
        select = sa.select(*columns)
        select = select.where(sa.literal(1) == sa.literal(0))
        return db.compile(select)

    def _reflect_sources(self):
        """Reflect the datasources outside a run, where _fetch did not."""
        if self.control.is_analysis or self.control.is_report:
            if self.control.source_table is None:
                self.control.source_table = self.c.parser.parse_source_table()
        else:
            if self.control.source_table_a is None:
                self.control.source_table_a = \
                    self.c.parser.parse_source_table_a()
            if self.control.source_table_b is None:
                self.control.source_table_b = \
                    self.c.parser.parse_source_table_b()

    def expected_output_schema(self, table_name):
        """Get the columns a new result table would have, in order.

        The table is created empty under a scratch name through the same CTAS
        a run uses and read back, so the types are exactly Oracle's.
        """
        scratch = f'rapo_temp_schema_{uuid.uuid4().hex[:16]}'
        select = self._select_output_columns(table_name)
        db.execute(f'CREATE TABLE {scratch} AS\n{select}')
        try:
            return self._read_table_schema(scratch)
        finally:
            db.execute(f'DROP TABLE {scratch} PURGE')

    def _read_table_schema(self, table_name):
        query = sa.text('select lower(column_name) name, data_type, '
                        'data_length, char_length, char_used, '
                        'data_precision, data_scale, nullable '
                        'from user_tab_columns '
                        'where table_name = :table_name order by column_id')
        query = query.bindparams(table_name=table_name.upper())
        return db.execute(query, as_table=True)

    def diff_output_table(self, table_name, current_name=None, stats=True):
        """Compare an existing result table with the expected schema.

        Parameters
        ----------
        table_name : str
            Name the control's result table has, which tells its side.
        current_name : str, optional
            Existing table to compare, if not table_name (e.g. before a
            rename).
        stats : bool
            Add the row estimate and the first run, i.e. what a recreate
            would delete.

        Returns
        -------
        diff : dict
            The table, whether it exists, its estimated rows (optimizer
            statistics as of rows_analyzed, None without them), its first
            run, and the columns, each with a status: ok, added, widened,
            nullable, not_output (kept, only in the table) or incompatible.
        """
        current_name = current_name or table_name
        diff = {'table': current_name, 'exists': db.exists(current_name),
                'columns': [], 'rows': None, 'rows_analyzed': None,
                'oldest': None}
        expected = {column['name']: column
                    for column in self.expected_output_schema(table_name)}
        if not diff['exists']:
            diff['columns'] = [diff_column(None, column)
                               for column in expected.values()]
            return diff
        current = {column['name']: column
                   for column in self._read_table_schema(current_name)}
        for name, column in expected.items():
            diff['columns'].append(diff_column(current.get(name), column))
        for name, column in current.items():
            if name not in expected:
                diff['columns'].append(diff_column(column, None))
        if stats:
            diff.update(self._output_table_stats(current_name))
        return diff

    def _output_table_stats(self, table_name):
        # No count(*): on a nullable column the index cannot count rows, so
        # it would scan the whole table. The statistics estimate is free,
        # and min() reads the ends of the rapo_process_id index only.
        query = sa.text('select num_rows, last_analyzed from user_tables '
                        'where table_name = :table_name')
        query = query.bindparams(table_name=table_name.upper())
        stats = db.execute(query, as_dict=True) or {}
        oldest = None
        pid = db.execute(f'select min(rapo_process_id) from {table_name}',
                         as_scalar=True)
        if pid is not None:
            log = db.tables.log
            select = sa.select(log.c.added).where(log.c.process_id == pid)
            oldest = db.execute(select, as_scalar=True)
        return {'rows': stats.get('num_rows'),
                'rows_analyzed': stats.get('last_analyzed'),
                'oldest': oldest}

    def count_output_rows(self, table_name):
        """Count the rows of a result table exactly: a full scan."""
        if table_name not in output_table_names(self.control.name):
            raise ValueError(f'{table_name.upper()} is not a result table '
                             f'of {self.control.name}')
        if not db.exists(table_name):
            return None
        return db.execute(f'select count(*) from {table_name}',
                          as_scalar=True)

    def sync_output_table(self, table_name, heal=False):
        """Apply the safe schema changes to an existing result table.

        Missing columns are added, too narrow ones widened and NOT NULL ones
        that are no longer filled made nullable. Nothing is dropped.

        Parameters
        ----------
        table_name : str
            Result table of this control.
        heal : bool
            Raise when incompatible columns remain, since a run could not
            save into them.

        Returns
        -------
        diff : dict
            The diff the changes were made from, see diff_output_table().
        """
        diff = self.diff_output_table(table_name, stats=False)
        for column in diff['columns']:
            if column['ddl']:
                statement = (f'ALTER TABLE {table_name.upper()} '
                             f'{column["ddl"]}')
                logger.info(f'{self.c} Updating schema: {statement}')
                db.execute(statement)
        incompatible = [column for column in diff['columns']
                        if column['status'] == 'incompatible']
        if heal and incompatible:
            details = ', '.join(f'{i["name"].upper()} {i["current"]} -> '
                                f'{i["expected"]}' for i in incompatible)
            message = (f'Recreate schema needed for {table_name.upper()}: '
                       f'{details}')
            raise ValueError(message)
        return diff

    def sync_output_tables(self):
        """Apply the safe schema changes to the existing tables runs write."""
        diffs = []
        for table_name in self.control.written_output_names:
            if db.exists(table_name):
                diffs.append(self.sync_output_table(table_name))
        return diffs

    def recreate_output_tables(self):
        """Drop all result tables of the control, orphaned ones included, and
        create those runs write with the current schema."""
        for table_name in output_table_names(self.control.name):
            self._delete_output_table(table_name)
        for table_name in self.control.written_output_names:
            self._create_output_table(table_name)

    def drop_orphan_table(self, table_name):
        """Drop a result table of the control that runs no longer write."""
        if table_name not in self.control.orphan_output_names:
            raise ValueError(f'{table_name.upper()} is not an orphaned result '
                             f'table of {self.control.name}')
        db.drop(table_name)
        logger.info(f'{self.c} Orphaned {table_name.upper()} dropped')

    def rename_output_tables(self, old_name):
        """Rename the result tables of the control formerly named old_name."""
        old_control_name = old_name.lower()
        renames = []
        for table_name in output_table_names(self.control.name):
            prefix = table_name[:len('rapo_resx_')]
            old_table_name = f'{prefix}{old_control_name}'
            if old_table_name == table_name or not db.exists(old_table_name):
                continue
            if db.exists(table_name):
                message = f'table {table_name.upper()} already exists'
                raise ValueError(message)
            renames.append((old_table_name, table_name))
        for old_table_name, table_name in renames:
            db.execute(f'ALTER TABLE {old_table_name} RENAME TO {table_name}')
            query = sa.text('select count(*) from user_indexes '
                            'where index_name = :index_name')
            old_index = f'{old_table_name}_rapo_process_id_ix'
            query = query.bindparams(index_name=old_index.upper())
            if db.execute(query, as_scalar=True):
                db.execute(f'ALTER INDEX {old_index} '
                           f'RENAME TO {table_name}_rapo_process_id_ix')
            logger.info(f'{self.c} {old_table_name.upper()} renamed to '
                        f'{table_name.upper()}')
        return [table_name for _, table_name in renames]

    def _prepare_output_columns(self, table_name):
        output_columns = []
        chosen_columns = []
        date_columns = []
        key_columns = []
        if self.control.is_analysis or self.control.is_report:
            chosen_columns.extend(self.control.output_columns)
            if not chosen_columns:
                output_columns.extend(self.c.source_table.columns)
            date_columns.append(self.control.source_date_field)
        elif self.control.is_reconciliation:
            if table_name.startswith('rapo_resa'):
                chosen_columns.extend(self.control.output_columns_a)
                if not chosen_columns:
                    output_columns.extend(self.control.source_table_a.columns)
                    if (
                        db.is_table(self.control.source_table_a)
                        and not db.is_column(self.c.source_key_field_a,
                                             self.c.source_table_a)
                    ):
                        key_column = db.get_rowid(self.c.source_key_field_a)
                        key_columns.append(key_column)
                date_columns.append(self.control.source_date_field_a)
            elif table_name.startswith('rapo_resb'):
                chosen_columns.extend(self.control.output_columns_b)
                if not chosen_columns:
                    output_columns.extend(self.control.source_table_b.columns)
                    if (
                        db.is_table(self.control.source_table_b)
                        and not db.is_column(self.c.source_key_field_b,
                                             self.c.source_table_b)
                    ):
                        key_column = db.get_rowid(self.c.source_key_field_b)
                        key_columns.append(key_column)
                date_columns.append(self.control.source_date_field_b)
        elif self.control.is_comparison:
            chosen_columns.extend(self.control.output_columns)
            if not chosen_columns:
                for column in self.c.source_table_a.columns:
                    column_config = {
                        'column': f'a_{column.name}',
                        'column_a': column.name,
                        'column_b': None
                    }
                    chosen_columns.append(column_config)
                for column in self.c.source_table_b.columns:
                    column_config = {
                        'column': f'b_{column.name}',
                        'column_b': column.name,
                        'column_a': None
                    }
                    chosen_columns.append(column_config)
            date_columns.extend([self.control.source_date_field_a,
                                 self.control.source_date_field_b])
        mandatory_columns = self.control.mandatory_columns
        process_id = self.control.key_column

        for chosen_column in chosen_columns:
            column_a = chosen_column['column_a']
            column_b = chosen_column['column_b']
            column_name = chosen_column['column']
            if column_a or column_b:
                table_a = self.control.source_table_a
                table_b = self.control.source_table_b
                if column_a and column_b:
                    column_a = table_a.c[column_a]
                    column_b = table_b.c[column_b]
                    column = sa.func.coalesce(column_a, column_b)
                elif column_a:
                    column = table_a.c[column_a]
                elif column_b:
                    column = table_b.c[column_b]
                column = column.label(column_name) if column_name else column
            else:
                if table_name.startswith('rapo_rest'):
                    column = self.control.source_table.c[column_name]
                elif table_name.startswith('rapo_resa'):
                    column = self.control.source_table_a.c[column_name]
                elif table_name.startswith('rapo_resb'):
                    column = self.control.source_table_b.c[column_name]
            output_columns.append(column)
        output_columns.extend(key_columns)

        mandatory_names = [i.column_name for i in mandatory_columns]
        reserved_names = [*mandatory_names, process_id.name]
        output_columns = [column for column in output_columns
                          if column.name not in reserved_names]
        for mandatory_column in mandatory_columns:
            column = mandatory_column.null
            output_columns.append(column)
        output_columns.append(process_id)

        output_columns = db.normalize(output_columns, date_fields=date_columns)
        return output_columns

    def delete_output_table(self):
        """Delete control output table."""
        self._delete_output_table(self.control.output_name)

    def delete_output_table_a(self):
        """Delete control output table A."""
        self._delete_output_table(self.control.output_name_a)

    def delete_output_table_b(self):
        """Delete control output table B."""
        self._delete_output_table(self.control.output_name_b)

    def delete_output_tables(self):
        """Delete all control output tables."""
        for table_name in self.control.output_names:
            self._delete_output_table(table_name)

    def _delete_output_table(self, table_name):
        if db.exists(table_name):
            db.drop(table_name)

    def delete_output_records(self):
        """Delete records saved as control results in output tables."""
        for table in self.control.output_tables:
            self._delete_output_records(table)

    def _delete_output_records(self, table):
        if db.exists(table.name):
            if self.control.with_deletion:
                db.truncate(table.name)
            else:
                id = table.c.rapo_process_id
                delete = table.delete().where(id == self.control.process_id)
                db.execute(delete)

    def clean_output_table(self):
        """Delete data in control output table."""
        self._clean_output_table(self.control.output_name)

    def clean_output_table_a(self):
        """Delete data in control output table A."""
        self._clean_output_table(self.control.output_name_a)

    def clean_output_table_b(self):
        """Delete data in control output table B."""
        self._clean_output_table(self.control.output_name_b)

    def clean_output_tables(self):
        """Delete all data in all control output tables."""
        for table_name in self.control.output_names:
            self._clean_output_table(table_name)

    def _clean_output_table(self, table_name):
        if db.exists(table_name):
            db.truncate(table_name)

    def delete_temporary_tables(self):
        """Delete all temporary tables created during control execution."""
        logger.debug(f'{self.c} Deleting temporary tables...')
        for table_name in self.control.temporary_names:
            self._delete_temporary_table(table_name)
        logger.debug(f'{self.c} Temporary tables deleted')

    def _delete_temporary_table(self, table_name):
        if db.exists(table_name):
            db.purge(table_name)

    def lock(self):
        """Acquires a control-level lock on the control logs."""
        class Lock:
            """Represents a held lock of the logs for the given control."""

            def __init__(self, control):
                self.control = self.c = control
                self._released = False
                self._acquire()

            def _acquire(self):
                checkpoint = db.tables.checkpoint
                backoff_time = 5
                max_wait_time = 60
                time_limit = self.control.config['timeout']
                deadline = None
                if isinstance(time_limit, int):
                    deadline = tm.monotonic()+time_limit
                while True:
                    insert = checkpoint.insert().values(
                        control_id=self.control.id,
                        process_id=self.control.process_id,
                        added=dt.datetime.now()
                    )
                    try:
                        db.execute(insert)
                    except sa.exc.IntegrityError:
                        if deadline and tm.monotonic() > deadline:
                            message = ('control is locked by another run of '
                                       'the same control')
                            raise TimeoutError(message)
                        tm.sleep(backoff_time)
                        backoff_time = min(backoff_time+5, max_wait_time)
                    else:
                        break

            def release(self):
                """Release the lock held for this control run."""
                if not self._released:
                    self.control.executor.release_lock()
                    self._released = True

            def __enter__(self):
                return self

            def __exit__(self, _, __, ___):
                self.release()

        return Lock(self.control)

    def release_lock(self):
        """Delete the checkpoint lock held for this control run.

        A process killed while it holds the lock never releases it itself,
        so whoever finishes the run releases it instead.
        """
        checkpoint = db.tables.checkpoint
        delete = checkpoint.delete().where(
            sa.and_(
                checkpoint.c.control_id == self.control.id,
                checkpoint.c.process_id == self.control.process_id
            )
        )
        db.execute(delete)

    def prerun_hook(self):
        """Execute database prerun hook function."""
        logger.debug(f'{self.c} Executing prerun hook function...')
        process_id = self.control.process_id
        select = f'select rapo_prerun_control_hook({process_id}) from dual'
        query = sa.text(select)
        try:
            result_code = db.execute(query, as_scalar=True)
            if result_code is None or result_code.upper() == 'OK':
                logger.debug(f'{self.c} Hook function evaluated OK')
                return True, result_code
            else:
                logger.debug(f'{self.c} Hook function evaluated NOT OK '
                             f'[{result_code}]')
                return False, result_code
        except Exception as error:
            logger.error(f'{self.c} Error evaluating prerun hook')
            logger.error()
            return False, str(error)

    def postrun_hook(self):
        """Execute database postrun hook procedure."""
        logger.debug(f'{self.c} Executing postrun hook procedure...')
        process_id = self.control.process_id
        query = sa.text(f'begin rapo_postrun_control_hook({process_id}); end;')
        db.execute(query)
        logger.debug(f'{self.c} Hook procedure executed')

    def _fetch_records_to_table(self, select, table_name):
        logger.debug(f'{self.c} Start fetching...')
        parallelism = self.control.config['parallelism']
        if parallelism:
            hint = f'parallel({parallelism})'
            select = select.with_hint(sa.text(table_name), hint)
        select = db.compile(select)
        ctas = sa.text(f'CREATE TABLE {table_name} AS\n{select}')
        text = db.formatter.document(ctas)
        logger.info(f'{self.c} Creating {table_name} with query:\n{text}')
        db.execute(ctas)
        logger.info(f'{self.c} {table_name} created')
        table = db.table(table_name)
        logger.debug(f'{self.c} Fetching done')
        return table

    def _count_fetched_to_table(self, table):
        logger.debug(f'{self.c} Counting fetched in {table}...')
        count = sa.select(sa.func.count()).select_from(table)
        fetched = db.execute(count, as_scalar=True)
        logger.debug(f'{self.c} Fetched in {table} counted')
        return fetched

    def _index_table(self, table_name, key_field_name):
        logger.debug(f'{self.c} Creating index for {table_name}...')
        index_name = f'{table_name}_ix'
        parallelism = self.control.config['parallelism'] or 1
        create_index = (f'create index {index_name} '
                        f'on {table_name} ({key_field_name}) unusable')
        rebuild_index = (f'alter index {index_name} rebuild online '
                         f'parallel {parallelism} '
                         'nologging')
        db.execute(create_index)
        db.execute(rebuild_index)
        logger.debug(f'{self.c} Index for {table_name} created')


RESULT_PREFIXES = ('rapo_rest_', 'rapo_resa_', 'rapo_resb_')


def output_table_names(control_name):
    """Get every result table name a control of this name may own."""
    return [f'{prefix}{control_name}'.lower() for prefix in RESULT_PREFIXES]


def diff_column(current, expected):
    """Compare a result table column with the one the configuration expects.

    Either may be None (missing on that side); both are user_tab_columns
    rows. Returns the column's status and the ALTER TABLE clause fixing it.
    """
    name = (expected or current)['name']
    item = {'name': name,
            'current': _column_type(current) if current else None,
            'expected': _column_type(expected) if expected else None,
            'status': 'ok', 'ddl': None}
    if current is None:
        item['status'] = 'added'
        item['ddl'] = f'ADD ({name} {item["expected"]})'
    elif expected is None:
        item['status'] = 'not_output'
        if current['nullable'] == 'N':
            item['ddl'] = f'MODIFY ({name} NULL)'
    else:
        fits = _column_fits(current, expected)
        if fits is None:
            item['status'] = 'incompatible'
        elif fits is False:
            item['status'] = 'widened'
            widened = _column_widened(current, expected)
            item['expected'] = widened
            item['ddl'] = f'MODIFY ({name} {widened})'
        elif current['nullable'] == 'N' and expected['nullable'] == 'Y':
            item['status'] = 'nullable'
            item['ddl'] = f'MODIFY ({name} NULL)'
    return item


_TEXT_TYPES = ('VARCHAR2', 'NVARCHAR2', 'CHAR', 'NCHAR', 'RAW')


def _column_type(column):
    """Render a user_tab_columns row as the type of an ALTER TABLE."""
    data_type = column['data_type']
    if data_type in _TEXT_TYPES:
        if data_type == 'RAW':
            return f'RAW({column["data_length"]})'
        if data_type.startswith('N'):
            return f'{data_type}({column["char_length"]})'
        unit = 'CHAR' if column['char_used'] == 'C' else 'BYTE'
        return f'{data_type}({column["char_length"]} {unit})'
    if data_type == 'NUMBER':
        precision, scale = column['data_precision'], column['data_scale']
        if precision is None and scale is None:
            return 'NUMBER'
        if precision is None:
            return f'NUMBER(*,{scale})'
        return f'NUMBER({precision},{scale or 0})'
    if data_type == 'FLOAT':
        return f'FLOAT({column["data_precision"]})'
    return data_type


def _type_family(data_type):
    if data_type in ('VARCHAR2', 'CHAR'):
        return 'CHAR'
    if data_type in ('NVARCHAR2', 'NCHAR'):
        return 'NCHAR'
    if data_type == 'DATE' or re.fullmatch(r'TIMESTAMP\(\d\)', data_type):
        return 'DATE'
    return data_type


def _number_digits(column):
    """Get the integer and fraction digits a NUMBER column holds.

    None stands for any, i.e. an unconstrained or floating NUMBER.
    """
    precision, scale = column['data_precision'], column['data_scale']
    if scale is None:
        return None, None
    return (precision or 38) - scale, scale


def _text_length(column):
    """Get the length a text column is limited by, in its own unit."""
    if column['char_used'] == 'C':
        return column['char_length']
    return column['data_length']


def _column_fits(current, expected):
    """Tell whether the current column holds every value of the expected one.

    Returns True when it does, False when a MODIFY can widen it, None when
    the types cannot be converted in a table with data.
    """
    current_type, expected_type = current['data_type'], expected['data_type']
    if _type_family(current_type) != _type_family(expected_type):
        return None
    if current_type in _TEXT_TYPES:
        # A CHAR-semantics column counts characters, and an expected text
        # of n bytes has up to n characters.
        if current['char_used'] == 'C':
            return current['char_length'] >= _text_length(expected)
        return current['data_length'] >= expected['data_length']
    if current_type == 'NUMBER':
        integer, fraction = _number_digits(current)
        if integer is None:
            return True
        expected_integer, expected_fraction = _number_digits(expected)
        if expected_integer is None:
            return False
        return integer >= expected_integer and fraction >= expected_fraction
    if current_type == expected_type:
        return True
    if _type_family(current_type) == 'DATE':
        # A TIMESTAMP holds a DATE, and a DATE converts to a TIMESTAMP.
        if expected_type == 'DATE':
            return True
        return current_type != 'DATE' and current_type >= expected_type
    return None


def _column_widened(current, expected):
    """Get the type an existing column is widened to so both fit in it."""
    data_type = current['data_type']
    if data_type in _TEXT_TYPES:
        data_type = ('VARCHAR2' if 'VARCHAR2' in (data_type,
                                                   expected['data_type'])
                     else data_type)
        if data_type in ('VARCHAR2', 'CHAR') and 'C' in (current['char_used'],
                                                         expected['char_used']):
            length = min(max(_text_length(current), _text_length(expected)),
                         4000)
            return f'{data_type}({length} CHAR)'
        if data_type.startswith('N'):
            length = max(current['char_length'], expected['char_length'])
            return f'{data_type}({length})'
        length = max(current['data_length'], expected['data_length'])
        if data_type in ('VARCHAR2', 'CHAR'):
            return f'{data_type}({length} BYTE)'
        return f'{data_type}({length})'
    if data_type == 'NUMBER':
        integer, fraction = _number_digits(current)
        expected_integer, expected_fraction = _number_digits(expected)
        if expected_integer is None:
            return 'NUMBER'
        integer = max(integer, expected_integer)
        fraction = max(fraction, expected_fraction)
        if integer + fraction > 38:
            return 'NUMBER'
        return f'NUMBER({integer + fraction},{fraction})'
    return _column_type(expected)
