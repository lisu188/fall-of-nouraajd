# Multilevel Campaign (Heroes III-style) — Design

Status: **Phase 1 implemented.** This doc specifies a campaign system — an
ordered, optionally branching sequence of scenario maps with hero carryover
and briefings, in the spirit of Heroes of Might & Magic III campaigns —
grounded in the mechanisms this engine already has. Every claim about engine
behavior below was verified against the code at the cited locations.

Implementation notes (deltas from the proposal below):

- Driver: `res/campaign.py`; shipped manifest:
  `res/campaigns/fallOfNouraajd/campaign.json`; start menu gained a
  `CAMPAIGN` option (`res/game.py new()`).
- The player-side completion property is named `campaign_finished` (not
  `campaign_completed` as sketched below) to stay distinct from the
  pre-existing `campaign_completed` *map* bool the siege script sets.
- Carryover v1 supports `gold_max`, `items_allow`, `items_deny`.
  `reset_active_quests` was deferred — no shipped scenario needs it.
- The ritual map declares only `CAMPAIGN_OUTCOMES = ("good_ending",)`: a lost
  captive never calls `complete_scenario`, so the bad ending leaves the player
  on the map exactly as standalone play does. The `siege_hard` branch shown in
  the example manifest below remains illustrative, not shipped content.
- Validation additions live in `scripts/validate_content.py`
  (manifest schema, DAG reachability/acyclicity/terminal checks, outcome
  cross-checks against `CAMPAIGN_OUTCOMES`, carryover item refs,
  `complete_scenario`/`fallback_map` literal checks). Driver unit tests
  (`tests/test_campaign_driver.py`, fake-based, no `_game`) and gameplay tests
  (`test.py` `test_campaign_driver_routes_full_campaign_with_carryover`,
  `test_campaign_state_survives_save_load`) cover the runtime; the
  walkthrough test joined the CI full-route campaign gate.

Terminology note: the existing `res/maps/multilevel/` map is **not** a
campaign — it is a single map with multiple Z-levels connected by
`LevelStairs` (`res/maps/multilevel/script.py`). "Multilevel campaign" in this
doc means the HoMM3 sense: multiple scenario maps played in sequence as one
story, with the hero persisting across them.

## Goal

Ship a data-driven campaign layer so that:

1. A campaign is declared as content (`res/campaigns/<id>/campaign.json`), not
   hardcoded in map scripts.
2. The player picks a campaign from the start menu, sees a briefing, plays the
   scenario, and on scenario victory is carried — hero, inventory, gold,
   quests — into the next scenario, possibly chosen by branching on the
   scenario's outcome (as HoMM3 does with alternate scenario paths).
3. Campaign progress survives save/load with **no save-format schema change**.
4. Scenario maps stay playable standalone (the current NEW → pick-a-map flow
   keeps working), and map scripts no longer need to know which map comes next.

## What the engine already provides (verified)

The engine is closer to "campaign-ready" than it looks; the missing piece is
orchestration, not plumbing.

- **Cross-map player carryover works today.**
  `CSceneManager::performMapChange` (`src/core/CSceneManager.cpp:154`) loads
  the destination via `CMapLoader::loadNewMap`, re-attaches the *same*
  `CPlayer` object with `attachPlayer`, and carries the turn counter over.
  Covered by `test.py`
  `test_campaign_transitions_preserve_player_and_start_siege` (~line 15890):
  after `finish_cleanse()` the map is `ritual` and `getPlayer()` is the same
  object. Inventory, gold, stats, effects, `quests`, and `completedQuests`
  (`src/object/CPlayer.h`) all ride along because they live on the player.
- **A hardcoded three-scenario chain already exists.**
  nouraajd → ritual (`res/maps/nouraajd/script.py:929`, Beren's
  `finish_cleanse`) and ritual → siege (`res/maps/ritual/script.py:236`,
  `free_captive`, which also grants a 300-gold + LifePotion reward first).
  Ritual even has a branch signal already: it sets `good_ending` as a map
  bool. This chain is the prototype the campaign layer generalizes.
- **Transitions are forward-only.** `performMapChange` always calls
  `loadNewMap` — there is no cache of visited maps, so re-entering an earlier
  map would reload it fresh (the source map object is kept alive only for the
  duration of the transition). Campaigns must therefore be DAGs, which matches
  HoMM3 semantics (you never return to a finished scenario).
- **Per-map quest state does *not* carry.** `QuestStateStore`
  (`quest_state.py:38`) reads/writes quest states as *map* properties from
  each map's `QUEST_KEYS`/`QUEST_DEFAULTS`; a fresh map initializes fresh
  defaults. Anything that must outlive a scenario has to live on the player.
