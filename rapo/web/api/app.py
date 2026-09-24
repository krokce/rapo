"""Contains web API application and routes."""

import asyncio
import contextlib
import datetime as dt
import os

import fastapi
import fastapi.responses
import socketio
import sqlalchemy as sa

from . import events
from .auth import verify_token

from ...config import config, path as CONFIG_PATH
from ...database import db
from ...kpi import kpi
from ...logger import logger, LOG_DIR
from ...reader import reader

from ...core import journal
from ...core import logs
from ...core import mailer
from ...core import schedule
from ...core import sqlcheck
from ...core.control import Control
from ...core.runner import runner
from ...core.scheduler import scheduler, upcoming


UI_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', 'ui'))

# Swagger and the schema it reads can not carry the Bearer token, so they
# would describe the whole API to anyone able to reach the port. They are
# served only when [API] docs is switched on.
DOCS_ENABLED = bool(config.check('API') and config['API'].get('docs'))

# Options of rapo.ini never sent to the browser, matched by name fragment.
SECRET_OPTIONS = ('password', 'token', 'secret')


def find_control(process_id):
    """Get control of the run with the given process ID, or answer 404."""
    try:
        return Control(process_id=process_id)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=404, detail=str(error))


@contextlib.asynccontextmanager
async def lifespan(app):
    """Run the run manager and the scheduler together with the server."""
    runner.listeners.append(events.poke_scheduler)
    scheduler.listeners.append(events.poke_scheduler)
    logs.cleaner.start()
    await asyncio.to_thread(runner.start)
    scheduler.start()
    yield
    await asyncio.to_thread(scheduler.stop)
    await asyncio.to_thread(runner.stop)
    logs.cleaner.stop()


fastapi_app = fastapi.FastAPI(
    title='Rapo',
    docs_url='/api/docs' if DOCS_ENABLED else None,
    openapi_url='/api/openapi.json' if DOCS_ENABLED else None,
    redoc_url=None,
    lifespan=lifespan)
api = fastapi.APIRouter(prefix='/api',
                        dependencies=[fastapi.Depends(verify_token)])
logger.configure(console=False)


@api.get('/help', response_class=fastapi.responses.HTMLResponse)
def help():
    """Get help message."""
    path = os.path.join(os.path.dirname(__file__), 'templates/help.html')
    with open(path, 'r') as file:
        return file.read()


@api.get('/status')
def status():
    """Get scheduler status."""
    input_dict = reader.read_scheduler_record()
    if not input_dict:
        raise fastapi.HTTPException(status_code=404,
                                    detail='No scheduler record found')
    output_dict = {
        'server': input_dict['server'],
        'username': input_dict['username'],
        'pid': input_dict['pid'],
        'start_date': input_dict['start_date'],
        'stop_date': input_dict['stop_date'],
        'status': input_dict['status']
    }
    return output_dict


@api.get('/session')
def session():
    """Get API status."""
    input_dict = reader.read_web_api_record()
    if not input_dict:
        raise fastapi.HTTPException(status_code=404,
                                    detail='No web API record found')
    output_dict = {
        'server': input_dict['server'],
        'username': input_dict['username'],
        'pid': input_dict['pid'],
        'url': input_dict['url'],
        'debug': input_dict['debug'],
        'start_date': input_dict['start_date'],
        'stop_date': input_dict['stop_date'],
        'status': input_dict['status']
    }
    return output_dict


@api.get('/version')
def version():
    """Get application version."""
    from ... import __version__
    return {'version': __version__}


@api.get('/info')
def info():
    """Get application info."""
    scheduler_config = config.get('SCHEDULER', {})
    database_config = config.get('DATABASE', {})
    output_dict = {
        'instance_name': scheduler_config.get('instance_name'),
        'schema_name': database_config.get('username'),
        'database_server': database_config.get('host'),
        'database_name': (
            database_config.get('sid') or
            database_config.get('service_name')
        ),
        'config_path': CONFIG_PATH,
        'log_directory': LOG_DIR,
        'kpi_available': kpi.available
    }
    return output_dict


@api.get('/parameters')
def parameters():
    """Get the parameters of rapo.ini as they are written there."""
    output_dict = {}
    for section_name, section in config.items():
        output_dict[section_name] = {
            name: value for name, value in section.items()
            if not any(secret in name for secret in SECRET_OPTIONS)
        }
    return output_dict


