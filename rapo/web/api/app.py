"""Contains web API application and routes."""

import asyncio
import contextlib
import datetime as dt
import os

import fastapi
import fastapi.responses
import socketio

from . import events
from .auth import verify_token

from ...config import config, path as CONFIG_PATH
from ...logger import logger, LOG_DIR
from ...reader import reader

from ...core import journal
from ...core import logs
from ...core import schedule
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
        'log_directory': LOG_DIR
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
                debug_mode: bool = False):
    """Initiate control run and queue it for execution."""
    if not runner.active:
        raise fastapi.HTTPException(status_code=503,
                                    detail='Run manager is not running')
    runner.submit(name, journal.MANUAL, date_from=date_from, date_to=date_to,
                  date=date, debug_mode=debug_mode)
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


@api.delete('/delete-control-output-tables')
def delete_control_output_tables(name: str):
    """Delete control output tables."""
    control = Control(name)
    control.executor.delete_output_tables()
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


@api.post('/save-control')
def save_control(data: dict = fastapi.Body(...)):
    """Create or update control in configuration table."""
    try:
        reader.save_control(data)
    except Exception as error:
        logger.error()
        raise fastapi.HTTPException(status_code=400, detail=str(error))
    scheduler.refresh()
    events.poke()
    return {'status': 200}


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
    caught = runner.submit(name, journal.CATCHUP, timestamp=timestamp,
                           chain=True)
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
