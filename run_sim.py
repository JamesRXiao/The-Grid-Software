"""
run_sim.py — run a game in the on-screen pygame simulator.

    python run_sim.py games/my_game.py

Opens a window showing the floor. Click (and drag) on tiles to simulate
microswitch presses. The game runs exactly as it would on real hardware — the
only thing that changes is the backend.
"""

import sys
import time

import config
from sdk import GridClient, ModuleLayout
from sim.sim_backend import SimBackend
from runner import load_game


def main():
    if len(sys.argv) != 2:
        print("usage: python run_sim.py games/your_game.py")
        sys.exit(1)

    game_path = sys.argv[1]

    layout = ModuleLayout(config.LAYOUT)
    game = load_game(game_path)
    print(f"[sim] loaded '{game.name}' on {layout}")

    backend = SimBackend(layout, title=f"The Grid — {game.name}")
    client = GridClient(backend)

    backend.start()

    # We can't reuse runner.run_loop verbatim because the sim must pump its
    # window on the main thread each frame. The loop body is otherwise identical
    # to run_loop(), so game behaviour matches real hardware exactly.
    fps = game.fps if getattr(game, "fps", None) else config.FPS
    interval = 1.0 / fps

    game.setup(client)
    last = time.perf_counter()
    try:
        while backend.running:
            now = time.perf_counter()
            dt = now - last
            last = now

            client._refresh_input()   # pull presses (from mouse) + edge state
            game.update(client, dt)   # game draws + reacts
            client._flush()           # push surface to backend
            backend.pump()            # service window events + redraw

            elapsed = time.perf_counter() - now
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        print("\n[sim] stopping (Ctrl+C)")
    finally:
        game.teardown(client)
        backend.stop()


if __name__ == "__main__":
    main()
