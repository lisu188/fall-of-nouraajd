# Creature Archetypes: Monster Race Family Taxonomy

Status: Approved taxonomy (design). Scope: groups the concrete production monster
templates in `res/config/monsters.json` into **race families** for later runtime
authoring work (EPIC_02 "create race files").

This document is design-only. It does **not** create any runtime config and does
**not** rename any concrete monster template id. The race family ids below are
*proposed* identifiers to be consumed by the later `res/config/creature_races.json`
authoring task.

## Naming policy

Per the creature-archetype naming policy, every race family id:

- uses lowerCamelCase, and
- ends with the suffix `Race` (e.g. `pritzRace`).

Concrete monster template ids in `res/config/monsters.json` (e.g. `Pritz`,
`PritzMage`) are **unchanged** by this taxonomy.

## Monster vs player-class classification

`res/config/monsters.json` mixes two kinds of top-level templates. Per AGENTS.md
("Map NPC vs player template rule"), `CPlayer`-class templates are *player
classes*, not monsters, and must not be placed as ordinary map actors. They are
excluded from the race-family taxonomy below.

Classification by the `class` field of each top-level template:

| Template id | `class` | Kind | In race taxonomy? |
| --- | --- | --- | --- |
| `Assasin` | `CPlayer` | Player class | No (player class) |
| `Sorcerer` | `CPlayer` | Player class | No (player class) |
| `Warrior` | `CPlayer` | Player class | No (player class) |
| `Inquisitor` | `CPlayer` | Player class | No (player class) |
| `Wayfarer` | `CPlayer` | Player class | No (player class) |
| `Gooby` | `CCreature` | Production monster | Yes |
| `OctoBogz` | `CCreature` | Production monster | Yes |
| `Pritz` | `CCreature` | Production monster | Yes |
| `PritzMage` | `CCreature` | Production monster | Yes |
| `Cultist` | `CCreature` | Production monster | Yes |
| `CultLeader` | `CCreature` | Production monster | Yes |
| `GoblinThief` | `CCreature` | Production monster | Yes |

The seven `CCreature` templates are the production monsters that require an
approved target race family (or a documented unresolved blocker).

## Source evidence used for grouping

Grouping is backed by template names/labels, animation paths, and how each
template is actually referenced in map configs/scripts:

- **Pritz / PritzMage** — shared `Pritz` name stem; both used together as the
  Pritscher siege force (`siegePritz` / `siegePritzMage` in
  `res/maps/siege/config.json`, with `"affiliation": "siege"`) and as ritual
  attackers (`ritualPritz` / `ritualMage` -> `PritzMage` in
  `res/maps/ritual/config.json`). `defendSiegeQuest` describes the attackers as
  the "Pritscher siege" and notes "Pritz mages carry extra wands". Shared lore +
  shared name stem => one race, `PritzMage` is the caster variant.
- **Gooby** — the named hunt boss "the Dreaded Gooby" (`res/maps/nouraajd`
  quest/dialog and `gooby` actor in `res/maps/nouraajd/config.json`). Distinct
  named creature; no other template shares its stem.
- **OctoBogz** — described in `res/maps/nouraajd/dialog2.json` as "twisted things
  part octopus, part hare, all shadowcraft" that lash with Abyssal Shadows. A
  distinct aberration lineage; no shared stem with any other template.
- **GoblinThief** — sole goblinoid template; carries the `preciousAmulet` in the
  amulet quest (`goblinThief` in `res/maps/nouraajd/config.json`). No other
  goblin template exists yet.
- **Cultist / CultLeader** — shared `Cult` stem and shared deployment as the
  ritual cult (`ritualCultist`, `ritualLeaderTemplate` -> `CultLeader` in
  `res/maps/ritual/config.json`; `CultLeader`/`Cultist` spawned together in
  `res/maps/nouraajd/script.py`). However `Cultist` is *also* reused as plain
  human NPCs (`questGiver`, `oldWoman` in `res/maps/nouraajd/config.json`, both
  `npc: true`). This makes the underlying race ambiguous (human cult faction vs.
  a distinct creature race), so these two are left **UNRESOLVED** below.

## Approved taxonomy

| Monster template (`res/config/monsters.json`) | Proposed race family id | Status | Source-backed rationale |
| --- | --- | --- | --- |
| `Pritz` | `pritzRace` | Approved | Pritscher siege/ritual footsoldier; shared `Pritz` stem. |
| `PritzMage` | `pritzRace` | Approved | Caster variant of the same Pritz force (siege/ritual mage wave). |
| `Gooby` | `goobyRace` | Approved | Named hunt creature "the Dreaded Gooby"; no shared stem. |
| `OctoBogz` | `octoBogzRace` | Approved | Distinct octopus/hare shadowcraft aberration (dialog2 lore). |
| `GoblinThief` | `goblinRace` | Approved | Sole goblinoid; reserves a goblin race for future goblin templates. |
| `Cultist` | (none yet) | **UNRESOLVED** | See blocker CRA-1. |
| `CultLeader` | (none yet) | **UNRESOLVED** | See blocker CRA-1. |

Every production (`CCreature`) monster template is accounted for: five have an
approved race family, two are explicitly unresolved.

### Proposed race families summary

- `pritzRace` — `Pritz`, `PritzMage`
- `goobyRace` — `Gooby`
- `octoBogzRace` — `OctoBogz`
- `goblinRace` — `GoblinThief`

All proposed ids end with the required `Race` suffix.

## Unresolved design blockers

### CRA-1: Cult templates (`Cultist`, `CultLeader`) have no approved race family

The `Cult` stem suggests a single `cultRace` (with `CultLeader` as the elite
variant), mirroring the `pritzRace` decision. The blocker is that `Cultist` is
not used purely as a hostile creature: it is also the base template for ordinary
town NPCs (`questGiver`, `oldWoman` in `res/maps/nouraajd/config.json`, both
flagged `npc: true` with `CNpcRandomController`). "Cult" is a *faction/affiliation*
in the existing content, not clearly a biological race, and the same template
spans both robed cultists and unrelated townsfolk.

Open questions that must be answered by design before a race id is assigned:

1. Is "cult" a race, or a human faction whose members should share a future
   `humanRace`-style family?
2. Should the NPC reuse of `Cultist` (questGiver, oldWoman) be re-pointed to a
   neutral human template so the `Cultist` monster template can carry a hostile
   race cleanly, or must the race family tolerate NPC reuse?
3. Should `CultLeader` share whatever family `Cultist` lands in (elite variant),
   or is it a separate boss-tier race?

Until these are answered, `Cultist` and `CultLeader` remain without an approved
race family. Do not invent a `cultRace` id in runtime config until this blocker
is resolved.

## Notes for downstream (EPIC_02) work

- This document is the source of truth for the monster->race mapping. The later
  task that authors `res/config/creature_races.json` should consume the approved
  ids above and must also add the file to the root `CMakeLists.txt` resource copy
  rules (creating `res/**` runtime config requires that update). It was
  intentionally **not** created here to avoid stepping on that work and to avoid
  an untracked/uncopied resource.
- Player-class templates (`Assasin`, `Sorcerer`, `Warrior`, `Inquisitor`,
  `Wayfarer`) are out of scope for creature races.
