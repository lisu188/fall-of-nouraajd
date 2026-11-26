# Baldur's Gate city item and interaction artwork

Eight original PNG icons extend the city's outlined, hand-painted dark-fantasy artwork. The subjects use
supporting source identities and existing native object categories. Their colors, ornament, clothing and
materials are visual adaptation choices. No original BG1 artwork was extracted or copied.

| Asset | Consumer in the city |
| --- | --- |
| `items/ordinaryBook.png` | 56 history books, including BOOK10 |
| `items/understandingTomeV2.png` | BOOK08, Tome of Understanding |
| `items/carriedDuke.png` | MISC55, Duke Eltan's portable body; depicted as an intact unconscious adult |
| `items/wrappedChildRemainsV2.png` | MISC54, Child's Body; a solemn, entirely wrapped non-graphic bundle |
| `items/questRing.png` | MAGE04, an unidentified ring referenced by the AR1100 Door0127 key field |
| `items/antidoteBottle.png` | POTN20 and POTN47 identities; shared visual style preserves separate item rules |
| `interactions/woodenChest.png` | 92 ARE type-2 chests, including AR0006#container1 |
| `interactions/closedDoor.png` | Staged for future door-state rendering. Existing doors keep their current open/closed behavior. |

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

The city declares all eight PNGs. Seven images appear on 62 item recipes and 92 containers. The Tome
of Understanding retains its native use action, and the two antidotes retain their separate source IDs.
Door rendering still uses a single animation across both states. The closed-door icon is staged for a
future state-aware implementation.

The chest audit checked the SHA-256 of all 212 ARE files against the city fixture and matched the name
and position of every one of their 731 containers. The container type is a little-endian word at record
offset 0x24. Type 2 identifies a chest. AR0004#container1, an early art reference, is type 3 and keeps
its existing sprite. Reproduce the checked-in indices against the installed EE base archives with
`python scripts/audit_baldurs_gate_city_chests.py --game-root "<installation>" --check`.
[IESDP ARE V1.0 container records](https://gibberlings3.github.io/iesdp/file_formats/ie_formats/are_v1.htm#formAREAV1_0_Containers)

Original-game source parity, native rendering, gameplay and owner visual acceptance require separate evidence.
