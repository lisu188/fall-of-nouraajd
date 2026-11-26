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

## Disabled poison source foundation

The city builder stages seven retained poison dialogue graphs, including TENYA2: 84 states, 135 transitions and
219 authored state/reply mappings. `scripts/build_baldurs_gate_city_poison.py` validates that exact inventory and
adds separate source-mode dialogs, actor factories and finite action positions to the existing city resources.
`plugin_cityPoisonSourceEnabled` remains false. All existing dialog definitions retain their previous contents.

The map-local implementation binds conversations and saved continuations to actual actor instances. It implements
ordered fees, rewards and item transfers; separately created NPC ownership; prospective death witnesses; delayed
actions; and the acquisition/cure consumer with distinct 650 kill XP, 1,500 scroll-delivery XP and 10,000 cure XP.
The city separately opts into native `sourceKillXp` settlement on fresh entry and verified load. It never adds a
second kill reward from Python. The source-only callback tests use doubles and do not establish native gameplay.

Source-mode activation remains pending actual routes and the unfinished SHOUT listeners, charm producer, BOOK08
conversion, warning/fatal scheduler, outside-history producers, progressed-save migration and source slot priority.
Unlinked branches remain in the inventory without a claim of natural reachability. Unsupported SHOUT continuations
are refused before mutation. These holds and the original-versus-EE differences remain acceptance requirements;
staging these graphs does not close their ledger obligations.

### Original patch evidence

