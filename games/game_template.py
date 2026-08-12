"""
AUTHOR: YOUR_NAME_HERE

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


class MyGame(Game):
    # Optional: a target frame rate and a display name.
    fps = 30
    name = "My Game"

    def setup(self, client):
        """Runs once before the first frame. Set up your state here."""
        # Example: remember the floor size and start with a blank floor.
        self.rows = client.rows
        self.cols = client.cols
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
