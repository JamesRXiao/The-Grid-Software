"""
layout.py — physical floor geometry, loaded from a layout JSON file.

The rest of the SDK (and every game) thinks purely in terms of a numpy array
of shape (rows, cols, 3): row 0 is the top of the floor, col 0 is the left,
and the last axis is RGB. This module is the *only* place that knows how those
(row, col) pixel coordinates map onto physical modules and the byte order the
firmware expects on the wire.

Because all of that mapping is derived from the layout JSON at load time,
changing the floor's shape or wiring is a data change (a new JSON file), never
a code change. Games never import this module directly.

Key concepts
------------
* Pixel grid:   rows x cols individually-addressable pixels. The whole floor.
* Module grid:  the floor is tiled by modules. Each module is 1 pixel-row tall
                and `pixels_per_module` pixel-cols wide. So the module grid is
                (rows) x (cols / pixels_per_module).
* Snake:        module IDs are assigned by walking the module grid in a
                serpentine order (see the JSON's "snake" block).
* Pixel order:  within a module, which physical pixel is index 0.

The firmware frame layout this produces:
    byte 0            : 0xFF header/sentinel
    bytes 1..12       : module 1  -> pixel0 RGB, pixel1 RGB, pixel2 RGB, pixel3 RGB
    bytes 13..24      : module 2  -> ...
    ...
    (module N occupies bytes  (N-1)*12 + 1  ..  (N-1)*12 + 12 )
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


# The firmware reserves 0xFF (255) as the frame-start sentinel, so no colour
# channel may ever be exactly 255 — it could otherwise be mistaken for a header
# during a resync. Every value written to the wire is clamped to this max.
MAX_CHANNEL_VALUE = 0xFE  # 254


class ModuleLayout:
    """Bidirectional map between the (row, col) pixel grid and the on-wire
    per-module byte order, built entirely from a layout JSON file."""

    def __init__(self, layout_path: str | Path):
        self.path = Path(layout_path)
        with open(self.path, "r") as f:
            cfg = json.load(f)

        # --- basic dimensions ------------------------------------------------
        self.name: str = cfg.get("name", self.path.stem)
        self.rows: int = int(cfg["rows"])
        self.cols: int = int(cfg["cols"])
        self.pixels_per_module: int = int(cfg["pixels_per_module"])
        self.first_module_id: int = int(cfg.get("first_module_id", 1))

        if self.cols % self.pixels_per_module != 0:
            raise ValueError(
                f"cols ({self.cols}) must be divisible by pixels_per_module "
                f"({self.pixels_per_module})"
            )

        # Module grid dimensions. A module is 1 pixel-row tall and
        # pixels_per_module pixel-cols wide, so:
        self.module_rows: int = self.rows
        self.module_cols: int = self.cols // self.pixels_per_module

        # Cross-check against any explicit values in the JSON (defensive: catches
        # a mis-written layout file early rather than as garbled output later).
        if "module_rows" in cfg and int(cfg["module_rows"]) != self.module_rows:
            raise ValueError("module_rows in layout JSON disagrees with rows/pixels_per_module")
        if "module_cols" in cfg and int(cfg["module_cols"]) != self.module_cols:
            raise ValueError("module_cols in layout JSON disagrees with cols/pixels_per_module")

        self.n_modules: int = self.module_rows * self.module_cols

        # --- snake / pixel-order config -------------------------------------
        snake = cfg.get("snake", {})
        self.snake_start: str = snake.get("start", "top_left")
        self.snake_primary_axis: str = snake.get("primary_axis", "vertical")
        self.snake_serpentine: bool = bool(snake.get("serpentine", True))
        self.pixel_order: str = cfg.get("pixel_order", "left_to_right")

        # --- frame sizing ----------------------------------------------------
        # 1 header byte + 3 bytes per pixel for every pixel on the floor.
        self.frame_len: int = 1 + self.n_modules * self.pixels_per_module * 3

        # --- build the lookup tables ----------------------------------------
        # For each module id we store the list of (row, col) pixel coordinates
        # it drives, ordered by physical pixel index 0..pixels_per_module-1.
        # This is what lets us pour a (rows, cols, 3) array into wire order fast.
        self._module_pixel_coords: dict[int, list[tuple[int, int]]] = {}
        self._build_maps()

        # Precompute a flat index array so serialisation is a couple of numpy
        # ops instead of a Python loop over every pixel each frame.
        self._build_serialisation_index()

    # ------------------------------------------------------------------ maps
    def _module_id_at(self, mrow: int, mcol: int) -> int:
        """Return the module ID sitting at module-grid cell (mrow, mcol),
        following the configured snake pattern."""
        # Normalise the starting corner into (row_from_top, col_from_left) plus
        # the direction the primary axis initially travels.
        start = self.snake_start
        top = "top" in start
        left = "left" in start

        if self.snake_primary_axis == "vertical":
            # IDs increment down (or up) a column first, then step columns.
            # Column order (which physical module-column is "first"):
            col_index = mcol if left else (self.module_cols - 1 - mcol)

            # Within this column, does the walk go top->bottom or bottom->top?
            # The very first column goes in the "start" vertical direction;
            # if serpentine, every other column flips.
            base_down = top  # first column travels downward when start is a top corner
            if self.snake_serpentine and (col_index % 2 == 1):
                going_down = not base_down
            else:
                going_down = base_down

            row_in_line = mrow if going_down else (self.module_rows - 1 - mrow)
            ordinal = col_index * self.module_rows + row_in_line

        else:  # primary_axis == "horizontal"
            # IDs increment across a row first, then step rows.
            row_index = mrow if top else (self.module_rows - 1 - mrow)

            base_right = left  # first row travels rightward when start is a left corner
            if self.snake_serpentine and (row_index % 2 == 1):
                going_right = not base_right
            else:
                going_right = base_right

            col_in_line = mcol if going_right else (self.module_cols - 1 - mcol)
            ordinal = row_index * self.module_cols + col_in_line

        return self.first_module_id + ordinal

    def _build_maps(self) -> None:
        """Populate _module_pixel_coords: module_id -> [(row,col), ...]."""
        for mrow in range(self.module_rows):
            for mcol in range(self.module_cols):
                module_id = self._module_id_at(mrow, mcol)

                # This module occupies one pixel-row (== mrow) and a horizontal
                # run of pixels_per_module pixel-columns starting here:
                base_col = mcol * self.pixels_per_module
                coords = []
                for p in range(self.pixels_per_module):
                    if self.pixel_order == "left_to_right":
                        col = base_col + p
                    elif self.pixel_order == "right_to_left":
                        col = base_col + (self.pixels_per_module - 1 - p)
                    else:
                        raise ValueError(f"unknown pixel_order: {self.pixel_order}")
                    coords.append((mrow, col))

                self._module_pixel_coords[module_id] = coords

    def _build_serialisation_index(self) -> None:
        """Precompute, for the flattened frame body, which (row, col) pixel
        feeds each position — so to_wire_bytes() is pure numpy indexing."""
        # Wire body order is module 1's 4 pixels, module 2's 4 pixels, ...
        rows_idx = []
        cols_idx = []
        for module_id in range(self.first_module_id, self.first_module_id + self.n_modules):
            for (r, c) in self._module_pixel_coords[module_id]:
                rows_idx.append(r)
                cols_idx.append(c)
        # Advanced-indexing arrays: frame[rows_idx, cols_idx] yields pixels in
        # exact wire order, shape (n_pixels, 3).
        self._ser_rows = np.asarray(rows_idx, dtype=np.intp)
        self._ser_cols = np.asarray(cols_idx, dtype=np.intp)

    # ---------------------------------------------------------------- public
    def coords_for_module(self, module_id: int) -> list[tuple[int, int]]:
        """The (row, col) pixels driven by a module, in physical pixel order."""
        return list(self._module_pixel_coords[module_id])

    def module_ids(self) -> list[int]:
        """All module IDs, ascending."""
        return list(range(self.first_module_id, self.first_module_id + self.n_modules))

    def empty_frame(self) -> np.ndarray:
        """A blank (rows, cols, 3) uint8 array — the canonical game surface."""
        return np.zeros((self.rows, self.cols, 3), dtype=np.uint8)

    def to_wire_bytes(self, frame: np.ndarray) -> bytes:
        """Convert a (rows, cols, 3) array into the exact 589-byte-style buffer
        the firmware expects: 0xFF header, then each module's pixels in order.

        Colours are clamped to MAX_CHANNEL_VALUE so a real 255 can never be
        mistaken for the frame sentinel on the wire.
        """
        if frame.shape != (self.rows, self.cols, 3):
            raise ValueError(
                f"frame shape {frame.shape} != expected ({self.rows}, {self.cols}, 3)"
            )

        # Gather pixels in wire order and clamp in one vectorised pass.
        body = frame[self._ser_rows, self._ser_cols]          # (n_pixels, 3)
        body = np.minimum(body, MAX_CHANNEL_VALUE).astype(np.uint8)

        out = bytearray(self.frame_len)
        out[0] = 0xFF
        out[1:] = body.tobytes()
        return bytes(out)

    def switch_bits_to_coords(self, module_id: int, bits: int) -> list[tuple[int, int]]:
        """Given a module's raw 4-bit switch byte, return the (row, col) of each
        pressed pixel. Switch bit i corresponds to physical pixel index i, whose
        (row, col) we already know from the module map."""
        coords = self._module_pixel_coords.get(module_id, [])
        pressed = []
        for i in range(self.pixels_per_module):
            if bits & (1 << i):
                if i < len(coords):
                    pressed.append(coords[i])
        return pressed

    def __repr__(self) -> str:
        return (
            f"<ModuleLayout {self.name!r} {self.rows}x{self.cols} px, "
            f"{self.n_modules} modules, frame_len={self.frame_len}>"
        )
