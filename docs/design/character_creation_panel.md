# Character Creation Panel — Design & Implementation Hand-off

Status: **Design-only hand-off.** Implement in an environment where the GUI can
be built and run. The doc was authored where `_game` could not be built (the
`vstd` / `random-dungeon-generator` submodules are outside the authoring
environment's network scope), so a bespoke interactive panel could not be
rendered or verified locally — hence this write-up instead of a blind,
CI-only implementation.

## Goal

Replace the two sequential text menus at character creation (class, then race,
each via `CGuiHandler::showSelection`) with a **single character-creation
screen** that shows the class options and race options together with a **live
preview** of the composed result, and returns the chosen `(classId, raceId)` to
`res/game.py`'s `new()` flow.

## Current state (already shipped)

- **Flow:** `play.py` → `game.new()` → `showSelection(["NEW","LOAD","RANDOM"])` →
  map pick → `choose_player_class(g)` → `choose_player_race(g)` →
  `CGameLoader.startGameWithPlayer(g, map, classId, raceId)`.
- **Selection UI:** `choose_player_class` / `choose_player_race` (`res/game.py`)
  call `CGuiHandler::showSelection`, a modal list of `CButton`s. Race options
  already carry a stat preview in their label, e.g. `"Outlander - STR+1 AGI-1
  STA+2 INT-2"` (`race_stat_preview` in `res/game.py`).
- **Data:** player-selectable races are `CCreatureRace` entries flagged
  `playerSelectable` in `res/config/creature_races.json`, each with an optional
  nested `baseStats` modifier; classes are the `CPlayer` templates
  (`player_class_options` enumerates `getAllSubTypes("CPlayer")`).
- **Race stat getters** are exposed to Python (`CStats.getStrength` etc.,
  `src/core/CModule.cpp`).

## Key framework finding: use buttons, not list views

Verified in this codebase:

- **`CListView` renders each item as its animation/icon**, laid out in a tile
  grid — `src/gui/panel/CListView.cpp:39`
  (`CAnimationProvider::getAnimation(gui->getGame(), object)`). It does **not**
  render text labels. Player **races have no art**, so a race `CListView` would
  render blank tiles. `collection_type` is
  `vstd::list<std::shared_ptr<CGameObject>>` (`CListView.h:72`).
- **`CButton` (via `CTextWidget`) renders text** —
  `src/gui/object/CWidget.cpp:81-88`
  (`CTextWidget::renderObject` → `gui->getTextManager()->drawTextCentered(...)`).
- `CGuiHandler::showSelection` (`src/handler/CGuiHandler.cpp`) already builds a
  column of text `CButton`s dynamically and blocks on the result.

**Therefore the chooser should be built from text `CButton`s** (one per class,
one per race) plus a `CWidget` preview pane — mirroring the proven
`showSelection` pattern — **not** from `CListView`s (which are icon-oriented and
would need per-option art that races don't have).

## Recommended approach (A): dynamic `CGuiHandler::showCharacterCreation()`

Mirror `showSelection` exactly, extended to two columns + a preview + confirm/
cancel. No new panel subclass required — everything is built dynamically and
wired via `panel->meta()->set_method(...)`, exactly as `showSelection` registers
its per-button `clickN` callbacks today.

Signature:

```cpp
// CGuiHandler.h
std::pair<std::string, std::string> showCharacterCreation();  // {classId, raceId}, {"",""} on cancel
```

Behavior (each step mirrors a proven line in `showSelection`):

1. Create the base panel from `panels.json`
   (`game->createObject<CGamePanel>("characterCreationPanel")`) — a
   `CCenteredLayout` container (~900×600), no static children (added
   dynamically), just like `selectionPanel`.
2. Left column: one `CButton` per class label
   (`player_class_options` equivalent — `getAllSubTypes("CPlayer")` + each
   template's `label`). Its dynamically-registered `clickN` captures and sets a
   local `selectedClass` shared_ptr, then requests a repaint.
3. Right column: one `CButton` per **player-selectable** race, label =
   `"<label> - <preview>"` (reuse the `race_stat_preview` formatting; the C++
   side can read `CCreatureRace::getBaseStats()` and the `CStats` getters).
   `clickN` sets `selectedRace`.
4. A `CWidget` preview pane with a **dynamically-registered `renderPreview`
   method** (register via `panel->meta()->set_method`, capturing the selection
   state) that draws e.g. `"Class: Warrior\nRace: Outlander (STR+1 AGI-1 STA+2
   INT-2)"`. Note multi-line: `drawTextCentered` is single-line in
   `showQuestion`; render each line separately or use `drawText`.
5. `CREATE` button → sets a `confirmed` flag (default any unpicked side to the
   first option, or gate `CREATE` until both are picked). `CANCEL` → sets
   `cancelled`.
6. Block: `vstd::wait_until([&]{ return confirmed || cancelled || !panel->getGui(); });`
   then `panel->close();` and return `{selectedClass?*:"" , selectedRace?*:""}`.

Bindings: expose `showCharacterCreation` on the `CGuiHandler` pybind class in
`src/core/CModule.cpp`; a `std::pair<std::string,std::string>` converts to a
Python tuple.

`res/game.py` integration (NEW and RANDOM paths):

```python
class_id, race_id = g.getGuiHandler().showCharacterCreation()
if not class_id:
    return  # cancelled
CGameLoader.startGameWithPlayer(g, map, class_id, race_id)   # NEW
# CGameLoader.startRandomGameWithPlayer(g, class_id, race_id) # RANDOM
```

Keep `choose_player_class` / `choose_player_race` as a fallback (or remove once
the panel is proven).

### Approach B (alternative): dedicated `CGameCharacterCreationPanel` subclass

A `CGamePanel` subclass with `V_META`-reflected methods and a JSON definition in
`panels.json`. Cleaner separation, but more code + type registration, and if it
uses `CListView` it inherits the icon-rendering problem above. If you prefer a
subclass, still build it from `CButton` rows, not `CListView`. Given the extra
surface area, **Approach A is recommended** as the lower-risk first cut.

## Runtime pitfalls to resolve during implementation

- **Event loop / `wait_until`:** `wait_until` spins; it does not pump the loop
  itself. `showSelection` works when called *during* `new()` (before
  `play.py`'s `event_loop` starts) — so the pattern is already proven in this
  exact call site. Mirror it precisely; don't invent a new blocking scheme.
- **Close must unblock:** `CREATE`/`CANCEL` must both set the awaited state and
  cause `panel->getGui()` to go null (via `close()`), or the lambda never
  returns. Follow `showSelection`'s `selected`-pointer discipline.
- **Callback registration:** dynamically-set method names must match the
  widget's `click`/`render` string exactly, or the call silently no-ops/logs a
  warning (`CWidget::renderObject` catches and warns).
- **Layout math:** extend `showSelection`'s per-row `y0/y1` percentages to
  two `x` columns + a preview region + a button row.
- **Multi-line preview text:** verify `drawText` vs `drawTextCentered` newline
  handling; render line-by-line if needed.

## Testing (headless, CI xvfb)

Two proven patterns to mirror (both in `test.py`):

- **Blocking-flow test** — `test_blocking_modal_gui_helpers_drive_panels`
  (~line 11587): `loadGame` → `loadGui` → `startGameWithPlayer` →
  `pump_event_loop` → `queue_sdl_inputs(game, lambda: push_sdl_mouse_click(x,y))`
  → assert `showCharacterCreation()` returns the expected `(class, race)`.
  Requires computing button screen coords from the layout.
- **Direct-invocation test** — `test_fight_panel_callbacks_and_list_views`
  (~line 11816): construct the panel, call its selection setters/callbacks
  directly, and assert the getters — avoids needing pixel coords. Expose the
  panel's selection state (or, for Approach A, add a thin testable entry point)
  so the (class, race) result can be asserted without simulated clicks.

`SDL_VIDEODRIVER=dummy` (set by `test.py`) makes this run headless; UI tests run
under xvfb in CI.

## Open design questions

1. **Race portraits?** Adding per-race art would enable an icon `CListView`
   layout and richer visuals. Absent art, button text is the pragmatic choice.
2. **Preview depth:** show just the race delta + class role (simple), or the
   *fully composed* base stats (requires instantiating a throwaway player)?
3. **Keep the sequential menus** as a fallback/accessibility path, or remove?
4. **CREATE gating:** require both picks, or default the unpicked side to the
   first option / the current defaults (class = first template, race = human)?

## References (verified in this repo)

- `src/handler/CGuiHandler.cpp` — `showSelection` (dynamic `CButton` panel +
  `vstd::wait_until` + `close`); the template for `showCharacterCreation`.
- `src/gui/object/CWidget.cpp:81-88` — `CTextWidget` renders text.
- `src/gui/panel/CListView.cpp:39`, `CListView.h:72` — `CListView` renders item
  **animations/icons**; `collection_type` is a list of `CGameObject`.
- `res/game.py` — `race_stat_preview`, `choose_player_race`,
  `player_class_options`, `player_race_options`; `new()` insertion point.
- `res/config/creature_races.json` — player-selectable races + `baseStats`.
- `src/core/CModule.cpp` — `CStats` getters and `CGuiHandler` bindings (add
  `showCharacterCreation` here).
- `test.py` — `test_blocking_modal_gui_helpers_drive_panels`,
  `test_fight_panel_callbacks_and_list_views` (headless panel test patterns).
