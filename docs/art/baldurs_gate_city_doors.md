# Standalone city doors

The city contains two door objects with a click polygon and no associated travel trigger. The other 87 placed door records share the travel region's landmark. Nineteen records have no independent click polygon or matched travel region. These counts come from the retained 212-area ledger and the installed EE base AREs. The source distinguishes a door's open flag, lock and click polygons from its open and closed lists of impassable search cells. [IESDP ARE V1 doors](https://gibberlings3.github.io/iesdp/file_formats/ie_formats/are_v1.htm#formAREAV1_0_Doors)

| Source | Native object | Behavior |
|---|---|---|
| AR0111#door1 | cityAr0111Door1 | Starts locked. After unlocking and opening, the source forbids closing. |
| AR0200#door12 | cityAr0200Door12 | Starts unlocked. The existing interaction can open and close it. |

At the city map's 64-pixel scale, each walkable cell touched by either door's impeded list retains walkable search-map samples in both positions. The interaction anchor stays accessible. The native artwork represents the state using a shared wooden-door design. Original WED artwork and original-versus-EE differences remain outside this visual evidence.

The closed sprite is the previously generated, unmodified city interaction asset. Its SHA-256 is `bb8eba391a7b6c1b2e8c080d04af0f1abf4380c01f9b6147b66ee6d2498fd3b5`. The open sprite is an edit of that source made with the built-in image generator. Its unmodified PNG has SHA-256 `6630fea5943940d6857c12ff954eea626862f121be32a815780628e470d718fe`.

## Open-state generation prompt

> Edit this existing square hand-painted dark-fantasy map sprite to show the same door fully open. Swing the oak leaf inward on its two existing left hinges until the narrow foreshortened leaf occupies only the left quarter of the opening. Reveal a deep unlit charcoal passage through the arch. Preserve the segmented tan stone frame, framing, scale, bottom alignment, worn red paint at the lower planks, black iron straps, restrained lighting and transparent margins. Keep the arch tall and the silhouette recognizable at 48 pixels. A single front-facing isolated game sprite with no lettering, floor scene, people, second frame or border.
