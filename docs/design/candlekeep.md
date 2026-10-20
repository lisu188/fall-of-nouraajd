# Candlekeep prologue

Candlekeep is a standalone scenario selected through **New adventure → Standalone scenario → Candlekeep**.
It adapts the original Baldur's Gate prologue to this game's heroes, equipment, movement and turn-based combat.
Departure with Gorion ends this scenario. The road ambush, later campaign and Chapter 6 return are separate scope.

## Map and authored interactions

The courtyard uses a 64 by 56 grid, compressing the supporting AR2600 raster's 5120 by 3840 coordinates.
Landmarks retain their relative positions. The temple priest is outdoors, as in the source area.
Seven interiors share disconnected regions of level 1; the inn's upstairs rooms occupy level 2.
Paired navigation-aware entrances keep all actors, containers and progress inside one serialized map.
The central library stays closed during the prologue.
The inn's upper floor has seven rooms. Every one of the 37 supporting area-container records has a separate
map object, including empty containers; loot is not pooled between rooms. The supporting container facts retain
their area, index, coordinates, raw lock/trap fields and native threshold conversion in the source fixture.

The six errands concern Phlydia, Firebead, Dreppin, Hull, Fuller and Reevor. Their rewards, inventory exchanges,
early item acquisition and repeated conversations have separate state from the optional training, theft,
services, aftermath conversations and departure. Objects have fixed contents rather than random chest loot.
NPC reward possessions are shared with their pickpocket inventory so stealing an item cannot create a second copy
at turn-in. Training creatures and rewards do not count toward the storehouse infestation.

Winthrop offers 44 base-archive stock rows after explicitly excluding the three documented EE weapon additions;
the outdoor temple offers four supply rows and six services. Five source drinks and four room tiers retain their
audited neutral prices. Full menus and quick purchases share saved finite stock counters. The supporting stock
facts and each native equipment conversion are in `tests/fixtures/candlekeep_shop_stock.json`.

The source-defined checklist is `tests/fixtures/candlekeep_interactions.json`.
Its entries retain conditions, outcomes, code references and branch obligations, including unresolved source questions.
It is deliberately outside the map directory: arbitrary JSON files there are loaded as object configuration.
Checklist membership and model tests are separate from a successful native gameplay witness.

## Native rules conversion

Checks read the hero's current composed `getStats()` result, including equipment and existing race modifiers.
No additional BG1 character sheet or selectable race/class is introduced.

| Source role | Native rule |
| --- | --- |
| Reaction | Intelligence plus local standing; below 7 unfavorable, 7–11 ordinary, at least 12 favorable |
| Routine / difficult / exceptional lock or theft | Agility at least 12 / 16 / 18 |
| Ordinary / reinforced forcing attempt | Strength at least 12 / 14, only where forcing is permitted |

Source-specific ownership and unavoidable-detection flags still apply after a successful ability check.
Crime and donation consequences belong to Candlekeep's saved local standing. They do not change other maps.
Quest stages, talk counters, unique possessions, stock depletion, training progress and departure claims use
serialized object or map properties, not process-global Python state.

Item names and transactions retain their source identity while effects and equipment use native templates.
This is an adaptation, not AD&D combat, pricing-reaction, spell or equipment-slot parity.
Tutorial instructions describe this engine's actual controls. Conversations use newly authored wording.

Obe's exercise uses two waves, five actual ally actors with native actions/controllers, and a saved limit of
120 map turns. Completion, stopping, timeout, defeat and departure restore the hero's saved HP, mana,
affiliation and equipment, and remove temporary actors and borrowed items. The initial purse adds 50 native gold.
These are explicit adaptation choices; the original timer, damage and starting-money rules remain unresolved.
Spawn/inspection flags alone do not prove that each ally acted in a native session.
Practice opponents inflict zero damage, as both classic guides describe. Native defeat recovery is still guarded:
it reclaims the hero's actual possessions before deleting practice actors, defers final restoration until after
unordered native respawn callbacks, and restores equipment before HP/mana to avoid native maximum-stat clamping.

Identify scrolls consume only when revealing an owned unidentified item; using Firebead's scroll can strand his
errand. Armor grants 20 native armor for 12 effect ticks. Infravision has no matching darkness/vision-range rule
and retains its scroll. Active Slow Poison and Raise Dead without a dead native companion decline without charge.
Those unsupported outcomes are acceptance gaps, not equivalent implementations of the original spells.

## Reproducible source audit

Run from the repository root with Python 3.11 or newer:

```powershell
python scripts/audit_candlekeep_source.py `
    --game-root "C:\Program Files (x86)\GOG Galaxy\Games\Baldur's Gate - Enhanced Edition" `
    --language en_US --area AR2600 --output-dir build/candlekeep-audit
```