- **The player has a serializable generic property bag.**
  `CGameObject::setProperty` falls back to `set_dynamic_property`
  (`src/object/CGameObject.h:~100`), and dynamic properties round-trip through
  the same meta-driven serialization that persists map quest-state properties
  in saves today. This is where campaign state goes (see below).
- **Saves are a single-map snapshot with the player embedded.**
  `CSaveFormat` (`src/core/CSaveFormat.h`) wraps one `CMap` snapshot
  (versioned envelope, `schemaVersion: 1`); the player — including dynamic
  properties — serializes inside it. So campaign position stored on the
  player is persisted for free.
- **Briefing raw material exists.** `CDialog` state machines
  (`res/maps/*/dialog*.json`, driven from `res/game.py:241`), `StartEvent`
  entry text, and `CGuiHandler::showMessage`/`showSelection` cover MVP
  briefing needs without new GUI work.

## Design

### 1. Campaign manifest — `res/campaigns/<campaignId>/campaign.json`

One JSON file per campaign; a new top-level content directory parallel to
`res/maps/`. Proposed schema (v1):

```json
{
  "format": "fall-of-nouraajd-campaign",
  "schemaVersion": 1,
  "campaignId": "fallOfNouraajd",
  "title": "The Fall of Nouraajd",
  "description": "From the ruined town to the siege beyond the marsh.",
  "start": "recovery",
  "scenarios": {
    "recovery": {
      "map": "nouraajd",
      "title": "Chapter I — The Ruined Town",
      "briefing": "The town of Nouraajd lies in ruin. Its dead do not rest...",
      "epilogue": "Beren seals the cave behind you. The road bends east.",
      "next": { "completed": "cleansing" }
    },
    "cleansing": {
      "map": "ritual",
      "title": "Chapter II — The Ritual",
      "briefing": "A ritual site pulses in the marsh. Someone is still alive in there.",
      "carryover": { "gold_max": 1000 },
      "next": { "good_ending": "siege", "bad_ending": "siege_hard" }
    },
    "siege": {
      "map": "siege",
      "title": "Chapter III — The Siege",
      "briefing": "The rescued captive points at the walls ahead.",
      "next": {}
    },
    "siege_hard": {
      "map": "siege",
      "title": "Chapter III — The Siege, Alone",
      "briefing": "No one is coming to help. The walls are ahead anyway.",
      "carryover": { "items_deny": ["LifePotion"] },
      "next": {}
    }
  }
}
```

Key decisions:

- **Scenarios are keyed nodes forming a DAG**, with `start` naming the entry
  node and `next` mapping *outcome → scenario id*. An empty `next` marks a
  final scenario: its completion ends the campaign (victory screen /
  `epilogue`, then back to the start menu). This is exactly HoMM3's model
  (linear chains are the common case; branches like `good_ending` vs
  `bad_ending` are the exception) and it matches the forward-only constraint
  above. Two nodes may reuse one map with different carryover/briefings
  (`siege` vs `siege_hard`).
- **Outcomes are strings emitted by the map script** (section 3), not
  conditions evaluated by the manifest. The map knows how it was won; the
  campaign only routes.
- **`carryover` is a per-scenario *entry* policy**, HoMM3-style, defaulting to
  "carry everything" (which is what the engine does naturally). Supported v1
  keys, all optional:
  - `gold_max` (int) — clamp gold on entry.
  - `items_allow` (list of item type ids) — keep only these.
  - `items_deny` (list) — strip these.
  - `reset_active_quests` (bool) — clear `player.quests` (not
    `completedQuests`) for stories where the slate wipes between chapters.
  Level/stat caps are deliberately out of scope for v1 — this game has one
  hero, no army, and no evidence yet that chapters need power clamping.
  The schema leaves room to add `level_max` later.
- **`briefing`/`epilogue` are plain strings in v1**, rendered with the
  existing message/blocking-text GUI. A richer full-screen briefing panel
  (portrait, map thumbnail, HoMM3 crystal-ball vibes) is a later phase and
  slots in behind the same manifest fields (e.g. by allowing an object value
  `{"panel": ..., "text": ...}` in place of the string).

### 2. Campaign runtime — Python driver, not C++

The orchestrator is a Python module, `res/campaign.py`, used by `res/game.py`.
Rationale: everything it needs is already exposed to Python (map/player
access, `changeMap`, GUI selection/message, dynamic properties), the content
it consumes is JSON+Python like the rest of `res/`, and it avoids touching the
save format or type registration. No new C++ types are required for v1.

Responsibilities:

- `list_campaigns()` — scan `res/campaigns/*/campaign.json` (Python-side
  directory scan, mirroring how `CResourcesProvider::getFiles("MAP")` scans
  `res/maps/`; a native `CResType::CAMPAIGN` can come later if anything C++
  ever needs it).
- `start(game, campaign_id)` — show the first scenario's briefing, then start
  its map through the existing
  `CGameLoader.startGameWithPlayer(g, map, classId, raceId)` flow (character
  creation unchanged), then stamp campaign state onto the player (section 4).
- `complete_scenario(game, outcome)` — the single entry point map scripts
  call (section 3). Looks up the current scenario's `next[outcome]`:
  - **next scenario exists**: show current `epilogue` (if any), apply the
    destination's `carryover` policy to the player, show the destination
    `briefing`, stamp the new scenario id onto the player, then
    `game.changeMap(next_map)` — the existing async
    `requestMapChange`/`performMapChange` path does the actual transfer.
  - **`next` empty**: show `epilogue`, mark the campaign completed on the
    player, and show the campaign-complete message.
  - **unknown outcome**: raise — content validation (section 6) makes this
    unreachable for shipped content.
- `active(game)` / `current_scenario(game)` — read campaign state off the
  player so map scripts and tests can query it.

### 3. Scenario completion signaling — decouple maps from routing

Today nouraajd's script hardcodes `changeMap("ritual")` and ritual hardcodes
`changeMap("siege")`. That couples each map to its successor and makes maps
unusable in a different campaign order. The design inverts it:

- Map scripts declare their outcomes and report one:

  ```python
  # res/maps/ritual/script.py
  CAMPAIGN_OUTCOMES = ["good_ending", "bad_ending"]

  def free_captive(self):
      ...
      campaign.complete_scenario(self.getGame(), "good_ending")
  ```

- `campaign.complete_scenario` behaves as follows when **no campaign is
  active** (standalone map play): it falls back to the map's current legacy
  behavior — for the existing three maps, the direct `changeMap` call — so
  the standalone NEW flow and every existing walkthrough test keep passing.
  Concretely, `complete_scenario` takes an optional
  `fallback_map="ritual"` argument used only when `active(game)` is false.
- `CAMPAIGN_OUTCOMES` is a plain module-level list in `script.py`, exactly
  like `QUEST_KEYS`/`QUEST_DEFAULTS`, so `scripts/validate_content.py` can
  read it without importing `_game` (it already parses script.py for the
  quest declarations the same way).

The existing nouraajd/ritual scripts migrate to this in the same change that
introduces the driver, and the current hardcoded chain becomes the first
shipped manifest (`fallOfNouraajd` above) — a pure refactor with an
already-existing regression test to protect it.

### 4. Campaign state — stored on the player, persisted for free

A `CampaignStateStore` in `res/campaign.py`, deliberately shaped like
`QuestStateStore` (`quest_state.py:38`) but writing **player** dynamic
properties instead of map properties, because the player is the only object
that crosses map transitions and is embedded in every save:

| Property (on `CPlayer`)       | Meaning                                   |
| ----------------------------- | ----------------------------------------- |
| `campaign_id`                 | Active campaign, `""` if none             |
| `campaign_scenario`           | Current scenario node id                  |
| `campaign_completed`          | Bool — campaign finished                  |
| `campaign_history`            | Comma-joined `scenario:outcome` pairs     |
| `campaign_var_<name>`         | Free-form campaign variables (section 5)  |

Consequences:

- **Save/load needs zero format work.** A save taken mid-campaign is an
  ordinary single-map snapshot; on LOAD, the player deserializes with its
  campaign properties, `campaign.active(game)` is true again, and the driver
  resumes routing on the next `complete_scenario`. `schemaVersion` stays 1.
- **Standalone play is the absence of these properties.** No mode flag
  anywhere else in the engine.
- `campaign_history` gives tests and epilogue text access to the taken path
  (e.g. "you spared the captive in Chapter II").

### 5. Campaign variables — cross-scenario story state

Per-map quest state intentionally stays map-local. For the HoMM3-style cases
where a choice in chapter 1 must be visible in chapter 3, the store exposes:

```python
campaign.set_var(game, "spared_cultist", "yes")
campaign.get_var(game, "spared_cultist", default="no")
```

backed by `campaign_var_*` player properties. Map scripts and dialog
conditions can call these directly (dialog condition methods are ordinary
Python on the dialog class, per `res/game.py:241`), e.g. a chapter-3 NPC whose
`condition` checks `campaign.get_var(...) == "yes"`. This is the minimal,
serialization-free answer to "campaign-level state"; no new quest machinery.

### 6. Start menu & discovery

`res/game.py new()` gains one option: `["NEW", "CAMPAIGN", "LOAD", "RANDOM"]`.

