# Compound Artifacts — Heroes 3-style Artifact Sets

Status: **Implemented.** This document is the design of record; the feature now
ships. Highlights of what landed and where:

- **Engine**: `CShield` (LeftHand) and `CPants` (Legs) item classes fill the
  previously dead slot types (`src/object/CItem.*`, registered in
  `src/core/CModule.cpp` + `src/plugin/NativePlugin.cpp`); a `coveredSlots`
  (`std::set<std::string>`) reflected property on `CItem` with occupancy
  enforcement in `CCreature::equipItem`; `onEquip`/`onUnequip` now dispatch to
  Python overrides (`CItem.cpp`); the slot classes plus `equipItem`,
  `getEquipped`, `getSlotWithItem`, `hasEquipped`, `getSlotConfiguration`, and
  `getCoveredSlots` are bound to Python; a `compound` `CTag` excludes combined
  artifacts from random loot (`CRngHandler`).
- **Content**: `res/config/artifact_sets.json` defines two four-piece H3 sets —
  *Armor of the Damned* (uses the new shield slot) and *Wrath of the Dragon
  Father* (uses the new pants slot). Runtime is `res/plugins/artifact_sets.py`.
- **Assembly UX**: equipping the last piece defers (via the event loop) a
  `showSelection` prompt to fuse the set; disassembly is offered by using the
  combined artifact from the inventory.
- **Validation/tests**: `_validate_artifact_sets` in
  `scripts/validate_content.py`, validator tests in
  `tests/test_content_validator.py`, and gameplay tests in `test.py`.

The design narrative below is preserved; where it describes options or future
phases, the bullets above record what was actually built. The two answered open
questions: **compound artifacts never appear in markets or random loot**
(pieces only), and **shields and pants slots were added**.

## Goal

Port Heroes of Might and Magic 3's *combination artifacts* to Fall of Nouraajd:

- Several ordinary equippable items (**pieces**) form a named **set**.
- When the player has every piece of a set **equipped**, the game offers to
  **assemble** them into a single **combined artifact** that is stronger than
  the sum of its parts (bigger stat block, plus an active ability).
- The combined artifact **occupies the equipment slots of all its pieces**
  (H3: Angelic Alliance fills weapon + shield + helm + armor + …), so
  assembling is a real trade-off, not free slot compression.
- The combined artifact can be **disassembled** back into its pieces at any
  time.

The item roster is already seeded with H3 artifacts, including two
near-complete H3 combos — this feature is a natural continuation of the
existing content:

| H3 combo | Pieces already in `res/config/` | Missing H3 piece |
| --- | --- | --- |
| Armor of the Damned | `SkullHelmet` (CHelmet), `RibCage` (CArmor), `BlackshardOfTheDeadKnight` (CWeapon) | Shield of the Yawning Dead — no shield class exists (see "Dead slot types") |
| Titan's Thunder | `ThunderHelmet` (CHelmet), `TitansCuirass` (CArmor), `TitansGladius` (CWeapon) | Sentinel's Shield — same |
| (future) Power of the Dragon Father subset | `CrownOfDragontooth`, `DragonScaleArmor`, `DragonboneGreaves` | most of the ten pieces |

## Engine facts this design builds on

- **Items** are data-defined JSON entries (`res/config/items.json`,
  `weapons.json`, `armors.json`): `class` (slot-type marker such as `CHelmet`)
  plus `properties` — `label`, `description`, `animation`, `power`, a `bonus`
  `CStats` block, and an optional `interaction` (active ability; item
  interactions cast at 0 mana, `src/object/CItem.cpp:70-75`). Subclasses carry
  no extra state (`src/object/CItem.h:71-137`).
- **Slots** are config data: `res/config/slots.json` defines slots `"0"`–`"7"`
  (RightHand, LeftHand, Head, Chest, Waist, Feet, Legs, Hands), each with the
  item classes it accepts. Fit is metadata-inheritance based
  (`CSlotConfig::canFit`, `src/core/CSlotConfig.cpp:26-36`).
- **Equipping** funnels through one choke point,
  `CCreature::equipItem(slot, item)` (`src/object/CCreature.cpp:532-579`): it
  validates fit, enforces the cursed-slot lock, fires `onUnequip`/`onEquip`
  game events on the items, mutates the serialized `equipped` map, and emits
  the `equippedChanged` signal.
- **Bonuses are recomputed live**: `CCreature::getStats()` composes race /
  class / base / level stats, then sums `item->getBonus()` over all equipped
  items, then effect bonuses (`src/object/CCreature.cpp:909-975`). Nothing is
  baked into the creature, so swapping pieces for a combined item "just works"
  statistically.