The development-only auditor uses the standard library. It resolves KEY/BIFF resources without extracting whole
archives, records base and effective override views separately, follows area/creature/dialog/script/store/item
references and records unresolved references. Original dialogue strings and compiled script blocks remain in
the ignored local audit, not in the published scenario or fixtures.

The inspected installation is **BG1 Enhanced Edition supporting evidence**, not original BG1 authority.
Its KEY SHA-256 is `728f50c48187f3a095e262fc2cc9e43004b4519ae9b96dd6c2615aeae4f85bce`;
the inspected English TLK SHA-256 is `a530306b14439e680f3c2d9f4b368b418b529fef9a015ac76d19a0b229be1d96`.
The install declares Sorcerer/Monk, Psion and Cipher GemRB class mods. The audit found 2046 override files;
119 referenced resources differ between its base and effective views. The adaptation uses the base evidence and
does not import those class mods.

The retained pre-review audit graph contains 9 ARE, 113 BCS, 106 CRE, 176 DLG, 332 ITM, 55 SPL and 2 STO resources in each
view, with 62 unresolved references per view. Shared actor dependencies extend into other chapters even with
the nine-area allowlist; excluded external areas and scripts remain recorded in the local report. This is an
overapproximation, not a proof that these references execute during the prologue. The auditor exits nonzero
while unresolved references remain. Its local gzip report's decompressed SHA-256 is
`36f545a938bef46acf00fcc759ada01af6351bddca3bc8f5857d223ba0b39e27`.
This retained report predates the correction for literal `GiveItem` and `UseItem` references whose IDS argument
is named `Object`. Its counts and hash describe that historical report; regenerate the audit before using
these numbers as evidence for the corrected parser.
Per-resource fingerprints cover complete payloads; BIF fingerprints explicitly identify header/table scope.
The audit does not establish execution reachability, interpret all
engine hardcoding, or prove that every original interaction is accounted for. Missing references, source
edition differences and unsupported semantics must remain visible. Original BG1 files were not found in the
readable C: filename scan; the available classic BG2 backup is not a substitute.

References: [classic annotated map](https://www.forgottenwars.com/bg1/maps/x_2600.jpg),
[Dudleyville walkthrough](https://www.forgottenwars.com/bg1/ar2600.htm),
[GameBanshee walkthrough](https://www.gamebanshee.com/baldursgate/walkthrough/candlekeep.php),
[Infinity Engine format documentation](https://gibberlings3.github.io/iesdp/file_formats/index.htm).
The two walkthroughs corroborate the errands and landmarks; they do not enumerate every original dialog branch.

## Validation and acceptance

Focused commands, from the repository root:

```text
python -m unittest tests.test_candlekeep_source tests.test_candlekeep_content
python scripts/validate_content.py --repo-root .
python -m unittest tests.test_gameplay_branch_catalog tests.test_gameplay_branch_driver
python test.py --suite mcp-branches --branch-group candlekeep
python scripts/generate_screenshots.py --maps candlekeep --no-random --output-dir screenshots
```

The MCP command requires a current `_game` build and CMake-staged resources. Its routes must move the actual hero,
select authored choices, perform native combat and transactions, and verify saves and observable state.
They cannot earn branch credit through injected flags, forced rewards or direct callback dispatch.
Pure parsing, model behavior and catalog coverage must be reported separately from those receipts.
The route module records native choice-selection purchases, sales, services and equipment loans as pending
obligations; model checks and headless cancellation receipts cannot supply that evidence. Portal teardown and
hero-defeat cleanup have named source/model contracts rather than fabricated natural-route receipts.

Visual acceptance needs isolated/offscreen captures of the courtyard, every interior, journal, dialog,
shop/service, training and departure states, followed by inspection of the actual images.
A model or source-layout check is not a freshly rendered screenshot.

Exhaustive original-game acceptance remains blocked until original-versus-EE tutor branches, training
timers/rewards/damage, crime details and complete service semantics have been reconciled. The inventory's
source-audit status must not be promoted simply because adaptation tests pass.

Known behavior gaps also include Jondalar's exact first-hit stop with Erik's archery, Tethtoril's invulnerability
and retaliation, other residents' full hostile spell/XP/possession outcomes, original guard visibility/delay,
warning/escape responses, and merchant buyback. The current Jondalar lesson uses a painless native proxy fight.
Source guard scripts summon one or two Watchers; matching that count does not establish detection-policy parity.
These remain acceptance blockers alongside the unsupported spells and pending native UI selections above.
