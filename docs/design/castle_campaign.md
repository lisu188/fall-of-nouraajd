# Long Live the Queen

The `longLiveTheQueen` campaign adapts the three Castle scenarios from the original
Heroes III Restoration of Erathia campaign into the engine's existing RPG combat
and character progression. It uses an ordinary player created through the campaign
browser. Catherine, Christian, and allied soldiers are NPCs.

| Chapter | Native map | Original extent | Victory |
| --- | --- | --- | --- |
| Homecoming | `castleHomecoming` | 72 × 72 × 2 | Defeat Terraneus's garrison and capture its underground entrance. |
| Guardian Angels | `castleGuardianAngels` | 36 × 36 × 2 | Capture every original enemy town and defeat every designated enemy hero. |
| Griffin Cliff | `castleGriffinCliff` | 72 × 72 × 2 | Liberate all seven distinct Griffin Towers. |

Inventory, equipment, gold, and character progression carry through ordinary map
transitions. Each map also works through standalone map selection. The same
objective gates apply; the first two standalone victories lead to the following
map, and Griffin Cliff ends in place.

## Reproduce the authored maps

The checked-in JSON is sufficient to play and validate the campaign. The original
installation is needed only to repeat authoring:

```powershell
python scripts/import_castle_campaign.py --heroes-dir "C:\path\to\Heroes III"
```

The importer reads `Data/H3pbitma.lod`, extracts `GOOD1.H3C` in memory, validates the
known source hash, and decodes its three RoE maps with type-specific binary record
handlers. The input is never modified. Unsupported editions, object records,
truncation, and invalid counts fail explicitly. No original graphics, music,
localized prose, or binary game files are required at runtime.

Source provenance is stored under
`res/campaigns/longLiveTheQueen/sources/`. Each document records the campaign and
map hashes, terrain/road/river bytes, object anchors, visit positions, footprint
masks, original owner/army data, and transit mappings. Source documents are outside
map directories because the engine treats all map-local JSON except `map.json` as
object configuration.

Interactive locations use the original visit mask, which may differ from the
object anchor. Terraneus's entrance is `(33, 35, 1)`; its anchor is farther east.
The importer preserves map extent and obstacle footprints and records the boat
route used by the RPG embark/disembark adaptation. Campaign roads use a plain
tile class and do not inherit the main game's healing road behavior.

Heroes III permits diagonal movement, while this engine's ordinary pathfinding
uses four directions. The importer connects the necessary disconnected land
components with a minimal set of original, walkable diagonal steps, recorded as
`diagonalRoutes`. Paired narrow-passage markers register those steps with the
existing navigation API. They do not change terrain, remove obstacles, or
automatically teleport a player stepping onto the marker.

## Objective and save behavior

The shared `castle_campaign` plugin reads each map's `castleMission` metadata.
Captured objectives and defeated defenders are stored as named boolean map
properties; completed chapter quests are also recorded on the carried player.
Capturing requires the active, living player to be on the same floor within one
cell of the objective and every named guard to have actually died. Removing a
living guard is not a combat victory. Captures and chapter rewards are idempotent.

The seventh distinct Griffin Tower completes the finale even if unrelated enemies
remain. Guardian Angels separately checks its enemy commander list. Quests are
completed before the existing campaign driver requests the next map, and retained
handles to an earlier chapter cannot advance the current chapter.

## Focused validation

Source and gate tests require only Python:

```sh
python -m unittest tests.test_castle_importer tests.test_castle_campaign -v
python scripts/validate_content.py
```

After normal CMake configuration has staged the resources beside `_game`, run:

```sh
python test.py GameTest.test_map_walkthrough_castleHomecoming GameTest.test_map_walkthrough_castleGuardianAngels GameTest.test_map_walkthrough_castleGriffinCliff
python test.py GameTest.test_castle_campaign_carryover_with_melee_and_caster GameTest.test_castle_partial_capture_survives_save_load
python test.py GameTest.test_castle_campaign_initializes_on_first_normal_turn
python test.py McpServerTest.test_stdio_castle_campaign_full_route
```

Use Python 3.12 and `GAME_BUILD_CONFIG=Release` for a Windows Visual Studio build.
Keep headless runs on `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`. If a
multi-config build's DLL searches only its sibling resource directories, use the
normal CMake installation rules to create an isolated validation installation:

```powershell
cmake --install cmake-build-release --config Release --prefix cmake-build-release/castle-validation-install
$env:GAME_BUILD_DIR = 'cmake-build-release/castle-validation-install/fall-of-nouraajd'
$env:GAME_BUILD_CONFIG = 'Release'
$env:SDL_VIDEODRIVER = 'dummy'
$env:SDL_AUDIODRIVER = 'dummy'
```

The native and stdio MCP walkthroughs share a source-derived traversal harness.
They move the actual player through reachable terrain, use authored transit,
fight the actual defenders, capture objectives, and assert quest and campaign
state. The complete native campaign runs with the unchanged Warrior and Sorcerer
templates; tests consume only supplies present in the game.
For headless combat they use the selected class template's existing fight
controller, preserving character stats, equipment, and ordinary combat actions.
The save regression checks partial objective progress, one-time supplies, and
navigation edges restored through normal turns, including controller movement
through an original diagonal passage.

MCP subprocesses use the existing concurrent stderr drain, critical log level,
disabled native log sink, and extended serialization timeout. Walkthrough logs
are written under the configured test output directory. CI supplies the complete
native, Python, performance-guard, and applicable coverage evidence according to
the repository's existing validation rules.

Artwork prompts and asset provenance are recorded in
[castle_art_prompts.json](castle_art_prompts.json). Regenerate the required panel,
authored-map, and random-map set with `scripts/generate_screenshots.py --output-dir screenshots`,
and the original landing, underground town, and Griffin Tower views with
`scripts/capture_castle_landmarks.py --tile-size 32`. Use a virtual screen or the
scripts' headless rendering support for these captures.
