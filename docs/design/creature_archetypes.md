# Creature Archetypes: Monster Race Family Taxonomy

Status: Approved taxonomy (design), now partially **implemented** in runtime
config. Scope: groups the concrete production monster templates in
`res/config/monsters.json` into **race families**.

This section was originally authored as design-only, but the runtime archetype
config it specifies now exists: `res/config/creature_races.json` and
`res/config/creature_classes.json` are authored and staged, and the
`CCreatureRace` / `CCreatureClass` engine objects consume them (see
`src/object/CCreatureClass.h`, `src/object/CCreatureRace.h`). The race family ids
below remain the source of truth for the monster->race mapping; concrete monster
template ids are still **not** renamed.

### Implementation status

Assignments are **identity-only / baseline-preserving**: each archetype object
contributes no `baseStats`/`actions` (classes declare only a matching `mainStat`),
so composed stats and actions equal the pre-archetype legacy result.

| Monster template | Race | Class | Status |
| --- | --- | --- | --- |
| `Gooby` | `goobyRace` | `bruteClass` | Assigned |
| `OctoBogz` | `octoBogzRace` | `bruteClass` | Assigned |
| `Pritz` | `pritzRace` | `bruteClass` | Assigned |
| `PritzMage` | `pritzRace` | `mageClass` | Assigned |
| `GoblinThief` | `goblinRace` | `thiefClass` | Assigned |
| `Cultist` | `humanRace` | `cultistClass` | Assigned |
| `CultLeader` | `humanRace` | `cultistClass` | Assigned |

Notes:

- **`GoblinThief` → `thiefClass`**: the taxonomy's rogue role. Although the
  class selects `mainStat: agility` over `GoblinThief`'s own `strength`, this is
  numerically baseline-preserving *for this creature*: its `agility` and
  `strength` are equal at base (5 = 5) and in `levelStats` (2 = 2), and it wears
  no equipment, so `getMainValue()` returns the identical value under either main
  stat. Composed stats/actions therefore equal the legacy result.
- **`Cultist`/`CultLeader` race resolved as `humanRace`**: CRA-1 is resolved in
  favor of the human-faction interpretation — "cult" is an affiliation, not a
  biological race, and every use of the `Cultist` template (hostile cultists and
  the `questGiver`/`oldWoman` townsfolk it is reused for) is human, so they share
  `humanRace`. No `cultRace` id was invented. The assignment is race-only and
  baseline-preserving (`humanRace` contributes no stats/actions).
- **`Cultist`/`CultLeader` class assigned as `cultistClass`** at the template
  level. `cultistClass` is minimal (`mainStat: strength`, no actions/level
  growth), so it is mechanically baseline-preserving for every Cultist-derived
  use — the hostile cultists, the derived hostile templates
  (`ritualCultist`/`ashCultist`/`plagueCultist`), and the `questGiver`/`oldWoman`
  NPC reuses all keep their existing `strength` main stat and gain no abilities.
  Trade-off (UNRESOLVED-CLS-1): the two non-combat NPC reuses inherit the
  `cultistClass` *tag*, which is semantically imperfect though behaviorally
  inert. A later refinement can move the class to per-spawn / hostile-only
  assignment (or re-point the NPC reuses to a neutral human template); until
  then the template-level assignment keeps the class identity complete without
  any gameplay change.
- Player-class templates (`Warrior`, `Sorcerer`, `Assasin`, `Wayfarer`,
  `Inquisitor`) are a separate player-class extraction workstream; e.g.
  `WarriorClass` is authored in `res/config/creature_classes.json`.

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

### CRA-1: Cult templates (`Cultist`, `CultLeader`) race family — RESOLVED (`humanRace`)

**Resolution:** "cult" is a *faction/affiliation*, not a biological race. The
`Cultist` template is not used purely as a hostile creature — it is also the base
template for ordinary town NPCs (`questGiver`, `oldWoman` in
`res/maps/nouraajd/config.json`, both `npc: true` with `CNpcRandomController`) —
and every one of those uses (robed cultists and townsfolk alike) is **human**.
The shared race family is therefore **`humanRace`**, not a `cultRace`. This
answers the original open questions as follows:

1. *Is "cult" a race or a human faction?* — A human faction. Members share
   `humanRace`.
2. *Re-point the NPC reuse, or tolerate it?* — Tolerate it. Because the shared
   race is `humanRace`, it is correct for the `questGiver`/`oldWoman` reuses too,
   so no re-pointing is needed. `race: humanRace` is assigned at the template
   level and is baseline-preserving for every use (the race contributes no
   stats/actions).
