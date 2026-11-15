# Baldur's Gate city NPC artwork

The standalone city uses 41 local PNG cutouts to distinguish townspeople, guards, nobles, merchants,
spellcasters, children, small-folk characters, animals and encountered creatures. The existing
`barrowKnight`, `fenGhoul` and `lengSpider` images supply three additional body families.

The files live in `res/maps/baldursGate/images/npc/`. They were generated with the built-in imagegen
tool. The complete prompts, any background-only edit prompts, dimensions and selected-byte fingerprints
are recorded in `baldurs_gate_city_npc_prompts.json`. Selected outputs were copied without pixel
transformation. Development evidence retains the generated originals and discarded variants outside Git.

## Appearance selection

`scripts/build_baldurs_gate_city.py` applies appearance after all source actor factories are prepared.
It uses audited source animation/sex facts and the existing creature class, race, store and custody
properties. Guard roles take priority over cleric-shaped source bitmaps. Source-animated animals and
monsters retain corresponding bodies, and human disguises stay human. Clothing families are visual
adaptations and do not assign a new occupation, alignment, race or class to an actor.

The compact table covers the 425 source-creature identities currently instantiated by the authored
city. Its source fingerprint checks all 571 supporting CRE records. New or changed source identities
require an appearance audit instead of silently inheriting a generic portrait. The original-versus-EE
source questions remain separate acceptance requirements.

The original artwork increment changes animation references on 1,326 creature definitions and the
Emissary Tar corpse container. Their other fields, item ownership, statistics, quests, dialogue,
positioning, schedules and collision remain unchanged. The final pass includes the existing poison
encounter factories so their cloned templates receive their own appearances.

The integrated Seven Suns content adds one configured revealed-doppelganger template. It receives
the same local doppelganger image as the native replacement factory, bringing the appearance pass to
1,327 creature definitions plus the corpse container. The existing four-lineage native stock test
asserts the actual prepared actors' animation path; native execution remains a separate validation lane.
The appearance regression freezes the combined Seven Suns gameplay metadata while excluding only
source actor artwork and asset declarations.

The combined baseline was derived by a three-way structural merge of the reviewed artwork parent
`27a98ea7` and Seven Suns main `6e7029b7`, relative to their common base `bef5940e`. No non-appearance
scalar conflicts were present. The artwork parent's normalized gameplay digest remains the original
`db282539abd9ce4b1d54b920b764c3f5d7f3b08e70d28d35b724511bfd61f037`;
the Seven Suns parent's digest is `dbc9fa36a8ef934db2f5fdf92d262828c3844beb06879b0dca1848e2f6954d1e`.
Their derived union, rather than an unrestricted rebaseline, is frozen as
`3c62c252a5790d00b209aa0b3c9bdf98daf5a9d4d2578f1b49c35f9948648f02`.

## Resource staging and checks

The map's `assets` declarations feed the existing registered CMake map-asset staging function and the
map directory installation rule. Other scenarios and the global reviewed artwork set keep their
existing assets. Animation references use `maps/baldursGate/images/npc/<id>` without a file extension.

Every PNG is below the native four-million-pixel limit, has actual RGBA transparency and has transparent
corners. The static renderer consumes one whole image per animation, so these files are individual
cutouts rather than sprite sheets.

Run the focused checks with:

```text
python -m unittest tests.test_baldurs_gate_city_appearances
python scripts/build_baldurs_gate_city.py --check
python scripts/build_baldurs_gate_city_ledger.py --check
```

The regression tests cover appearance precedence, source disguises and cloned factories, unchanged
non-appearance data, declaration completeness, copied bytes and PNG limits. Model and resource checks
remain distinct from native gameplay, rendered readability, original-game parity and owner acceptance.
