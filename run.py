"""
run.py — run a game on the real LED floor.

    python run.py games/my_game.py

Loads your game, connects to the controller board over serial, and drives it.
Use run_sim.py instead to run the same game in the on-screen simulator.
"""

import sys

import config
from sdk import GridController, GridClient, ModuleLayout
from runner import load_game, run_loop


def main():
    if len(sys.argv) != 2:
        print("usage: python run.py games/your_game.py")
        sys.exit(1)

    game_path = sys.argv[1]

    layout = ModuleLayout(config.LAYOUT)
    game = load_game(game_path)
    print(f"[run] loaded '{game.name}' on {layout}")

    backend = GridController(
        port=config.PORT,
        layout=layout,
        baudrate=config.BAUDRATE,
        fps=config.FPS,
        reconnect=config.RECONNECT,
    )
    client = GridClient(backend)

    backend.start()
    try:
        run_loop(game, client, default_fps=config.FPS)
    finally:
        backend.stop()


if __name__ == "__main__":
    main()
