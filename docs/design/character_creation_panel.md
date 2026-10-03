# Unified character creation

Character creation uses the shared `CGameCampaignBrowserPanel`, configured by
`CGuiHandler.showCharacterCreationOptions(classesJson, racesJson)`. This document
describes the implementation and acceptance requirements for issue #1506.

## Selection and adventure flow

`res/ui.py` owns the frontend. `newAdventure` selects a scenario, campaign, or
random adventure, then calls `chooseCharacter` once. Both class and race belong
to the same modal chooser. Confirmation returns stable resource IDs, which are
passed unchanged to `startGameWithPlayer`, `campaign.start`, or
`startRandomGameWithPlayer`. Display labels are never used as resource IDs.

The existing roster contains five class templates (`Assasin`, `Inquisitor`,
`Sorcerer`, `Warrior`, `Wayfarer`) and four selectable races (`highlanderRace`,
`humanRace`, `outlanderRace`, `wandererRace`): twenty compositions. The chooser
enumerates actual `CPlayer` templates and `CCreatureRace.playerSelectable`
entries; it does not maintain a second roster.

`characterChoices` builds each preview from the actual composed player template
with the selected race. The preview includes description, Strength, Agility,
Stamina, Intelligence, maximum health and mana, effective starting abilities,
and equipped items. These temporary objects are not added to the map.

Changing the highlighted class or race updates the preview. It does not start
an adventure. The panel remembers the previous preview in the current GUI
handler, and explicit confirmation starts the selected composition. Escape,
Back, and panel teardown resolve to empty IDs. Invalid IDs are rejected by
`chooseCharacter`; cancellation returns to the adventure mode chooser.
Loading a save bypasses character creation and keeps the saved player's class,
race, equipment, progression, and campaign state.

## Layout and input

The shared panel draws text choice rows and a scrolling details pane. Wide
layouts display the class column, race column, and preview together. Compact
layouts use Class, Race, and Details pages. Arrow keys move between rows or
columns/pages; Home and End select list endpoints; Tab moves through the
choice, race, details, confirmation, and Back controls. Enter confirms, and
Escape cancels. Mouse choices use the same panel selection state.

The implementation lives in `src/gui/panel/CGameCampaignBrowserPanel.*` and
`src/handler/CGuiHandler.cpp`; the Python binding is in `src/core/CModule.cpp`.
It reuses `campaignBrowserPanel` from `res/config/panels.json`. No separate
character-creation resource, race portraits, or sequential-menu fallback is
required.

## Acceptance matrix

| Requirement | Automated evidence |
| --- | --- |
| Existing five classes and four races yield exactly twenty compositions | `CharacterCreationFlowTest.testExistingRosterHasExactlyTwentyCompositions` |
| Scenario, campaign, and random routes use one chooser and pass exact IDs | All twenty compositions through all three routes in `CharacterCreationFlowTest` |
| Cancel and invalid IDs create no map; LOAD bypasses the chooser | `CharacterCreationFlowTest` cancellation and load tests |
| Preview stats, maximum health/mana, abilities, and equipment match the selected runtime player | All twenty compositions in `CharacterPreviewRuntimeTest` |
| Real keyboard selection, preview-only highlights, confirmation, cancellation, teardown, and usable bounds | `XvfbGameplayProcessTest.test_character_creation_all_twenty_compositions`: all twenty compositions at 800×600, 1280×720, and 1920×1080 in one GUI session |
| Captures contain rendered pixels and valid PNG metadata | Six first/last-composition captures in that virtual-display test, checked with the existing screenshot helper |
| Existing pointer selection and modal behavior remain covered | Existing `GameTest.test_character_creation_uses_unified_confirmation_with_stable_ids`, blocking helper tests, and campaign-browser GUI tests |
| Tests are selected once in their intended source/native suites | `TestRunnerSuiteTest` source and native discovery assertions |

The source tests can run without `_game`:

```sh
python3 -m unittest tests.test_character_creation_acceptance.CharacterCreationFlowTest
```

After building `_game`, run the native preview and virtual-display acceptance:

```sh
python3 test.py CharacterPreviewRuntimeTest
GAME_XVFB_ONLY_CHILD_TESTS=test_character_creation_all_twenty_compositions python3 test.py --suite ui
```

The normal PR `build` workflow selects source tests, native gameplay tests,
Linux GUI tests under Xvfb, and applicable coverage. A skipped compiled-module
or display check does not count as runtime acceptance. Close #1506 after these
checks pass on the delivered head and its PR merges. Source assertions alone
do not establish rendered correctness.

Captures live in the test session's `GAME_TEST_OUTPUT_DIR`. The current PR
Linux UI job validates them without uploading that directory. The existing
coverage report uploads `coverage/test-output` when available; durable capture
evidence requires its published artifact to contain the six chooser PNGs. This
acceptance change alters tests and documentation, so it does not change the
rendered UI or require regeneration of the repository's full screenshot set.
