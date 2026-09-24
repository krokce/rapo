"""Python Revenue Assurance Process Optimizer."""

from .core.scheduler import Scheduler
from .core.control import Control
from .web import Server


__author__ = 'Timur Faradzhov'
__copyright__ = 'Copyright 2026, The Rapo project'
__credits__ = ['Timur Faradzhov', 'Kostadin Taneski']

__license__ = 'MIT'
__version__ = '0.8.2+fork'
__maintainer__ = 'Kostadin Taneski'
__email__ = 'kosta@taneski.com'
__status__ = 'Development'

__all__ = [Scheduler, Control, Server]
