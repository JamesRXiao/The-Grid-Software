"""
AUTHOR: erich

game_template.py — copy this file to start a new game.

    1. Copy this file in the games/ folder and rename it, e.g. my_game.py
    2. Rename the class if you like (the runner finds the Game subclass for you).
    3. Fill in setup() and update().
    4. Run it:
           python run_sim.py games/my_game.py     # in the pygame simulator
           python run.py     games/my_game.py     # on the real floor

You only ever interact with `client` (a GridClient). You never touch the SDK,
serial ports, or module IDs.

The floor is a grid of pixels addressed as (row, col):
    * row 0 is the TOP, col 0 is the LEFT
    * client.rows and client.cols give the size (don't hard-code it —
      it comes from the active layout, so your game works on any floor shape)

Colours are (r, g, b) tuples, each 0..254.
"""

from sdk import Game

import numpy as np
import math


class MyGame(Game):
    # Optional: a target frame rate and a display name.
    fps = 30
    scale = 5 # must be odd for good
    wave_constant = scale*2.0
    friction_constant = 10.0 / scale
    name = "Wave Sim"

    def setup(self, client):
        """Runs once before the first frame. Set up your state here."""
        # Example: remember the floor size and start with a blank floor.
        
        scale = self.scale
        self.rows = client.rows
        self.cols = client.cols

        self.h = np.zeros([self.rows*scale + 2, self.cols*scale + 2])
        self.v = np.zeros([self.rows*scale + 2, self.cols*scale + 2])
        self.a = np.zeros([self.rows*scale + 2, self.cols*scale + 2])
        client.clear()

    def update(self, client, dt):
        """Runs every frame. `dt` is seconds since the last update.

        Use `dt` for anything time-based (movement, animation) so your game
        looks the same regardless of the exact frame rate.
        """
        scale = self.scale
        wave_constant = self.wave_constant
        friction_constant = self.friction_constant
        # Start from a clean floor each frame (remove this if you want to draw
        # cumulatively instead).
        client.clear()

        # --- Example: light every pressed pixel white -----------------------
        for (row, col) in client.pressed_coords():
            client.set_pixel(row, col, (254, 254, 254))

        for x in range(1, self.rows*scale+1):
            for y in range(1, self.cols*scale+1):
                dh = 0
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    dh += self.h[x+dx][y+dy] - self.h[x][y]
                self.v[x][y] += dh * wave_constant * dt
                self.v[x][y] += self.a[x][y] * dt
                self.v[x][y] *= math.exp(-friction_constant * dt)
                self.a[x][y] *= math.exp(-10 * dt)
            
        for x in range(1, self.rows*scale+1):
            for y in range(1, self.cols*scale+1):
                self.h[x][y] += self.v[x][y]

        for x in range(0, self.rows):
            for y in range(0, self.cols):

                if client.just_pressed(x, y):
                    self.a[x*scale + (scale//2)+1][y*scale + (scale//2)+1] += 20
                    
                h_avg = 0
                for x2 in range(x*scale+1, (x+1)*scale+1):
                    for y2 in range(y*scale+1, (y+1)*scale+1):
                        h_avg += self.h[x2][y2]
                h_avg /= (scale*scale)

                brightness = 255 * (1 / (1 + math.exp(-(h_avg - 0.1)*55)))
                client.set_pixel(x, y, (brightness, brightness, brightness))

        # --- Handy things you can do ----------------------------------------
        # client.set_pixel(row, col, (r, g, b))       set one pixel
        # client.fill_rect(r0, c0, r1, c1, (r,g,b))   fill a rectangle
        # client.clear((r, g, b))                     fill whole floor
        # client.frame[...]                           numpy array, edit directly
        #
        # client.is_pressed(row, col)                 held right now?
        # client.just_pressed(row, col)               pressed this frame?
        # client.just_released(row, col)              released this frame?
        # client.pressed_coords()                     list of (row, col) held

    def teardown(self, client):
        """Runs once when the game stops. Optional — clean up here."""
        pass
