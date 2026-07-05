# Midjourney selected asset pack

Source archive: `mj_best_picks_selected.zip`

Archive SHA-256: `d9594b29942f6c530a5555a7c53049059fcc1cb0178376bb49d3fab376f49b2c`

This manifest records the selected generated images and their intended in-repository target paths. The uploaded archive contained 52 selected PNG files and 5 rows marked `MISSING`.

Rows marked `MISSING` in the manifest were not added as selected image files in the source archive and still need new art selection or generation.

Missing object ids:

- `ashCultist` -> `res/images/monsters/ashCultist.png`
- `deepSpawn` -> `res/images/monsters/deepSpawn.png`
- `coldHorror` -> `res/images/monsters/coldHorror.png`
- `marchRaider` -> `res/images/monsters/marchRaider.png`
- `fenGhoul` -> `res/images/monsters/fenGhoul.png`

## Integration notes

The manifest target paths use the engine's PNG resource convention, for example `res/images/items/quest/preciousAmulet.png` maps to animation id `images/items/quest/preciousAmulet`. The texture cache appends `.png` when an animation path has no extension.

The Nouraajd quest item placeholders currently still need code/config wiring review before replacing existing generic animations, especially `preciousAmulet`, `holyRelic`, and `skullOfRolf`.