@api.post('/run-control')
def run_control(name: str, date: str | None = None,
                date_from: str | None = None, date_to: str | None = None,
                debug_mode: bool = False, iterations: bool = False):
    """Initiate control run and queue it for execution.

    The run cascades into the controls following it, the way a scheduled run
    does. Its iterations are performed only when they are asked for.
    """
    if not runner.active:
        raise fastapi.HTTPException(status_code=503,
                                    detail='Run manager is not running')
    try:
        runner.submit(name, journal.MANUAL, cascade=True,
                      iterations=iterations, date_from=date_from,
                      date_to=date_to, date=date, debug_mode=debug_mode)
    except Exception as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    events.poke()
    return {'status': 200}


@api.post('/cancel-control')
def cancel_control(id: int):
    """Cancel running control."""
    if not runner.cancel(id):
        # Not a run of this server: void its status, its owner will stop it.
        control = find_control(id)
        control.cancel()
    events.poke()
    return {'status': 200}


@api.delete('/revoke-control-run')
def revoke_control_run(id: int):
    """Revoke patricular control run."""
    control = find_control(id)
    control.revoke()
    events.poke()
    return {'status': 200}


@api.post('/send-control-email')
def send_control_email(process_id: int):
    """Send the email of a finished control run again."""
    control = find_control(process_id)
    if control.status != 'D':
        detail = f'Run {process_id} has status {control.status}, not D'
        raise fastapi.HTTPException(status_code=400, detail=detail)
    try:
        mailer.send_run_email(control, trigger='resend')
    except mailer.EmailError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    return {'status': 200}


@api.post('/send-test-email')
def send_test_email(control_name: str, to: str):
    """Send the email of the control's last finished run to an address."""
    process_id = mailer.read_last_done_run(control_name)
    if not process_id:
        detail = f'Control {control_name} has no finished run (status D)'
        raise fastapi.HTTPException(status_code=400, detail=detail)
    control = find_control(process_id)
    try:
        mailer.send_run_email(control, trigger='test', override_to=to)
    except mailer.EmailError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    return {'status': 200}


@api.delete('/delete-control-output-tables')
def delete_control_output_tables(name: str):
    """Delete control output tables."""
    control = Control(name)
    control.executor.delete_output_tables()
    return {'status': 200}


def _schema_control(data):
    """Build a Control from a stored control with an editor's changes."""
    control_id = data.get('control_id')
    saved = reader.read_control_config_by_id(control_id) if control_id else {}
    if not saved:
        raise fastapi.HTTPException(status_code=400,
                                    detail='The control is not saved yet.')
    config = dict(saved)
    config.update({key: value for key, value in data.items()
                   if key in saved and key not in ('control_id',
                                                   'created_date',
                                                   'updated_date')})
    name = config['control_name'] or saved['control_name']
    return Control(name, config=config), saved


def _active_run(control_id):
    log = db.tables.log
    select = (sa.select(sa.func.count())
                .where(log.c.control_id == control_id)
                .where(log.c.status.in_(['I', 'W', 'S', 'P', 'F'])))
    return bool(db.execute(select, as_scalar=True))


@api.post('/check-control-schema')
def check_control_schema(data: dict = fastapi.Body(...)):
    """Compare the result tables of a control with the schema its (unsaved)
    configuration would create."""
    control, saved = _schema_control(data)
    config = control.config
    saved_name = saved['control_name']
    sides = {'source_name': 'source', 'source_name_a': 'A',
             'source_name_b': 'B'}
    source_changed = [label for key, label in sides.items()
                      if (config.get(key) or '').lower()
                      != (saved.get(key) or '').lower()]
    answer = {'control_name': control.name,
              'renamed_from': (saved_name if saved_name.lower()
                               != control.name.lower() else None),
              'source_changed': source_changed,
              'rebuilt_each_run': control.with_drop,
              'active_run': _active_run(saved['control_id']),
              'tables': []}
    if control.with_drop:
        return answer
    try:
        control.executor._reflect_sources()
    except sa.exc.NoSuchTableError as error:
        answer['error'] = f'Datasource {str(error).upper()} does not exist.'
        return answer
    except Exception as error:
        answer['error'] = f'Datasource cannot be read: {error}'
        return answer
    for table_name in control.output_names:
        current_name = table_name
        if answer['renamed_from']:
            old_name = (table_name[:len('rapo_resx_')]
                        + saved_name.lower())
            if db.exists(old_name) and not db.exists(table_name):
                current_name = old_name
        try:
            diff = control.executor.diff_output_table(table_name,
                                                      current_name)
        except Exception as error:
            diff = {'table': current_name, 'exists': db.exists(current_name),
                    'columns': [], 'error': f'{type(error).__name__}: {error}'}
        diff['target'] = table_name
        answer['tables'].append(diff)
    return answer


