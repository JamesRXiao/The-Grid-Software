"""
press_color.py — light each pressed pixel a random colour.

The simplest possible interactive example. While a switch is held, its pixel
shows a colour; each newly-pressed pixel gets a fresh random colour that stays
put until released. Released pixels go dark.

Run it:
    python run_sim.py examples/press_color.py     # simulator (click tiles)
    python run.py     examples/press_color.py     # real floor
"""

import random

from sdk import Game


class PressColor(Game):
    name = "Press = Colour"
    fps = 30

    def setup(self, client):
        # Remember the colour chosen for each currently-held pixel, keyed by
        # (row, col). We only re-roll a colour on a fresh press, so a held
        # pixel stays a steady colour rather than flickering every frame.
        self._colours = {}

    def update(self, client, dt):
        client.clear()

        for (row, col) in client.pressed_coords():
            key = (row, col)
            # Assign a colour the moment this pixel is first pressed.
            if key not in self._colours:
                self._colours[key] = (
                    random.randint(0, 254),
                    random.randint(0, 254),
                    random.randint(0, 254),
                )
            client.set_pixel(row, col, self._colours[key])

        # Forget colours for pixels that are no longer held, so the next press
        # gets a new random colour.
        held = set(client.pressed_coords())
        for key in list(self._colours.keys()):
            if key not in held:
                del self._colours[key]
