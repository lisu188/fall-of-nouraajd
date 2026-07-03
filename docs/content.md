# Content schema

Reference for author-facing content declarations validated by
`scripts/validate_content.py`. Run the validator locally with:

```
python3 scripts/validate_content.py --repo-root .
```

## Map assets (`map.json` → `assets`)

Each map lives in `res/maps/<name>/` and is described by a Tiled-style
`map.json`. A map may additionally declare the local assets it owns through an
**optional** top-level `assets` array. The declaration documents and validates
which files, directories, and logical resources a map owns. It is now also
load-bearing: engine loading treats the map's own directory as an active scoped
search root (so map-local animations/textures resolve), and the CMake build
**stages each declared asset into the build tree**. A map-local asset that an
animation/background field references but does not declare would therefore not be
packaged — so declared assets and referenced assets must stay consistent (see
**Reference consistency and staging** below). Adding `assets` remains safe and
purely additive for existing maps: they declare no `assets` and reference only
global (`res/`-wide) resources, so nothing changes for them.

### Shape

```json
{
  "width": 64,
  "height": 64,
  "layers": [ /* ... */ ],
  "assets": [
    { "path": "images/portrait.png", "kind": "file" },
    { "path": "frames", "kind": "directory" },
    { "path": "anim/walk", "kind": "animationRoot" },
    { "path": "hero.combat.idle", "kind": "logicalId", "description": "combat idle pose" }
  ]
}
```

`assets`, when present, must be a JSON array. Each entry is an object with:

| Field         | Required | Description |
| ------------- | -------- | ----------- |
| `path`        | yes      | A safe POSIX-style relative path (or logical id) — see **Path safety**. |
| `kind`        | yes      | One of the kinds below. |
| `description` | no       | Free-form note for authors and reviewers. |

### Kinds

- **`file`** — a single asset file under the map directory
  (for example `images/portrait.png`). The file must exist.
- **`directory`** — a directory of assets under the map directory. The
  directory must exist.
- **`animationRoot`** — an animation base path under the map directory. It
  resolves either to a directory (multi-frame animation) or to a sibling
  `<path>.png` file (single-frame animation), mirroring how the engine resolves
  animations. One of the two must exist.
- **`logicalId`** — a logical asset identifier rather than a filesystem path.
  It is constrained to the same safe-path character rules but is **not** checked
  against the filesystem.

### Path safety

`path` is always interpreted relative to the map's own directory and must stay
within it. The validator rejects a declaration when its `path`:

- is absolute or begins with `/`;
- contains a `..` traversal segment, a `.` segment, or an empty segment;
- contains a backslash (`\`) or a colon (`:`), including Windows drive letters;
- is empty or has surrounding whitespace.

A `path` may not be declared more than once within a single map's `assets`
array.

### Reference consistency and staging

Once a map declares an `assets` array, the validator additionally enforces that
every **map-local** animation/background reference the map makes is declared.
Concretely, it walks the map's own object layers (`map.json` object
`properties.animation` / `properties.background`) and the map's local config
entries (per-map `config.json` / `dialog*.json` `properties.animation` /
`properties.background`), and for each referenced value:

- If the value resolves to a **global** asset under `res/` (as a directory, a
  file, or a `<value>.png` sprite), it is packaged independently of the map and
  is left alone — this is how the existing maps reference shared `images/...`
  animations.
- If the value resolves **only** under the map's own directory (map-local) but
  is **not** matched by a declared `assets` entry, the validator reports an
  error: an undeclared map-local asset would not be staged, so the map would
  break on a fresh build. Declare it with kind `file`, `directory`, or
  `animationRoot` (an `animationRoot` at `path` matches a reference to `path`,
  and a `file` at `path.png` matches a reference to `path`). `logicalId` entries
  are logical handles and never satisfy a filesystem reference.

On the build side, `CMakeLists.txt` reads each map's `map.json`, and for every
declared entry stages it into the build tree next to the map: `file` and
`animationRoot` (`<path>.png` form) are copied with `configure_file(... COPYONLY)`,
`directory` and directory-form `animationRoot` entries are copied wholesale, and
`logicalId` entries are skipped. Maps without an `assets` array are a no-op.

## Player class and race profiles (`res/config/classes.json`, `res/config/races.json`)

Player **class** and **race** profiles are data-only config entries that describe
the composable pieces of a player build. They are intentionally *not* engine
object configs: each profile omits `class`/`ref`, so the engine's config loader
skips them (they are read by higher-level class/race code, introduced
separately). This keeps existing player templates in `res/config/monsters.json`
working unchanged while the profiles are staged and validated.

Both files are top-level JSON objects keyed by a profile id.

### Class profile (`classes.json`)

| Field              | Required | Type | Description |
| ------------------ | -------- | ---- | ----------- |
| `profileKind`      | yes      | string `"playerClass"` | Marks the entry as a class profile. |
| `label`            | yes      | non-empty string | Display name. |
| `actions`          | yes      | array of non-empty strings | Base action ids granted by the class. |
| `levelling`        | yes      | object (level string → action id string) | Actions unlocked per level. |
| `statContribution` | yes      | object (stat name → integer) | Per-level stat contribution of the class. |
| `startingEquipment`| yes      | object | Starting equipment policy — see below. |

`startingEquipment` requires a `policy` of `"fixed"` or `"none"`; when `"fixed"`
it may carry a `slots` object mapping slot ids to item ids.

### Race profile (`races.json`)

| Field                  | Required | Type | Description |
| ---------------------- | -------- | ---- | ----------- |
| `profileKind`          | yes      | string `"playerRace"` | Marks the entry as a race profile. |
| `label`                | yes      | non-empty string | Display name. |
| `baseStatContribution` | yes      | object (stat name → integer) | Base stat contribution of the race. |
| `traits`               | no       | array of non-empty strings | Race traits (distinct from canonical gameplay tags). |
| `resistances`          | no       | object (name → integer) | Damage/effect resistances. |
| `visual`               | no       | object | Optional visual variation (e.g. an `animation` root). |

Unknown top-level keys in a profile are reported so typos are caught.

## Crafting recipes (`res/config/crafting.json`)

Each top-level key is a recipe id handled by the crafting plugin
(`res/plugins/crafting.py`); `scripts/validate_content.py` enforces the schema.

| Field           | Required | Type | Meaning |
| --------------- | -------- | ---- | ------- |
| `station`       | yes      | string | Must match some building's `craftingStationId` property. |
| `inputs`        | no       | array of item entries | Reagents consumed by the craft. Each item id may appear only once — use `count` for multiples (the runtime merges duplicates defensively, but the validator rejects them). |
| `output`        | yes*     | item entry | The crafted result. Exactly one of `output` / `outputs` must be present. |
| `outputs`       | yes*     | non-empty array of item entries | Multi-item results. |
| `gold`          | no       | non-negative integer | Gold cost, paid together with the reagents *before* the success roll — a failed craft still consumes its full cost. |
| `successChance` | no       | integer 0–100 (default 100) | Chance the craft produces its output. |
| `unlockFlag`    | no       | non-empty string | Boolean property gating the recipe; checked on the player first, then on the current map. |
| `unlockHint`    | no       | non-empty string | Map-agnostic guidance shown while the recipe is locked. A map can override it per flag by setting an `unlockHint_<FLAG>` string property on its station instance (see `scribeDesk1` in `res/maps/nouraajd/config.json`). Without either, a generic "This recipe is locked." is shown — the raw flag name is never displayed. |

An item entry is `{ "item": "<config id>", "count": <positive integer> }`
(`count` defaults to 1). Item ids must exist in the global config.

## Gameplay tags (`"tags"`)

Objects (items, effects, interactions, potions, …) may declare a `"tags"` array
of canonical gameplay tags. The vocabulary is closed and defined in
`src/core/CTags.h` (`enum class CTag`) — authoring an unlisted tag string is
rejected at load time (and by the string `hasTag`/`addTag`/`removeTag`
overloads), so typos fail loudly rather than silently doing nothing.

| Tag      | Meaning |
| -------- | ------- |
| `buff`   | Effect/interaction is beneficial and self-targeted; the AI will not cast it at an enemy and skips it when picking an offensive action. |
| `compound` | Marks a combined ("compound") artifact assembled from an artifact set. Compound items are excluded from random loot (`CRngHandler`) and are never authored into markets, so the player only ever obtains them by assembling a set (see **Artifact sets** below). |
| `curse`  | Effect/interaction is harmful — the negative counterpart to `buff`. Non-buff effects already target the victim, so a `curse`-tagged effect lands on the enemy; the tag is a marker for content, AI targeting, and curse-cleansing/resistance mechanics. Note: this tags a harmful *effect*, distinct from `cursed`, which locks an *item* to its slot. |
| `cursed` | Once equipped, the item is locked to its slot and cannot be unequipped or swapped out. The lock is enforced in `CCreature::equipItem` and mirrored in the inventory UI. Lift it (Baldur's Gate "remove curse") by clearing the tag — `removeTag(CTag::Cursed)` from an effect, interaction, or plugin — after which the item unequips normally. Any negative stats a cursed item imposes are ordinary content (its equipment bonuses / attached effect), not part of the tag itself. |
| `heal`   | Consumable restores HP; monster AI will quaff it when hurt. |
| `mana`   | Consumable restores mana; monster AI will quaff it when low. |
| `quest`  | Quest item — players cannot drop it, and the inventory UI blocks unequipping it. |
| `stun`   | Effect stuns its victim; a stunned creature skips its turn. |
| `wand`   | Marks wand-type items for wand-specific handling. |

Adding a tag touches four mirrored sites: the `CTag` enum (`src/core/CTags.h`),
the `TAG_DEFINITIONS` table (`src/core/CTags.cpp`), the pybind `CTag` binding
(`src/core/CModule.cpp`), and this table.

## Artifact sets (`res/config/artifact_sets.json`)

Heroes 3-style compound artifacts. A set groups several equippable **pieces**;
when the player has every piece equipped, the game offers to fuse them into a
single **combined artifact** that occupies all the pieces' slots and grants a
stronger bonus plus an active ability. The combined artifact can be
disassembled back into its pieces by using it from the inventory. Runtime logic
lives in `res/plugins/artifact_sets.py`; the full design is in
`docs/design/compound_artifacts.md`.

`artifact_sets.json` is a top-level JSON object keyed by a set id. Each value:

| Field      | Required | Type | Description |
| ---------- | -------- | ---- | ----------- |
| `label`    | yes      | non-empty string | Display name used in the assemble/disassemble prompts. |
| `pieces`   | yes      | array of ≥ 2 item ids | The set pieces. Each must resolve to a **distinct** equipment slot. |
| `combined` | yes      | item id | The combined artifact produced by assembling the set. |

Validated by `_validate_artifact_sets` in `scripts/validate_content.py`:

- every `pieces` entry and the `combined` id resolve to a global item config;
- the pieces map to pairwise-distinct slots (via the class → slot mapping in
  `res/config/slots.json`), and each piece class fits a real slot;
- the combined item's own class fits exactly one piece's slot (its **primary**
  slot); its `coveredSlots` property must list exactly the *other* pieces' slot
  ids (this is what makes assembly occupy the whole set — see `coveredSlots`
  below);
- the combined item declares the `compound` tag (so loot/markets never hand it
  out directly), and inherits the `quest` tag if any piece carries it;
- a `combined` id is never also a piece, and a piece belongs to at most one set.

### Combined artifacts and `coveredSlots`

A combined artifact is an ordinary item entry whose `class` is a Python subclass
of the primary slot's class (e.g. `CompoundArmor`), registered in
`res/plugins/artifact_sets.py`. Beyond the usual item fields it uses:

- **`coveredSlots`** — a reflected `CItem` property (array of slot id strings):
  the extra slots the artifact occupies while equipped, in addition to its
  primary slot. `CCreature::equipItem` blocks those slots while the artifact is
  worn and frees them when it is removed. Ordinary items omit it (empty).
- **`tags: ["compound"]`** — required (see above).

Set pieces are ordinary items re-classed to a `Set*` slot subclass (e.g.
`SetHelmet`, `SetShield`, `SetPants`) so that equipping one triggers the
set-completion check. `res/config/slots.json` maps every equipment slot,
including the `CShield` (LeftHand) and `CPants` (Legs) slots used by four-piece
sets.