@api.get('/count-control-table-rows')
def count_control_table_rows(name: str, table: str):
    """Count the rows of a result table of a control exactly.

    A full scan, so only on request: check-control-schema gives the
    statistics estimate.
    """
    control = Control(name)
    try:
        rows = control.executor.count_output_rows(table.lower())
    except ValueError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    return {'table': table.upper(), 'rows': rows,
            'counted': dt.datetime.now().replace(microsecond=0)}


@api.post('/update-control-schema')
def update_control_schema(name: str):
    """Apply the safe schema changes (add, widen, nullable) to the result
    tables of a saved control."""
    control = Control(name)
    try:
        control.executor._reflect_sources()
        diffs = control.executor.sync_output_tables()
    except Exception as error:
        logger.error()
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    incompatible = [f"{diff['table']}.{column['name']}"
                    for diff in diffs for column in diff['columns']
                    if column['status'] == 'incompatible']
    events.poke()
    return {'status': 200, 'incompatible': incompatible}


@api.post('/recreate-control-schema')
def recreate_control_schema(name: str):
    """Drop the result tables of a saved control and create them anew."""
    control = Control(name)
    try:
        control.executor._reflect_sources()
        control.executor.recreate_output_tables()
    except Exception as error:
        logger.error()
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    events.poke()
    return {'status': 200}


@api.delete('/delete-control-temporary-tables')
def delete_control_temporary_tables(id: int):
    """Delete temporary tables of particular control run."""
    control = find_control(id)
    control.executor.delete_temporary_tables()
    return {'status': 200}


@api.get('/get-running-controls')
def get_running_controls():
    """Get list of currently running controls in JSON."""
    return reader.read_running_controls()


@api.get('/get-all-controls')
def get_all_controls():
    """Get list of all controls in JSON."""
    return reader.read_control_config_all()


@api.get('/get-control-versions')
def get_control_versions(control_id: str | None = None):
    """Get list of control versions by ID in JSON."""
    if control_id is None:
        return []
    return reader.read_control_config_versions(control_id)


@api.get('/get-control-runs')
def get_control_runs(date: dt.date | None = None):
    """Get all control runs started on the passed day (default: the server's today) in JSON."""
    today = dt.date.today()
    day = date or today
    return {'date': day.isoformat(), 'today': today.isoformat(),
            'runs': reader.read_control_results_for_day(day)}


@api.get('/read-control-logs')
def read_control_logs(control_name: str | None = None, days: int = 31,
                      limit: int = fastapi.Query(5000, ge=1, le=50000)):
    """Get list of control logs in JSON."""
    if control_name is None:
        return []
    return reader.read_control_logs(
        control_name, days, ['W', 'C', 'E', 'D', 'I', 'S', 'P', 'F', 'X'],
        limit=limit)


@api.get('/get-datasources')
def get_datasources():
    """Get list of all DB datasources in JSON."""
    return reader.read_datasources()


@api.get('/get-datasource-columns')
def get_datasource_columns(datasource_name: str | None = None):
    """Get list of DB datasource columns in JSON."""
    if datasource_name is None:
        return []
    return reader.read_datasource_columns(datasource_name)


@api.get('/get-kpi-types')
def get_kpi_types():
    """Get list of available KPI types in JSON."""
    return kpi.read_kpi_types()


@api.get('/get-control-kpis')
def get_control_kpis(control_name: str | None = None):
    """Get KPI configuration of the control in JSON."""
    if control_name is None:
        return []
    return kpi.read_control_kpis(control_name)


@api.get('/get-kpi-type-usage')
def get_kpi_type_usage():
    """Get controls that use each KPI type in JSON."""
    return kpi.read_kpi_type_usage()


@api.post('/save-kpi-type')
def save_kpi_type(data: dict = fastapi.Body(...)):
    """Create, update or rename KPI type in catalogue table."""
    # The code is the primary key, so a rename must say what it renames.
    previous = data.pop('previous_kpi_type', None)
    try:
        kpi.save_kpi_type(data, previous=previous)
    except Exception as error:
        logger.error()
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    return {'status': 200}


@api.delete('/delete-kpi-type')
def delete_kpi_type(kpi_type: str):
    """Delete KPI type from catalogue table."""
    try:
        kpi.delete_kpi_type(kpi_type)
    except Exception as error:
        logger.error()
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    return {'status': 200}


@api.post('/validate-kpi-sql')
def validate_kpi_sql(data: dict = fastapi.Body(...)):
    """Parse KPI or alarm statement without executing it."""
    return kpi.validate_statement(data.get('statement'),
                                  kind=data.get('kind') or 'kpi')


