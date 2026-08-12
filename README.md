# The Grid Software
EAsT camPUS REX 2026 led floor small build software :D

A 7×28 pixel interactive LED floor. Write games in Python that light up the
floor and react to people stepping on it — test them in an on-screen simulator,
then run the exact same code on the real hardware.

A layout of the floor can be found here: [Google Sheets](https://docs.google.com/spreadsheets/d/1Plh8lO02KhHBDETudAaVY9BvlBedDt_4V1slBKskpGw/edit?usp=sharing)

Project led by James Xiao, Vivian Ang, Xinlan Tanner

MIT '29

## Notes (!)
- Pygame is unable to be installed with pip on the latest version (3.14) of Python. Use `pip install pygame-ce` instead.
- Due to frame protocol reasons, each color value command (R, G, B), can be from 0-254 instead of 0-255. Bright white would be (254, 254, 254).
- Pls refrain from making the entire dance floor full bright white. While our system is designed to safely handle more than that load, we don't want to overload our power supplies and heat up our boards :(

## Quick start

```bash
git clone <this-repo>
cd the-grid
pip install -r requirements.txt

cp config.example.py config.py      # then edit config.py (set your COM port)
#^^ ONLY REQUIRED FOR ACTUAL FLOOR devs dont do this

# Try an example in the simulator (click/drag tiles to "step" on them):
python run_sim.py examples/press_color.py

# Run it on the real floor instead:
python run.py examples/press_color.py
```

## Write your own game

1. Copy the template:
   ```bash
   cp games/game_template.py games/my_game.py
   ```
2. Fill in `setup()` and `update()`. You only ever use `client` — never touch
   the SDK, serial ports, or module IDs.
3. Run it:
   ```bash
   python run_sim.py games/my_game.py     # simulator
   python run.py     games/my_game.py     # real floor
   ```

A game is just a class:

```python
from sdk import Game

class MyGame(Game):
    name = "My Game"
    fps = 24

    def setup(self, client):
        client.clear()

    def update(self, client, dt):
        client.clear()
        for (row, col) in client.pressed_coords():
            client.set_pixel(row, col, (254, 254, 254))
```

## The floor

- Addressed as `(row, col)`: **row 0 is the top, col 0 is the left.**
- Size comes from the active layout — use `client.rows` / `client.cols`, never
  hard-code numbers, so your game works on any floor shape.
- Colours are `(r, g, b)` tuples, each **0–254** (255 is reserved by the
  firmware; values are clamped for you automatically).

## GridClient API

Drawing:
- `client.clear(rgb=(0,0,0))` — fill the whole floor
- `client.set_pixel(row, col, rgb)` — one pixel
- `client.get_pixel(row, col)` — read a pixel back
- `client.fill_rect(r0, c0, r1, c1, rgb)` — fill a rectangle
- `client.set_frame(array)` — replace the whole floor with a `(rows, cols, 3)`
  numpy array
- `client.frame` — the live numpy surface; edit it in place if you prefer

Input:
- `client.is_pressed(row, col)` — held right now?
- `client.just_pressed(row, col)` — pressed on this frame? (edge)
- `client.just_released(row, col)` — released on this frame? (edge)
- `client.pressed_coords()` — list of `(row, col)` currently held
- `client.pressed_mask()` — full boolean `(rows, cols)` grid

Sizes: `client.rows`, `client.cols`, `client.shape`.

Use the `dt` passed to `update()` for anything time-based, so your game looks
the same regardless of the exact frame rate.

## Frame rate

You set a target FPS (in `config.py`, or per-game via the game's `fps`
attribute), but on real hardware the **controller firmware enforces the true
minimum time between frames** to keep the bus reliable. Treat your FPS as a
best-effort ceiling, not a guarantee — which is exactly why `update()` gives you
`dt`.

## Repository layout

```
the-grid/
  sdk/                SDK — you don't edit this
    layout.py         floor geometry from layouts/*.json
    controller.py     real-hardware backend (serial + threads)
    client.py         GridClient — the API your game uses
    game.py           the Game base class
  games/
    game_template.py  copy this to start a game
  examples/
    press_color.py    random colour on press
    rainbow.py        full-floor numpy animation
    play_video.py     play an MP4 on the floor, audio from speakers
  sim/
    sim_backend.py    pygame simulator (same interface as the real backend)
  layouts/
    default.json      the 7×28 floor definition
  config.example.py   copy to config.py and set your port
  run.py              run a game on real hardware
  run_sim.py          run a game in the simulator
```

## Changing the floor shape

The floor's dimensions and wiring live entirely in `layouts/default.json` —
grid size, how module IDs snake across the floor, and pixel order within a
module. To use a different physical floor, add a new JSON file and point
`config.py`'s `LAYOUT` at it. **No game or SDK code changes** — games only ever
see `client.rows` / `client.cols` and `(row, col)` coordinates.

## For SDK maintainers

Games depend **only** on `GridClient`'s public method signatures. You can
refactor `GridController`, `SimBackend`, `ModuleLayout`, or the wire protocol
freely as long as that surface stays stable. Record anything that touches the
game-facing API in `CHANGELOG.md`. The real and sim backends implement the same
small interface (`layout`, `start`, `stop`, `set_frame`, `get_switch_state`), so
`GridClient` and every game are identical across both.