3. *Does `CultLeader` share the family?* — Yes; `CultLeader` is also `humanRace`.

No `cultRace` id was invented. What remains deferred is the combat **class**: a
`cultistClass` role would be wrong for the non-combat NPC reuses if attached at
template level (see UNRESOLVED-CLS-1), so the class is left unassigned pending
that separate decision. `Cultist` and `CultLeader` now carry `humanRace`
(race-only).

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

This taxonomy is now **implemented** in runtime config: the class ids it defines
are authored in `res/config/creature_classes.json` (`bruteClass`, `mageClass`,
`WarriorClass`) and referenced from templates via the `creatureClass` property. It
still does **not** rename any concrete template id in `res/config/monsters.json`.
See the Implementation status table at the top of this document for current
assignments.

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

### UNRESOLVED-CLS-1: Cultist template's NPC reuse vs `cultistClass` — RESOLVED (template-level, minimal)

The `Cultist` template is reused as non-combat NPCs. This is resolved by keeping
`cultistClass` **minimal** (`mainStat: strength`, no actions or level growth) and
attaching it at the **template level**. Because the class contributes no
abilities and only names the `strength` main stat the Cultist-derived templates
already use, the attachment is mechanically **baseline-preserving for every use**,
including the `questGiver`/`oldWoman` NPC reuses (which keep their stats and gain
nothing). The residual cost is purely semantic — those two NPCs carry a
`cultistClass` tag they would not thematically warrant. A future refinement may
move the class to per-spawn / hostile-only assignment (or re-point the NPC reuses
to a neutral human template); that is a cosmetic cleanup, not a correctness fix,
so it is deferred rather than blocking the class assignment.

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

The four-source composition itself is implemented by
`CCreature::getEffectiveInteractions` (`src/object/CCreature.cpp`), which folds
the sources in precedence order — `race.actions`, then `creatureClass.actions`,
then `creatureClass.levelling` (level-gated), then the concrete template's own
`levelling` (level-gated) and `actions` — and deduplicates by the key above with
last/most-specific winning. Each archetype reference is independently
null-guarded, so a legacy creature with neither a race nor a `creatureClass`
composes only its own concrete sources. This composition is pinned by
`test_creature_effective_interactions_compose_archetype_sources` (race/class
sources fold in at the documented positions, including the legacy no-archetype
path) alongside `test_creature_effective_interactions_compose_and_dedupe_sources`
in `tests/unit/test_object.cpp`.

---

# Creature stat precedence contract

Status: Approved (design + engine). Scope: pins the order in which a creature's
*effective* (composed) stats are assembled from its sources, so the upcoming
race/class archetype authoring (EPIC_02) and the existing concrete monster
templates produce one stable, well-defined stat block instead of an ambiguous or
order-dependent merge. This is the stat analogue of the action merge contract
above.

## Approved precedence order

A creature's effective stats are composed by accumulating, in this order from
least specific to most specific (a later source's contribution is applied on
top of the earlier ones):

1. **`race.baseStats`** — flat stats every member of the race always has.
2. **`creatureClass.baseStats`** — flat stats granted by the creature's class at
   creation.