- **Python item classes are established practice**: `TownPortalScroll` in
  `items.json` resolves to a `@register(context)` class in
  `res/plugins/object.py`; per-instance overrides are retained via
  `CPythonOverrides` (`src/core/CPythonOverrides.h`) and consulted by
  `CItem::onUse` (`src/object/CItem.cpp:55-60`). `onEquip`/`onUnequip` do
  **not** consult overrides yet (`CItem.cpp:47-53`) — that is the main engine
  gap this design fills.
- **Crafting** (`res/config/crafting.json` + `res/plugins/crafting.py`) is
  prior art for "consume N items → produce 1 item" with atomic inventory
  transactions and validator-checked item refs
  (`scripts/validate_content.py:3575`).
- **Tags**: `cursed` locks an item to its slot (enforced in `equipItem`),
  `quest` blocks dropping/unequipping (`src/core/CTags.h`, docs/content.md).
- **Python binding gaps**: `CModule.cpp` binds `getItemAtSlot`, `addItem`,
  `removeItem`, `countItems`, `useItem` — but **not** `equipItem`,
  `getEquipped`, `getSlotWithItem`, or `hasEquipped`. Assembly logic in Python
  needs those bound.

### Dead slot types

`slots.json` names `CShield` (LeftHand) and `CPants` (Legs), but neither class
exists in C++ or the validator's class list — LeftHand effectively accepts only
`CSmallWeapon`, and Legs accepts nothing. Set pieces are therefore limited to
slots with real classes (RightHand, LeftHand/small weapon, Head, Chest, Waist,
Feet, Hands). Introducing shields to complete the four-piece H3 combos is out
of scope here; the launch sets ship as three-piece versions.

## Design

### 1. Set definition schema — `res/config/artifact_sets.json`

Plain-data config (crafting.json precedent: no `class`, read by the plugin,
validated by a dedicated validator pass):

```json
{
  "armorOfTheDamned": {
    "label": "Armor of the Damned",
    "pieces": ["SkullHelmet", "RibCage", "BlackshardOfTheDeadKnight"],
    "combined": "ArmorOfTheDamned"
  },
  "titansThunder": {
    "label": "Titan's Thunder",
    "pieces": ["ThunderHelmet", "TitansCuirass", "TitansGladius"],
    "combined": "TitansThunder"
  }
}
```

| Field | Required | Description |
| --- | --- | --- |
| `label` | yes | Display name used in the assemble/disassemble prompts. |
| `pieces` | yes | ≥ 2 item ids; each must resolve to a distinct equipment slot. |
| `combined` | yes | Item id of the combined artifact (an ordinary item entry). |

Deliberately **not** in v1: partial-set bonuses (Diablo-style "2 of 4 pieces"
thresholds), unlock flags, multiple sets sharing a piece. All three are
forward-compatible schema extensions.

### 2. The combined artifact is an ordinary item

Authored next to other items; its `class` decides its **primary slot** and
must equal the class of exactly one piece. New reflected property
`coveredSlots` (phase 3) lists the other pieces' slot ids it blocks:

```json
"ArmorOfTheDamned": {
  "class": "CompoundArmor",
  "properties": {
    "animation": "images/items/armors/armorofthedamned",
    "bonus": { "class": "CStats", "properties": {
      "armor": 170, "intelligence": 12, "stamina": 14, "strength": 8,
      "agility": 5, "dmgMin": 22, "dmgMax": 30, "shadowResist": 25, "crit": 3 } },
    "interaction": { "ref": "Doom" },
    "coveredSlots": ["0", "2"],
    "label": "Armor of the Damned",
    "description": "Blackshard, rib cage and skull fused into one damned panoply.",
    "power": 22
  }
}
```

`CompoundArmor` / `CompoundWeapon` / … are thin Python classes registered by
the plugin (one per slot type used by a combined item); their `onUse` override
drives disassembly (see §5). Bonus guideline: **sum of the pieces plus a
10–20% premium**, and an `interaction` for H3 flavor (`Doom` above;
`LightningBolt` for Titan's Thunder — both already exist in
`interactions.json`). `power` ≈ sum of piece powers; verify against
`CMarket` pricing/stocking before finalizing numbers (open question §Q2).

Art: the validator requires the `animation` root to exist. Bespoke combined
art is a content TODO; until it lands, reuse the primary piece's animation
root (valid and cheap).

### 3. Engine enablers (small, generic changes)

1. **Python override wiring for equip events** — mirror the `onUse` pattern in
   `CItem::onEquip`/`onUnequip` (`src/object/CItem.cpp:47-53`): consult
   `CPythonOverrides::find_override(this, "onEquip"/"onUnequip")` and call it
   with the event before the debug log. This makes every Python-classed item
   equip-aware; it reaches all equip paths (GUI click, drag-drop, scripts)
   because the events are fired inside `CCreature::equipItem`.
