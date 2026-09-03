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
        # Set by the TX thread once the port is open; cleared on disconnect.
        # The RX thread waits on this before reading, so it never races to open
        # the port or reads from a None/closed serial object.
        self._port_ready = threading.Event()
        self._ser: serial.Serial | None = None
        self._tx_thread: threading.Thread | None = None
        self._rx_thread: threading.Thread | None = None

    # --------------------------------------------------------------- serial
    def _open_serial(self) -> None:
        """Open (or reopen) the serial port. Only ever called by the TX thread —
        the TX thread is the sole owner of the port's lifecycle. Retries until
        successful or stop() is called, then signals _port_ready so the RX
        thread knows it is safe to start reading."""
        while not self._stop_evt.is_set():
            try:
                self._ser = serial.Serial(self.port, self.baudrate, timeout=0.02)
                print(f"[GridController] connected on {self.port}")
                self._port_ready.set()   # unblock the RX thread
                return
            except (serial.SerialException, OSError) as e:
                if not self.reconnect:
                    raise
                print(f"[GridController] open failed ({e}); retrying in 1s...")
                self._stop_evt.wait(1.0)

    # ------------------------------------------------------------ tx thread
    def _tx_loop(self) -> None:
        """The TX thread owns the serial port — it opens it, sends frames, and
        if the port drops it closes it, clears _port_ready (pausing the RX
        thread), and reconnects. The RX thread never calls open/close itself,
        so there is never a race to open the same port twice."""
        interval = 1.0 / self.fps
        self._open_serial()   # open once before entering the loop

        while not self._stop_evt.is_set():
            loop_start = time.perf_counter()

            # Snapshot the frame under the lock, then serialise + write outside
            # the lock so we never block the game thread for long.
            with self._lock:
                frame_copy = self._frame.copy()

            wire = self.layout.to_wire_bytes(frame_copy)

            try:
                self._ser.write(wire)
            except (serial.SerialException, OSError) as e:
                print(f"[GridController] write failed ({e}); reconnecting...")
                self._port_ready.clear()   # tell RX thread: port is gone
                self._close_port_quietly()
                self._open_serial()        # TX thread reconnects exclusively
                continue

            elapsed = time.perf_counter() - loop_start
            remaining = interval - elapsed
            if remaining > 0:
                self._stop_evt.wait(remaining)

    def _clear_module(self, module_id: int) -> None:
        """Set all switches for a module to unpressed. Called when a module
        goes silent — firmware only transmits when something is pressed."""
        with self._lock:
            for (r, c) in self.layout.coords_for_module(module_id):
                self._switch_grid[r, c] = False

    # ------------------------------------------------------------ rx thread
    def _rx_loop(self) -> None:
        from collections import deque
        import time

        valid_ids = set(self.layout.module_ids())
        HIGH_NIBBLE = 0xF0
        READ_SIZE = 64

        rx: deque = deque()

        # Track when we last heard from each module (seconds, perf_counter).
        # If a module goes silent for longer than SILENCE_TIMEOUT, its switches
        # are assumed released — handles the case where firmware only transmits
        # when something is pressed.
        SILENCE_TIMEOUT = 0.099
        last_seen: dict[int, float] = {}

        while not self._stop_evt.is_set():
            if not self._port_ready.wait(timeout=0.1):
                continue

            now = time.perf_counter()

            # Clear any module that has gone quiet for longer than the timeout.
            for module_id in list(last_seen.keys()):
                if now - last_seen[module_id] > SILENCE_TIMEOUT:
                    self._clear_module(module_id)
                    del last_seen[module_id]

            try:
                chunk = self._ser.read(READ_SIZE)
            except (serial.SerialException, OSError) as e:
                print(f"[GridController] read failed ({e}); waiting for reconnect")
                self._port_ready.clear()
                rx.clear()
                last_seen.clear()
                continue

            if chunk:
                rx.extend(chunk)

            while len(rx) >= 2:
                node_id = rx[0]
                bits    = rx[1]

                if node_id in valid_ids and (bits & HIGH_NIBBLE) == 0:
                    rx.popleft()
                    rx.popleft()
                    last_seen[node_id] = time.perf_counter()
                    self._apply_switch(node_id, bits)
                else:
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
        self._port_ready.clear()   # TX thread will set this once port is open
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