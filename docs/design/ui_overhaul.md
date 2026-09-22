# Interface and dialogue design

The interface uses opaque charcoal surfaces, warm ivory text and restrained gold selection accents. Existing
world artwork, gameplay rules, resource identifiers, character eligibility and quest outcomes remain authoritative.
Source Sans 3 supplies controls and prose; Source Serif 4 supplies headings. Both font assets and their SIL Open
Font License notices ship through the existing CMake resource handling.

## Interaction

Inventory, abilities, trade and combat lists select on left-click. Repeated selection never executes an action.
Hover previews details; right-click pins inspection. Use, Equip, Unequip, trade quantity controls and combat
execution buttons perform the named operation and revalidate its availability. Drag-to-equip remains a shortcut.

Tab/Shift+Tab moves focus, arrows navigate lists, and Enter/Space activates the focused control. Search starts with
`/` on a searchable list. Escape dismisses the top cancellable surface and restores its owner's focus. It never
chooses an authored dialogue response merely because that response leads to `EXIT`. Combat Escape opens Pause.
Opening, closing and scene transitions consume the triggering input. Inspection and navigation do not advance turns.
Held keys remain suppressed across panel changes until release, so acknowledging a reader cannot also wait a world
turn or acknowledge the following reader. A fresh world press retains the existing movement/wait repeat behavior.

I/J/C retain Inventory, Journal and Character navigation. M opens the expanded map; F12 opens the existing gated
developer console. World clicks preview a destination; Travel or Enter commits it. Manual movement or waiting
invalidates the previous preview. Settings remap gameplay bindings while reserving interface navigation keys.

## Layout and presentation

`CUiTheme`, `CTextManager`, `CGui` and `CGamePanel` own shared colors, font roles, scaling, focus and management shells.
User interface and text scales range from 100 to 200 percent in 25-percent steps; automatic scaling applies above
the 1080p reference display. The two user scale settings do not multiply text enlargement twice. Preferences live
outside game saves and are validated before application.

Management screens preserve selection and scroll state. When columns no longer fit, labelled regions become
separate pages, available with mouse arrows or `[` / `]`. Text remains at the chosen scale. Lists provide search,
scrolling and keyboard-accessible paging; footers reserve the space needed by the actual rendered button labels.
Compact trade regions expose the action for the inventory currently being viewed.

The frontend provides Continue, New adventure, Load, Settings, Help and Quit; adventure/scenario/campaign browsers;
a combined character preview; chapter briefings/outcomes; named saves and overwrite review; and operation-specific
loading and failure feedback. Character previews initialize a detached character using the same level-one resource
initialization as the started player. Save failure leaves the active session available.

Campaign and scenario previews accept optional `artwork` paths to existing bundled PNGs under `images/`.
The native browser and chapter reader preserve artwork proportions and move it above text at compact sizes;
missing artwork returns its space to the text. `showCampaignArtworkScreen` adds this presentation while the
existing three-argument `showCampaignScreen` remains compatible.

Combat records the latest 64 authoritative encounter events. The Combat log button or `L` opens a scrollable,
read-only reader without changing the selected action, target, round, or world turn. Closing the encounter or
changing scenes also closes its reader. The search field retains ordinary `L` text entry.

Conversation choices retain authored order and conditional visibility. Consequential action labels precede authored
response prose. Transcript/history views are read-only. Dialogue callbacks validate the owning scene, including
queued scene changes, and cannot continue acting through a detached panel.
The 25 authored conversations now contain 115 states and 210 options; added states/options make commitments and
in-progress reminders explicit. Related quest context is shown only for the player's active matching quests.
Map scripts route substantial lore to titled readers, observed reward gains to consolidated receipts, and routine
discoveries/progress to History. Blocked world actions can anchor their resolved requirement beside the actual object.

## Verification and accessibility

All automated GUI runs, screenshots and game-session subprocesses use an isolated virtual/offscreen display. Linux
uses Xvfb; supported Windows runs use SDL dummy/offscreen video and software rendering. Missing isolation blocks the
specific display check rather than opening a window on the user's desktop. Screenshot generation checks nonempty,
loadable PNGs and dimensions, and includes every registered panel, every authored map, a random map, frontend states
and enlarged-scale variants. The capture generator refreshes the README image aliases from the same run.

