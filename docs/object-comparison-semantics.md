# Object Comparison Semantics

This audit records the current comparison semantics for game-object pointers in
`src/object`, `src/gui`, and `src/handler`. `CGameObject::name_comparator` is
an equality predicate, not a strict ordering comparator.

## Semantic Categories

- Shared-pointer identity: the code needs the exact live object instance.
- Runtime map/object identity: the code needs the object currently registered
  in a map slot or GUI tree, usually checked by pointer plus map/name lookup.
- Configured type equality: the code needs a configured identity key such as
  `typeId`, `type`, `name`, `stateId`, option number, or trigger key.
- Serialized value equality: the code needs equality of serialized object
  references or values. No audited call site currently requires full serialized
  object value equality.

## Explicit Comparator

| Site | Current semantic | Notes |
| --- | --- | --- |
| `src/object/CGameObject.cpp` `CGameObject::name_comparator` | Configured type equality / serialized reference-key equality | Nulls use shared-pointer identity. Non-empty `typeId` is the configured key. If both `typeId` values are empty, equality falls back to `type` plus `name`. Other serialized fields are ignored, so this is not full serialized value equality. |
| `src/object/CCreature.cpp` `addEffect` and `setEffects` | Configured type equality | Effect insertion deduplicates by `CGameObject::name_comparator`, so two effect instances with the same `typeId` or `type` plus `name` are treated as the same active effect. |

## Object Model

| Site | Current semantic | Notes |
| --- | --- | --- |
| `src/object/CMarket.cpp` `CMarket::items`, `add`, `remove`, `sellItem`, `buyItem` | Shared-pointer identity | Market stock and inventory transfers operate on concrete item instances. |
| `src/object/CCreature.cpp` `items`, `actions`, `addItems`, `removeItem`, `hasInInventory`, `useItem`, `getAllItems` | Shared-pointer identity | Inventory/action membership preserves distinct item/action instances even when configured ids match. |
| `src/object/CCreature.cpp` `equipped`, `equipItem`, `hasEquipped`, `getSlotWithItem` | Shared-pointer identity | Equipment slot values point to concrete item instances. |
| `src/object/CCreature.cpp` `effects`, `removeEffect`, `getEffects` | Shared-pointer identity after configured de-duplication | The set stores concrete effect instances; only insertion through `addEffect` applies configured equality. |
| `src/object/CCreature.cpp` `isPlayer`, `beforeMove`, `afterMove` fight predicates | Runtime map/object identity | Movement and combat events require the live creature still registered on the same map under the same object name. |
| `src/object/CMapObject.cpp` `move`, `setCoords`, `setPos*` registration checks | Runtime map/object identity | Coordinate-side effects only apply when the map name lookup returns the same live object. |
| `src/object/CPlayer.cpp` `quests`, `completedQuests`, `checkQuests`, setters | Shared-pointer identity | Quest sets store concrete quest objects. |
| `src/object/CPlayer.cpp` `addQuest` | Configured type equality | New quests are skipped by `typeId` when present, otherwise by `name`, across active and completed quests. |
| `src/object/CDialog.cpp` `states`, `options`, setters | Shared-pointer identity | Dialog collections preserve configured object instances. |
| `src/object/CDialog.cpp` `getState` | Configured type equality | State lookup uses `stateId`. |

## Handlers

| Site | Current semantic | Notes |
| --- | --- | --- |
| `src/handler/CEventHandler.cpp` `registerTrigger` | Shared-pointer identity or configured type equality | Duplicate trigger registration skips the same trigger pointer, or another trigger with the same `type`, `typeId`, and `name` for the same object/event key. |
| `src/handler/CEventHandler.cpp` `getTriggers` | Shared-pointer identity | The returned set contains concrete trigger instances. |
| `src/handler/CFightHandler.cpp` `is_registered_on_map`, `is_active_participant`, `contains_participant`, turn-order comparisons, reward eligibility, `defeatedCreature` | Runtime map/object identity | Combat must track live participants, not configured creature types. Vector membership and winner/loser checks use pointer identity. |
| `src/handler/CFightHandler.cpp` `sanitize_opponents` | Runtime object identity | Duplicate opponents are removed by raw `CCreature *` identity after map registration checks. |
| `src/handler/CFightHandler.cpp` loot accumulation | Shared-pointer identity | Reward item sets contain concrete generated or dropped item instances. |
| `src/handler/CRngHandler.cpp` `calculateRandomLoot`, `calculateRandomEncounter`, `getRandomEncounter` | Shared-pointer identity | Randomly generated objects are distinct live instances; encounter affiliation hashing combines those pointers. |
| `src/handler/CGuiHandler.cpp` `showLoot` | Shared-pointer identity | The loot panel receives concrete item instances. |
| `src/handler/CGuiHandler.cpp` `showSelection` widget set | Shared-pointer identity | Temporary widgets are distinct GUI instances before being attached as children. |