The international BG1 1.1.4315 patch contains 45 resources in the audited city closure, including 18 dialogues,
four areas, twelve creatures, nine items and two compiled scripts. The installer fingerprint matches the
international release recorded by the historical PlayOnLinux installer. The executable was read as an archive.
[Historical patch URL and checksum](https://www.playonlinux.com/en/app-772-Baldurs_Gate_Patch_114315.html)

Reproduce the checked-in factual comparison using a privately extracted patch and the installed EE game:

```powershell
python scripts/audit_baldurs_gate_city_patch.py --patch-file "$patchFile" --patch-override "$patchOverrideDir" --ee-root "$eeRoot" --output tests/fixtures/baldurs_gate_city_classic_patch.json --check
```

The tool verifies both the installer and extracted city member fingerprints, reads the EE base archive and
checks each EE member against the existing city inventory. Dialogue comparisons use state number and choice
position within each state. Inserting a choice can shift later choices in that state. Unused script pool entries
and whitespace between tokens do not change this comparison. Quoted operands, action order, reply and journal
references, flags and transition targets are significant. Each record also compares the state trigger indices
used for entry priority and records the EE hostile-interruption header flags. A string reference identifies a TLK entry within its
own edition. Matching references alone leave the actual wording unverified. The comparison covers the fields
decoded by the existing parsers. The two compiled scripts have fingerprint comparisons only.
[Infinity Engine dialogue layout](https://gibberlings3.github.io/iesdp/file_formats/ie_formats/dlg_v1.htm)

| Source location (zero-based) | Verified original patch record | Outstanding city behavior |
| --- | --- | --- |
| Lothander, state 14, first choice | The handoff takes the geas scroll, awards 1,500 party XP and requests a transfer of `POTN20` from the speaker. EE creates `LOPOTN20` instead. The classic graph has 16 states and 24 choices. | Verify ownership after prior theft and reconcile the two EE-only trailing states with the retained EE obligations. |
| Diviner, state 0, second choice | Both editions request 50 gold. Only EE conditions the choice on the party having at least 50 gold. | Preserve availability of the classic choice. The amount actually removed from a poor party requires engine evidence. |
| Fenten, state 3, first choice | The classic action transfers all carried `MISC12` shells and pays 250 gold once for that transaction. EE adds a second choice under a history condition. | Exercise multiple shells, one payment, repeat visits with new shells and initial reaction-dependent departure. |

These records cover a subset of the game data. Original-game execution, the rest of the installation, text
comparisons and native city acceptance remain open. No EE ledger obligations are retired by this audit.

The original AR0111 area places a fourth actor, `SLAVE4`, at source coordinates (996, 278). The EE area has
three placements. Its first container also reduces the original lock difficulty from 100 to 90. In AR0109 the
second container moves four source pixels horizontally between editions. Ithmeera in AR0145 stands at
(595, 511) in the patch and (575, 517) in EE. The AR0146 maze door has an empty travel-trigger reference in
the classic record and `Door0123` in EE. The area's region and door connections require separate checks
before treating that difference as a change to playable access.

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

The city starts with a recorded native hero profile and history selection. The existing hero and experience grant determine its actual level and composed stats. History is not played campaign progress. Quests use composed native statistics: Intelligence plus local standing for reaction; Agility 12, 16 or 18 for audited lock/theft tiers; Strength 12 or 14 for source-permitted forcing. Source prohibitions and unavoidable detection take precedence. Native combat experience and item effects require documented conversions; unsupported source effects must remain visible acceptance gaps.

First-visit and later-return states share one serialized map. Deaths, actual possessions, containers, locks, followers, stock, clocks and optional quests must survive transitions and reloads. Outside errands are labelled text-choice excursions; the city interlude applies only after its prerequisites. Completing the finale records the city storyline without completing unrelated optional quests.

Acceptance requires the complete declared source/interaction manifest, focused regressions, real MCP routes using natural movement and dialogue choices, all five hero classes collectively, save/reload checks, isolated visual inspection, selected Linux/Windows builds, applicable coverage of at least 90 percent, and review resolution. Record these evidence classes separately. Check local capacity against the 90 percent disk guard before native builds or captures. Prefer CI for heavy compilation and automated checks; these cannot substitute for missing original-source reconciliation or owner acceptance.

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

### Poison-chain source inventory

`tests/fixtures/baldurs_gate_city_poison_dialogue.json` records the supporting EE
graphs for Marek, Lothander, the Diviner, the priestess, Jalantha and Chanthalas:
72 states and 112 transitions, including false and unlinked entries. It also
records nine selected script blocks, four item headers, two item abilities,
eleven inline effects and eight explicit unresolved frontiers. All 218 additional
ledger obligations remain planned, with native, original-game and owner
acceptance pending. These records retain source identities and fingerprints;
original binaries, dialogue prose and full script dumps stay outside Git.

`tests/fixtures/baldurs_gate_city_poison_followup.json` preserves 41 additional
supporting-EE source records: TENYA2's 12 states and 23 transitions, BDMAREK's
header, ability and two effects, and two GTIMES constants. Every record adds a
required planned ledger obligation; the preceding 218 poison records and all
older ledger rows remain unchanged. These additions award no native, original
game, coverage or owner acceptance.

TENYA2 supplies body-item alternatives through BOYBODY and MISC54. Seven terminal
transitions give the item to LastTalkedToBy and depart; those transitions occur
on eight syntactic paths. A separate transition creates MISC54 on the actor and
turns hostile. The retained graph does not establish external entry into its
unlinked state. PUMBERL's conditioned summon, the separate Tenya/Tenya2 death
identities, actual ownership and the starting-history bridge remain pending.

PoisonParty and PoisonParty2 are distinct GLOBAL timers, initialized respectively
to ONE_DAY = 7200 and TEN_DAYS = 72000 before Lothander's later agreement choice.
The selected warning block rearms only PoisonParty. Their durations are not
summed; source scheduling and conversion to this engine's clock remain pending.
BDMAREK's declared ability owns opcode 215 and opcode 142 effects. That table
contains no opcode 309. This selected payload does not establish exclusive
manual drinking, absence of automatic cure, or the complete producer chain;
42 BALDUR blocks and newly encountered resource identifiers remain unfollowed.
No original dialogue prose, binary payload or full script dump is committed.

The development auditor can additionally decode bounded ITM V1 inline effect
fields with `--item-effects`; existing invocations retain their previous output
and resource-discovery behavior. For example:

```powershell
python scripts/audit_candlekeep_source.py --game-root "C:\Program Files (x86)\GOG Galaxy\Games\Baldur's Gate - Enhanced Edition" --scope city --item-effects --output-dir build/city-source-audit
```

The opt-in decoder bounds each item to 16 abilities, 64 unique effects and 128
effect references, and validates those limits before legacy table expansion.
It records raw fields, order, offsets and hashes. Effect execution, native stat
conversion and original-edition behavior remain separate work; resource fields
can also name variables and are never followed by this decoder. In particular,
POTN47's EE variable effect establishes a possible producer, while its relation
to other cure paths and the classic guide's retrieval behavior remains unresolved.

Focused development checks are separate from native acceptance:

```powershell
python -B -m unittest tests.test_candlekeep_source tests.test_binding_source_layout tests.test_baldurs_gate_city_content tests.test_baldurs_gate_city_geometry tests.test_baldurs_gate_city_regions tests.test_baldurs_gate_city_routes tests.test_baldurs_gate_city_ledger tests.test_quest_journal tests.test_ui_dialogue -q
python test.py --suite mcp-branches --branch-group baldursGate
```

The first command uses source checks and native-shaped model doubles. The second requires a current staged native binary and real movement/dialogue/combat. Planned routes cover all five existing hero classes, but an unexecuted route is not a passing receipt. Shop chooser cancellation never proves an item was sold, stolen or transferred.

Current acceptance blockers include original BG1-versus-EE reconciliation, unsupported source scripts and item effects, crime/arrest/escape outcomes, remaining conversation and recruitment branches, exact shop/temple formulas, and complete native save/reload and visual evidence. The owner confirmed that neither an original installation nor an alternate build volume is available. Recheck capacity before large local builds or captures; historical cleanup evidence does not replace a current capacity check. The 90 percent guard remains in force.

City structured metadata uses a `city-json:` text prefix to preserve its string type through native loading,
cloning and saves. The runtime accepts protected and legacy plain JSON text and protects subsequent state writes.
The encoding changes only structured text, leaving native references and typed properties intact. An older save
whose metadata was already coerced into native object collections cannot be reconstructed or safely reseeded by
this repair. Focused source/model checks and deferred native loading/save probes remain separate evidence classes.

## Bounded palace source audits

The palace audit fixtures are factual development metadata from installed BG1EE
resources, supporting an original-BG1 target. They contain fingerprints, selected
operation/selector facts and actor script-slot bindings, without original binary
payloads, compiled script bodies or dialogue prose. The initial manifest of 43
resources and supplemental manifest of 22 remain unchanged as historical evidence.
The initial 43-resource snapshot predates `decoderResourceFingerprints`; new standalone
reports use that separate field to fingerprint ACTION.IDS and TRIGGER.IDS without
changing the historical inventory. A fresh installed-source report reproduces the
initial snapshot bytes after removing only that field, and its decoder sizes and
SHA-256 values match the expanded closure's ACTION.IDS and TRIGGER.IDS entries.
Every compiled script must decode without warnings before the report derives negative
inventories such as trigger absence. The expanded listener closure fingerprints
79 resources, 21 CRE, 22 actor BCS plus the area script and four
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


### Item movement and per-instance restrictions

Known source ITM flags and CRE/STO instance flags remain separate. `plugin_cityItemFlags` preserves the known
item-header bits; the existing `plugin_citySourceFlags` on materialized possessions continues to record instance
bits. An item without the ITM movable/droppable bit (`0x4`) is immovable. The generated item template records that
restriction, and source materialization combines it with instance undroppable (`0x8`) into
`plugin_cityUndroppable`. Instance unstealable (`0x2`), stolen (`0x4`), identified (`0x1`), quantities and charges keep
their existing meanings. Missing header evidence retains the existing fallback policy.

This projection is local to city source items. Existing native city fixed-loot settlement already skips an actual
undroppable possession before removing or granting it; the city's theft, companion-transfer and selling paths also
check that value. The item stays with its actual owner. No weapon is deleted, no stock is reduced, and no natural-
weapon blacklist or global loot policy is introduced. Known immovable templates are also ineligible for sale.
Classic BG1's separate unsellable bit (`0x800`) remains respected; its critical bit (`0x1`) alone does not prevent sale.

For example, retained CARRIO1 has header flags 32, which lack movement permission, and CARRIO's instance flags 0 add no
extra restriction. Its actual Attack item must remain owned instead of becoming loot or a theft/sale choice. The
retained crawler's authored 420 XP stays unchanged. This uses supporting EE base facts and format documentation;
original patched BG1 parity remains open.

The primary definitions are [ITM flags](https://gibberlings3.github.io/iesdp/file_formats/ie_formats/itm_v1.htm#Header_Flags)
and [CRE item flags](https://gibberlings3.github.io/iesdp/file_formats/ie_formats/cre_v1.htm#CREV1_0_Item). The pinned
[GemRB inventory implementation](https://github.com/gemrb/gemrb/blob/e76cad7a6190b65292b223a92cf219e0c7a39047/gemrb/core/Inventory.cpp#L137)
corroborates deriving undroppable from missing movement permission. Reimplementation code is supporting evidence.

Already-initialized saved items require a separately reviewed migration; no retrospective deletion or source-stock
reseed is authorized here. Source callback tests and JSON property round trips are distinct from native defeat,
native save/reload and real MCP evidence, which remain required before gameplay acceptance.


### Poison journal clues

The opt-in poison source path presents readable objectives and hints for the active poison/geas tasks and completed
Diviner reading. These getters use existing quest stages and heard-clue flags; they do not progress a quest, pay a fee,
change a timer or grant a reward. Default-off legacy text, the completed cure's genuine branch journal and both geas
outcome descriptions remain unchanged.

Before Lothander's offer is accepted, the hint directs the player back to him. Agreeing to help introduces the Diviner
in the market square. The correct Diviner answer names Jalantha Mistmyr at the Water Queen's House; its automatic
continuation records `DivinerAsked=1`. Only Lothander's later directions (`DivinerAsked=2`) introduce the Blade and
Stars Inn. His completed scroll-return or priest-death outcome supplies the later Marek lead. No temple or inn clue is
shown before the corresponding information has been heard.

The completed reading records its actual 50-gold fee and no experience. Wrong-question alternatives retain their
source differences: the treasure answer sets `LothanderMove=9`, while the profit answer does not. Neither invents the
correct geas answer or completes the Diviner task. Their existing effects and one-reading-per-day rule are untouched.

Tests execute those dialogue paths through the source model, compare repeated reads against all active/completed quest
collections and serialized state, and keep the disabled/dead-player legacy path available. They supply no native GUI,
MCP, save/reload or fresh visual acceptance; updated staged views must be captured and inspected separately.


## Partial BOOK08 native use conversion

The disabled `plugin_cityBook08NativeConversionEnabled` component also requires poison source mode. It maps source Wisdom+1 to permanent owned `baseStats.intelligence`+1, using current composed stats only to verify the result. It accepts one identified carried actual BOOK08 with a valid raw charge triple `[0,0,0]` or explicit `[1,0,0]`. For the retained zero triple, a documented map-local ordinary-load conversion derives one effective use; the unchanged stored triple and policy are retained in the same-instance receipt. This follows pinned GemRB ordinary-load charge sanitization and the documented single-use tome, without claiming patched original BG1 loader equivalence. It never recharges a spent item, awards on acquisition, or rewrites source fixtures. The callback reserves the use, adds the owned base bonus, removes the exact item and completes a saved receipt. Disabled/unidentified/malformed/shared items grant nothing; consumed items or existing receipts cannot grant twice. Interrupted pending receipts remain quarantined. Giving the unused tome to Jalantha retains its actual ownership and grants no statistic; using it first removes her required book condition.

Fresh configured BOOK08 objects use the existing scroll Python wrapper through the map-local `BaldursGateUnderstandingTome(CScrollBase)` class. Its inherited engine disposal policy is false; its own successful callback removes the exact item. The default scroll text action is never called. Existing saved plain `CItem` instances require a reviewed migration; they are not silently replaced. The source ability-pending marker stays true: blue lighting, EFF_M08 audio and unread notice11338 are not implemented, and original Wisdom/cap/usability behavior remains an original-versus-EE acceptance question. The authored use notice describes the native Intelligence outcome. Source checks are not native use/save, MCP, exhaustive-parity or owner acceptance.

Focused native component checks transfer Chanthalas's original zero-charge book by identity, call the actual player's
`useItem`, and verify unchanged resources, owned base Intelligence 5 to 6 and composed Intelligence 15 to 16 with the
existing Wanderer race and a real equipment bonus. Independent disabled/identified and enabled/unidentified refusals
retain the item. Spent state and an unspent registered subclass survive actual save/reload; the saved receipt prevents
a repeat award. These use fresh private resource copies with both opt-ins enabled before map creation. Their explicit
inventory transfer, identification and equipment setup are unit fixtures, not played acquisition or MCP/UI acceptance.
## Seven Suns warning conversation

The warning merchant `AR0601#actor2` (`cityAr0601Actor2`, source dialogue `DOPPSM`)
uses a finite native dialogue session for the twelve edges reachable from the normal
entry state. The factual fixture `tests/fixtures/baldurs_gate_seven_suns_warning.json`
retains all nine states and seventeen edges. External entries and their eight
unreachable state/edge obligations remain planned. Installed EE records support
these facts; they do not establish original-BG1 parity.

The first accepted choice applies its ordered source-global writes immediately.
`plugin_citySourceGlobals` stores shared source globals as protected JSON text;
names are ASCII case-insensitive within the literal `GLOBAL` scope. Existing spelling,
unrelated variables and unknown scopes are retained. Cancellation before any choice
has no story effect. Cancellation after a choice retains the committed globals and
talk bookkeeping. Reopening starts at the normal entry, with the saved globals.

The terminal choices quietly retire the same living merchant with his actual items
and effects. They grant no death, combat, experience, gold or loot credit. The
separate `citySevenSunsWarningLead` journal entry remains open and grants no reward;
it does not accept or complete Scar's quests. Raw journal flags `92` include the
general journal bit. BG2-only quest-status bits are not used to infer a classic BG1
unsolved status. The dialogue prose and lead are reworded for this engine.

Each committed edge holds a bounded unsafe-operation lease. The session captures
the game context, public map epoch, assigned player and exact registered source
actor, and checks them across callbacks. The Python surface adds only the read-only
`CGuiHandler.supportsSevenSunsWarning()` capability. Finite UI intents own the actual
mutations. Uncertain partial work keeps a pending receipt and quarantines saves;
the implementation does not claim arbitrary callback rollback.

The optional serialized `CMap.sceneRetiredObjects` field retains retired objects.
It is omitted when empty, and the save-format version is unchanged. A private
lifetime anchor lets map destruction release retired actor/effect cycles without
clearing effects during exploration or harming an actor adopted by another live map.
The clock also retains the exact warning actor reference for replay checks.

The ledger adds twenty-nine explicit obligations without removing older entries.
Eleven authored MCP cases cover the reachable paths, cancellation, shared globals,
the journal, identity preservation, refusal and save/reload across all five existing
hero classes. Authored routes, the twenty-four native test cases and the fixed-work
performance guard require actual execution before they count as evidence.

Focused source and model checks:

```powershell
python -B -m unittest tests.test_baldurs_gate_seven_suns_warning tests.test_baldurs_gate_seven_suns_routes tests.test_baldurs_gate_city_ledger tests.test_native_test_profile -q
python -B scripts/build_baldurs_gate_city.py --check
python -B scripts/build_baldurs_gate_city_ledger.py --check
```

Original-source reconciliation, external DOPPSM entries, original automatic-dialogue
timing, source/native acceptance of the separate DOPMER transformations and stock, Scar reward
differences and Jhasso's departure remain open. This warning flow does not satisfy
those obligations or the complete city acceptance matrix.

## Seven Suns disguised merchants and replacement stock

The four `DOPMER` actors retain distinct dialogue counters and source identities:
`AR0601#actor1`, `AR0601#actor3`, `AR0602#actor1`, and `AR0602#actor2`.
The factual graph retains all fourteen states, twenty-four edges, and thirteen
terminal paths. The native UI flow offers the audited first, second, and third
entries. Beginning a conversation commits its separate initiation counter, including
when the player subsequently cancels. Later initiations have no audited entry and
refuse cleanly. This counter timing is a documented conversion; original cancellation
timing remains unproven. Saves with prior generic talk counts and no dedicated counter
require a migration decision rather than silently resetting the conversation.

Reveal choices apply their ordered shared `GLOBAL` writes and close the dialogue.
On the next city-coordinator turn, the finite native service checks eligible merchants
in the active source area. It quietly retires each exact disguise and publishes a
new hostile native `CCreature` at the same location. Actors on other floors wait until
their source area is active. Combat ownership or closed save admission postpones
replacement before mutation. The registered name stays stable for the existing city
death hooks, while retained old and new references distinguish the two creatures.
The old disguise earns no death, gold, experience, loot, or quest-completion credit.

The replacement uses audited base `DOPPSS` facts: 28 HP, a real equipped `S1-12`
weapon with 1–12 native damage, and 420 experience through the actual owned defeat
path. Its native body uses strength/agility/intelligence 6, stamina 4, hit 75, damage
0, and critical chance 0. Weapon enchantment 1 is source metadata only. The weapon
is undroppable and unstealable. The winner receives the fixed experience award once;
other actors keep the existing scaled-experience rule. Source combat rules and party
experience sharing are not established by this conversion.

One fixed `RNDTRE05` selection resolves through six audited table rows to no item,
gold, or one of ninety-seven concrete item codes. The bounded compiler snapshots
validated source metadata once. Stacks use their audited capacity and quantity;
nonstackable `*10` entries remain one item. Initial charges use the first three base
ability maxima as an explicit native conversion. Each selected row consumes one
native d20; authentic original table weights and creation-time charge semantics
remain unresolved. A missing table column means no possession in this conversion;
original missing-cell behavior remains unproven. Every selected item is a real owned
object, never an unresolved random-family placeholder. Materialization uses base records, keeping the seventeen
effective item differences introduced by installed mods outside the native stock.

A closed, bounded certificate records the selected rows, exact outcome, initial
owned descriptors, source fingerprints, and native conversion. The decoder replays
the finite table closure and checks integer, boolean, string, object, and array types
without narrowing. Initial publication additionally verifies the exact controllers,
configured Attack action, equipped weapon, stock, and source metadata across
callbacks. Later receipt checks permit legitimate damage, death, purchases, theft,
and item transfers without regenerating the initial stock. Failed construction keeps
its staged actor under a private map lifetime anchor before callback exposure.

The ledger adds fifty-one obligations without dropping the previous 7,500 entries.
Seventeen authored MCP cases span the thirteen paths and the five existing hero
classes, with cancellation, area scheduling, repeated settlement, identity checks,
and save/reload. These are route plans until executed against the exact staged binary.
Native unit cases and deterministic bounded-work guards likewise require execution.

The hostile-action script entry still needs an actual attack-attempt witness;
damage alone cannot represent misses or offensive spells. The separate basement
`DOPPSS` body and stock, Jhasso's departure and Scar's reward conditions
remain distinct pending work. Potion, scroll, wand and ammunition abilities are
explicitly unimplemented in this stock increment. Existing Scar quest completion
and reward rules are unchanged. Installed EE evidence, source/model tests, native
execution, visual inspection and owner acceptance remain separate claims.

## Seven Suns five-death witness

The city coordinator records one death for each of the four merchant lineages above
and the basement `AR0603#actor2`. Both audited source creature records use the
`SSDopple` death variable. The serialized witness retains the source actor, area,
creature and original/replacement role; the clock retains the exact original and
corpse references. A counted actor must be dead and absent from the live registry.
Replacement credit additionally requires its committed replacement receipt and the
same retained old/new owners. Quiet retirement, a same-name clone, unrelated deaths,
forged counter rows and repeated destruction callbacks cannot grant credit.

The witness joins the existing engine-owned destruction callback after generic
corpse/death bookkeeping. Invalid witness data fails closed without preventing that
bookkeeping. Old saves with generic deaths but no witness retain an unknown count;
the implementation does not infer source credit from missing actors. The read-only
`BaldursGateClock.sevenSunsDeathCount()` query validates the retained owners and
serialized rows before returning a count. It does not change Scar's quest guards,
grant rewards or establish original-game parity.

One additional ledger row maps these five source identities. The authored Warrior
MCP route requires a fresh native victory against every counted actor, checkpoints
0, 2, 4 and 5, save/reload at 2 and 5, and unchanged resources on repeated queries
and later ordinary turns. The route is pending until executed against the exact
staged binary. Pre-transformation lethal attacks, attack-attempt timing, the basement
body/stock/reward conversion and the original Scar outcome conditions remain open.
