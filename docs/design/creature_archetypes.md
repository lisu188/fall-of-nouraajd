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

---

# Creature Class IDs: Reusable Combat-Role Taxonomy

Status: Approved taxonomy (design). Scope: defines reusable creature **class
ids** that represent a learned **combat role / progression** (e.g. caster,
front-line bruiser, rogue), to be consumed by the later `res/config/creature_classes.json`
authoring work (EPIC_02). This section **extends** the race-family taxonomy
above; it does not rewrite or contradict it.

A **class is orthogonal to a race**: a race is *what a creature is* (species /
lineage), a class is *what role it has learned to fight as*. Two creatures of
different races can share a class (a Pritz mage and a human cultist can both be
`mageClass`), and a single race can contain members of several classes.

This taxonomy is design-only. It does **not** create any runtime config and does
**not** rename any concrete template id in `res/config/monsters.json`.

## Naming policy (classes)

Per the creature-archetype naming policy enforced by
`scripts/validate_content.py` (`CREATURE_CLASS_ID_SUFFIX = "Class"`,
`CREATURE_CLASS_REFERENCE_PROPERTY = "creatureClass"`), every class id:

- uses lowerCamelCase, and
- ends with the suffix `Class` (e.g. `mageClass`).

The JSON property that *references* a class from a template is `creatureClass`,
never the reserved object-constructor key `class`.

Concrete template ids in `res/config/monsters.json` are **unchanged** by this
taxonomy. Existing player templates (`Sorcerer`, `Warrior`, `Assasin`,
`Inquisitor`, `Wayfarer`) remain class-bearing concrete templates with their ids
preserved; the reusable class ids below describe the *role* each one already
embodies and do not replace those templates.

## How existing templates express a role (source evidence)

Roles are grounded in each template's `mainStat` and its `levelling` ability set
in `res/config/monsters.json`:

- **Caster / mage role** — `mainStat: intelligence`; learns offensive spells.
  `Sorcerer` (`MagicMissile`, `FrostBolt`, `ShadowBolt`, `ChaosBlast`, ...),
  `PritzMage` (`MagicMissile`, `FrostBolt`).
- **Front-line bruiser role** — `mainStat: strength`; learns strikes / sustain.
  `Warrior` (`Strike`, `Barrier`, `BloodThirst`, `DeathStrike`),
  plus the strength-based melee monsters `Gooby`, `OctoBogz`, `Pritz`.
- **Rogue / thief role** — `mainStat: agility`; learns stealth / poison / mark
  abilities. `Assasin` (`SneakAttack`, `Mutilation`, `LethalPoison`,
  `Backstab`), `Wayfarer` (`WayfarersStride`, `SneakAttack`, `SmugglersMark`,
  `Backstab`), and the agility-flavoured `GoblinThief` (its `label` is
  "Goblin Thief").
- **Holy / inquisitor martial role** — `mainStat: intelligence` but melee-armed
  (`Sword` + `Robe`); a hybrid sword-and-faith fighter. `Inquisitor`
  (`ExposeCorruption`, `Strike`, `SanctifiedWard`, `Barrier`).
- **Cult role** — `Cultist` / `CultLeader` are deployed as the ritual cult
  (see the race-family section). As a *combat role* they fight as low-tier melee
  (`mainStat: strength`, basic attacks; `CultLeader` is the elite variant). The
  role "cultist" here is a thematic faction-fighter, distinct from the
  unresolved *race* question for these templates (see below).

## Approved class taxonomy

| Class id | Combat role | Primary stat | Maps to existing templates |
| --- | --- | --- | --- |
| `mageClass` | Spell caster (ranged magical damage) | intelligence | `Sorcerer` (player), `PritzMage` |
| `bruteClass` | Front-line melee bruiser | strength | `Warrior` (player), `Gooby`, `OctoBogz`, `Pritz` |
| `thiefClass` | Rogue / stealth striker | agility | `Assasin` (player), `Wayfarer` (player), `GoblinThief` |
| `martialClass` | Sword-and-faith hybrid fighter (holy martial) | intelligence (melee-armed) | `Inquisitor` (player) |
| `cultistClass` | Faction melee fighter / ritual cultist | strength | `Cultist`, `CultLeader` (elite variant) |

Every proposed class id ends with the required `Class` suffix and is
lowerCamelCase. All twelve concrete templates have a role mapping.

### Proposed classes summary

- `mageClass` — caster; `Sorcerer`, `PritzMage`.
- `bruteClass` — strength melee; `Warrior`, `Gooby`, `OctoBogz`, `Pritz`.
- `thiefClass` — agility rogue; `Assasin`, `Wayfarer`, `GoblinThief`.
- `martialClass` — holy martial hybrid; `Inquisitor`.
- `cultistClass` — ritual cult fighter; `Cultist`, `CultLeader`.

## Acceptance: no class id duplicates a concrete template id

Concrete top-level template ids in `res/config/monsters.json` are:
`Assasin`, `Gooby`, `OctoBogz`, `Pritz`, `PritzMage`, `Sorcerer`, `Warrior`,
`Cultist`, `CultLeader`, `GoblinThief`, `Inquisitor`, `Wayfarer`.

