"""
controller.py — the real-hardware backend.

GridController owns the serial port and two background threads:

  * TX thread: on its own cadence, grabs whatever is currently in the shared
    frame buffer, serialises it to wire bytes, and writes it out. It does NOT
    wait for the game to produce a frame; it sends the latest one available.
    (The controller firmware enforces the true inter-frame gap, so Python
    pacing here is "best effort" — see docs/README.)

  * RX thread: continuously reads switch-data replies and updates a shared
    switch-state array.

Everything the backend exposes is via a small, stable interface that GridClient
depends on. A simulator backend (sim/sim_backend.py) implements the same
interface, so GridClient — and therefore game code — is identical whether it is
driving real hardware or the sim.

Backend interface (shared with the sim)
---------------------------------------
    layout                      -> ModuleLayout
    start()                     -> None
    stop()                      -> None
    set_frame(frame_array)      -> None      # (rows, cols, 3) uint8
    get_switch_state()          -> np.ndarray of shape (rows, cols) bool
    fps                         -> float     # advisory target
"""

from __future__ import annotations

import threading
import time

import numpy as np
import serial

from .layout import ModuleLayout


class GridController:
    def __init__(
        self,
        port: str,
        layout: ModuleLayout,
        baudrate: int = 460800,
        fps: float = 24.0,
        reconnect: bool = True,
    ):
        """
        port       : serial port name, e.g. 'COM3' or '/dev/ttyACM0'
        layout     : a ModuleLayout describing the floor
        baudrate   : nominal only for USB-CDC (the value is ignored by the CDC
                     driver) but pyserial requires one; kept for real UART setups.
        fps        : advisory target frame rate for the TX thread. The firmware
                     enforces the real minimum inter-frame time; this just caps
                     how often we bother sending.
        reconnect  : if True, transparently retry opening the port if it drops.
        """
        self.layout = layout
        self.port = port
        self.baudrate = baudrate
        self.fps = fps
        self.reconnect = reconnect

        # --- shared state, protected by _lock -------------------------------
        self._lock = threading.Lock()
        # The canonical game surface. Games write here (via GridClient); the TX
        # thread reads it. (rows, cols, 3) uint8.
        self._frame = layout.empty_frame()
        # Latest known switch state as a boolean grid aligned to the pixels.
        self._switch_grid = np.zeros((layout.rows, layout.cols), dtype=bool)

        # --- lifecycle ------------------------------------------------------
        self._stop_evt = threading.Event()
        self._ser: serial.Serial | None = None
        self._tx_thread: threading.Thread | None = None
        self._rx_thread: threading.Thread | None = None

    # --------------------------------------------------------------- serial
    def _open_serial(self) -> None:
        """Open (or reopen) the serial port. Retries while reconnect is on and
        we have not been asked to stop."""
        while not self._stop_evt.is_set():
            try:
                self._ser = serial.Serial(self.port, self.baudrate, timeout=0.02)
                print(f"[GridController] connected on {self.port}")
                return
            except (serial.SerialException, OSError) as e:
                if not self.reconnect:
                    raise
                print(f"[GridController] open failed ({e}); retrying in 1s...")
                # Wait, but stay responsive to stop().
                self._stop_evt.wait(1.0)

    def _ensure_serial(self) -> bool:
        """Return True if we have a usable, open port; try to (re)open otherwise.
        Returns False only if we are stopping."""
        if self._ser is not None and self._ser.is_open:
            return True
        self._open_serial()
        return self._ser is not None and self._ser.is_open

    # ------------------------------------------------------------ tx thread
    def _tx_loop(self) -> None:
        interval = 1.0 / self.fps
        while not self._stop_evt.is_set():
            loop_start = time.perf_counter()

            if not self._ensure_serial():
                break  # stopping

            # Snapshot the frame under the lock, then do the (slower)
            # serialisation + write outside the lock so we never block the game
            # thread for long.
            with self._lock:
                frame_copy = self._frame.copy()

            wire = self.layout.to_wire_bytes(frame_copy)

            try:
                self._ser.write(wire)
            except (serial.SerialException, OSError) as e:
                print(f"[GridController] write failed ({e}); will reconnect")
                self._close_port_quietly()
                continue  # loop back, _ensure_serial will reopen

            # Pace to the advisory FPS. Sleep in small slices so stop() is snappy.
            elapsed = time.perf_counter() - loop_start
            remaining = interval - elapsed
            if remaining > 0:
                self._stop_evt.wait(remaining)

    # ------------------------------------------------------------ rx thread
    def _rx_loop(self) -> None:
        """Parse 2-byte [node_id, switch_bits] replies from the stream.

        Robust framing: rather than assuming reads land on packet boundaries
        (USB-CDC may batch or split them), we accumulate bytes and validate
        candidate packets. A packet is [node_id, bits] where node_id is in the
        valid module-id range and bits has no illegal high nibble set. If the
        lead byte isn't a plausible node_id we drop exactly one byte and resync,
        rather than deleting from the front of a growing bytearray each time.
        """
        from collections import deque

        valid_ids = set(self.layout.module_ids())
        # Upper 4 bits of the switch byte must be zero (only 4 switches/module).
        HIGH_NIBBLE = 0xF0

        rx = deque()  # bytes waiting to be parsed; O(1) popleft
        # Adaptive read size: ask for a modest chunk; timeout keeps us responsive.
        READ_SIZE = 64

        while not self._stop_evt.is_set():
            if not self._ensure_serial():
                break

            try:
                chunk = self._ser.read(READ_SIZE)
            except (serial.SerialException, OSError) as e:
                print(f"[GridController] read failed ({e}); will reconnect")
                self._close_port_quietly()
                continue

            if chunk:
                rx.extend(chunk)

            # Parse as many whole, plausible packets as we can.
            while len(rx) >= 2:
                node_id = rx[0]
                bits = rx[1]

                # Validate the candidate packet.
                if node_id in valid_ids and (bits & HIGH_NIBBLE) == 0:
                    rx.popleft()  # consume node_id
                    rx.popleft()  # consume bits
                    self._apply_switch(node_id, bits)
                else:
                    # Misaligned: drop one byte and try to resync on the next.
                    rx.popleft()

    def _apply_switch(self, module_id: int, bits: int) -> None:
        """Update the shared switch grid from one module's reply."""
        pressed_coords = self.layout.switch_bits_to_coords(module_id, bits)
        with self._lock:
            # Clear this module's pixels first, then set the pressed ones.
            for (r, c) in self.layout.coords_for_module(module_id):
                self._switch_grid[r, c] = False
            for (r, c) in pressed_coords:
                self._switch_grid[r, c] = True

    # --------------------------------------------------------- backend API
    def set_frame(self, frame: np.ndarray) -> None:
        """Replace the current frame. Called by GridClient. Non-blocking."""
        with self._lock:
            # Copy in so the caller can keep mutating their own array freely.
            np.copyto(self._frame, frame)

    def get_switch_state(self) -> np.ndarray:
        """Return a copy of the current (rows, cols) boolean pressed-grid."""
        with self._lock:
            return self._switch_grid.copy()

    def start(self) -> None:
        self._stop_evt.clear()
        self._tx_thread = threading.Thread(target=self._tx_loop, name="grid-tx", daemon=True)
        self._rx_thread = threading.Thread(target=self._rx_loop, name="grid-rx", daemon=True)
        self._tx_thread.start()
        self._rx_thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        for t in (self._tx_thread, self._rx_thread):
            if t is not None:
                t.join(timeout=1.0)
        self._close_port_quietly()

    # --------------------------------------------------------------- helpers
    def _close_port_quietly(self) -> None:
        try:
            if self._ser is not None and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        self._ser = None
