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

The city now uses all twelve terrain materials. The explicit decisions for all 212 areas, including every
one of the 203 interiors and underground areas, are recorded in `baldurs_gate_city_floor_materials.json`.
The manifest distinguishes 53 classic-guide location/floor identities from the chosen artistic materials.
Unidentified ordinary interiors receive a neutral wooden floor without inventing a building identity.
The palace, temples and Sorcerous Sundries use marble; civic/trading premises use flagstone; the maze and
final temple use worn dungeon paving; the Undercity uses earth; and the three sewer areas use wet masonry.
These are visual adaptations, not claims about original BG1 TIS or WED pixels.

Outdoor grass, earth, boardwalk and water accents follow the dominant raw search-map samples in each
already projected native cell. Source value 12 also supplies water appearances in already blocked cells.
The [IESDP terrain legend](https://gibberlings3.github.io/iesdp/appendices/search.html) documents BG2, so
interpreting those supporting EE indices is an explicit aesthetic conversion with unresolved classic
material differences. Water-looking walkable cells remain walkable; blocked water-looking cells remain
blocked. Appearance supplies no swimming, hazards, footstep effects or new movement rules.

Sixteen map-local recipes clone the exact existing `CTile` street, ground or wall properties and change
only their texture references. Class, `canStep`, `tileType`, label and movement cost remain unchanged.
The global `GroundTile` is unchanged. Existing tile identities remain in the first palette, which now
uses an image collection referencing the existing PNGs; the loader reads that palette's type table and
requires no additional tileset or native API. Interior exits and stairs keep their current graphics.
The `ruinedTemple` building icon remains staged for a later underground appearance pass.

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

The frozen gameplay guard keeps its existing digest. A separate test-owned area table and an independently
expanded source raster check every material assignment and every new recipe. The independently reconstructed
legacy masks must match the five layer hashes from immutable main `9acf3570`, covering all 215,040 cells.
Only after checking every current cell and the complete palette may normalization restore the original
GIDs and remove the sixteen exact appearance recipes. Wrong walkable appearances, blocked appearances,
outside cells, classes, movement properties and palette image paths are rejected.

Normalization then checks and restores the existing 55 environment animations and removes the reviewed
NPC appearances. The unchanged frozen digest proves the remaining map, actors, portals, quests, inventories,
rewards, geometry and dialogs remain unchanged. No digest is rebased to accept the material pass.

The interaction ledger retains all 7,811 rows and their statuses; only the configuration input fingerprint
changes. The catalog's reviewed content fingerprint changes because it includes animation references and
asset declarations. Callback, campaign-edge and outcome inventories remain unchanged.

Source checks, PNG inspection and asset-copy verification do not establish native rendering, gameplay,
original BG1 parity or owner acceptance. Those remain separate validation lanes.
