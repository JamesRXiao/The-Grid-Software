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
import random

import numpy as np
class MyGame(Game):
    # Optional: a target frame rate and a display name.
    fps = 30
    time_update = 0.5
    name = "My Game"

    def setup(self, client):
        """Runs once before the first frame. Set up your state here."""
        # Example: remember the floor size and start with a blank floor.
        self.rows = client.rows
        self.cols = client.cols
        self.grid = np.zeros([client.rows+2, client.cols+2], dtype = int)
        self.time_since_last_update = 0
        client.clear()

    def update(self, client, dt):
        """Runs every frame. `dt` is seconds since the last update.

        Use `dt` for anything time-based (movement, animation) so your game
        looks the same regardless of the exact frame rate.
        """
        # Start from a clean floor each frame (remove this if you want to draw
        # cumulatively instead).
        client.clear()

        # --- Example: light every pressed pixel white -----------------------
        for (row, col) in client.pressed_coords():
            client.set_pixel(row, col, (254, 254, 254))

        self.time_since_last_update += dt
        if self.time_since_last_update > self.time_update:
            self.time_since_last_update -= self.time_update
            new_grid = np.zeros_like(self.grid)
            for x in range(1, self.rows+1):
                for y in range(1, self.cols+1):
                    cnt = 0
                    for (dx, dy) in [(-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1)]:
                        cnt += self.grid[x+dx][y+dy]
                    
                    if cnt == 3 and self.grid[x][y] == 0:
                        new_grid[x][y] = 1
                    if cnt == 2 or cnt == 3 and self.grid[x][y] == 1:
                        new_grid[x][y] = 1
            self.grid = new_grid
        
        for x in range(1, self.rows+1):
            for y in range(1, self.cols+1):
                if client.just_pressed(x-1, y-1):
                    for (dx, dy) in [(0, 0), (-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1)]:
                        if x + dx == 0 or y + dy == 0 or x + dx == self.rows +1 or y + dy == self.cols+1:
                            continue
                        self.grid[x+dx][y+dy] ^= 1#max(0, random.randint(0, 5)-4)
        
        for x in range(1, self.rows+1):
            for y in range(1, self.cols+1):
                client.set_pixel(x-1, y-1, (self.grid[x][y]*255,self.grid[x][y]*255,self.grid[x][y]*255))
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