- **CAMPAIGN** → `showSelection` over `list_campaigns()` titles → character
  creation as today → `campaign.start(...)`.
- **NEW** (standalone single map) and **RANDOM** are untouched.
- **LOAD** is untouched — campaign resumption is implicit via the player
  properties (section 4).

### 7. Content validation — `scripts/validate_content.py`

New checks, all runnable with stdlib only (consistent with the CI-first
validation contract in CLAUDE.md):

1. Manifest schema: required keys, `schemaVersion == 1`, `start` and every
   `next` target exist in `scenarios`, every `map` exists under `res/maps/`.
2. **Graph checks**: every scenario reachable from `start`; the graph is
   acyclic (forward-only constraint); at least one reachable terminal node
   (empty `next`).
3. **Outcome cross-check**: for each scenario, the outcome keys of `next` are
   a subset of the map's declared `CAMPAIGN_OUTCOMES` (parsed from
   `script.py` the same way `QUEST_KEYS` is today) — and warn on declared
   outcomes that no manifest routes, to catch dead branches.
4. Carryover references: every id in `items_allow`/`items_deny` exists in
   `res/config/items.json` (or other item-defining configs).
5. Briefing/epilogue present-and-nonempty for every scenario (authoring
   hygiene; HoMM3 scenarios always brief).

Plus matching cases in `tests/test_content_validator.py`.

### 8. Testing plan

- **Validator unit tests** (no `_game`): good manifest passes; each failure
  mode above produces a targeted error.
- **Driver unit tests** (with `_game`): `CampaignStateStore` round-trip;
  carryover policy application (gold clamp, allow/deny lists,
  `reset_active_quests`); outcome routing including branch selection and
  terminal handling.
- **Gameplay test — full campaign walkthrough**: extend the existing pattern
  (`test_campaign_transitions_preserve_player_and_start_siege`) to drive the
  `fallOfNouraajd` manifest end to end: start via `campaign.start`, complete
  nouraajd, assert same player object + `campaign_scenario == "cleansing"`
  after the async transition (`pump_event_loop`), take the `good_ending`
  branch in ritual, assert arrival in siege with the reward items intact.
- **Save/load mid-campaign test**: save in chapter 2, load, assert
  `campaign.active()` and that completing the scenario still routes correctly.
- **Regression**: all existing standalone-map walkthroughs unchanged (the
  fallback path in section 3 is what these exercise).
- `scripts/generate_walkthrough_video.py` can later grow a `--campaign` mode;
  not required for v1.

### 9. Implementation phases

1. **Phase 1 — driver + manifest + migration (MVP).** `res/campaign.py`,
   `res/campaigns/fallOfNouraajd/campaign.json`, `CAMPAIGN_OUTCOMES` +
   `complete_scenario` migration of nouraajd/ritual scripts, start-menu
   option, validator checks, tests above. Briefings via the existing blocking
   message GUI. This alone delivers a playable, savable, branching campaign.
2. **Phase 2 — presentation.** Full-screen briefing/epilogue panel (built the
   `showSelection` way: dynamic `CButton`/`CTextWidget` composition per
   `docs/design/character_creation_panel.md` findings), campaign-select
   screen with descriptions, victory screen.
3. **Phase 3 — authoring depth.** `level_max`-style carryover caps if content
   needs them; multiple shipped campaigns (the newer maps — kadath,
   ninemarches, sunderedmarch, vhulmarn — are natural chapters for a second
   campaign); optional per-branch epilogue text keyed by outcome.

### Risks / open questions

- **Dynamic-property serialization of the player** is relied on for campaign
  state. Map dynamic properties demonstrably persist in saves (quest state
  does exactly this); phase 1 must include a test pinning the same for
  player-side dynamic properties before anything else builds on it. If it
  turns out player dynamic properties are filtered anywhere in
  (de)serialization, fallback is a small set of real `V_PROPERTY` fields on
  `CPlayer` (a C++ change + type-registration touch, still no save schema
  bump thanks to defaulting).
- **Async transition + immediate carryover mutation ordering**: carryover is
  applied to the player *before* `changeMap` is requested; since the same
  player object is re-attached, ordering is safe, but the walkthrough test
  should assert post-transition state to pin it.
- **Revisiting maps** (hub-and-spoke campaigns) is explicitly out of scope:
  it requires persisting left-behind map snapshots (effectively multi-map
  saves) and a `schemaVersion` bump. The DAG constraint keeps v1 honest.
- **Mid-scenario map death / defeat routing** (HoMM3 restarts the scenario):
  v1 keeps the engine's current death behavior; a `"defeat"` outcome routed
  by `next` is a natural later extension since outcomes are already strings.