None of these template ids end with `Class`, and none equal any approved class
id above (`mageClass`, `bruteClass`, `thiefClass`, `martialClass`,
`cultistClass`). The suffix policy makes collision structurally impossible:
template ids are PascalCase concrete names, class ids are lowerCamelCase ending
in `Class`. **No class id duplicates any concrete template id.**

## Class vs the Cultist/CultLeader race blocker

The race-family section leaves `Cultist` / `CultLeader` **UNRESOLVED** at the
*race* level (blocker CRA-1: is "cult" a biological race or a human faction, and
how to handle the NPC reuse of `Cultist` for `questGiver` / `oldWoman`).

Because **class is orthogonal to race**, `cultistClass` as a *combat role* is
independent of CRA-1 and resolves cleanly: it describes how the hostile cult
templates fight (low-tier melee, `CultLeader` elite), regardless of which race
family they eventually land in. Assigning `cultistClass` does **not** require
CRA-1 to be resolved, and does **not** pre-judge it.

One consequence to flag for downstream: the NPC reuses of the `Cultist`
template (`questGiver`, `oldWoman`, both `npc: true`) are not combatants, so a
`creatureClass: cultistClass` reference, if added at the template level, would
also attach to those NPCs. EPIC_02 authoring should attach class either per
spawn or only to the hostile uses, OR re-point the NPC reuses to a neutral human
template first (this is the same re-pointing question raised by CRA-1, item 2).
Marked **UNRESOLVED-CLS-1** below; it does not block approving the class id list.

## Unresolved class items

### UNRESOLVED-CLS-1: Cultist template's NPC reuse vs `cultistClass`

The `Cultist` template is reused as non-combat NPCs. Whether `cultistClass` is
attached at template level (leaking onto NPCs) or only at hostile spawn sites is
a downstream authoring decision tied to CRA-1; flagged here, not resolved.

### UNRESOLVED-CLS-2: `martialClass` lore name needs human approval

`martialClass` currently has exactly one member (`Inquisitor`) and is partly a
catch-all for the "intelligence main stat but sword-armed holy fighter" shape.
The role exists and is correct, but the *name* (`martialClass` vs e.g. a more
lore-specific holy/inquisitor name) should be confirmed by design before runtime
authoring. The id itself is policy-valid; only the lore label is pending.

## Notes for downstream (EPIC_02) class work

- This section is the source of truth for the template->class (role) mapping.
  The later task that authors `res/config/creature_classes.json` should consume
  the approved class ids above, reference them via the `creatureClass` property
  (never `class`), and must add the new file to the root `CMakeLists.txt`
  resource copy rules. The runtime config was intentionally **not** created here
  (doc-only deliverable; class-config authoring is EPIC_02 work) to avoid an
  untracked/uncopied resource.
- Classes (roles) and races (species) are independent axes. A future template
  may carry both a race family id and a `creatureClass` id.

---

# Creature action merge contract

Status: Approved (design + engine). Scope: pins the order in which a creature's
actions are composed from its archetype sources and how duplicate actions are
deduplicated, so the upcoming race/class archetype authoring (EPIC_02) and the
existing concrete monster templates compose a single, stable action set instead
of accumulating duplicates.

## Precedence order

A creature's available actions are composed by merging, in this order, from
least specific to most specific:

1. **Race innate actions** — actions every member of the race always has.
2. **Class starting actions** — actions granted by the creature's class at
   creation.
3. **Class level unlocks** — actions unlocked as the creature gains levels
   (today expressed by the `levelling` map, applied via `levelUp`).
4. **Concrete-template actions** — actions declared on the concrete template /
   spawn (the most specific source).

Sources are applied in that sequence, so a later (more specific) source is the
"winner" when two sources contribute the same action.

## Deduplication key (last/most-specific wins)

Actions are deduplicated by configured identity:

- the dedupe key is the action **`typeId`**;
- when `typeId` is empty, it falls back to the action **`name`**.

When a later source contributes an action whose key matches one already present,
the earlier action is replaced by the later one (last/most-specific wins). The
relative order of unrelated, surviving actions is otherwise preserved
(stable merge). Consequences:

- duplicate generic actions (e.g. two `Attack` definitions arriving from a race
  source and again from a concrete template, common after archetype migration)
  collapse to a **single** `Attack` entry rather than accumulating;
- a unique concrete override (an action a more specific source defines that no
  earlier source provided) is **preserved**;
- an action redefined by a more specific source replaces the earlier definition
  rather than coexisting with it.

This key matches the engine's existing configured-identity semantics
(`CGameObject::sameConfiguredType` / `name_comparator`, which prefer a matching
`typeId` and fall back to type/name only when `typeId` is empty).

## Where this is enforced and tested

The merge primitive every source funnels through is
`CCreature::addAction` (`src/object/CCreature.cpp`): `setActions` composes the
set by calling `addAction` per entry, and level unlocks call it via `levelUp`.
`addAction` deduplicates by the key above and keeps the last-added (more
specific) action. This contract is pinned by the native regression test
`test_creature_action_merge_dedupes_by_type_id` in
`tests/unit/test_object.cpp`.
