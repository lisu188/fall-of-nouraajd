# Baldur's Gate city item and interaction artwork

Eight original PNG icons extend the city's outlined, hand-painted dark-fantasy artwork. The subjects use
supporting source identities and existing native object categories. Their colors, ornament, clothing and
materials are visual adaptation choices. No original BG1 artwork was extracted or copied.

| Asset | Intended source identity or category |
| --- | --- |
| `items/ordinaryBook.png` | Ordinary history books, represented by BOOK10 |
| `items/understandingTomeV2.png` | BOOK08, Tome of Understanding |
| `items/carriedDuke.png` | MISC55, Duke Eltan's portable body; depicted as an intact unconscious adult |
| `items/wrappedChildRemainsV2.png` | MISC54, Child's Body; a solemn, entirely wrapped non-graphic bundle |
| `items/questRing.png` | MAGE04, an unidentified ring referenced by the AR1100 Door0127 key field |
| `items/antidoteBottle.png` | POTN20 and POTN47 identities; shared visual style preserves separate item rules |
| `interactions/woodenChest.png` | A closed wooden container; AR0004#container1 is a representative existing object |
| `interactions/closedDoor.png` | A stable closed interior-door icon; AR0111#door1 is a representative existing object |

Paths in the table are relative to `res/maps/baldursGate/images/`. The source key reference names an item
whose metadata says ring, so this batch supplies a ring icon. It adds no conventional key or new key effect.
The container and doorway references identify existing objects; their exact original materials and artwork
have not been established.

All eight selected files are 1254 by 1254 RGBA PNGs with transparent corner pixels. Each has 1,572,516 pixels,
below the native `MAX_ALPHA_MASK_PIXELS` limit of 4,000,000. They total 7,687,373 bytes. Read-only Pillow checks
verified decoding, dimensions, alpha values and SHA-256 fingerprints. Selected files were copied unchanged
from the built-in image generator; no resizing, recoloring, compositing or manual alpha cleanup was applied.

Visible silhouettes have clear padding when measured at alpha two or greater: the Duke's minimum is about
5.7 percent, the door's about 7.6 percent, and the other six exceed 12 percent. Sparse alpha-one background
pixels remain outside those silhouettes, so a strict fully zero-alpha padded border is not certified. Two
initial generations had an alpha-one corner; imagegen corrections produced the selected V2 files. All
original generations and complete private generation receipts remain preserved outside Git.

The complete generation and correction prompts, source pointers, PNG measurements and fingerprints are in
`baldurs_gate_city_items_interactions_prompts.json`. Existing key, potion and city-building images were
inspected to establish the palette, contours and painted shading before generation.

This batch contains assets and provenance only. Map asset declarations, approved consumer assignments and
staging through the existing CMake map-asset hook remain pending. Map data, dialogs, builders, inventories,
quest effects, locks, source ledgers and test expectations are unchanged. No native game or desktop capture
was run. Exact-head rendering, gameplay, persistence and owner visual acceptance remain separate work.
