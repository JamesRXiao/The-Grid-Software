"""
rainbow.py — a scrolling rainbow across the whole floor.

A non-interactive example showing how to draw the entire floor efficiently with
numpy each frame, and how to use `dt` so the animation runs at the same visual
speed no matter the frame rate. Works on any floor shape (nothing hard-coded).

Run it:
    python run_sim.py examples/rainbow.py
    python run.py     examples/rainbow.py
"""

import colorsys

import numpy as np

from sdk import Game


class Rainbow(Game):
    name = "Rainbow"
    fps = 30

    def setup(self, client):
        self._t = 0.0
        # Precompute a per-column hue offset so the rainbow spreads across the
        # width of the floor, whatever that width is.
        self._col_offsets = np.linspace(0.0, 1.0, client.cols, endpoint=False)

    def update(self, client, dt):
        self._t += dt * 0.2  # scroll speed (cycles per ~5 seconds)

        # Build a (cols,) array of hues, then a (cols, 3) colour table.
        hues = (self._col_offsets + self._t) % 1.0
        # colorsys is per-value; vectorise with a small comprehension (cols is
        # small — a few dozen — so this is plenty fast).
        table = np.array(
            [colorsys.hsv_to_rgb(h, 1.0, 1.0) for h in hues]
        )  # (cols, 3) in 0..1
        table = (table * 254).astype(np.uint8)

        # Broadcast the column colours across every row.
        client.frame[:, :] = table[np.newaxis, :, :]
