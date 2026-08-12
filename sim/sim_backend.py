"""
sim_backend.py — a drop-in replacement for GridController that renders to a
pygame window instead of driving real hardware, and turns mouse clicks on tiles
into microswitch presses.

It implements the exact same backend interface GridClient expects:

    layout, start(), stop(), set_frame(frame), get_switch_state()

so GridClient — and therefore your game — is byte-for-byte identical whether it
runs here or on the real floor.

Rendering runs on the main thread (pygame requires this on most platforms), so
unlike the real controller there are no background threads: the runner calls
set_frame() each tick, and the sim also exposes pump()/should_run so the sim
runner can service window events and redraw in lock-step with the game loop.

Nothing here is hard-coded to a particular floor size — every dimension comes
from the layout.
"""

from __future__ import annotations

import numpy as np

try:
    import pygame
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "pygame is required for the simulator. Install it with:\n"
        "    pip install pygame"
    ) from e


class SimBackend:
    #: Size of each pixel tile in the window, in screen pixels.
    TILE = 28
    #: Gap between tiles, in screen pixels.
    GAP = 3
    #: Window background.
    BG = (18, 18, 20)
    #: Colour of an "off" tile (so the grid is visible even when dark).
    OFF_TILE = (34, 34, 38)
    #: Outline drawn around a tile whose switch is currently pressed.
    PRESS_OUTLINE = (255, 255, 255)

    def __init__(self, layout, title: str = "The Grid — Simulator"):
        self.layout = layout
        self.rows = layout.rows
        self.cols = layout.cols
        self._title = title

        # Shared state (single-threaded here, but kept behind the same methods
        # as the real backend for a clean swap).
        self._frame = layout.empty_frame()
        self._switch_grid = np.zeros((self.rows, self.cols), dtype=bool)

        self._screen = None
        self._running = False

        # Which tile the mouse is currently holding down (a press), if any.
        self._mouse_tile: tuple[int, int] | None = None

    # --------------------------------------------------------- backend API
    def start(self) -> None:
        pygame.init()
        pygame.display.set_caption(self._title)
        w = self.GAP + self.cols * (self.TILE + self.GAP)
        h = self.GAP + self.rows * (self.TILE + self.GAP)
        self._screen = pygame.display.set_mode((w, h))
        self._running = True

    def stop(self) -> None:
        self._running = False
        pygame.quit()

    def set_frame(self, frame: np.ndarray) -> None:
        np.copyto(self._frame, frame)

    def get_switch_state(self) -> np.ndarray:
        return self._switch_grid.copy()

    # ----------------------------------------------------- sim-only extras
    @property
    def running(self) -> bool:
        return self._running

    def pump(self) -> None:
        """Service window events and redraw. The sim runner calls this once per
        frame (after the game has drawn). Handles quit + mouse-as-switch."""
        self._handle_events()
        self._draw()

    # --------------------------------------------------------------- guts
    def _tile_at_pixel(self, x: int, y: int) -> tuple[int, int] | None:
        """Map a screen (x, y) to a (row, col) tile, or None if in a gap."""
        stride = self.TILE + self.GAP
        col = (x - self.GAP) // stride
        row = (y - self.GAP) // stride
        # Reject clicks that landed in the gap between tiles.
        in_col = self.GAP + col * stride <= x < self.GAP + col * stride + self.TILE
        in_row = self.GAP + row * stride <= y < self.GAP + row * stride + self.TILE
        if in_col and in_row and 0 <= row < self.rows and 0 <= col < self.cols:
            return (int(row), int(col))
        return None

    def _set_press(self, tile: tuple[int, int] | None, pressed: bool) -> None:
        if tile is None:
            return
        r, c = tile
        self._switch_grid[r, c] = pressed

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                tile = self._tile_at_pixel(*event.pos)
                if tile is not None:
                    self._mouse_tile = tile
                    self._set_press(tile, True)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Release whatever we were holding.
                self._set_press(self._mouse_tile, False)
                self._mouse_tile = None

            elif event.type == pygame.MOUSEMOTION and self._mouse_tile is not None:
                # Dragging: move the held press from tile to tile so you can
                # "swipe" across switches.
                tile = self._tile_at_pixel(*event.pos)
                if tile != self._mouse_tile:
                    self._set_press(self._mouse_tile, False)
                    self._mouse_tile = tile
                    self._set_press(tile, True)

    def _draw(self) -> None:
        self._screen.fill(self.BG)
        stride = self.TILE + self.GAP
        for r in range(self.rows):
            for c in range(self.cols):
                cr, cg, cb = self._frame[r, c]
                colour = (int(cr), int(cg), int(cb))
                # Show the faint off-tile colour when a pixel is fully dark, so
                # the grid stays legible.
                if colour == (0, 0, 0):
                    colour = self.OFF_TILE
                x = self.GAP + c * stride
                y = self.GAP + r * stride
                rect = pygame.Rect(x, y, self.TILE, self.TILE)
                pygame.draw.rect(self._screen, colour, rect, border_radius=4)
                if self._switch_grid[r, c]:
                    pygame.draw.rect(self._screen, self.PRESS_OUTLINE, rect, width=2, border_radius=4)
        pygame.display.flip()
