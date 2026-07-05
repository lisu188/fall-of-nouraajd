# MJ best-picks selected asset integration

## Scope

This note records the uploaded `mj_best_picks_selected.zip` integration targets for the selected Fall of Nouraajd asset pack.

The uploaded package was inspected locally. It contains 57 manifest rows, 52 PNG source selections, and 50 unique selected target PNG paths after resolving duplicate target rows by keeping the highest numeric `selected_variant` for each target path.

## Repository verification

- Static object rendering loads the object animation path through `CTextureCache::getTexture(...)`.
- `CTextureCache::getTexture(...)` appends `.png` when the animation path does not already end with `.png`.
- Dynamic animations use `path/time.json` plus frame files, so the selected one-file targets are appropriate only for static animation/image references.
- Nouraajd currently still uses generic quest-item animation paths for `skullOfRolf`, `holyRelic`, and `preciousAmulet`; JSON rewiring must be reviewed before replacing those references.
- Ninemarches already contains several matching object ids that currently reuse generic monster/item animation paths.

## Selected target paths

```text
res/images/items/quest/ashRelic.png
res/images/items/quest/boneKey.png
res/images/items/quest/brassKey.png
res/images/items/quest/fenRelic.png
res/images/items/quest/holyRelic.png
res/images/items/quest/ironKey.png
res/images/items/quest/preciousAmulet.png
res/images/items/quest/skullOfRolf.png
res/images/items/quest/warBanner.png
res/images/monsters/barrowKnight.png
res/images/monsters/citadelPriest.png
res/images/monsters/cryptWardenEast.png
res/images/monsters/cryptWardenNorth.png
res/images/monsters/cryptWardenWest.png
res/images/monsters/deepSpawn.png
res/images/monsters/drownedHybrid.png
res/images/monsters/elderThing.png
res/images/monsters/fenGhoul.png
res/images/monsters/fieldRaider.png
res/images/monsters/highPriestOfLeng.png
res/images/monsters/housecarlEast.png
res/images/monsters/housecarlWest.png
res/images/monsters/lengMan.png
res/images/monsters/lengSpider.png
res/images/monsters/nightGaunt.png
res/images/monsters/occupierEast.png
res/images/monsters/occupierGate.png
res/images/monsters/occupierWest.png
res/images/monsters/plagueCultist.png
res/images/monsters/ritualCultist.png
res/images/monsters/ritualLeaderTemplate.png
res/images/monsters/ritualMage.png
res/images/monsters/ritualPritz.png
res/images/monsters/theBarrowWarlord.png
res/images/monsters/theCrawlingChaos.png
res/images/monsters/theNameless.png
res/images/monsters/theNinefoldKing.png
res/images/monsters/theUsurper.png
res/images/monsters/tideHierophant.png
res/images/monsters/watchCaptain.png
res/images/npc/banneretHild.png
res/images/npc/dreamerGuide.png
res/images/npc/elderMaren.png
res/images/npc/lengMerchant.png
res/images/npc/lengPriest.png
res/images/npc/markedWidow.png
res/images/npc/oldTollman.png
res/images/npc/quartermasterVoss.png
res/images/npc/ritualCaptive.png
res/images/npc/ritualWitness.png
```

## Rows intentionally not materialized from the uploaded manifest

These manifest rows had no selected file in the uploaded package:

```text
ashCultist
coldHorror
marchRaider
```

The manifest also had duplicate target rows for `ironKey`, `fenGhoul`, `barrowKnight`, and `deepSpawn`. Duplicate rows should not be committed twice to the same target path.

## Manual review checklist

1. Decode and commit the selected PNGs to the target paths above.
2. Review Nouraajd config rewiring for `skullOfRolf`, `holyRelic`, and `preciousAmulet` before changing animation ids.
3. Review Ninemarches config rewiring for matching item, monster, and NPC ids before replacing current generic animations.
4. Run `python3 test.py` and a visual gameplay smoke test after binary assets are committed.

## Tooling limitation observed during this integration attempt

GitHub tree content entries store base64 text literally; they do not decode binary content. Binary PNG uploads through the available connector require explicit per-file blob creation. The full binary pack is therefore not represented by this note alone.
