"""
AUTHOR: Annabella Du

game_template.py — copy this file to start a new game.

    1. Copy this file in the games/ folder and rename it, e.g. my_game.py
    2. Rename the class if you like (the runner finds the Game subclass for you).
    3. Fill in setup() and update().
    4. Run it:
           python run_sim.py games/pong.py     # in the pygame simulator
           python run.py     games/pong.py     # on the real floor

You only ever interact with `client` (a GridClient). You never touch the SDK,
serial ports, or module IDs.

The floor is a grid of pixels addressed as (row, col):
    * row 0 is the TOP, col 0 is the LEFT
    * client.rows and client.cols give the size (don't hard-code it —
      it comes from the active layout, so your game works on any floor shape)

Colours are (r, g, b) tuples, each 0..254.


row 0: keeps track of how many points each player has lost 
       (starts with full bar, game over when a player has an empty bar)
row 1: empty, used to detect point loss
row 2: where the player controls the paddle
row 3: where the ball detects collisions

ideally the layout is at least 17 pixels long
it'll look better if there are an odd number of rows
"""

from sdk import Game
import colorsys
import math
import random

class MyGame(Game):
    # Optional: a target frame rate and a display name.
    fps = 30
    name = "pong"

    def setup(self, client):
        """Runs once before the first frame. Set up your state here."""
        self.sim_testing = True

        self.rows = client.rows
        self.cols = client.cols
        client.clear()

        self.state = 0

        self.p1_col = 2
        self.p2_col = self.cols - 3

        self.p1_pos = int(self.rows / 2)
        print(self.p1_pos)
        self.p2_pos = int(self.rows / 2)
        self.p1_draw = self.p1_pos
        self.p2_draw = self.p2_pos

        self.p1_rgb = (0, 0, 0)
        self.p1_mid_rgb = (0, 0, 0)
        self.p1_light_rgb = (0, 0, 0)
        self.p2_rgb = (0, 0, 0)
        self.p2_mid_rgb = (0, 0, 0)
        self.p1_light_rgb = (0, 0, 0)

        self.max_points = min(5, self.rows) # max 5 points
        self.p1_points = self.max_points
        self.p2_points = self.max_points

        self.p1_last = self.p1_pos
        self.p2_last = self.p2_pos

        self.ball_pos = [int(self.rows / 2), int(self.cols / 2)]
        self.ball_pixels = [round(self.ball_pos[0]), round(self.ball_pos[1])]
        self.ball_timer = 0
        self.ball_cycle = 5
        self.ball_h = 0
        # velocity is in pixels/second (vy, vx)
        self.ball_velocity = [random.choice([-1, 1]) * 3, random.choice([-1, 1]) * 6]

        self.p1_count = {
            3: [(-1, 0), (-1, 2), (-1, 4), (0, 0), (0, 2), (0, 4), (1, 0), (1, 1), (1, 2), (1, 3), (1, 4)],
            2: [(-1, 0), (-1, 2), (1, 3), (-1, 4), (0, 0), (0, 2), (0, 4), (1, 0), (-1, 1), (1, 2), (1, 4)],
            1: [(-1, 0), (-1, 4), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 0)]
        }
        self.p2_count = {
            3: [(-1, -4), (-1, -3), (-1, -2), (-1, -1), (-1, 0), (0, -4), (0, -2), (0, 0), (1, -4), (1, -2), (1, 0)],
            2: [(-1, -4), (-1, -3), (-1, -2), (-1, 0), (0, -4), (0, -2), (0, 0), (1, -4), (1, -2), (1, -1), (1, 0)],
            1: [(-1, 0), (0, -4), (0, -3), (0, -2), (0, -1), (0, 0), (1, -4), (1, 0)]
        }

        self.p1_count_pos = (self.p1_pos, 4)
        self.p2_count_pos = (self.p2_pos, self.cols - 5)
        self.timer = 0
        self.blink_dur = 2
        self.blink_freq = (2 * math.pi) / self.blink_dur

        self.winner = 0
        self.wave_time = 2
        self.wave_speed = self.cols / self.wave_time
        self.wave_front = 0
        self.winner_rgb = (0, 0, 0)

        self.idle_cycle = 10
        self.idle_h = 0
        self.reset_p1 = []
        self.reset_p2 = []
        for row in range(self.rows):
            for col1 in range(3):
                self.reset_p1.append((row, col1))
            for col2 in range(self.cols - 3, self.cols):
                self.reset_p2.append((row, col2))

    def update(self, client, dt):
        """Runs every frame. `dt` is seconds since the last update.

        Use `dt` for anything time-based (movement, animation) so your game
        looks the same regardless of the exact frame rate.
        """
        client.clear()
        if self.state == 0: # game setup
            # both player paddles blink until players are in the right spot
            self.timer += dt
            v = (math.sin(self.timer * self.blink_freq) + 1) / 2
            rgb = colorsys.hsv_to_rgb(0, 0, v * 255)
            client.set_pixel(self.p1_pos, self.p1_col, rgb)
            client.set_pixel(self.p2_pos, self.p2_col, rgb)

            if (client.is_pressed(self.p1_pos, self.p1_col) and client.is_pressed(self.p2_pos, self.p2_col)) or (self.sim_testing and client.is_pressed(0, 0)):
                self.state = 1
                h = random.random()
                self.p1_rgb = colorsys.hsv_to_rgb(h, 1, 255)
                self.p1_mid_rgb = colorsys.hsv_to_rgb(h, 0.3, 255)
                self.p1_light_rgb = colorsys.hsv_to_rgb(h, 0.1, 255)
                self.p2_rgb = colorsys.hsv_to_rgb((h + 0.5) % 1, 1, 255)
                self.p2_mid_rgb = colorsys.hsv_to_rgb((h + 0.5) % 1, 0.3, 255)
                self.p2_light_rgb = colorsys.hsv_to_rgb((h + 0.5) % 1, 0.1, 255)
                self.timer = 3
        elif self.state == 1: # round setup
            self.timer -= dt
            # paddles
            self.draw_paddles(client)
            # ball (stationary)
            self.draw_ball(client, dt)
            # start round
            if self.timer <= 0:
                self.state = 2
                return
            if self.timer % 1 >= 0.5:
                self.draw_points(client, blink=False)
                for (r, c) in self.p1_count[math.ceil(self.timer)]:
                    client.set_pixel(self.p1_count_pos[0] + r, self.p1_count_pos[1] + c, self.p1_rgb)
                for (r, c) in self.p2_count[math.ceil(self.timer)]:
                    client.set_pixel(self.p2_count_pos[0] + r, self.p2_count_pos[1] + c, self.p2_rgb)                
            else:
                self.draw_points(client, blink=True)
                for (r, c) in self.p1_count[math.ceil(self.timer)]:
                    client.set_pixel(self.p1_count_pos[0] + r, self.p1_count_pos[1] + c, self.p1_mid_rgb)
                for (r, c) in self.p2_count[math.ceil(self.timer)]:
                    client.set_pixel(self.p2_count_pos[0] + r, self.p2_count_pos[1] + c, self.p2_mid_rgb)
        elif self.state == 2: # gameplay
            # points and paddles
            self.draw_points(client)
            self.draw_paddles(client)
            # update ball position
            self.ball_pos[0] += self.ball_velocity[0] * dt
            self.ball_pos[1] += self.ball_velocity[1] * dt
            self.ball_pixels = [round(self.ball_pos[0]), round(self.ball_pos[1])]
            self.draw_ball(client, dt)
            # check top/bottom wall collision
            if self.ball_pos[0] <= 0:
                self.ball_pos[0] = 0
                self.ball_velocity[0] *= -1
            elif self.ball_pos[0] >= self.rows - 1:
                self.ball_pos[0] = self.rows - 1
                self.ball_velocity[0] *= -1
            # ball moving left and collision check with p1 paddle
            if self.ball_velocity[1] < 0 and self.ball_pos[1] <= self.p1_col + 0.5:
                if abs(self.ball_pos[0] - self.p1_draw) <= 1.5:
                    relative_hit = self.ball_pos[0] - self.p1_draw
                    normalized_offset = max(-1.0, min(1.0, relative_hit / 1.5))
                    current_speed = math.hypot(self.ball_velocity[0], self.ball_velocity[1])
                    new_speed = current_speed * 1.05
                    bounce_angle = normalized_offset * math.radians(50) # max angle of 50 degrees
                    self.ball_velocity[0] = new_speed * math.sin(bounce_angle)
                    self.ball_velocity[1] = new_speed * math.cos(bounce_angle)
                    self.ball_pos[1] = self.p1_col + 0.51
            # ball moving right and collision chekc with p2 paddle
            elif self.ball_velocity[1] > 0 and self.ball_pos[1] >= self.p2_col - 0.5:
                if abs(self.ball_pos[0] - self.p2_draw) <= 1.5:
                    relative_hit = self.ball_pos[0] - self.p2_draw
                    normalized_offset = max(-1.0, min(1.0, relative_hit / 1.5))
                    current_speed = math.hypot(self.ball_velocity[0], self.ball_velocity[1])
                    new_speed = current_speed * 1.05
                    bounce_angle = normalized_offset * math.radians(50)
                    self.ball_velocity[0] = new_speed * math.sin(bounce_angle)
                    self.ball_velocity[1] = -new_speed * math.cos(bounce_angle)
                    self.ball_pos[1] = self.p2_col - 0.51
            # check score
            if self.ball_pos[1] <= self.p1_col: # p2 scored
                self.p1_points -= 1
                self.reset_point(-1)
            elif self.ball_pos[1] >= self.p2_col: # p1 scored
                self.p2_points -= 1
                self.reset_point(1)
            # check game over
            if self.p1_points <= 0 or self.p2_points <= 0:
                self.state = 3
                self.timer = 0
                if self.p2_points <= 0:
                    self.winner = 1
                    self.winner_rgb = self.p1_rgb
                else:
                    self.winner = 2
                    self.winner_rgb = self.p2_rgb
        elif self.state == 3: # game over
            self.timer += dt
            self.wave_front = self.timer * self.wave_speed
            for r in range(self.rows):
                for c in range(self.cols):
                    dist = c
                    if self.winner == 2:
                        dist = self.cols - 1 - c
                    if dist <= self.wave_front:
                        client.set_pixel(r, c, self.winner_rgb)
            if self.timer >= self.wave_time + 1.0:
                self.timer = 0
                self.state = 4
                self.p1_pos = int(self.rows / 2)
                self.p2_pos = int(self.rows / 2)
                r, g, b = [c / 255.0 for c in self.winner_rgb]
                self.idle_h = colorsys.rgb_to_hsv(r, g, b)[0]
        elif self.state == 4: # waiting for restart
            self.timer += dt
            hue = (self.idle_h + (self.timer / self.idle_cycle)) % 1.0
            client.clear(colorsys.hsv_to_rgb(hue, 1, 255))
            reset_color = colorsys.hsv_to_rgb(hue, 0.5, 255)
            p1_reset = False
            p2_reset = True
            for (r, c) in self.reset_p1:
                client.set_pixel(r, c, reset_color)
                if client.is_pressed(r, c):
                    p1_reset = True
            for (r, c) in self.reset_p2:
                client.set_pixel(r, c, reset_color)
                if client.is_pressed(r, c):
                    p2_reset = True
            if (p1_reset and p2_reset) or (self.sim_testing and client.is_pressed(0, 0)):
                self.setup(client)
    
    def draw_points(self, client, blink=False):
        # center point: round(self.rows / 2) - 1
        # half of max points: 
        # p1 first point pos: center point - 
        # try (7 rows, 5 max points, 2 points currently), (4 rows, 4 max points, 3 points currently)
        center = int(self.rows / 2) # 3
        half_pts = int (self.max_points / 2) # 2
        p1_range = range(center - half_pts, center - half_pts + self.p1_points)
        p2_range = range(center + half_pts - self.p2_points + 1, center + half_pts + 1)
        for i in range(self.rows):
            if i in p1_range and not blink:
                client.set_pixel(i, 0, self.p1_rgb)
            else:
                client.set_pixel(i, 0, self.p1_mid_rgb)
            if i in p2_range and not blink:
                client.set_pixel(i, self.cols-1, self.p2_rgb)
            else:
                client.set_pixel(i, self.cols-1, self.p2_mid_rgb) 

    def draw_paddles(self, client, blink=False):
        # checks to see if players have moved
        for (row, col) in [(r, c) for (r, c) in client.pressed_coords() if client.just_pressed(r, c)]:
            if col == self.p1_col and row != self.p1_last:
                self.p1_last = row
            elif col == self.p2_col and row != self.p2_last:
                self.p2_last = row
        # draws paddles
        self.p1_draw = max(1, min(self.p1_last, self.rows - 2))
        self.p2_draw = max(1, min(self.p2_last, self.rows - 2))
        for i in [-1, 0, 1]:
            if blink:
                client.set_pixel(self.p1_draw + i, self.p1_col, self.p1_mid_rgb)
                client.set_pixel(self.p2_draw + i, self.p2_col, self.p2_mid_rgb)
            else:
                client.set_pixel(self.p1_draw + i, self.p1_col, self.p1_rgb)
                client.set_pixel(self.p2_draw + i, self.p2_col, self.p2_rgb)

    def draw_ball(self, client, dt):
        self.ball_timer += dt
        self.ball_h = (self.ball_timer % self.ball_cycle) / self.ball_cycle
        client.set_pixel(*self.ball_pixels, colorsys.hsv_to_rgb(self.ball_h, 1, 255))

    def reset_point(self, mult):
        self.ball_velocity = [random.choice([-1, 1]) * 3, mult * 6]
        self.state = 1
        self.ball_pos = [int(self.rows / 2), int(self.cols / 2)]
        self.ball_pixels = [round(self.ball_pos[0]), round(self.ball_pos[1])]
        self.timer = 3