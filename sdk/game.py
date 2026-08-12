"""
game.py — the Game contract.

Every game is a subclass of Game that implements two methods:

    setup(self, client)         called once, before the first frame
    update(self, client, dt)    called every frame; dt is seconds since last

The runner (run.py / run_sim.py) is responsible for the loop, timing, input
refresh, and flushing the frame — the game only decides what to draw and how to
react to input. Keeping the loop in the runner (not the game) is what lets the
exact same game run on real hardware or in the sim unchanged.

A game may optionally override teardown() for cleanup (closing files, etc.).
"""

from __future__ import annotations


class Game:
    #: Optional advisory target FPS for this game. The runner uses it if set;
    #: otherwise it falls back to the config default. The firmware still
    #: enforces the true minimum inter-frame time on real hardware.
    fps: float | None = None

    #: Optional human-readable name, shown by the sim / runner.
    name: str = "Untitled Game"

    def setup(self, client) -> None:
        """Called once before the loop starts. Initialise game state here.
        `client` is a GridClient."""
        pass

    def update(self, client, dt: float) -> None:
        """Called every frame. `dt` is seconds elapsed since the previous
        update. Draw into `client` and read input from it here."""
        raise NotImplementedError("Your game must implement update(self, client, dt)")

    def teardown(self, client) -> None:
        """Called once when the game is stopping (Ctrl+C or window close).
        Optional — override to release resources."""
        pass