2. **Bindings** — expose on the creature binding in `src/core/CModule.cpp`:
   `equipItem(slot, item)` (with `None` meaning unequip, matching the C++
   contract), `getEquipped()`, `getSlotWithItem(item)`, `hasEquipped(item)`.
   `CSlotConfig::getFittingSlots`/`canFit` are already bound.
3. *(Phase 3)* **`coveredSlots`** — `V_PROPERTY(CItem, std::vector<std::string>,
   coveredSlots, ...)` (same reflected shape as `CSlot::types`), empty for
   normal items. `CCreature::equipItem` refuses a `newItem` targeting a slot
   covered by any currently equipped item, and refuses equipping an item whose
   `coveredSlots` intersect occupied slots (the assembly flow empties them
   first). Unequipping the coverer frees the slots. Stats are untouched — the
   combined item's own `bonus` is the whole contribution.

Risk to verify early with a unit test: a `@register`-ed Python subclass of
`CHelmet` must still satisfy `CSlotConfig::canFit` (meta inheritance) and
round-trip through save serialization. `TownPortalScroll` demonstrates the
construction/serialization half; the slot-fit half is untested today because
scrolls are never equipped.

### 4. Assembly flow — `res/plugins/artifact_sets.py`

New Python plugin (add to `res/plugins/manifest.json`), structured like
`crafting.py` (a runtime singleton that loads its config via
`CResourcesProvider`).

- The plugin registers thin **piece classes** per slot type (`SetHelmet(CHelmet)`,
  `SetArmor(CArmor)`, `SetWeapon(CWeapon)`, `SetBoots(CBoots)`, `SetGloves(CGloves)`,
  `SetBelt(CBelt)`, `SetSmallWeapon(CSmallWeapon)`) whose `onEquip` calls
  `maybe_offer_assembly(player)`. Set pieces are re-authored with these classes
  (`"class": "CHelmet"` → `"class": "SetHelmet"` for `SkullHelmet`, etc.) —
  a cheap, validator-checked content edit; their stats and behavior are
  otherwise unchanged, so existing gameplay and saves are unaffected.
- `maybe_offer_assembly(player)`, for players only (`isPlayer()`):
  1. Find sets whose every piece is equipped (`getEquipped()` type-id match).
  2. For each, refuse silently if any equipped piece has the `cursed` tag
     (cursed items cannot leave their slots; assembling would bypass the lock).
  3. Prompt via `CGuiHandler::showSelection`:
     `["Assemble the Armor of the Damned", "Not now"]`. Because the prompt
     fires only on the equip event that *completes* the set, declining never
     nags — re-equipping any piece re-offers, exactly like H3's re-prompt on
     pickup.
  4. On accept, atomically: unequip every piece (`equipItem(slot, None)` — the
     pieces land in inventory), remove the piece instances from inventory
     (`removeItem`), create the combined item
     (`getObjectHandler().createObject`), `addItem` + `equipItem` it into its
     primary slot. Phase 3 ordering matters: empty the covered slots before
     equipping the coverer.
- **Tag propagation**: if any piece carries `quest`, the combined item entry
  must also carry `quest` (validator-enforced, §6) so the un-droppable
  invariant survives assembly; on disassembly the freshly created pieces get
  their authored tags back.

### 5. Disassembly flow

The combined item's `onUse` override (already-wired Python path,
`CItem.cpp:55-60`; triggered from the inventory like potions/scrolls) prompts
`["Disassemble the Armor of the Damned", "Keep it"]`. On accept:

1. If equipped, unequip it (frees the covered slots).
2. Remove the combined instance; create **fresh piece instances** from the set
   definition and `addItem` them. If the combined item was equipped, re-equip
   each piece into its slot (all just freed, so this cannot fail).

Regenerating pieces from config instead of storing instances inside the
combined item keeps serialization untouched (no new container property, saves
round-trip because the combined artifact is an ordinary equipped/inventory
item). Consequence to accept: pieces are stateless templates today, so nothing
is lost; if pieces ever gain per-instance state, revisit. A combined artifact
tagged `cursed` (content choice) simply cannot be unequipped, which blocks
step 1 — consistent with the slot-lock semantics.

### 6. Validation — `scripts/validate_content.py`

New pass `_validate_artifact_sets`, run with the other global-config passes
(crafting precedent at `:3575`), plus unit tests in
`tests/test_content_validator.py`:

- every entry has non-empty `label`, `pieces` (≥ 2), `combined`; unknown keys
  reported (profile-validation precedent);
