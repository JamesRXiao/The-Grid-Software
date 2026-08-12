"""
runner.py — shared machinery for run.py and run_sim.py.

Both entry points do the same thing: load a game file, build a GridClient over
some backend, and drive the update loop. The only difference is which backend
they construct (real GridController vs. the pygame SimBackend). Keeping the loop
here means the two runners behave identically and a game is guaranteed to run
the same in the sim and on hardware.
"""

from __future__ import annotations

import importlib.util
import inspect
import time
from pathlib import Path

from sdk import Game, GridClient


def load_game(game_path: str) -> Game:
    """Import a game .py file and instantiate its Game subclass.

    The file just needs to define exactly one subclass of Game (any name).
    """
    path = Path(game_path)
    if not path.exists():
        raise FileNotFoundError(f"game file not found: {game_path}")

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find the Game subclass defined in this module (ignore the imported base).
    candidates = [
        obj for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, Game) and obj is not Game and obj.__module__ == module.__name__
    ]
    if not candidates:
        raise ValueError(
            f"{game_path} defines no Game subclass. "
            f"Copy games/game_template.py to start."
        )
    if len(candidates) > 1:
        names = ", ".join(c.__name__ for c in candidates)
        raise ValueError(f"{game_path} defines multiple Game subclasses ({names}); keep one.")

    return candidates[0]()


def run_loop(game: Game, client: GridClient, default_fps: float,
             should_continue=lambda: True) -> None:
    """Drive a game to completion.

    game            : the Game instance
    client          : a ready GridClient (its backend already started)
    default_fps     : fallback FPS if the game doesn't specify one
    should_continue : callable returning False when the loop should end
                      (the sim passes one that goes False when its window closes)
    """
    fps = game.fps if getattr(game, "fps", None) else default_fps
    interval = 1.0 / fps

    game.setup(client)

    last = time.perf_counter()
    try:
        while should_continue():
            now = time.perf_counter()
            dt = now - last
            last = now

            client._refresh_input()   # pull latest presses, roll edge state
            game.update(client, dt)   # game draws + reacts
            client._flush()           # push surface to backend

            # Pace the loop to the target FPS.
            elapsed = time.perf_counter() - now
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        print("\n[runner] stopping (Ctrl+C)")
    finally:
        game.teardown(client)
