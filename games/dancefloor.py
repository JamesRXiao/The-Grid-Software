"""
AUTHOR: Annabella Du

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
import colorsys
import math

class MyGame(Game):
    # Optional: a target frame rate and a display name.
    fps = 30
    name = "My Game"

    def setup(self, client):
        """Runs once before the first frame. Set up your state here."""
        # Example: remember the floor size and start with a blank floor.
        self.rows = client.rows
        self.cols = client.cols
        rainbow = [(0, 97, 89), (33, 100, 100), (56, 100, 100), (138, 100, 50), (222, 100, 100), (290, 52, 51)]
        lesbian = [(13, 100, 84), (24, 86, 94), (24, 100, 100), (0, 0, 75), (324, 55, 82), (323, 39, 71), (324, 98, 64)]
        bisexual = [(329, 98, 84), (304, 32, 61), (220, 100, 66)]
        transgender = [(197, 94, 98), (348, 79, 96), (0, 0, 75)]
        nonbinary = [(58, 97, 99), (0, 0, 75), (274, 57, 82), (0, 0, 17)]
        self.schemes = [
            {'colors': rainbow, 'switch': 'lerp', 'pattern': 'cycle'},
            {'colors': lesbian, 'switch': 'lerp', 'pattern': 'oscillate'},
            {'colors': bisexual, 'switch': 'lerp', 'pattern': 'oscillate'},
            {'colors': transgender, 'switch': 'lerp', 'pattern': 'oscillate'},
            {'colors': nonbinary, 'switch': 'lerp', 'pattern': 'cycle'}
        ]
        self.scheme_index = -1
        self.cur_scheme = self.schemes[self.scheme_index]

        self.mode = -1
        self.total_modes = 4

        self.color_timer = 0
        self.color_dur = 5 # time to transition between colors
        self.total_dur = 30 # how long

        # radial mode variables
        self.press_timers = {} # (r, c) -> time
        self.pixel_lightness = {} # (r, c) -> lightness

        # standing mode variables
        self.standing_colors = {} # (r, c) -> (h, s, v)

        # wave mode variables
        self.wave_speed = 6
        self.wave_width = 3.5
        self.trail_map = {} # (r, c) -> intensity
        self.drift_speed = 12 # speed of the trail
        self.drift_buffer = 0
        self.trail_decay = 2.5

        # color radial
        self.spectrum_ripples = {}  # (r, c) -> timer
        self.spectrum_speed = 8.0   # pixels/sec
        self.spectrum_width = 12.0

        self.speed = 3.0 # pixels/sec
        self.max_time = 1.0 # fade lifetime once released

        self.change_color_scheme()

    def update(self, client, dt):
        """Runs every frame. `dt` is seconds since the last update.

        Use `dt` for anything time-based (movement, animation) so your game
        looks the same regardless of the exact frame rate.
        """
        # Start from a clean floor each frame (remove this if you want to draw
        # cumulatively instead).
        client.clear()
        pressed_coords = client.pressed_coords()
        if self.mode == 0: # radial
            base_color = self.get_base(self.cur_scheme, dt)
            client.clear(self.rgb(base_color))
            # update timers for pressed pixels and unpressed
            for pos in list(self.press_timers.keys()):
                if pos in pressed_coords:
                    self.press_timers[pos] = 0
                else: 
                    self.press_timers[pos] += dt
                    if self.press_timers[pos] >= self.max_time:
                        del self.press_timers[pos]
            for pos in pressed_coords: 
                if pos not in self.press_timers.keys():
                    self.press_timers[pos] = 0
            # set lightness boosts
            self.pixel_lightness = {}
            for (cr, cc), timer in self.press_timers.items():
                wave_radius = timer * self.speed
                fade_out = 1 - (timer / self.max_time)
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        dist = abs(dr) + abs(dc)
                        if dist <= 2:
                            r, c = cr + dr, cc + dc
                            if 0 <= r < self.rows and 0 <= c < self.cols:
                                dist_from_wave = abs(dist - wave_radius)
                                if dist_from_wave < 1:
                                    boost = (1 - dist_from_wave) * fade_out
                                    self.pixel_lightness[(r, c)] = max(self.pixel_lightness.get((r, c), 0.0), boost)
            # set pixel colors
            for (r, c), boost in self.pixel_lightness.items():
                h, s, v = base_color
                new_s = max(0, s - (boost * 120))
                new_v = min(100, v + (boost * (100 - v)))
                client.set_pixel(r, c, self.rgb((h, new_s, new_v)))
            
        elif self.mode == 1: # standing
            base_color = self.get_base(self.cur_scheme, dt)
            for pos in pressed_coords:
                self.standing_colors[pos] = base_color
            for (r, c), hsv_color in self.standing_colors.items():
                client.set_pixel(r, c, self.rgb(hsv_color))

        elif self.mode == 2:  # wave
            self.color_timer += dt
            time_offset = self.color_timer * 0.4
            # trail starts on pressed coords
            for (r, c) in pressed_coords:
                if client.just_pressed(r, c) or (r, c) not in self.trail_map:
                    self.trail_map[(r, c)] = 1.0
            # trail moves left
            self.drift_buffer += dt * self.drift_speed
            shift_steps = int(self.drift_buffer)
            if shift_steps > 0:
                self.drift_buffer -= shift_steps
                new_trail = {}
                for (r, c), intensity in self.trail_map.items():
                    new_c = c - shift_steps
                    if new_c >= 0:
                        new_trail[(r, new_c)] = max(new_trail.get((r, new_c), 0.0), intensity)
                self.trail_map = new_trail
            # trail fade
            trail_decay = 2
            for pos in list(self.trail_map.keys()):
                self.trail_map[pos] -= dt * trail_decay
                if self.trail_map[pos] <= 0:
                    del self.trail_map[pos]
            # ombre background
            for c in range(self.cols):
                pos_progress = (c / self.cols) + time_offset
                bg_hsv = self.get_base_at_time(self.cur_scheme, pos_progress * self.color_dur)
                h, s, v = bg_hsv
                for r in range(self.rows):
                    foam = self.trail_map.get((r, c), 0.0)
                    if foam > 0:
                        new_s = max(0.0, s - (foam * 100.0))
                        new_v = min(100.0, v + (foam * (100.0 - v)))
                        client.set_pixel(r, c, self.rgb((h, new_s, new_v)))
                    else:
                        client.set_pixel(r, c, self.rgb(bg_hsv))

        elif self.mode == 3:  # Sequential Full Spectrum Ripple per Step
            self.color_timer += dt
            colors = self.cur_scheme['colors']
            num_colors = len(colors)

            # 1. Register a new multi-color ripple on step
            for (r, c) in pressed_coords:
                if client.just_pressed(r, c) or (r, c) not in self.spectrum_ripples:
                    self.spectrum_ripples[(r, c)] = 0.0  # Expansion timer

            # Calculate total duration for a ripple to display all colors and clear the floor
            ring_spacing = 1.5   # Distance between color rings
            full_spectrum_radius = num_colors * ring_spacing
            max_reach = max(self.rows, self.cols) + full_spectrum_radius

            # 2. Update active wave timers and delete ripples after ALL colors finish
            for pos in list(self.spectrum_ripples.keys()):
                self.spectrum_ripples[pos] += dt
                current_radius = self.spectrum_ripples[pos] * self.speed
                if current_radius > max_reach:
                    del self.spectrum_ripples[pos]

            # 3. Calculate pixel colors for active multi-ring ripples
            pixel_colors = {}

            for (cr, cc), timer in self.spectrum_ripples.items():
                wave_front = timer * self.speed

                min_r = max(0, int(cr - wave_front - 2))
                max_r = min(self.rows, int(cr + wave_front + 2))
                min_c = max(0, int(cc - wave_front - 2))
                max_c = min(self.cols, int(cc + wave_front + 2))

                for r in range(min_r, max_r):
                    for c in range(min_c, max_c):
                        dist = abs(r - cr) + abs(c - cc)  # Diamond radius

                        # Check if pixel falls inside the expanding multi-color wave band
                        if wave_front - full_spectrum_radius <= dist <= wave_front:
                            # Calculate index in the color scheme based on distance behind wave front
                            dist_behind_front = wave_front - dist
                            color_pos = dist_behind_front / ring_spacing

                            if 0 <= color_pos < num_colors:
                                c1 = int(color_pos)
                                c2 = min(num_colors - 1, c1 + 1)
                                t = color_pos - c1

                                if self.cur_scheme['switch'] == 'step':
                                    wave_color = colors[c1]
                                else:  # lerp
                                    wave_color = self.lerp_hsv(colors[c1], colors[c2], t)

                                # Fade out wave as it spreads further away
                                fade = max(0.0, 1.0 - (dist / max_reach))
                                h, s, v = wave_color
                                lit_hsv = (h, s, v * fade)

                                # If ripples overlap, render the brighter one
                                if (r, c) not in pixel_colors or lit_hsv[2] > pixel_colors[(r, c)][2]:
                                    pixel_colors[(r, c)] = lit_hsv

            # 4. Render active ripples onto the black floor
            for (r, c), hsv_color in pixel_colors.items():
                client.set_pixel(r, c, self.rgb(hsv_color))

        # switch color schemes
        if self.color_timer > self.total_dur:
            self.change_color_scheme()

    def rgb(self, hsv):
        r, g, b = colorsys.hsv_to_rgb(hsv[0] / 360.0, hsv[1] / 100.0, hsv[2] / 100.0)
        return (int(r * 254), int(g * 254), int(b * 254))

    def hsv(self, rgb):
        h, s, v = colorsys.rgb_to_hsv(rgb[0] / 254.0, rgb[1] / 254.0, rgb[2] / 254.0)
        return (h * 360.0, s * 100.0, v * 100.0)

    def change_color_scheme(self):
        self.color_index = 0
        self.color_timer = 0
        self.scheme_index = (self.scheme_index + 1) % len(self.schemes)
        self.cur_scheme = self.schemes[self.scheme_index]

        self.mode = (self.mode + 1) % self.total_modes
        print(f"scheme: {self.scheme_index} | mode: {self.mode}")

        self.press_timers.clear()
        self.pixel_lightness.clear()
        self.standing_colors.clear()
        self.trail_map.clear()
        self.spectrum_ripples.clear()

    def get_base(self, scheme, dt):
        # switch modes: lerp and step
        # pattern modes: cycle and oscillate
        self.color_timer += dt
        colors = scheme['colors']
        num_colors = len(colors)

        if scheme['pattern'] == 'cycle':
            total_segments = num_colors
        else:
            total_segments = 2 * (num_colors - 1)
        full_cycle_dur = total_segments * self.color_dur
        cycle_time = self.color_timer % full_cycle_dur

        # set color index
        color_index, color_time = divmod(cycle_time, self.color_dur)
        color_index = int(color_index)
        t = color_time / self.color_dur

        # pattern: cycle vs oscillate
        if scheme['pattern'] == 'cycle':
            c1 = color_index % num_colors
            c2 = (color_index + 1) % num_colors
        else: # scheme = oscillate
            if color_index < num_colors - 1: # forward
                c1 = color_index
                c2 = color_index + 1
            else: # backward
                c1 = (num_colors-1) - (color_index - (num_colors-1))
                c2 = c1 - 1

        # switch: lerp vs step
        if scheme['switch'] == 'lerp':
            return self.lerp_hsv(colors[c1], colors[c2], t)
        else: # switch = step
            return colors[c1]

    def get_base_at_time(self, scheme, time_val):
        colors = scheme['colors']
        num_colors = len(colors)

        if scheme['pattern'] == 'cycle':
            total_segments = num_colors
        else:
            total_segments = 2 * (num_colors - 1)

        full_cycle_dur = total_segments * self.color_dur
        cycle_time = time_val % full_cycle_dur

        # set color index
        color_index, color_time = divmod(cycle_time, self.color_dur)
        color_index = int(color_index)
        t = color_time / self.color_dur

        # pattern: cycle vs oscillate
        if scheme['pattern'] == 'cycle':
            c1 = color_index % num_colors
            c2 = (color_index + 1) % num_colors
        else:  # scheme = oscillate
            if color_index < num_colors - 1:  # forward
                c1 = color_index
                c2 = color_index + 1
            else:  # backward
                c1 = (num_colors - 1) - (color_index - (num_colors - 1))
                c2 = c1 - 1

        # switch: lerp vs step
        if scheme['switch'] == 'lerp':
            return self.lerp_hsv(colors[c1], colors[c2], t)
        else:  # switch = step
            return colors[c1]

    def lerp(self, start, end, t):
        return start + (end - start) * t

    def lerp_hsv(self, hsv1, hsv2, t):
        t = max(0.0, min(1.0, t))        
        h1, s1, v1 = hsv1
        h2, s2, v2 = hsv2
        dh = (h2 - h1) % 360
        if dh > 180:
            dh -= 360
        h = (h1 + dh * t) % 360
        s = self.lerp(s1, s2, t)
        v = self.lerp(v1, v2, t)
        return (h, s, v)