3. **`creature.baseStats` overrides** — the concrete template / spawn's own
   `baseStats` (today's `CCreature::baseStats`), layered on top of race/class
   base.
4. **`creatureClass.levelStats` (per level)** — the class's per-level stat growth,
   applied once for each level the creature has reached.
5. **`creature.levelStats` overrides (per level)** — the concrete template's own
   per-level growth (today's `CCreature::levelStats`), applied once per level.
6. **Equipment** — the stat bonuses of every equipped item.
7. **Effects** — the stat bonuses of every active effect.

Numeric stats accumulate additively (each source's per-property value is added),
so for numeric properties "later overrides earlier" means the later source's
contribution is layered on top of (added after) the earlier sources. The
ordering still matters for any non-commutative or selecting step (notably the
main stat below) and to give a single, reproducible composition.

### Racial advancement (racialLevel) — future-gated growth source

Racial advancement is modeled **separately from the class-driven `level`**
(EPIC_08/STORY_04/SUBSTORY_01): `CCreatureRace.racialLevelStats` is a
hit-dice-style per-racial-level growth block and `CCreature.racialLevel` counts
racial levels, distinct from `CCreature.level`. It folds in **between positions
3 and 4** above (position "3a"): race-derived growth is the least-specific
per-level source, so it opens the growth block ahead of
`creatureClass.levelStats` and `creature.levelStats`, mirroring how
`race.baseStats` leads the base block. Both default neutral (`racialLevel = 0`,
empty progression), so the fold is a strict no-op for all existing content, and
there is deliberately **no XP or level-up wiring** for `racialLevel` yet —
raising it requires explicit XP/scale design and is deferred. The legacy path
(`race == null`) has no racial source by construction. Pinned by
`test_racial_progression_defaults_keep_composition_neutral` and
`test_racial_level_composes_race_progression_independently_of_class_level` in
`tests/unit/test_object.cpp`.

## Main stat selection (class first, then legacy creature baseStats)

The composed block's **`mainStat`** is a *selected* (not accumulated) field. It
is taken from the most specific source that declares it, resolved as:

- **`creatureClass.baseStats.mainStat`** first (the class defines the role /
  primary attribute), then
- **falling back to the legacy `creature.baseStats.mainStat`** when no class is
  present or the class does not declare a main stat.

With no archetype objects in the codebase yet, every creature resolves to the
legacy `creature.baseStats.mainStat` fallback; this is the value
`CCreature::getStats` currently seeds onto the composed block. `getMainValue()`
then reads the named property out of the fully composed block, so the main stat
reflects all of the accumulated numeric sources above.

## Future sources (race / creatureClass) compose at the documented positions

The race and `creatureClass` archetype objects (`CCreatureClass`) do **not**
exist in the codebase yet (`git grep CCreatureClass src/` finds only design
comments). Positions 1, 2, and 4 above are therefore *future* sources: they have
no backing object today and contribute nothing. The contract pins where they
slot in once the archetype foundation lands, so adding them later is a localized
change at `CCreature::getStats` (insert race/class base ahead of
`creature.baseStats`, and class level growth ahead of `creature.levelStats`)
without disturbing the equipment-then-effects tail or the
class-then-legacy main-stat rule.

## Where this is enforced and tested

The single composition primitive is `CCreature::getStats`
(`src/object/CCreature.cpp`): it seeds the main stat (legacy creature
`baseStats` today, class-first once classes exist), then `addBonus`-accumulates
`baseStats`, `levelStats` once per level, every equipped item's bonus, and every
effect's bonus, in the documented order. This contract is pinned by the native
regression tests `test_no_archetype_creature_stats_keep_legacy_composition`
(full per-property composition) and
`test_creature_stat_precedence_orders_sources_and_main_stat` (override ordering
and the class-then-legacy main-stat fallback) in `tests/unit/test_object.cpp`.

---

# Legacy fallback compatibility contract

Status: Approved (design + engine). Scope: pins, as a **hard forward-compatibility
rule**, the behavior of a creature that has **neither a race nor a
`creatureClass`**. Such a creature uses the **current legacy stat and level-up
paths exactly**, with no behavioral change of any kind. This protects existing
saves, existing test fixtures, and any partial-migration state in which only some
creatures have been given an archetype. It is the compatibility counterpart of the
stat-precedence and action-merge contracts above: those define how archetype
sources compose *when present*; this one defines what must happen when they are
**absent**.

## Approved hard rule

For a creature with no race and no `creatureClass` (the **legacy creature**):

1. **Stats** are composed **exactly** as the legacy path composes them today —
   `creature.baseStats` (seeding `mainStat`), then `creature.levelStats` applied
   once per level, then equipment bonuses, then effect bonuses. No race/class base
   stats, no class level growth, and no class-supplied main stat participate,
   because there are no such sources. The composed block is bit-for-bit the
   pre-archetype result.
2. **Level-up** runs the legacy path **exactly** — incrementing `level` and
   applying the concrete template's own `levelling` unlock for that level. No
   race- or class-driven level action, growth, or progression is introduced.
3. **Main stat** resolves to the legacy `creature.baseStats.mainStat`. The
   class-first selection rule never engages because there is no class.

Because the race / `creatureClass` archetype objects (`CCreatureRace`,
`CCreatureClass`) do **not exist in the codebase yet**, **every** creature is a
legacy creature today, and this rule pins that observed behavior so that landing
the archetype foundation cannot silently alter it.

## Deserialization assigns no default race or class

Deserialization (loading a creature from JSON config or from a save) **must not**
assign a default race or `creatureClass`. A creature is a legacy creature unless
its source data explicitly provides an archetype reference. Concretely:

- The serialization/property contract for a creature is the `V_META` property
  list on `CCreature` (`src/object/CCreature.h`). It declares the legacy stat and
  progression fields (`baseStats`, `levelStats`, `levelling`, `level`, `exp`,
  `equipped`, `items`, `effects`, ...) and declares **no** `race` and **no**
  `creatureClass` property. A loaded creature therefore acquires neither, and any
  archetype keys that may appear in future data are simply not bound onto a
  legacy-shaped object.
- No constructor, loader, or post-load step seeds a fallback/default archetype.
  An old save or an un-migrated fixture round-trips to a legacy creature
  unchanged.

A **later migration may opt in** to assigning a race/class — but only explicitly,
guarded, and version-gated. Absent such an explicit opt-in, the deserialized
result is a legacy creature. This is a hard rule: a default archetype must never
be introduced implicitly as a side effect of adding the archetype foundation.

## Where this is grounded and enforced

Grounded in the current legacy paths in `src/object/CCreature.cpp`:

- **Stat composition** — `CCreature::getStats` (`src/object/CCreature.cpp:834`).
  Positions 1, 2, and 4 (race base, class base, class level growth) are documented
  extension points that contribute nothing today, so the function already produces
  the exact legacy composition for a creature with no archetype.
- **Level-up** — `CCreature::levelUp` (`src/object/CCreature.cpp:572`) and the
  per-level unlock it applies, `CCreature::getLevelAction`
  (`src/object/CCreature.cpp:100`), which reads only the concrete template's
  `levelling` map.
- **Deserialization** — the `V_META` property declaration on `CCreature`
  (`src/object/CCreature.h:50`), which binds only the legacy fields and **no**
  race/class property, so loading assigns no default archetype.

When the archetype foundation lands, it must preserve this rule: the
race/`creatureClass` sources may only ever *add* to a creature that explicitly
declares them, and the no-archetype path must remain identical to today's legacy
behavior. The stat side of "identical to legacy" is already pinned by the native
regression test `test_no_archetype_creature_stats_keep_legacy_composition` in
`tests/unit/test_object.cpp` (a creature with no archetype composes to the legacy
stat block); the level-up and no-default-archetype guarantees here are pinned by
this approved contract and must be covered by a regression test alongside any
change that introduces the archetype objects.

---

# Creature template overlay layer (future mechanics, EPIC_08)

Status: Scaffolding (definition object + composition hook landed; no content uses
it). Scope: an OPTIONAL, ORDERED transformation layer for variant overlays --
elite, undead, cult-touched, diseased, boss -- applied AFTER race/class
composition. Templates never replace the race or the `creatureClass` reference;
boss/cult status is expressly NOT modeled as a race.

- **Definition object** — `CCreatureTemplate` (`src/object/CCreatureTemplate.h`),
  a CGameObject-derived metadata definition like `CCreatureRace`/`CCreatureClass`
  (registered in `NativePlugin::register_creatures`, never spawnable, never a
  `CCreature` subtype). Properties, all optional with neutral defaults:
  `statAdjustments` (additive `CStats` delta), `actions` (action additions),
  `subtypes` (data-only classification tags), `scaleAdjustment` (delta to
  `getScale`), and `order` (the ordering key).
- **Attachment** — `CCreature.templates` (`std::set` V_PROPERTY, so template
  references serialize/clone exactly like the race/class references). Templates
  apply in ascending `order`, ties broken by configured identity
  (`CCreature::getOrderedTemplates`).
- **Stat hook** — `CCreature::buildComposedStats` folds `statAdjustments` in
  template order after the race/class/creature base+level stack (position 6),
  before equipment/effects. **Action hook** — `getEffectiveInteractions` merges
  template actions after class sources and before the concrete template's own
  sources, under the same dedupe key as the action merge contract. **Scale
  hook** — `getScale` adds the accumulated `scaleAdjustment`.
- **Neutrality invariant** — a creature with NO templates composes bit-identically
  to the contracts above; example definitions in
  `res/config/creature_templates.json` are intentionally unreferenced. Pinned by
  `test_no_template_creature_composes_bit_identically_to_baseline`,
  `test_creature_templates_compose_after_race_and_class_in_order`,
  `test_creature_templates_do_not_replace_race_or_class` and
  `test_creature_template_metadata_round_trip` in `tests/unit/test_object.cpp`.

# Developer guide: adding a race, a class, or a monster

Status: Reference. Scope: the concrete, file-level steps for extending the
archetype model, and the rules that must not be violated. This ties together the
taxonomy and the contracts above into a checklist so a future agent adds content
in the right places and does not reintroduce player-only class/race logic.

## Where each thing lives

| Thing | Authored in | Engine object | Notes |
| --- | --- | --- | --- |
| Race archetype | `res/config/creature_races.json` | `CCreatureRace` (`src/object/CCreatureRace.h`) | Metadata only; not a spawnable creature. Id ends with `Race`. |
| Class archetype | `res/config/creature_classes.json` | `CCreatureClass` (`src/object/CCreatureClass.h`) | Metadata only. Id ends with `Class` and must not duplicate a concrete template id. |
| Concrete monster | `res/config/monsters.json` | `CCreature` / `CPlayer` template | Keeps its own id; references a race/class by `{"ref": "..."}`. |

Both archetype objects are registered as constructible types in
`src/core/CModule.cpp` (`register_type_metadata<CCreatureRace, CGameObject>()` /
`<CCreatureClass, CGameObject>()`, plus the pybind `class_` bindings). A new
*field* on either object must be wired through its `V_META` property list and, if
Python needs it, its pybind bindings — but adding a new *instance* (a new race or
class id) needs no C++ change, only JSON.

## Adding a monster archetype (race and/or class)

1. **Add the race** to `res/config/creature_races.json` and/or the **class** to
   `res/config/creature_classes.json`. Follow the naming policy: lowerCamelCase,
   suffix `Race` / `Class`, and never let a class id equal a concrete template id.
2. **Assign it** on the concrete template in `res/config/monsters.json` via a
   `"race": {"ref": "<raceId>"}` and/or `"creatureClass": {"ref": "<classId>"}`
   entry. Do **not** rename the concrete template id.
3. **Keep monster assignments baseline-preserving** unless the task explicitly
   changes balance: an identity-only archetype contributes no `baseStats`/`actions`
   (a class may declare only a matching `mainStat`), so composed stats and actions
   equal the pre-archetype legacy result. See the *Implementation status* table for
   worked examples (e.g. `GoblinThief` → `thiefClass` is baseline-preserving because
   its `agility` and `strength` are equal).
4. **Regenerate the stat baseline fixture** when an assignment changes composed
   stats: `tests/fixtures/creature_stat_scale_baseline.json` is config-derived and
   guarded by `tests/test_creature_stat_scale_baseline.py`.

## Staging is required (do not skip)

`res/config/*.json` files are **not** globbed into the build — each is staged by an
explicit `configure_file(res/config/<name>.json config/<name>.json)` line in
`CMakeLists.txt` (see the block around lines 262–277, which already lists
`creature_races.json` and `creature_classes.json`). If you introduce a **new**
config file, add its `configure_file` line, or the engine will not load it at
runtime and `createObject` will fall back to class-name construction — a failure
that unit tests and `validate_content.py` do not catch but the gameplay
walkthrough does.

## What validation enforces

`scripts/validate_content.py` (run `python3 scripts/validate_content.py
--repo-root .`) already checks that:

- every `CCreatureClass` `actions` / `levelling` entry resolves to a
  `CInteraction`, and `levelling` keys are positive-integer strings;
- map `script.py` player class checks reference a **known** class id
  (`getPlayerClassId()` against config-derived ids);
- only races whose `playerSelectable` property is true participate in player race
  selection.

Extend the validator (and `tests/test_content_validator.py`) when you add a new
class/race invariant rather than relying on runtime discovery.

## Rules that must not be violated

- **Do not rename** concrete monster/player template ids in `monsters.json`, nor
  any quest/dialog/object id. The archetype layer references templates; it never
  renames them.
- **Do not invent a player-selectable race.** `CCreatureRace.playerSelectable`
  defaults to `false`; monster races are non-selectable. Making a race
  player-selectable (or adding a new player race/class) is **content-owner-gated**
  and must not be inferred by an agent — it requires explicit approval, because it
  changes the player-facing new-game roster. Assigning an existing archetype to a
  *monster* is not gated.
- **Never assign a default archetype implicitly.** Per the *Legacy fallback
  compatibility contract*, deserialization must not seed a race/`creatureClass`;
  a creature is legacy unless its data explicitly declares one.
- **Compose, don't special-case.** Stats and actions must flow through the
  documented precedence/merge order (see the *stat precedence* and *action merge*
  contracts), not through player-type or class-name branches in gameplay code.
