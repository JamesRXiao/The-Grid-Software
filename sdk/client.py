"""
client.py — the game-facing API.

GridClient is the ONLY thing game code touches. It presents the floor as a
numpy array of shape (rows, cols, 3) and offers helpers for setting pixels and
reading presses. It knows nothing about serial ports, module IDs, wire bytes,
or threads — it forwards to a backend that implements the backend interface
(GridController for real hardware, SimBackend for the simulator).

Because games depend only on GridClient's method signatures, the backend and
everything below it can be refactored freely as long as this surface stays
stable.

Coordinate convention
---------------------
    (row, col): row 0 is the TOP of the floor, col 0 is the LEFT.
    rgb:        a (r, g, b) tuple or list, each 0..254. (255 is reserved by the
                firmware; values are clamped for you.)
"""

from __future__ import annotations

import numpy as np


class GridClient:
    def __init__(self, backend):
        """`backend` is any object implementing the backend interface:
        .layout, .set_frame(), .get_switch_state(). (GridController or the sim.)
        """
        self._backend = backend
        self.layout = backend.layout

        # The game's working surface. Games draw into this (directly or via the
        # helpers) and it is pushed to the backend once per update via _flush(),
        # which run.py / run_sim.py call for them.
        self._frame = self.layout.empty_frame()

        # Cache of the latest switch snapshot for this frame, refreshed by
        # _refresh_input() at the top of each update tick. Also keep the
        # previous snapshot so we can offer edge-triggered "just pressed".
        self._pressed = np.zeros((self.rows, self.cols), dtype=bool)
        self._prev_pressed = np.zeros((self.rows, self.cols), dtype=bool)

    # ---------------------------------------------------------- dimensions
    @property
    def rows(self) -> int:
        return self.layout.rows

    @property
    def cols(self) -> int:
        return self.layout.cols

    @property
    def shape(self) -> tuple[int, int]:
        return (self.rows, self.cols)

    # ------------------------------------------------------------- drawing
    def clear(self, rgb=(0, 0, 0)) -> None:
        """Fill the whole floor with one colour (default: off)."""
        self._frame[:, :] = rgb

    def set_pixel(self, row: int, col: int, rgb) -> None:
        """Set a single pixel. Out-of-range coordinates are ignored so games
        can't crash on an off-floor write."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self._frame[row, col] = rgb

    def get_pixel(self, row: int, col: int):
        """Return the current (r, g, b) of a pixel as a tuple."""
        r, g, b = self._frame[row, col]
        return (int(r), int(g), int(b))

    def fill_rect(self, row0: int, col0: int, row1: int, col1: int, rgb) -> None:
        """Fill an inclusive rectangle of pixels. Coordinates are clamped to
        the floor."""
        r0, r1 = sorted((max(0, row0), min(self.rows - 1, row1)))
        c0, c1 = sorted((max(0, col0), min(self.cols - 1, col1)))
        self._frame[r0:r1 + 1, c0:c1 + 1] = rgb

    def set_frame(self, frame: np.ndarray) -> None:
        """Replace the whole surface at once with a (rows, cols, 3) array.
        Handy for games that compute the entire floor themselves (e.g. video)."""
        if frame.shape != (self.rows, self.cols, 3):
            raise ValueError(
                f"frame shape {frame.shape} != ({self.rows}, {self.cols}, 3)"
            )
        np.copyto(self._frame, frame.astype(np.uint8, copy=False))

    @property
    def frame(self) -> np.ndarray:
        """Direct access to the working surface for numpy-native games.
        Mutating this array in place is fully supported."""
        return self._frame

    # --------------------------------------------------------------- input
    def is_pressed(self, row: int, col: int) -> bool:
        """True if the switch under this pixel is currently held."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return bool(self._pressed[row, col])
        return False

    def just_pressed(self, row: int, col: int) -> bool:
        """True only on the frame a press first appears (edge-triggered)."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return bool(self._pressed[row, col] and not self._prev_pressed[row, col])
        return False

    def just_released(self, row: int, col: int) -> bool:
        """True only on the frame a press disappears (edge-triggered)."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return bool(self._prev_pressed[row, col] and not self._pressed[row, col])
        return False

    def pressed_coords(self) -> list[tuple[int, int]]:
        """List of (row, col) for every currently-held pixel."""
        rs, cs = np.where(self._pressed)
        return list(zip(rs.tolist(), cs.tolist()))

    def pressed_mask(self) -> np.ndarray:
        """The full (rows, cols) boolean press grid (a copy)."""
        return self._pressed.copy()

    # ------------------------------------------------- runner-facing hooks
    # These are called by run.py / run_sim.py around each game update — game
    # authors don't normally call them.
    def _refresh_input(self) -> None:
        """Pull the latest switch snapshot from the backend and roll the edge
        state forward. Called once at the start of each frame."""
        self._prev_pressed = self._pressed
        self._pressed = self._backend.get_switch_state()

    def _flush(self) -> None:
        """Push the working surface to the backend for display/transmit."""
        self._backend.set_frame(self._frame)
