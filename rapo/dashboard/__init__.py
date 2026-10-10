"""Contains the Dashboard: aggregates of runs, scheduler, files and KPIs.

`collect(parts, span)` answers get-dashboard: each part is computed in its
own thread, so the slowest decides, and one failing part answers its error
without failing the others. The queries behind them are kept for a few
seconds and dropped by the live events (`memo`).
"""

import concurrent.futures

from ..logger import logger
from . import files as file_data
from . import kpis as kpi_data
from . import runs as run_data
from . import schedule
from . import spans
from .memo import memo


def _tiles(span):
    return {**run_data.tiles(),
            **(file_data.tiles() or {}),
            'files_waiting': file_data.waiting_tile(),
            'files_processing': file_data.processing_tile(),
            'kpi_alarms': kpi_data.tiles() if kpi_data.available() else None}


PARTS = {
    'tiles': _tiles,
    'timeline': run_data.timeline,
    'runs': run_data.runs,
    'scheduler': lambda span: schedule.scheduler(),
    'files': file_data.files,
    'kpis': kpi_data.kpis,
}

_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=len(PARTS), thread_name_prefix='Dashboard')


def check(parts, span):
    """Raise ValueError for an unknown part or span."""
    spans.check(span)
    unknown = [part for part in parts if part not in PARTS]
    if unknown or not parts:
        raise ValueError(f'parts are some of {", ".join(PARTS)}')


def collect(parts, span):
    """Get the parts of the Dashboard for a span.

    Returns
    -------
    parts : dict
        By part, its payload, or {error} when it failed.
    """
    check(parts, span)
    futures = {part: _executor.submit(PARTS[part], span)
               for part in dict.fromkeys(parts)}
    result = {}
    for part, future in futures.items():
        try:
            result[part] = future.result()
        except Exception as error:
            logger.error()
            result[part] = {'error': f'{type(error).__name__}: {error}'}
    return result


def invalidate(kind):
    """Drop what a change makes stale: runs, controls, scheduler, or a kind
    of datasources:changed.
    """
    memo.invalidate(kind)


__all__ = ['collect', 'check', 'invalidate', 'PARTS', 'file_data']