The shared text colors meet the 4.5:1 body-text target on the background, panel and selected surfaces. The lowest
ratio among ordinary text roles on the selected surface is 5.11:1 for the gold accent; primary text is 10.00:1 and
secondary text 5.69:1. The smallest bundled font's measured `Agpq` glyph body is 19 pixels at reference scale and
39 pixels at 4K scale. These asset checks are separate from rendered screen/overflow inspection. The reference
criteria are [XAG 101 text display](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/101),
[XAG 112 navigation](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/112), and
[WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

Focused native suites are `ui_foundations_unit_tests`, `ui_navigation_unit_tests`, `ui_management_unit_tests`,
`ui_frontend_unit_tests` and `ui_dialogue_unit_tests`. They also belong to `for_unit_tests` for repository CI.
Python source/asset suites include `tests.test_ui_frontend`, `tests.test_ui_dialogue`, `tests.test_ui_accessibility`,
`tests.test_generate_screenshots` and `tests.test_mcp_stdio_encoding`. `tests.test_ui_mcp_dialogue` drives the actual
player through amulet, companion, captive/Voss and ritual scene routes with observable reward/quest assertions.
The Sundered March route checks its gate, banner reminder and guarded late reward. `tests.test_ui_mcp_management`
visits authored crafting and trade stations, revalidates costs/ownership, and approaches an authored enemy before
executing an owned ability. These deterministic routes use explicit setup for resources and combat statistics;
they complement the natural Nouraajd GUI quest walkthrough rather than establishing a complete campaign playthrough.
Existing crafting, save, inventory, trade and Nouraajd walkthrough tests retain their gameplay assertions while
using the new explicit interface actions.

## Rendering and cache evidence

The opt-in [profile harness and complete samples](../../scripts/ui_text_profile/README.md) retain the exact workload
and reproduction commands for the diagnostic comparison below.

Text cache keys include text, wrapping width, role, effective pixel size and color. Texture entries are bounded at
512 and font entries at 24. Readers and persistent management details split long text into cached, UTF-8-safe
paragraph chunks and draw only visible chunks, so the individual texture limit cannot discard the end of a letter,
item comparison, transaction, or journal entry. Changing scale invalidates obsolete text metrics and font/text caches.

The deterministic performance guard warms 200 distinct strings and draws 2,000 cached copies. It requires zero new
texture loads for the warm draws, successful render copies, bounded entries and correct invalidation. Run it with:

```sh
cmake --build cmake-build-release --target performance_guard_tests -j4
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
```

On Windows add `--config Release` to the build and `-C Release` to CTest, use the configured Python 3.12 home, and
set `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`, `SDL_RENDER_DRIVER=software` before native execution.

Supplemental local profiling compared original commit `065b5d6010bffa6044b422e0ff6292557bfcf313` with the redesigned
text path using MSVC 19.44, x64 Release, SDL dummy/software, the same harness and dependency installation. The workload
was 200 strings of width 600, 200 cached lookups, and 200 redraw passes of ten strings, after one warm-up and across
seven measured samples. Recorded median milliseconds were:

| Version | Cold text | Cached lookup | 2,000 redraws |
| --- | ---: | ---: | ---: |
| Original | 17.3044 | 0.0880 | 117.4568 |
| Redesigned text path | 15.6275 | 0.0789 | 41.8992 |

Every sample recorded 2,000 successful copies and zero failed/skipped copies. These timings are diagnostic: font
assets changed, the original build did not use the current unity/PCH configuration, and later layout changes are
not represented by that timing snapshot. They do not establish a whole-frame speedup. Deterministic cache/render
counts remain the acceptance gate. The original full performance run also exposed three sparse-map path failures
caused by Windows configuration-directory resource lookup; the current provider resolves the verified parent
build resource directory, and the unchanged path assertions pass in the current focused run.

The current Windows Release guard also verifies 700 choice rows with zero new textures across four warm redraws,
and 700 detail paragraphs with six visible texture loads (budget 16) followed by zero new textures across 25 warm
redraws. The detail guard checks that copies correspond only to visible paragraphs and that unchanged text is not
remeasured. These counts were obtained with the CTest performance command above using SDL dummy/software rendering;
the [retained chooser profile](../../scripts/ui_text_profile/README.md#choice-list-cache-profile) records the earlier
723-texture-per-redraw development result and its fixture limitations.

Required Linux, Windows, full-suite and coverage evidence comes from the PR's path-selected `build` workflow. A
successful focused local run or screenshot set alone is not a claim that those release checks have completed.
