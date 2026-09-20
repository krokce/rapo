"""Command-line entry points for running rapo as a standalone app."""

from .core.scheduler import Scheduler
from .web import Server


def run_scheduler():
    Scheduler()


def run_server():
    Server()
