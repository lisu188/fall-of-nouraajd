# Baldur's Gate city environment artwork

The city has 24 new local PNG assets: twelve transparent building icons and twelve opaque terrain materials.
They follow the existing bold ink contours, angular painted shading and worn medieval palette used by the
city NPC artwork. They are original visual adaptations; they do not reproduce extracted BG artwork.

## Asset set

| Group | Assets |
| --- | --- |
| Homes and commerce | `timberHouse`, `stoneTownhouse`, `merchantShop`, `innTavern`, `magicShop` |
| Civic and fortified buildings | `temple`, `cityGate`, `guardBarracks`, `ducalPalace`, `guildhall` |
| Other buildings | `dockWarehouse`, `ruinedTemple` |
| Outdoor materials | `streetCobble`, `flagstonePaving`, `packedEarth`, `grassCourtyard` |
| Interior materials | `woodenFloor`, `marbleFloor`, `dungeonFlagstone`, `sewerWalkway` |
| Water and walls | `sewerWater`, `riverWater`, `stoneWall`, `rockWall` |

Files are stored under `res/maps/baldursGate/images/buildings/` and `images/tiles/`.
The complete prompts, imagegen follow-up prompts, sizes, alpha measurements and SHA-256 fingerprints are in
`baldurs_gate_city_environment_prompts.json`. Selected PNGs were copied byte-for-byte from the built-in
image generator. Original and discarded generations remain in development evidence outside Git.

## Current assignments

The existing builder assigns eleven building families to 53 reviewed outdoor-origin portals, including
the eastern gate marker. The explicit source identities and destinations are documented in
`baldurs_gate_city_environment_mapping.json`. The renderer displays each building as one map-cell icon;
these images do not add a larger building footprint or alter an entrance.

The existing city street and wall tiles use `streetCobble` and `stoneWall`. Their resource IDs, tile types,
passability and other fields remain unchanged. The global `GroundTile` is unchanged. The other ten materials
are staged for later floor authoring, and `ruinedTemple` is staged for a later underground appearance pass.
Interior exits and stairs keep their current graphics.

All 24 assets are declared in the map's `assets` list alongside the existing 41 NPC PNGs. The existing
CMake map-asset hook copies them and the map directory installation rule includes them. Animation IDs omit
the `.png` extension.

## Image constraints and visual limits

Every selected image is 1254 by 1254 pixels, below the native four-million-pixel limit. Buildings have RGBA
transparency and transparent corners. Their visible silhouettes have at least ten percent padding when
measured at alpha two or greater. The generator also emitted sparse alpha-one specks beyond those bounds;
a strict completely zero-alpha ten-percent margin is not achieved. No manual alpha cleanup was applied.

Tiles are opaque RGB images with effective alpha 255. Every tile has four distinct corner colors, which
avoids the engine's exact equal-corner background-masking condition. They were designed for repeating use,
but perfect seamless joins have not been certified.

## Validation boundaries

The frozen gameplay guard keeps its existing digest. Test-owned normalization first checks each approved
new animation and restores only those exact 55 environmental fields to their old values. The existing
NPC normalization then proves the rest of the gameplay configuration is unchanged. Tests also preserve
the original 41-NPC asset checks, portal targets, locks, tile data, passability, inventories and rewards.

The interaction ledger retains all 7,811 rows and their statuses; only the configuration input fingerprint
changes. The catalog's reviewed content fingerprint changes because it includes animation references and
asset declarations. Callback, campaign-edge and outcome inventories remain unchanged.

Source checks, PNG inspection and asset-copy verification do not establish native rendering, gameplay,
original BG1 parity or owner acceptance. Those remain separate validation lanes.