- every piece id and the combined id resolve to global item configs;
- pieces map to **pairwise distinct slots** (via the class → slot mapping from
  `slots.json`), and every piece class is accepted by some real slot (guards
  against dead slot types);
- the combined item's class matches exactly one piece's slot (primary), and —
  phase 3 — its `coveredSlots` equal the remaining pieces' slot ids;
- the combined item is not itself a piece of any set; a piece belongs to at
  most one set; the combined id differs from all piece ids;
- warn when the combined `bonus` is not ≥ the piece sum per stat, and when a
  piece has `quest` but the combined item does not;
- document the schema in `docs/content.md` alongside crafting.

### 7. GUI

- **Assemble/disassemble prompts**: `showSelection` modals (existing pattern,
  used by crafting stations) — no new widgets required for the MVP.
- **Tooltips** (`src/handler/CTooltipHandler.cpp:39-67`): v1 ships static
  authored text — each piece's `description` ends with
  "Part of the Armor of the Damned (3 pieces)." Dynamic progress
  ("2/3 pieces") is a phase-4 enhancement: the tooltip handler needs access to
  a set registry, which means either a C++-side reader for
  `artifact_sets.json` or a Python-populated lookup — decide when phase 4 is
  scheduled.
- **Covered slots** (phase 3/4): `CGameInventoryPanel`'s equipped `CListView`
  should render covered slots non-interactive (drag/click refusal already
  falls out of the engine rule; visuals are polish). The equipped list's
  existing `rightClickCallback` support (`src/gui/panel/CListView.cpp:275`) is
  the natural home for H3-style right-click assemble/disassemble later.

## Phasing (each independently mergeable)

| Phase | Contents | Touches |
| --- | --- | --- |
| 0 | Schema + `artifact_sets.json` (definitions only) + validator + content.md docs | `res/config`, `scripts/`, `tests/test_content_validator.py` |
| 1 | Engine enablers: `onEquip`/`onUnequip` override wiring, pybind bindings; unit test for Python-subclass slot fit + save round-trip | `src/object/CItem.cpp`, `src/core/CModule.cpp`, `tests/unit` |
| 2 | `artifact_sets.py` runtime (assemble + disassemble), piece/combined class re-authoring, launch content for both sets, gameplay tests | `res/plugins`, `res/config`, `test.py` |
| 3 | `coveredSlots` property + `equipItem` enforcement + validator cross-check; rebalance combined bonuses upward once slots are truly occupied | `src/object`, `src/core`, `scripts/` |
| 4 | GUI polish: dynamic tooltip progress, covered-slot rendering, right-click affordances | `src/handler`, `src/gui` |

Balance note: **before phase 3, assembling frees slots**, so a
sum-plus-premium bonus would be strictly dominant. Author phase-2 bonuses as
plain piece-sums (premium = the granted `interaction` only) and add the
numeric premium in phase 3 when the slots become occupied. Phases 1–2 need a
coverage run (`./scripts/run_coverage.sh`) — they touch `src/object`,
`src/core`, `res/plugins` and `test.py`.

## Test plan

- **Validator**: happy path + each rule in §6 (missing piece ref, duplicate
  slot, combined-in-own-pieces, shared piece, quest-tag mismatch).
- **C++ unit** (`tests/unit/test_object.cpp`): equip-event override dispatch;
  phase 3 — `coveredSlots` refusal matrix (equip into covered slot, equip
  coverer over occupied slots, unequip frees).
- **Python gameplay** (`test.py`): completing equip triggers exactly one
  prompt; declining re-offers on re-equip; accepting swaps pieces for the
  combined item with stats equal to the authored bonus; disassembly
  round-trips (equipped and in-inventory variants); cursed piece blocks
  assembly; quest tag survives assemble/disassemble; save/load with a combined
  artifact equipped; AI creatures never prompt.
- **UI/xvfb**: inventory panel refresh after assembly (existing
  `equippedChanged`-driven refresh should cover it — assert, don't assume).

## Open questions

- **Q1 — Loot distribution**: should the random map generator / markets ever
  hand out a combined artifact directly, or only pieces? Recommendation:
  pieces only (H3 behavior); combined items excluded from market stock.
- **Q2 — `power` semantics**: confirm how `CMarket` uses `power` before
  assigning combined-item powers ≈ sum of pieces (e.g. Titan's Thunder ≈ 61 vs.
  the current max of 26); if power drives stocking tiers, large values may
  need a cap or a market exclusion anyway per Q1.
- **Q3 — LeftHand/Legs slots**: introducing `CShield`/`CPants` classes would
  unlock four-piece H3-faithful combos; worth a separate proposal.
