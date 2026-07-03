# Fog of War — Design & Implementation Hand-off

Status: **Design-only hand-off.** Implement in an environment where the GUI can
be built and run. The doc was authored where `_game` could not be built (the
`vstd` / `random-dungeon-generator` submodules and native SDL/pybind deps are
outside the authoring environment's scope), so the rendering changes could not
be verified locally — hence this write-up instead of a blind, CI-only
implementation. All file/line references were verified against the current
`main` tree.

## Goal

Add a classic three-state fog of war to the overworld map view, toggleable per
map:

| State | Terrain | Static objects (signs, buildings, items) | Creatures | Interaction |
| --- | --- | --- | --- | --- |
| **Unexplored** — never seen | hidden (shroud) | hidden | hidden | no click-to-move target |
| **Explored** — seen before, outside current vision | drawn, dimmed | drawn, dimmed | hidden | click-to-move allowed |
| **Visible** — within vision radius of the player | drawn | drawn | drawn | unchanged |

- **Vision rule (v1):** a tile is *visible* iff
  `map->getDistance(playerCoords, tileCoords) <= R` on the player's current z
  level. `CMap::getDistance` is wrap-aware (`src/core/CMap.h:179`, via
  `getShortestDelta`), so wrapping maps work for free. No line-of-sight
  occlusion in v1 (see Future extensions).
- **Explored** is persistent (survives save/load); **visible** is transient and
  recomputed from the player's position — it is never stored.
- The feature is **off by default** on every map; a per-map flag opts in.

Non-goals for v1: LOS/occlusion (mountains blocking sight), per-creature vision
for AI (monsters keep their current omniscient behavior), fog during fights,
stat-driven vision radius.

## Current state (engine survey)

There is **no existing fog/shroud/vision/explored code** — a repo-wide grep
only hits the unrelated GUI widget gate `CGameGraphicsObject::isVisible()`
(a `CScript`-predicate for whether a *widget* renders,
`src/gui/object/CGameGraphicsObject.h:52`) and ELF symbol visibility macros.
This is a greenfield feature. The load-bearing engine facts:

- **The map view is a player-centered proxy grid.**
  `CMapGraphicsObject::getProxiedObjects(gui, x, y)`
  (`src/gui/object/CMapGraphicsObject.cpp:41`) is called per screen cell and
  returns the list of animations to draw there: it converts the cell to world
  coords (`:69-70`), fetches the tile (`:73`), attaches the click-to-move
  callback (`:76-99`), then appends every object at those coords (`:102-112`),
  an optional coordinate label gated on
  `map->getBoolProperty("showCoordinates")` (`:114`), and a path footprint.
  **This one function is the render choke point for the main view** — fog
  decides here, per cell, what to return.
- **The minimap is a second, independent leak surface.**
  `CMinimapGraphicsObject::renderObject`
  (`src/gui/object/CMinimapGraphicsObject.cpp:369`) builds a terrain texture by
  iterating **all** tiles (`draw_terrain`, `:267`), caches it behind a content
  hash (`terrain_signature`, `:277`), and draws a marker for **every** map
  object (`:404-413`). Without gating, the minimap reveals the whole map and
  every creature.
- **Tiles are lazily materialized.** `CMap::getTile` (`src/core/CMap.cpp:376`)
  creates a fallback tile (from `defaultTiles`) on first lookup. Only tiles
  that were ever looked up exist as `CTile` objects — the renderer already
  materializes everything that enters the viewport, so per-tile state written
  at reveal time behaves consistently.
- **Serialization is automatic for `V_PROPERTY`s.** `object_serialize`
  (`src/core/CSerialization.cpp:358`) walks every `V_META` property; `CMap`'s
  `tiles` set is a property (`src/core/CMap.h:70`) and each `CTile` serializes
  its own properties (`src/object/CTile.h:29-33`). A new `bool` property on
  `CTile` persists through save/load with **zero serializer changes**.
- **Player steps have a precise commit hook.** `CMap::move()` commits each step
  via `creature->moveTo(target)` then
  `controller->onStepCommitted(creature, target)` (`src/core/CMap.cpp:667-674`);
  `CPlayerController::onStepCommitted` (`src/core/CController.h:56`) fires
  exactly once per committed player step. Teleports/attach go through
  `CMap::attachPlayer` (`src/core/CMap.cpp:170-172`) and
  `CMap::restorePlayerAfterLoad` (`:204`).
- **Refresh signals already exist.** The map view subscribes to `turnPassed`
  (→ `refreshAll`) and `tileChanged`/`objectChanged` (→ per-cell
  `refreshObject`) in `CMapGraphicsObject::initialize`
  (`src/gui/object/CMapGraphicsObject.cpp:169-179`). `turnPassed` fires at the
  end of every `CMap::move()` (`src/core/CMap.cpp:691`), so the whole viewport
  re-evaluates after every player move — fog needs no new signals for the
  common case.
- **Per-map feature flags have a precedent.** `showCoordinates` is read as a
  dynamic bool property on the map object
  (`src/gui/object/CMapGraphicsObject.cpp:114`); dynamic properties are settable
  from Python (`setBoolProperty`, `src/object/CGameObject.h:123`) and from
  content.
- **Overlay stacking uses priorities.** Children render in ascending
  `priority`; the coordinate label uses `setPriority(4)`
  (`src/gui/object/CMapGraphicsObject.cpp:139`), the footprint likewise. A fog
  dim overlay slots in above them.

## Design

### 1. State model

**Persistent — `explored` flag per tile.** Add to `CTile`
(`src/object/CTile.h:29`):

```cpp
V_PROPERTY(CTile, bool, explored, isExplored, setExplored)
```

with `bool explored = false;` backing field. This round-trips through saves
automatically and is already reachable from Python via the generic
`tile.getBoolProperty("explored")` accessors — no new bindings required for
inspection.

**Transient — current visibility is computed, not stored.** Because the v1
rule is a wrap-aware distance check, per-cell visibility is O(1):

```cpp
bool isCurrentlyVisible = map->getDistance(playerCoords, actualCoords) <= radius
                          && actualCoords.z == playerCoords.z;
```

No visible-set cache, no invalidation bugs, nothing extra to clear on map
switch or z change. If a later LOS extension makes the check expensive, a
recompute-on-step cache can be introduced behind the same helper without
changing callers.

**Per-map knobs — declared properties on `CMap`.** Add to the `V_META` block
(`src/core/CMap.h:67`):

```cpp
V_PROPERTY(CMap, bool, fogOfWar, getFogOfWar, setFogOfWar),        // default false
V_PROPERTY(CMap, int, fogOfWarRadius, getFogOfWarRadius, setFogOfWarRadius)  // default 6
```

Declared (not dynamic) properties are required here: saved maps are restored
purely by deserialization — `CMapLoader::loadSavedMap`
(`src/core/CLoader.cpp:1029`) never re-runs `loadFromTmx` (only
`loadNewMap`, `:1017`, does) — so the flags must round-trip through the
`V_META` walk in `object_serialize` to survive save/load. They remain fully
scriptable: `CGameObject::setProperty` routes to the declared property whenever
one exists (`src/object/CGameObject.h:102-106`), so
`map.setBoolProperty("fogOfWar", True)` from Python and
`CSerialization::setProperty` from the loader both hit the same field.

**Central helpers on `CMap`** (implementation in `src/core/CMap.cpp`) so the
map view, minimap, and Python all share one definition:

```cpp
bool  fogOfWarEnabled();                 // getFogOfWar()
int   getVisionRadius();                 // getFogOfWarRadius(), clamped >= 1
bool  isVisibleFrom(Coords eye, Coords target);   // distance rule above
bool  isExplored(Coords coords);         // false when fog on and tile missing/unexplored
void  revealAround(Coords center, int radius);    // materialize + setExplored(true)
```

`revealAround` iterates the `(2R+1)²` square around `center` on `center.z`,
filters with `isVisibleFrom`, normalizes each coordinate, skips out-of-bounds
cells (`isWithinBounds`, `src/core/CMap.h:173`), and calls `getTile(c)` +
`setExplored(true)`. Materializing via `getTile` is deliberate: it is exactly
what the renderer already does for viewport cells, and it is what lets the
flag persist. When fog is disabled, `isExplored` returns `true`
unconditionally so all call sites degrade to current behavior.

### 2. Reveal flow

Reveal happens at every point where the player's position is established or
changes:

1. **Per committed step** — `CPlayerController::onStepCommitted`
   (`src/core/CController.h:56`): call
   `map->revealAround(coords, map->getVisionRadius())` when fog is enabled.
   This covers keyboard moves, click-to-move paths, and scripted `moveTo`,
   since they all commit through `CMap::move()`.
2. **On attach** — end of `CMap::attachPlayer(player, coords)`
   (`src/core/CMap.cpp:172`): reveal around the entry/teleport coords. This
   covers new game, map transitions, and portal-style relocations that
   re-attach the player.
3. **After load** — `CMap::restorePlayerAfterLoad` (`src/core/CMap.cpp:204`):
   reveal around the restored position. Loaded saves already carry explored
   flags; this only guarantees the current standing position is lit even for
   saves created before the feature existed.

Anything that moves the player *without* the commit hook (e.g.
`relocateWithoutMoveHooks`, `src/object/CMapObject.h:76`) intentionally skips
hooks today; call sites that teleport the player should follow with an explicit
`revealAround`, and the audit of those call sites is part of the implementation
checklist.

No new refresh signal is needed after a step: `turnPassed` already triggers
`refreshAll`. Script-driven reveals outside a turn (e.g. a quest revealing a
region) should emit the existing `tileChanged` signal per revealed coord —
`refreshObject(Coords)` is already wired for it — or simply rely on the next
turn's `refreshAll`.

### 3. Render gate — main map view

In `CMapGraphicsObject::getProxiedObjects`
(`src/gui/object/CMapGraphicsObject.cpp:41`), after computing `actualCoords`
(`:70`), when `map->fogOfWarEnabled()`:

- **Unexplored** (`!map->isExplored(actualCoords)`): return only a shroud
  animation (opaque dark 32×32 texture, `images/fog/shroud`), **without** the
  click-to-move callback — unexplored terrain is not a click target, and the
  early return also skips `getObjectsAtCoords`, so nothing about the cell
  leaks (no tile art, no objects, no tooltips derived from animations).
- **Explored, not visible** (`!map->isVisibleFrom(playerCoords, actualCoords)`):
  keep the tile animation *with* its click callback (players expect to path
  back through known terrain), keep non-creature objects, **skip any object
  castable to `CCreature`** (`vstd::cast<CCreature>` filter in the object loop
  at `:107`), and append a semi-transparent dim overlay
  (`images/fog/dim`, ~55% black) at `setPriority(5)` so it sits above the
  coordinate label and footprint.
- **Visible**: unchanged behavior.

The footprint/path preview (`:118-123`) needs no change: paths only exist over
tiles the player can click, and dimmed cells intentionally keep the preview.

Two static assets are needed under `res/images/fog/` (`shroud.png`, `dim.png`),
loaded through the existing `CAnimationProvider::getAnimation` path the
footprint already uses (`:145`). Both are trivial generated PNGs; `dim.png`
carries its alpha in the texture so no new blend-mode plumbing is required.

Per-cell proxy caching (`proxyAnimations`, `CMapGraphicsObject.h`) is keyed by
screen cell and rebuilt on refresh; the shroud/dim animations should be cached
in the same `ProxyAnimationSlot` structure (one extra slot member) so steady
state allocates nothing.

### 4. Render gate — minimap

In `src/gui/object/CMinimapGraphicsObject.cpp`, when fog is enabled:

- **Terrain**: in `draw_terrain` (`:267`), skip tiles with
  `!tile->isExplored()`, and replace `draw_default_terrain` (`:243`) — which
  floods the whole level with the default tile color — with per-cell painting
  only for explored coords. Unexplored area stays `MINIMAP_BACKGROUND`.
- **Texture cache**: fold the explored state into `terrain_signature` (`:277`)
  — hash `tile->isExplored()` alongside the tile type per tile, and hash the
  fog flag + radius once — otherwise the cached texture goes stale as the
  player explores.
- **Markers**: in the object loop (`:404-413`), draw creature markers only for
  currently-visible coords (`map->isVisibleFrom(playerCoords, coords)`); draw
  non-creature markers only for explored coords. Player marker and viewport
  rectangle (`:415-416`) draw unconditionally.

### 5. Toggle & content wiring

Two per-map knobs, the declared `CMap` properties from §1:

- `fogOfWar` (bool, default false)
- `fogOfWarRadius` (int, default 6)

Recommended wiring: extend `CMapLoader::loadFromTmx`
(`src/core/CLoader.cpp:798-835`) to apply the map-level `properties{}` block
generically to the `CMap` object via `CSerialization::setProperty`, skipping
the already-consumed `x`/`y`/`z` entry keys. Today only `x/y/z` are read, so
this is a small, backward-compatible addition and lets map authors declare:

```json
"properties": { "x": "110", "y": "111", "z": "0", "fogOfWar": "true", "fogOfWarRadius": "6" }
```

Fallback that needs **zero loader changes** (useful for prototyping and for
script-controlled fog): the per-map `script.py` sets
`map.setBoolProperty("fogOfWar", True)` on load, following the
`showCoordinates` pattern. Both paths write the same declared property, so the
engine reads one source of truth either way.

Content rollout: v1 ships with fog **off everywhere** (pure engine feature +
tests on the `test` map). Enabling it on a campaign map (the RANDOM
dungeon-generator flow is the natural first candidate) is a separate content
change with its own playtest.

### 6. Python & tooling surface

Bind on `CMap` in `src/core/CModule.cpp` (map bindings around `:639-679`):
`revealAround(coords, radius)`, `isExplored(coords)`,
`isVisibleFrom(eye, target)`. This gives:

- quests/plugins the ability to reveal regions (map items, scrying effects);
- `mcp.py` / headless walkthroughs the ability to assert fog state;
- tests a direct, render-free observation point.

`tile.explored` is additionally reachable through the existing generic
property accessors with no new bindings.

### 7. Save/load & compatibility

- New saves: `explored` rides along on each serialized tile; `fogOfWar`/
  `fogOfWarRadius` ride along as declared `CMap` properties. No `CSaveFormat`
  schema/migration work — the format is property-driven, and `loadSavedMap`
  restores the flags with the rest of the map object.
- Old saves loaded by the new engine: tiles default to `explored = false`.
  On maps with fog disabled (all of them at v1 ship time) this is invisible.
  If fog is later enabled on an existing campaign map, old saves start
  re-shrouded except the post-load reveal around the player — acceptable, and
  called out in the content-enablement checklist.
- Save size: only materialized tiles serialize today, and the viewport already
  materializes everything seen on screen; `revealAround` materializes a
  slightly larger ring (radius vs. half-viewport). Marginal growth, no new
  mechanism.

## Implementation plan

1. **`CTile.explored`** — property, getter/setter, backing field
   (`src/object/CTile.h`, `CTile.cpp`). C++ unit test: property round-trips
   through `CSerialization::serialize`/`deserialize`.
2. **`CMap` fog properties & helpers** — `fogOfWar`/`fogOfWarRadius`
   `V_PROPERTY`s plus `fogOfWarEnabled`, `getVisionRadius`, `isVisibleFrom`,
   `isExplored`, `revealAround` (`src/core/CMap.h/.cpp`). Unit tests: radius
   math on wrapping and bounded maps, z isolation, `isExplored` fail-open when
   fog disabled, property round-trip through map serialization.
3. **Reveal hooks** — `CPlayerController::onStepCommitted`
   (`src/core/CController.cpp`), `CMap::attachPlayer`,
   `CMap::restorePlayerAfterLoad`; audit player-teleport call sites of
   `relocateWithoutMoveHooks` and add explicit reveals where needed.
4. **Assets** — `res/images/fog/shroud.png`, `res/images/fog/dim.png`.
5. **Main-view gate** — `CMapGraphicsObject::getProxiedObjects` branching per
   §3, shroud/dim slots in the proxy animation cache.
6. **Minimap gate** — terrain/marker/signature changes per §4.
7. **Loader property pass-through** — map-level `properties{}` →
   `CSerialization::setProperty` (`src/core/CLoader.cpp`); update
   `docs/content.md` and, if the validator learns the new keys,
   `scripts/validate_content.py`.
8. **Python bindings** — `revealAround`/`isExplored`/`isVisibleFrom`
   (`src/core/CModule.cpp`).
9. **Tests** — see below; enable fog on `res/maps/test` (via its `script.py`
   or map properties) for gameplay-suite coverage.

Steps 1–3 are render-free and testable headlessly; 5–6 are the GUI half; each
step keeps the tree green independently because fog defaults to off.

## Validation plan

Per the repo workflow (build `_game`, then):

- `python3 scripts/validate_content.py --repo-root .` — unaffected unless step
  7 adds validated keys.
- C++ `for_unit_tests`: new tests from steps 1–2 (serialization round-trip,
  radius/wrap/z math, reveal materialization counts).
- `ctest -L performance`: `revealAround` is O(R²) ≈ 169 tile touches per step
  at R=6, and the render gate adds one distance check per viewport cell per
  refresh — well under existing per-frame work, but the perf guards must stay
  green since `getProxiedObjects` is hot.
- `python3 test.py`: a gameplay test on the `test` map — enable fog, walk a
  few steps, assert `isExplored` transitions at, inside, and beyond the
  radius, save via `CMapLoader.save`, reload, and assert the explored flags
  survived. These are state-level assertions; rendering behavior belongs to
  the UI suite.
- UI/xvfb suite: a smoke test that a fog-enabled map renders (no crash, shroud
  animation resolvable); pixel-exactness is not asserted, matching existing UI
  test conventions.
- Coverage gate: changes touch `src/core/**`, `src/object/**`, `src/gui/**` →
  `./scripts/run_coverage.sh` applies (90% eligible-line gate).
- Manual: `GAME_PLAYTEST_TRACE=1` walkthrough on a fog-enabled map; verify the
  minimap does not pre-render unexplored terrain and creature markers pop only
  inside the radius.

## Alternatives considered

- **Explored set on `CMap` (`std::set<Coords>` property) instead of per-tile
  flag.** Avoids materializing tiles at reveal time, but needs a new
  serializable collection wrapper, a second source of truth beside the tile
  grid, and custom (de)serialization — while the per-tile flag is one line of
  reflection and zero serializer work. Rejected for v1; worth revisiting only
  if reveal-time materialization proves costly on huge maps.
- **Computing "explored" implicitly as "tile is materialized."** Tempting
  (lazy materialization already approximates "was in viewport") but wrong:
  `getTile` is called by pathfinding, scripts, and the minimap for cells the
  player has never seen, so materialization over-approximates exploration.
- **A fullscreen fog overlay widget instead of per-cell gating.** A single
  overlay can darken, but cannot *withhold* information — objects would still
  be drawn beneath, tooltips and the minimap would leak, and click handling
  would still target hidden cells. Per-cell gating at the choke point is the
  only place that controls information flow, not just pixels.
- **Storing the visible set and diffing per step.** Saves the per-cell
  distance check but introduces cache invalidation on map switch, z change,
  teleport, and load. The check is O(1) integer math per cell; there is
  nothing to optimize yet.

## Future extensions (out of scope for v1)

- **Line-of-sight occlusion**: opaque tile types (mountains, walls) block
  sight via raycasts (`Coords` math exists; `CPathFinder` is A*, not reusable
  for LOS). Slot it behind `CMap::isVisibleFrom` so callers don't change.
- **Stat- or item-driven radius**: torches, elevation, `CPlayer` stats feeding
  `getVisionRadius`.
- **Scripted map memory items**: quest rewards calling `revealAround` over
  landmarks — the Python binding from step 8 already enables this.
- **AI symmetry**: creatures using the same visibility rule to acquire the
  player, turning fog into a stealth mechanic.
