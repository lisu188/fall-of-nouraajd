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

## Generated district content

`python scripts/build_baldurs_gate_city.py` compiles the factual fixture into the standalone `baldursGate` resources. `--check` verifies deterministic output without rewriting it. The nine exterior wards occupy the ground level; the other 203 source areas occupy disconnected regions on four additional levels. Each source travel trigger or world-map link retains its identity, direction and target entrance. Collision adjustments and safe arrival positions are recorded in `tests/fixtures/baldurs_gate_city_geometry.json`.

The current adaptation contains 56 authored quest/interaction definitions and three labelled outside-city excursions. Ordinary actors, containers, shops and minor interiors are included in the atlas, but their presence does not imply that every original conversation or script has been implemented. Static source corpses remain noncombat containers. Chapter-seven departure scripts park surviving first-visit actors without awarding death rewards. Aldeth, Tamoko and Narlen share one persistent actor and one inventory across their source scenes.

The first entry adds 10,000 native experience and 1,000 gold to the selected existing hero. The serialized starting profile records actual composed stats, resources, carried and equipped items, and the explicitly selected history. History finalization freezes those choices; it grants no outside campaign completion. Source item identities, charges, item-slot indices and drop restrictions remain separate from native gear conversions.

Shop actions respect source store capability flags, accepted item categories and fenced-goods rules. Native stack valuation multiplies the raw source value by actual stack quantity before markup and the one-gold purchase minimum; this follows the [GemRB pricing implementation](https://github.com/gemrb/gemrb/blob/master/gemrb/GUIScripts/GUISTORE.py#L1609-L1616) as supporting evidence. Nonstackable charges are not stack quantity. Exact reaction, depreciation and charge-ratio valuation remain source acceptance gaps.

Narlen's verified source timer value20 is represented as20 native turns after the explicit lookout start. The actual source Watchman must be present for a warning, and only that officer's death can satisfy the violent alternative. Exact original timer units, class restrictions and all silence/betrayal branches remain pending; the conversion is not an original timing-equivalence claim.

All 188 nontravel regions retain their polygons and native cell projections. Entering a region can record a visit without granting source trap, spell or quest effects. Unsupported effects remain pending in the ledger. Whole-polygon observations occur on coordinator ticks; exact original trap timing has not been established. The source region projection has a deterministic bounded-work regression.

The factual ledger is generated outside runtime configuration:

```powershell
python scripts/build_baldurs_gate_city_ledger.py
python scripts/build_baldurs_gate_city_ledger.py --check
```

Its strict `--require-mapped` and `--require-acceptance` modes are expected to fail until all declared obligations and evidence are complete. No generated row has accepted native gameplay status. The ledger rejects invented receipts, missing source fingerprints and stale input mappings.

Focused development checks are separate from native acceptance:

```powershell
python -B -m unittest tests.test_candlekeep_source tests.test_binding_source_layout tests.test_baldurs_gate_city_content tests.test_baldurs_gate_city_geometry tests.test_baldurs_gate_city_regions tests.test_baldurs_gate_city_routes tests.test_baldurs_gate_city_ledger tests.test_quest_journal tests.test_ui_dialogue -q
python test.py --suite mcp-branches --branch-group baldursGate
```

The first command uses source checks and native-shaped model doubles. The second requires a current staged native binary and real movement/dialogue/combat. Planned routes cover all five existing hero classes, but an unexecuted route is not a passing receipt. Shop chooser cancellation never proves an item was sold, stolen or transferred.

Current acceptance blockers include original BG1-versus-EE reconciliation, unsupported source scripts and item effects, crime/arrest/escape outcomes, remaining conversation and recruitment branches, exact shop/temple formulas, and complete native save/reload and visual evidence. The owner confirmed that neither an original installation nor an alternate build volume is available. After bounded verified cleanup, C: remains above 95 percent used. No local native build or capture is authorized by that cleanup result; the 90 percent guard remains in force.


## Bounded palace source audits

The palace audit fixtures are factual development metadata from installed BG1EE
resources, supporting an original-BG1 target. They contain fingerprints, selected
operation/selector facts and actor script-slot bindings, without original binary
payloads, compiled script bodies or dialogue prose. The initial manifest of 43
resources and supplemental manifest of 22 remain unchanged. The expanded listener
closure fingerprints 79 resources, 21 CRE, 22 actor BCS plus the area script and four
cutscene boundaries. Shout 50's escape-only receiver, earlier behavior 3 guard/noble
branches and surviving doppelgangers' source EA 28 are recorded facts, not an
implemented script scheduler.

Run only the pure source contracts for focused feedback:

```powershell
python -B -m unittest tests.test_baldurs_gate_palace_audit tests.test_baldurs_gate_palace_shout tests.test_baldurs_gate_palace_listener_closure -q
```

The optional installed-resource reader is bounded to the fixed 79-resource closure:

```powershell
python -B scripts/audit_baldurs_gate_palace_listener_closure.py --game-root <installed-game-root> --project-root .
```

The reader compares base/effective bytes and reproduces the reviewed metadata with
an explicit 192 KiB output cap. Helper fingerprints normalize CRLF to LF; source-origin
paths use declared archive-style separators. Optional CLI outputs use exclusive
creation after serialization and size checks, preserving existing evidence and
targets created by another writer immediately before the final open. The installed SAREVO.ITM
override remains an item/effect boundary. Script scheduling, event consumption,
geometry, live actor ownership and original-versus-EE reconciliation remain pending.
These tests/audits grant no native execution, gameplay, original parity, acceptance
or ledger credit; all corresponding closure acceptance flags remain false.
