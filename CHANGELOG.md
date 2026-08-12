# Changelog

All notable changes to the Grid SDK are recorded here. Game code depends only
on `GridClient`'s public methods, so watch the **SDK API** sections for anything
that could affect your games.

## [0.1.0] — initial release
### SDK API (what games use)
- `GridClient`: `clear`, `set_pixel`, `get_pixel`, `fill_rect`, `set_frame`,
  `frame`, `is_pressed`, `just_pressed`, `just_released`, `pressed_coords`,
  `pressed_mask`, `rows`, `cols`, `shape`.
- `Game` base class: `setup(client)`, `update(client, dt)`, `teardown(client)`,
  optional `fps` and `name`.
- Coordinates are `(row, col)`, row 0 top, col 0 left. Colours `(r,g,b)` 0..254.

### Internals (safe to change without touching games)
- `GridController` real-hardware backend: serial + TX/RX threads, robust switch
  framing, transparent reconnect, 0xFE colour clamp.
- `SimBackend` pygame simulator with click/drag-to-press.
- Data-driven `ModuleLayout` (layouts/*.json) — floor shape/wiring is config.
