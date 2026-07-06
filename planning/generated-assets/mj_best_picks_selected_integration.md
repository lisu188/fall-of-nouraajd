# MJ best-picks selected asset integration

Source archive: `mj_best_picks_selected.zip`

Archive SHA-256: `d9594b29942f6c530a5555a7c53049059fcc1cb0178376bb49d3fab376f49b2c`

The selected archive contains 57 manifest rows, 52 selected PNG rows, 50 unique target PNG paths, the source manifest, and a contact sheet.

Duplicate target rows were resolved by keeping the highest numeric `selected_variant` for each target path:

- `ironKey`: kept variant 3 over variant 2.
- `barrowKnight`: kept variant 2 over variant 1.

Rows still missing after applying selected duplicate rows:

- `ashCultist`
- `coldHorror`
- `marchRaider`

The committed image targets follow the engine resource convention: `res/images/.../name.png` is referenced by JSON as `images/.../name`, and the texture cache appends `.png`.

Matching top-level map config entries were rewired to their selected `target_animation_id` values in:

- `res/maps/gravemoor/config.json`
- `res/maps/hearthfall/config.json`
- `res/maps/kadath/config.json`
- `res/maps/ninemarches/config.json`
- `res/maps/nouraajd/config.json`
- `res/maps/ritual/config.json`
- `res/maps/sunderedmarch/config.json`
- `res/maps/usurpergate/config.json`
- `res/maps/vhulmarn/config.json`

Missing-only object ids keep their existing placeholder animation paths until art is selected.
