# Baldur's Gate city scenario

This scenario targets the city in officially patched, unmodded original Baldur's Gate. It is independent of the Candlekeep prologue. The playable boundary consists of nine exterior districts and their individually enumerated interiors, sewers, Undercellar, Thieves' Maze, Undercity and final temple. Wyrm's Crossing, Tales of the Sword Coast and Enhanced Edition additions are outside that boundary.

The implementation is delivered in stages: source inventory and opt-in runtime support; district content; the later return and finale; then complete acceptance evidence. A source record or a passing model test does not establish an original-game outcome or native gameplay parity.

## Evidence and source policy

- [Classic city plan](https://www.forgottenwars.com/bg1/city_plan.htm), [area index](https://www.forgottenwars.com/bg1/megamap.htm), [quest checklist](https://www.forgottenwars.com/bg1/checklist.htm) and [GameBanshee city walkthrough](https://www.gamebanshee.com/baldursgate/walkthrough/baldursgateeastern.php) provide geographic and behavioral corroboration. Dudleyville explicitly includes Tales and community fixes; individual claims require an edition decision.
- `tests/fixtures/baldurs_gate_city_source.json` contains factual metadata and fingerprints from the installed EE base archives. It excludes overrides from payload selection. KEY-indexed archives may still contain installed modifications. The fixture is supporting evidence, not authenticated original BG1 data.
- The explicit 212-area manifest in the auditor prevents resource-prefix traversal from silently including expansion areas. Every linked area outside it remains a recorded boundary. Missing references, uninterpreted effects and original-versus-EE differences remain outstanding acceptance requirements.
- Original binaries, extracted artwork and full dialogue/script dumps must remain outside Git. Generated native resources use existing project artwork and reworded conversation text.

Reproduce the supporting fixture with:

```powershell
python scripts/build_baldurs_gate_source_fixture.py --game-root "C:\Program Files (x86)\GOG Galaxy\Games\Baldur's Gate - Enhanced Edition" --language en_US --output tests/fixtures/baldurs_gate_city_source.json
```

The general auditor retains its existing Candlekeep invocation. Use `--scope city --area AR0800` with `scripts/audit_candlekeep_source.py` to audit the bounded city dependency closure. Audit output belongs outside the original installation and outside resource configuration directories.

## Opt-in regional simulation

`CMap.activeSimulationRegion` is a serialized string. An empty value preserves the existing all-object simulation. With a nonempty value, objects with a matching `simulationRegion` receive turn hooks, controller planning, movement commits and controller turn-end callbacks. The actual map player, objects with no region and objects with `alwaysSimulate=true` remain active.

Changing the region invalidates already scheduled work, including a switch away and back during an awaited controller request. A region switch inside a committed turn consumes that turn once. It does not give actors in the newly entered area an extra turn. A city coordinator uses `alwaysSimulate` to advance global deadlines; area-local AI stays dormant outside its source area. This optimization bounds dispatched callbacks and controller requests; it still scans the map's object registry and makes no total CPU-time claim.

`tests/unit/test_simulation_regions.cpp` uses a deterministic workload derived from the source fixture: 545 exterior actors, three global actors, then 724 additional dormant interior actors. The active-ward request budget remains 64. Native checks also cover suspended work, region changes, opt-out behavior and serialized region properties. These tests require compilation before their results count as runtime evidence.

## Optional allied encounters

Existing combat entry points retain their behavior unless a map enables `plugin_cityAlliedCombat`. Its comma-separated `plugin_cityCompanionNames` identifies at most five distinct, living, affiliated NPC creatures in the same map and level. Natural encounter discovery examines at most 32 names and a bounded combat radius (default 8 cells, clamped to 1 through 16). Explicit `fightManyWithAllies` and `fightManyWithAlliesOutcome` accept candidate actor lists.

The hero supplies the player decision controller. Allies use native AI fight controllers and participate in initiative, effects, stalls and bounded rounds. Enemies choose a living hero-side target. Defeated enemies grant native experience and their actual carried possessions to the surviving hero. Fallen allies follow creature destruction and actual loot transfer; the city coordinator must retain companion death state. Hero defeat ends the encounter immediately, even if ordinary player destruction respawns the hero. No six-character selection interface is introduced.

The city additionally enables `plugin_cityFixedLoot`: defeated NPCs transfer only their actual bag/equipped possessions and saved gold, with no unrelated random loot. Source-forbidden drops stay with the removed actor; removing equipped references prevents resurrection from duplicating items. The flag is opt-in and preserves other maps' loot behavior.

`tests/unit/test_allied_combat.cpp` covers native ally actions, exact rewards, invalid candidates, participant limits, mover perspectives, ally death, hero respawn, effects, cancellation and stale map contexts.

## Content and acceptance contracts

The map generator aggregates factual source collision metadata into native cells, places individually identified objects, and records any placement adjustment. Source actor schedules, locks, traps, ownership, stock and door states must have an implemented outcome or an explicit unresolved ledger obligation. Merely drawing a container or offering a generic conversation does not satisfy that obligation.

The city starts with an explicit native level-five profile and a recorded history selection. History is not played campaign progress. Quests use composed native statistics: Intelligence plus local standing for reaction; Agility 12, 16 or 18 for audited lock/theft tiers; Strength 12 or 14 for source-permitted forcing. Source prohibitions and unavoidable detection take precedence. Native combat experience and item effects require documented conversions; unsupported source effects must remain visible acceptance gaps.

First-visit and later-return states share one serialized map. Deaths, actual possessions, containers, locks, followers, stock, clocks and optional quests must survive transitions and reloads. Outside errands are labelled text-choice excursions; the city interlude applies only after its prerequisites. Completing the finale records the city storyline without completing unrelated optional quests.

Acceptance requires the complete declared source/interaction manifest, focused regressions, real MCP routes using natural movement and dialogue choices, all five hero classes collectively, save/reload checks, isolated visual inspection, selected Linux/Windows builds, applicable coverage of at least 90 percent, and review resolution. Record these evidence classes separately. The local C: disk guard currently blocks large native builds and captures; CI can provide compilation and automated checks, but cannot substitute for missing original-source reconciliation or owner acceptance.