@api.post('/validate-sql')
def validate_sql(data: dict = fastapi.Body(...)):
    """Parse a statement of the control editor without executing it."""
    return sqlcheck.check(data.get('kind'), data.get('statement'), data)


@api.post('/save-control')
def save_control(data: dict = fastapi.Body(...)):
    """Create or update control in configuration table."""
    # An absent key leaves the KPI configuration alone, an empty list clears it.
    kpi_config = data.pop('kpi_config', None)
    # The updated_date the editor loaded: a row changed since then is not
    # overwritten (optimistic lock). Callers without it overwrite as before.
    expected_updated_date = data.pop('expected_updated_date', None)
    control_id = data.get('control_id')
    previous_name = (reader.read_control_name_by_id(control_id)
                     if control_id else None)
    if control_id and expected_updated_date:
        stamp = reader.read_control_stamp(control_id=control_id)
        expected = dt.datetime.fromisoformat(str(expected_updated_date))
        if stamp and stamp['updated_date'] != expected:
            changed = f"{stamp['updated_date']:%d.%m.%Y %H:%M:%S}"
            who = f" by {stamp['updated_by']}" if stamp['updated_by'] else ''
            detail = f'The control was changed{who} at {changed}.'
            raise fastapi.HTTPException(status_code=409, detail=detail)
    try:
        reader.save_control(data)
    except Exception as error:
        logger.error()
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    # The result tables are named after the control, so they follow a rename.
    rename_error = None
    control_name = data.get('control_name')
    if previous_name and control_name and previous_name != control_name:
        try:
            Control(control_name).executor.rename_output_tables(previous_name)
        except Exception as error:
            logger.error()
            rename_error = error
    try:
        if kpi_config is not None:
            control_name = data.get('control_name') or previous_name
            kpi.save_control_kpis(control_name, kpi_config,
                                  old_name=previous_name)
    except Exception as error:
        # The control itself is saved by now, so the scheduler must be told.
        logger.error()
        scheduler.refresh()
        events.poke()
        raise fastapi.HTTPException(
            status_code=400,
            detail=f'Control was saved, but its KPI configuration was not: '
                   f'{error}')
    scheduler.refresh()
    events.poke()
    if rename_error:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f'Control was saved, but its result tables were not '
                   f'renamed: {rename_error}')
    return {'status': 200, **saved_stamp(data)}


def saved_stamp(data):
    """Get ID and updated_date of a control just saved, read back from the DB.

    The date is the one rapo_config_upd_trg stamped with the DB clock, which
    is what the editor compares against on its next save.
    """
    stamp = reader.read_control_stamp(control_id=data.get('control_id'),
                                      control_name=data.get('control_name'))
    if not stamp:
        return {}
    return {'control_id': stamp['control_id'],
            'updated_date': stamp['updated_date']}


@api.delete('/delete-control')
def delete_control(control_id: int):
    """Delete control from configuration table."""
    reader.delete_control(control_id)
    scheduler.refresh()
    events.poke()
    return {'status': 200}


@api.get('/get-control-run-log')
def get_control_run_log(process_id: int,
                        max_bytes: int = fastapi.Query(logs.READ_LIMIT, ge=1,
                                                       le=50*1024*1024)):
    """Get run details from the control log and its log file."""
    try:
        run = reader.read_control_result(process_id)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=404, detail=str(error))
    config = reader.read_control_config_by_id(run['control_id'])
    run = {**run,
           'control_name': config.get('control_name'),
           'control_type': config.get('control_type')}
    return {'run': run, 'log': logs.read_run_log(process_id, max_bytes)}


@api.get('/download-control-run-log')
def download_control_run_log(process_id: int):
    """Download the log file of a control run."""
    try:
        run = reader.read_control_result(process_id)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=404, detail=str(error))
    path = logs.run_log_path(run['control_id'], process_id)
    if not os.path.isfile(path):
        raise fastapi.HTTPException(status_code=404,
                                    detail='Log file not found')
    name = reader.read_control_name_by_id(run['control_id']) or 'control'
    return fastapi.responses.FileResponse(path, media_type='text/plain',
                                          filename=f'{name}_{process_id}.log')


@api.get('/get-control-run')
def get_control_run(process_id: int):
    """Get details of particular control run in JSON."""
    control = find_control(process_id)
    return {
        'name': control.name,
        'date_from': control.date_from,
        'date_to': control.date_to,
        'process_id': control.process_id,
        'start_date': control.start_date,
        'end_date': control.end_date,
        'status': control.status,
        'fetched_number': control.fetched_number,
        'success_number': control.success_number,
        'error_number': control.error_number,
        'error_level': control.error_level,
        'fetched_number_a': control.fetched_number_a,
        'fetched_number_b': control.fetched_number_b,
        'success_number_a': control.success_number_a,
        'success_number_b': control.success_number_b,
        'error_number_a': control.error_number_a,
        'error_number_b': control.error_number_b,
        'error_level_a': control.error_level_a,
        'error_level_b': control.error_level_b
    }


