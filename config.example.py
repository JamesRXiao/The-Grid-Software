"""
config.example.py — copy this to config.py and edit for your machine.

    cp config.example.py config.py     # then edit config.py

config.py is gitignored so everyone's local port/settings stay out of the repo.
Game code never reads this file — only the runners (run.py / run_sim.py) do.
"""

# Serial port the controller board is on.
#   Windows: "COM3", "COM5", ...
#   macOS:   "/dev/tty.usbmodemXXXX"
#   Linux:   "/dev/ttyACM0"
PORT = "COM3"

# Which floor layout to use. Point this at a different file in layouts/ to
# switch floor shapes without touching any other code.
LAYOUT = "layouts/default.json"

# Advisory default frame rate. A game can override via its `fps` attribute.
# On real hardware the firmware still enforces the true minimum inter-frame gap,
# so this is a ceiling on how often we bother sending, not a guarantee.
FPS = 24

# Nominal baud rate. Ignored by the USB-CDC driver but pyserial requires a value.
BAUDRATE = 460800

# Transparently retry the serial connection if the port drops (cable wobble,
# OS reassigning the COM port, board reset).
RECONNECT = True