## GUI

| Site | Current semantic | Notes |
| --- | --- | --- |
| `src/gui/object/CGameGraphicsObject.cpp` `children` and `priority_comparator` | GUI ordering plus shared-pointer identity | Children are ordered by priority and break ties by pointer. |
| `src/gui/object/CGameGraphicsObject.cpp` `addChild`, `removeChild`, `findChild(shared_ptr)`, render/event snapshots | Shared-pointer identity | GUI tree operations require the exact child object. |
| `src/gui/object/CGameGraphicsObject.cpp` `setChildren` | Shared-pointer identity through default set input, then GUI ordering | Nulls are filtered; differences are computed against the priority-ordered child set. |
| `src/gui/object/CProxyGraphicsObject.cpp` `hasSameProxyChildren` | Shared-pointer identity plus rendered metadata | Proxy refresh checks child pointers, priority, and meta class name. |
| `src/gui/object/CProxyTargetGraphicsObject.cpp` `proxyObjects` | Coordinate key equality | Proxy holders are keyed by integer grid coordinates, not object values. |
| `src/gui/CGui.cpp` pointer capture, drag-session containment, `findChild` checks | Shared-pointer identity | GUI interaction state must follow the exact widget/root objects. |
| `src/gui/panel/CListView.cpp` `calculateIndices` with grouping enabled | Configured type equality | Grouping collapses objects by `typeId`. |
| `src/gui/panel/CListView.cpp` index maps and drag/callback payloads | Shared-pointer identity | Indexed objects and drag payloads are concrete object instances. |
| `src/gui/panel/CGameInventoryPanel.cpp` selection/equipment callbacks | Shared-pointer identity | Selection and use/equip actions require the selected concrete item. |
| `src/gui/panel/CGameTradePanel.cpp` selected inventory/market lists | Shared-pointer identity | Weak-pointer selections toggle and finalize concrete item instances. |
| `src/gui/panel/CGameFightPanel.cpp` action/item/enemy selections | Shared-pointer identity | Current action, item, and selected enemy are live object instances. |
| `src/gui/panel/CGameFightPanel.cpp` `setEnemies` | Configured/runtime name equality | The enemy list keeps one living enemy per object name, then subsequent selection uses pointer identity. |
| `src/gui/panel/CGameDialogPanel.cpp` `getCurrentOptions` | Configured type equality | Options are ordered and deduplicated by configured option number. |
| `src/gui/panel/CGameDialogPanel.cpp` `reload` widget set | Shared-pointer identity | Temporary text widgets are concrete GUI instances. |
| `src/gui/panel/CGameLootPanel.cpp` `items` | Shared-pointer identity | Loot panel items are concrete item instances. |
| `src/gui/object/CMapGraphicsObject.cpp`, `src/gui/object/CMinimapGraphicsObject.cpp` object/player checks | Runtime map/object identity | Render/proxy decisions compare live map objects and the active player pointer. |
| `src/gui/object/CSideBar.cpp` panel lookup | Shared-pointer identity | Sidebar panel values refer to concrete panel instances. |

## Migration Notes

- Do not replace pointer comparisons with `name_comparator` unless the caller is
  intentionally switching from live-instance identity to configured identity.
- Do not use `name_comparator` as an ordered-container comparator; it returns
  equality, not strict weak ordering.
- If a future migration needs full serialized value equality, add a separate
  helper and tests. The current comparator intentionally ignores fields outside
  the configured identity key.