@api.get('/scheduler-status')
def scheduler_status():
    """Get scheduler and run manager status."""
    return {**scheduler.status(), 'runner': runner.status()}


@api.post('/scheduler-stop')
def scheduler_stop():
    """Stop scheduling on all servers until started again."""
    scheduler.disable()
    return {'status': 200}


@api.post('/scheduler-start')
def scheduler_start():
    """Start scheduling from now on."""
    if not scheduler.enabled:
        raise fastapi.HTTPException(
            status_code=409,
            detail='Scheduler is disabled for this server in rapo.ini')
    scheduler.enable()
    return {'status': 200}


@api.get('/scheduler-upcoming')
def scheduler_upcoming(hours: int = fastapi.Query(24, ge=1, le=24*31),
                       control_name: str | None = None):
    """Get upcoming fires of scheduled controls."""
    return upcoming(hours, control_name)


@api.get('/scheduler-events')
def scheduler_events(control_name: str | None = None,
                     event_type: str | None = None,
                     trigger_type: str | None = None,
                     date_from: dt.date | None = None,
                     date_to: dt.date | None = None,
                     limit: int = fastapi.Query(500, ge=1, le=5000)):
    """Get scheduler events, latest first."""
    date_to = date_to+dt.timedelta(days=1) if date_to else None
    return journal.read_events(control_name, event_type, trigger_type,
                               date_from, date_to, limit)


@api.post('/run-missed')
def run_missed(event_id: int):
    """Run control for the scheduled time of a missed fire."""
    event = journal.read(event_id)
    if not event or event['event_type'] != journal.MISSED:
        raise fastapi.HTTPException(status_code=400,
                                    detail='Event is not a missed fire')
    if not runner.active:
        raise fastapi.HTTPException(status_code=503,
                                    detail='Run manager is not running')
    name = reader.read_control_name_by_id(event['control_id'])
    if not name:
        raise fastapi.HTTPException(status_code=400,
                                    detail='Control does not exist anymore')
    timestamp = event['scheduled_time'].timestamp()
    try:
        caught = runner.submit(name, journal.CATCHUP, timestamp=timestamp,
                               cascade=True, iterations=True)
    except Exception as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    journal.update(event_id, message=f'Run as event {caught}.')
    events.poke()
    return {'status': 200}


@api.get('/schedule-preview')
def schedule_preview(schedule_config: str,
                     count: int = fastapi.Query(5, ge=1, le=100)):
    """Get the next fires of a schedule configuration JSON."""
    try:
        item = schedule.parse(schedule_config)
    except (ValueError, TypeError) as error:
        raise fastapi.HTTPException(status_code=422, detail=str(error))
    if not item:
        return []
    return schedule.next_fire(item, dt.datetime.now(), limit=count)


@api.get('/iteration-preview')
def iteration_preview(name: str, date: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None):
    """Get the runs the iterations of a manual run would perform.

    The window of an iteration is computed by the engine itself, so what the
    UI offers before a run is what the run performs.
    """
    try:
        control = Control(name, date=date, date_from=date_from,
                          date_to=date_to)
        dates = control._iteration_dates()
        output_list = []
        for case in control.iteration_config:
            if not case['status']:
                continue
            iteration = Control(name, iteration_id=case['iteration_id'],
                                **dates)
            output_list.append({
                'iteration_id': case['iteration_id'],
                'iteration_description': case['iteration_description'],
                'date_from': iteration.date_from,
                'date_to': iteration.date_to,
            })
    except Exception as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    return output_list


fastapi_app.include_router(api)


@fastapi_app.get('/{path:path}', include_in_schema=False)
def serve_ui(path: str):
    """Serve UI files, falling back to index.html for SPA routes."""
    if path == 'api' or path.startswith('api/'):
        raise fastapi.HTTPException(status_code=404, detail='Not Found')
    file = os.path.realpath(os.path.join(UI_DIR, path))
    if file.startswith(UI_DIR + os.sep) and os.path.isfile(file):
        return fastapi.responses.FileResponse(file)
    return fastapi.responses.FileResponse(os.path.join(UI_DIR, 'index.html'))


# Socket.io is served under /api so that anything proxying /api reaches it.
app = socketio.ASGIApp(events.sio, other_asgi_app=fastapi_app,
                       socketio_path='api/socket.io')
