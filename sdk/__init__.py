"""
The Grid SDK.

Public API (what games and runners import):

    from sdk import GridClient, GridController, ModuleLayout

Games themselves normally only ever see a ready-made GridClient handed to them
by run.py / run_sim.py, so they rarely import anything from here directly.
"""

from .layout import ModuleLayout, MAX_CHANNEL_VALUE
from .client import GridClient
from .controller import GridController
from .game import Game

__all__ = ["ModuleLayout", "GridClient", "GridController", "Game", "MAX_CHANNEL_VALUE"]

__version__ = "0.1.0"
