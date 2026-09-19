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

from ...logger import logger
from ...reader import reader

from ...core import journal
from ...core import schedule
from ...core.control import Control
from ...core.runner import runner
from ...core.scheduler import scheduler, upcoming


UI_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', 'ui'))


@contextlib.asynccontextmanager
async def lifespan(app):
    """Run the run manager and the scheduler together with the server."""
    runner.listeners.append(events.poke_scheduler)
    scheduler.listeners.append(events.poke_scheduler)
    await asyncio.to_thread(runner.start)
    scheduler.start()
    yield
    await asyncio.to_thread(scheduler.stop)
    await asyncio.to_thread(runner.stop)


fastapi_app = fastapi.FastAPI(title='Rapo',
                              docs_url='/api/docs',
                              openapi_url='/api/openapi.json',
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
    from ...config import config
    scheduler_config = config['SCHEDULER']
    database_config = config['DATABASE']
    output_dict = {
        'instance_name': scheduler_config.get('instance_name'),
        'schema_name': database_config['username'],
        'database_server': database_config['host'],
        'database_name': (
            database_config.get('sid') or
            database_config.get('service_name')
        )
    }
    return output_dict


@api.get('/parameters')
def parameters():
    """Get application info."""
    from ...config import config
    scheduler_config = config['SCHEDULER']
    algorithm_config = config['ALGORITHM']
    database_config = config['DATABASE']
    logging_config = config['LOGGING']
    output_dict = {
        'scheduler_enabled': scheduler_config.get('enabled'),
        'control_parallelism': scheduler_config.get('control_parallelism'),
        'refresh_interval': scheduler_config.get('refresh_interval'),
        'maintenance_interval': scheduler_config.get('maintenance_interval'),
        'database_report_interval': scheduler_config.get(
            'database_report_interval'
        ),
        'event_retention_days': scheduler_config.get('event_retention_days'),
        'missed_window_hours': scheduler_config.get('missed_window_hours'),
        'lease_timeout': scheduler_config.get('lease_timeout'),
        'fuzzy_optimization': algorithm_config.get('fuzzy_optimization'),
        'normalization_type': algorithm_config.get('normalization_type'),
        'discrepancy_matching': algorithm_config.get('discrepancy_matching'),
        'database': {
            'max_overflow': database_config.get('max_overflow'),
            'pool_pre_ping': database_config.get('pool_pre_ping'),
            'pool_size': database_config.get('pool_size'),
            'pool_recycle': database_config.get('pool_recycle'),
            'pool_timeout': database_config.get('pool_timeout')
        },
        'logging': {
            'console': logging_config.get('console'),
            'file': logging_config.get('file'),
            'info': logging_config.get('info'),
            'debug': logging_config.get('debug'),
            'error': logging_config.get('error'),
            'warning': logging_config.get('warning'),
            'critical': logging_config.get('critical')
        }
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
        control = Control(process_id=id)
        control.cancel()
    events.poke()
    return {'status': 200}


@api.delete('/revoke-control-run')
def revoke_control_run(id: int):
    """Revoke patricular control run."""
    control = Control(process_id=id)
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
    control = Control(process_id=id)
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
def get_control_runs():
    """Get list of all control runs in JSON."""
    return reader.read_control_results_for_day()


@api.get('/read-control-logs')
def read_control_logs(control_name: str | None = None, days: int = 31):
    """Get list of control logs in JSON."""
    if control_name is None:
        return []
    return reader.read_control_logs(
        control_name, days, ['W', 'C', 'E', 'D', 'I', 'S', 'P', 'F', 'X'])


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


@api.get('/get-control-run')
def get_control_run(process_id: int):
    """Get details of particular control run in JSON."""
    control = Control(process_id=process_id)
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
