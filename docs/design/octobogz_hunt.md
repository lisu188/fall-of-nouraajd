# OctoBogz hunt lifecycle and balance contract

The eastern Nouraajd lair has three registered threats: scout, shadow brood, and
Alpha. These are the existing OctoBogz template at its authored level one, with
stable actor and quest identifiers. No additional mandatory actor, roster entry,
base stat increase, or player class is introduced. The source lair had a
three-OctoBogz encounter footprint; staging preserves that count.

## Objective and recovery

Entering the authored lair with the canonical living player starts the scout.
Confirmed scout death enables the remaining two slots. Completion requires the
actual deaths of all three registered actors, in any order after they exist;
removing the cave prop or one commander does not complete the hunt. Optional
legacy flood creatures outside the three adopted slots do not gate completion.
The journal reports distinct deaths out of three, including before quest
acceptance. Existing quest completion and reward flags award the original gold
and ShadowBlade once, including late acceptance and repeated interactions.

The version-one map registry stores slot names, pending/living/dead status, and a
bounded recovery snapshot of HP, mana, level, experience, phase, and once flags.
Migration adopts up to three nearby living legacy actors, preserving identity
and resources. With one or two adopted actors, a living brood is reused after
scout death; it is never duplicated. Extra actors remain optional. Existing
completed quest flags are grandfathered into a cleared registry.

A normally saved living actor is reused with its native HP, mana, equipment, and
effects. Removing a living registered actor records a small recovery snapshot
and makes that slot pending, without marking it dead. A missing unconfirmed
living slot also becomes pending. A bounded search of at most 25 authored nearby
cells restores one actor under the same name and phase; blocked placement keeps
the slot pending and warns once. This recovery snapshot intentionally does not
introduce a second full creature serializer for absent transient effects.

## Revised exclusive combat phases

The ordinary AI chooses potions, useful spells, and Attack using the existing
ranking and random streams. A phase may decorate only an already selected
configured Attack. The shadow brood warns on its first selected Attack; the Alpha
warns at or below half health. Warning still executes the full ordinary Attack.
The next eligible affordable attack costs five mana once. It converts one point of
that same damage roll from normal to shadow only when the target's composed normal
and shadow wards differ before the attack. Equal wards preserve the whole ordinary
Attack mitigation, block and weapon path. The pulse applies shadow resistance -1
for one turn. This post-hit debuff helps only a later shadow attack while it
remains active; it is not a guaranteed benefit in a solo fight. With insufficient mana it executes ordinary Attack and ends the
phase. Ordinary item and spell turns retain priority and preserve a pending
phase. Hunt actors never also use their composed brute-class signature.

The default-inert Attack hook accepts only explicit frost or shadow channels,
uses exactly one existing damage roll, preserves its zero-damage guard and
configured weapon proc, and disarms before that proc. A finally block clears the
hook after rejected execution. A rejected or repeated pulse refunds its committed
mana through the existing bounded refund API. A miss remains an attempted paid
attack and applies no damage packet. Owned damage packets are decoded before
combat. Effects transfer out of the signature slot before linking to caster and
victim; the active creature effect set retains normal expiry and save behavior.
Phase and once flags persist; saving never retains an armed damage hook.

## Required evidence

The real-bound native fixture compares the original three actors against the
staged scout/Alpha/brood route with five ordinary level-three player templates,
source-authored level-one enemies, and paired seeds 100 through 110. Both random
streams reset once after route setup. Player HP, mana, items, experience, and loot
carry naturally between the three combats. Every original winning seed must
still win. Absolute median HP, mana, and inventory expenditures must stay within
10 percent, including zero baselines. All five classes must retain meaningful
incoming baseline damage. Assasin and Inquisitor must retain positive no-rest
victory witnesses, as both recorded platforms demonstrate. Warrior, Sorcerer and
Wayfarer remain in every numeric and per-seed victory comparison; their original
fixed no-rest setup does not establish universal victories. Real Alpha and brood
pulse/effect use must occur.
No stat, loadout, seed-count, threshold, or timer change is used to satisfy gates.

The same native executable tests ordinary Attack callbacks, a real Staff weapon
proc, both random streams, actual one-turn effect stats/endpoints/expiry, consumed
ownership slots, and exactly five mana for a used pulse. Controller and performance
fixtures preserve ordinary spell/item priority and bound 200 outer selections to
one charge, one pulse, and 198 ordinary Attack selections. Focused Python tests
exercise migration, partial saves, live removal, pending placement, late rewards,
misses, cancellation, and default hook behavior. The separate stdio MCP walkthrough
uses actual player movement and combat for Warrior and Sorcerer, with ordinary
progression, authored preparation/recovery and a partial save. These authored
victories are required independently of the deliberately fixed no-rest comparator.

The CI commands are:

```sh
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
python3 test.py --suite gameplay
```

Full-suite and canonical coverage remain required before acceptance. The local
source-only worktree has no native binary and C: remains above the 90 percent disk
guard, so native/MCP/GUI local execution is blocked; authored tests are not passing
runtime evidence.

The hunt uses published `getEffectiveInteractions` and generic label/mana-cost
property getters. Narrow native effect endpoint and `addEffect` bindings preserve
the normal active-effect lifecycle. A plugin method audit fails against prior
head `abbd1f7e`, while the actual embedded fixture checks these methods before
combat. That head's
[Linux job 110337723989](https://github.com/lisu188/fall-of-nouraajd/actions/runs/36852377715/job/110337723989)
failed Attack/proc, RNG and effect-application proofs, including zero observed
Alpha/brood pulse applications. Its route medians do not validate the revised
mechanics; fresh actual-bound evidence remains required after the API correction.

Head `cf14afaf` exposed another plugin contract mismatch: the native builtin
allowlist excludes `next`, so Attack lookup still stopped before combat callbacks.
Both helpers now use simple loops without expanding the sandbox. Focused plugin
tests run under that actual allowlist and reproduce the prior `NameError` before
passing with the correction. Zero-application medians from that failed run remain
invalid evidence for the revised phases.

## Retained failed harder challenge

Before the attack-preserving revision, head `ab269855` tested matched level-two
enemies on both routes. That harder challenge is supplementary diagnostic
evidence, rather than the source-authored level-one delivery comparator. It used
an empty warning turn followed by a delayed two-turn pulse; those opportunity
costs changed wins and expenditures substantially.

[Linux job 110305081296](https://github.com/lisu188/fall-of-nouraajd/actions/runs/36842288466/job/110305081296)
completed the route comparison in 6.93 seconds with 21 failures. The corresponding
[Windows job 110306037068](https://github.com/lisu188/fall-of-nouraajd/actions/runs/36842288466/job/110306037068)
completed it in 9.80 seconds with 23 failures. Each platform resets its own ordinary
C and native random streams; paired results are strict within that platform.

| Platform | Class | HP before/after | Mana before/after | Items before/after | Baseline wins | Alpha/brood pulses |
| --- | --- | --- | --- | --- | --- | --- |
| Linux | Warrior | 116 / 98 | 51 / 34 | 2 / 1 | 1/11 | 1 / 2 |
| Linux | Sorcerer | 83 / 83 | 105 / 105 | 0 / 0 | 0/11 | 0 / 0 |
| Linux | Assasin | 83 / 108 | 160 / 160 | 2 / 3 | 5/11 | 3 / 7 |
| Linux | Inquisitor | 135 / 149 | 186 / 124 | 3 / 3 | 9/11 | 3 / 6 |
| Linux | Wayfarer | 80 / 79 | 140 / 120 | 1 / 1 | 0/11 | 1 / 0 |
| Windows | Warrior | 152 / 117 | 68 / 34 | 3 / 1 | 4/11 | 1 / 0 |
| Windows | Sorcerer | 83 / 83 | 120 / 120 | 0 / 0 | 0/11 | 0 / 0 |
| Windows | Assasin | 105 / 100 | 160 / 160 | 4 / 3 | 8/11 | 3 / 8 |
| Windows | Inquisitor | 116 / 140 | 186 / 124 | 3 / 3 | 8/11 | 2 / 6 |
| Windows | Wayfarer | 108 / 92 | 160 / 120 | 1 / 1 | 0/11 | 1 / 0 |

The old coverage job timed out at the unchanged 60-second native limits for both
balance entries and handler tests. It never reached a passing coverage gate.
The revised source-level route, current full matrix, runtime saves, MCP
walkthrough, performance checks, and coverage still require completed CI evidence.


## First valid source-level route measurements

Head `85ca07a0`, run `36856329653`, reached the actual bound native comparator.
The role matrix passed in16.12 seconds on Linux; the source-level hunt route
completed in4.43 seconds. Linux median HP/mana/items were identical in both
modes for all five classes, and every baseline-winning seed remained winning.
Real Alpha/brood pulse effects were observed. The route still failed the existing
baseline-winning witness for Warrior, Sorcerer and Wayfarer (zero of11).
Those assertions are retained while authored preparation is examined.

Windows job `110350757593` completed the route in6.63 seconds and exposed a
separate real budget failure: Assasin mana median120 to140 (16.7 percent).
Warrior HP136 to137, mana34 to34, items2 to2 and one baseline win;
Sorcerer HP84 to84, mana90 to90, items0 to0 and zero wins;
Assasin HP81 to84, items3 to3 and nine baseline wins;
Inquisitor HP162 to162, mana144 to144, items4 to4 and four wins;
Wayfarer HP81 to81, mana100 to100, items1 to1 and zero wins.
Every baseline-winning seed was preserved. Sorcerer/Wayfarer failed their
witnesses in addition to the Assasin mana budget. The same Windows run also
reported a separate controller-unit-test segmentation fault. These are failing
acceptance results, not a reason to relax any comparison.

The comparator intentionally starts level-three templates with authored equipment,
empty inventories and experience zero on a tiny open map. It sequentially fights
three level-one actors, with no exploration, services or rest. Native route
traces record initial HP/mana, equipment/inventory/experience and each encounter's
outcome, survivors, phase use and observed costs without changing random streams,
loadouts or route state. Actual authored journey preparation is a separate MCP
acceptance requirement and cannot replace this fixed no-rest balance comparator.


## Authored map turns and ordinary retreat

Hunt actors retain the original cave-anchored `CRangeController` with target
`cave2` and distance10. Replacing it with player pursuit/leash256 introduced
pressure outside the three-slot objective and is reverted. The slot count,
placements, death gates, phase values and fixed no-rest combat comparator are
unchanged. Native save/recovery tests assert the anchor and range.

The required stdio MCP route now obtains each authored cardinal destination from
source terrain, checks the native tile's walkability flag, and calls the existing
integer-coordinate `CMapObject.moveTo` for exactly one cell. The registered
player's adjacent native movement checks `CMap.canStep` before committing,
including object footprints and normal movement hooks. The route then calls
`CMap.move`, pumps its event loop, and verifies one
actual map turn and at most one cell of movement. It replans after combat rollback,
blocked objects or wandering target movement. It records real level, experience,
HP/mana, inventory and turns before encounters and after a partial reload.
Source/mocked contracts verify movement and export APIs; they do not substitute
for actual binary/MCP evidence.

The route earns its existing class discovery750XP through the visited NPC.
This is natural progression and is not assumed to match the fixed level-three
balance comparator. After scout death it saves/reloads remaining living slots.
It then physically retreats to the existing road at(118,21),48 Wasteland cells
west of the lair, and takes bounded adjacent steps on verified RoadTiles at
(118,20)/(118,21). Ordinary road steps heal1HP and actual map turns regenerate
mana. It can encounter living actors during retreat and must remain alive;
there is no direct heal, stat/level setter, fabricated supply or reward call.
The same authored recovery can be used before the final encounter. Genuine
incidental deaths still count once and preserve any-order objectives.

Source contract classes are exposed through `test.py` so their cheap API,
movement, registry and sandbox regressions run in fast/full/coverage-safe suites.
Native runtime/MCP cases retain gameplay/full/coverage-safe discovery. A new
export check rejects the previous unexported `CMapLoader.save` call; the route
uses the published `saveWithResult` and requires successful persistence.

The earlier controller-queued fixture incorrectly called the unbound
`CTile.getCoords`. The replacement uses the already proven adjacent movement
and map-turn APIs. Its method-ownership check rejects that tile call and excluded
Coords constructors; its movement mock commits on `moveTo`, with a real map-turn
advance and rollback/replanning afterward. No production binding was added.

The user approved this distinction after the fixed original route proved
all-losing for three Linux classes. Only that universal no-rest victory witness
was corrected; all five classes,11 paired seeds,positive-HP witnesses,absolute
10-percent resource gates and every original winning seed remain unchanged.
The prior Windows Assasin mana120 to140 failure is still a strict mechanic
failure requiring resolution, not covered by the witness correction. The
disabled hunt callback fixture also explicitly retains all five baseline mana
points, alongside the used-pulse assertion that exactly five are spent.

Head4024453d's Windows seed106 trace is retained: the staged Alpha left the
Assasin at50HP versus51 for the original actor. Subsequent ordinary loot,
potion and spell decisions diverged; the staged route spent140mana instead
of120. The strict median gate rejected this even though that seed changed from
a loss to a win. The following generic phase trial delayed both warnings until quarter
health, keeping actors, stats, loadouts, seeds, route carryover and every numeric
and winning-seed gate unchanged. Real-bound warning contracts compare actual
damage, configured Attack/Staff callbacks, random streams, no mana expenditure
and exclusive phase state. Existing pulse-use and five-mana gates remain.

That quarter-health head `ea9c8309` also failed actual Windows run36870026760:
Assasin mana median remained120 to140. Linux kept every resource median but never
executed a brood pulse, so its explicit phase-use witness failed. These are retained
failed results, not balanced acceptance.

The current trial restores the initial brood and half-health Alpha warning timing,
and conditions the shadow conversion on unequal pre-attack wards. No class, seed,
level, loadout, actor count or numeric/winning-seed gate changed. Actual embedded
contracts compare equal wards with armor/block and full configured weapon procs,
while a controlled95/0 fight must cause2 damage versus1 and show the effect for one
victim turn in both initiative orders. The authored MCP route retains actor handles
before movement and records their actual pulse, phase, raw packet and mana after
combat or road retreat. At least one positive shadow packet across the real melee
and caster routes is required; a phase flag alone cannot satisfy this witness.
Fresh native, full-suite, coverage and authored-route outcomes remain pending.

Head9708a446 passed the fixed110-fight hunt comparison and closed phase/packet
contracts on Linux and Windows (Windows hunt entry5.66seconds). This does not
establish authored-route playability: Linux gameplay exposed a bare-JSON registry
string interpreted as an object by save loading, an unexported legacy fixture
director call, a closed Sorcerer town gate, and a Warrior return from the cave
to the map entry before the hunt completed. Windows still rejected its inherited
role matrix at Warrior/Cultist HP4 to3. Full-suite/coverage/MCP acceptance failed.

The registry now uses the opaque `octobogzHunt.v1:` string envelope, retaining
raw JSON reads for in-memory legacy compatibility without changing the native
save schema. A real runtime regression asserts the exact registry string in the
versioned save snapshot and reloads partial actors, HP/mana, owned effects and
phases. The legacy quest-boundary MCP fixture enters the real lair instead of
calling an unpublished director method. The dedicated combat route opens the
authored Sorcerer gate and rejects both a changed defeat receipt and any
unexplained multi-cell arrival; being alive after native respawn is insufficient.
Source regressions cover both failures. Real ordinary preparation and recovery
must still produce completed melee/caster hunts before this work is accepted.

The authored route opens the town gate, earns only its class-specific
discovery, recovers through actual road steps, then follows Rolf's original cave.
Nearby living authored Pritschers are discovered from map
handles and defeated through adjacent movement, with observed XP increases and
removal; no enemy count or resulting level is fabricated. At most32 preparation
targets are considered, with road recovery when injured. The route requires
actual level3 progression before entering the hunt and real MainQuest completion afterward,
retaining ordinary template equipment, earned loot and natural mana/HP recovery.
Every road pair is verified against source and actual native tiles. Recovery
requires actual HP and mana maxima, and defeat/teleport receipts remain gated.
This is a pending authored playability witness, separate from the unchanged
fixed no-rest comparator. The older relic boundary fixture now prepares the
authoritative Beren quest state alongside its derived legacy flag; it does not
claim natural relic progression or real combat.

Head84e5a743 passed both strict native comparisons and all native performance
guards on Linux and Windows. Linux job110461267304 completed the770-fight role
entry in2.12seconds and the110-fight hunt entry in1.53seconds; Windows
job110462066418 completed them in3.85 and2.44seconds. Instrumented coverage
also passed the native entries within their unchanged budgets. Its Python phase
failed, so no canonical coverage percentage or authored-route acceptance was
established.

The new walkthrough incorrectly blacklisted a destination after two combat
rollbacks. Native player victories deliberately return to the pre-step origin,
so several real Pritschers in one cave cell can cause several successful
nonarrivals. The helper now retains those cells and masks only false native
terrain or object passability. For an object it passes that object's existing
Coords handle to the bound `CMap.canStep`; it creates no Coords or new binding.
Three consecutive victory rollbacks and a removed blocker have focused
regressions. The512-step limit, cardinal movement, actual map turns and defeat
receipt checks remain unchanged.

The same run exposed two old quest-boundary MCP calls outside the export
allowlist, an omitted runtime player trigger target, and an optional actor packet
read before any packet existed. Those fixtures now use the existing generic HP
property and removal-by-name APIs, recognize the attached player, and inspect
actual serialized property presence before reading an owned packet. All five
new focused regressions fail against the preceding fixtures and pass after the
repairs. Dedicated combat movement still contains no HP/stat/item mutations.

The native partial-save fixture had directly changed health, mana and phase
without synchronizing the registry recovery snapshot before its exact-state
assertion. It now synchronizes before saving, as ordinary player turns do, while
retaining exact saved registry bytes and all loaded HP/mana, identity, phase,
effect and one-time reward assertions. Linux's ordinary Warrior did reach
level3 with3125XP at Rolf's cave and later defeat the scout alive, but its
observer failed afterward; this is partial real preparation/combat evidence,
not completion of either required authored route. Fresh full-suite, MCP and
canonical coverage acceptance remain required.

Head `dd36ccc7` passed Linux's unchanged770-fight role entry in2.10seconds and
110-fight hunt entry in1.53seconds, plus all native performance guards. Its
real-bound partial actor save/recovery test passed in4.325seconds, and legacy
adoption/addAction passed in0.451seconds. Both actual MCP classes completed
ordinary Rolf preparation and MainQuest without a defeat: Warrior reached
level3 with3625XP and98HP/126mana, and Sorcerer reached level3 with3875XP and
84HP/154mana. Both recovered naturally to those full resources before the hunt.
This establishes real preparation, not completed hunt acceptance.
Windows job110486406774 failed during CMake configuration because Python3
Development, Development.Module and Development.Embed were unavailable despite
finding interpreter3.12.10. It supplied no new native or MCP combat evidence.

The same Linux job110475369559 failed both walkthroughs because their late
observation expected a living scout after the entire lair-entry step. The
player's arrival spawns the scout, then the following ordinary map turn can
bring that scout into real combat and advance the registry to brood. The test
now captures actual living handles before movement and after arrival, before
that map turn. Capture is enabled only for the hunt and bounded to its lair
region. A confirmed defeat requires the retained actor to be dead, its named
map object to be absent, and its own registry slot to be dead. All three distinct
slots must satisfy that proof; flags alone cannot substitute for a fight.

After partial reload, living handles are rebound to the actual restored actors.
The pre-save living actor cannot stand in for a loaded actor's death. On the
first confirmed death, the observer also reads the retained actor's actual
phase, mana and packet, covering combat during road retreat before an explicit
defeat call. Spawn-then-first-turn death, direct movement death, reload identity
and already-dead pulse observation have focused regressions. Cardinal movement,
map turns, defeat receipts, incomplete partial objectives, once-only rewards
and positive shadow-packet budget assertions remain required. Fresh completed
melee/caster routes, full-suite and canonical coverage evidence are still pending.

Head `67d66b3e` Linux job110492763102 passed every native/performance entry,
including the unchanged770-fight matrix in1.86seconds and110-fight hunt in
1.33seconds. Real partial actor save/recovery passed in3.943seconds and legacy
adoption in0.350seconds. The prepared Warrior killed the scout, preserved exact
partial registry state through reload, and had16HP/108mana with4125XP afterward.
Its next retreat map turn caused a genuine defeat receipt and respawn. Sorcerer
lost during the scout encounter. Both losses remain rejected; the empty positive
packet list was an early-abort consequence, not phase acceptance. Windows
job110494259284 again failed Python development discovery before native tests.

The actual70HP/105mana scout is the ordinary initialized level-one template:
base stamina7/strength10 plus one levelStats increment stamina3/strength5.
The earlier49HP/70mana expectation described its uninitialized level-zero base.
No hunt actor stat inflation was found and no combat mechanic was changed for
these authored failures.

Sorcerer's Rolf departure carried two stronger40-percent healing draughts and
two smaller ones. The following Gooby detour spent those supplies before the
scout. The test now explicitly visits Gooby after the hunt while retaining its
actual final completion and quest-journal checks; naturally encountered Gooby
combat remains active throughout. Rolf's road recovery now precedes the hunt,
and actual carried healing types/powers are printed at the lair. No loot, level,
equipment, HP, mana, actor or fixed-comparator state is substituted.

The player also collects the already-authored Town Portal Scroll at108,110.
After the exact partial reload, using that owned item is the ordinary retreat
to source entry110,111. The test requires the same player/map, unchanged defeat
receipt and hunt state, exact entry coordinates and consumption of one owned
scroll before actual town-road recovery. Missing ownership, unconsumed items,
defeat, incorrect arrival or changed identity/objectives reject the transit.
This avoids the dangerous first retreat step without skipping an encounter or
counting respawn as survival. Its runtime outcome and both completed hunts
remain pending; strict native comparisons, actual distinct deaths, positive
packet budget, partial objectives and one-time rewards remain unchanged.

## Retained prepared-route results and measured follow-up

Head `6bfd3a63` passed the native comparisons and performance guards on Linux
and Windows. Windows job110511955655 completed the role matrix in2.69seconds
and the fixed hunt entry in1.74seconds; partial actor save/recovery passed in
7.156seconds and legacy adoption in0.531seconds. Both actual classes defeated
the scout, preserved exact partial objectives and used the owned source scroll
without a defeat receipt. The authored outcomes still diverged:

| Platform | Warrior | Sorcerer |
|---|---|---|
| Windows | All three actual deaths, reward once and MainQuest completed;4375XP,98HP/126mana,1200gold at the final snapshot | Lost to Alpha after the successful partial reload and portal;4000XP and a native defeat receipt |
| Linux | Lost to brood at4250XP despite full98HP/126mana before that encounter | Lost to Alpha at4000XP after partial reload and portal |

The Windows Warrior observed real Alpha damage17→16normal+1shadow and brood
damage38→37normal+1shadow. Each pulse spent5mana once. Its completed route is
partial platform evidence; the caster loss means the whole walkthrough failed.
Linux also reported a separate existing narrative ritual-route failure, which
is investigated independently rather than hidden by the hunt test.

Coverage job110511222761 passed all25native entries, including the unchanged
role matrix in11.07seconds and hunt entry in6.94seconds. The partial-save child
again timed out at30.044seconds; adoption passed in6.475seconds. The coverage
Warrior survived all three encounters and obtained the1000gold/ShadowBlade,
but the Python phase reached its existing1800-second limit before a completed
route and the caster result. No canonical percentage was produced. These
timeouts remain failed evidence, distinct from ordinary combat losses.

The next authored witness earns at least level4 and6000XP from existing Rolf
Pritz and, when still needed, the existing catacombs at57,103. Rolf discovery
retains its32-iteration bound. The catacombs can contain its ordinary timed
Pritz plus its entry neighbors; an18-iteration discovery cap is an upper bound,
not a promise of18 enemies or fixed experience. Each pursued living source
Pritz must be removed and grant actual native XP. The source holyRelic pickup
and cave removal are checked. Recovery uses only source RoadTiles57,115 and
58,115. Group combat at the catacombs remains real and a defeat still fails.
No turn-in experience, potion, gear, level, actor or stat is manufactured.
The fixed no-rest comparator remains level3 with all original rows and seeds.

Before optimizing, hunt-local diagnostics print bounded elapsed stages around
loading, the existing full-map serialization, both complete saves/reloads,
pulse and reward checks. The original 48 assertions remain; ordinary children
retain their 30-second watchdog, with the instrumented partial-save exception
described below. A timeout exposes bounded captured stdout/stderr tails and reraises
the same exception. MCP calls retain their exact delegate, arguments, results
and errors while reporting aggregate counts/times at journey checkpoints and
every128 actual movement steps. Current coordinates still use full actor JSON.
A read-only probe measures20 paired samples after one warm-up for that existing
read versus three scalar position getters; it requires unchanged coordinates,
turn, objective state, HP and mana. These measurements add no timing pass gate
and cannot replace the required workload, performance or coverage evidence.

## Recovery approach regression and retained diagnostic head

Head `57e44f00` passed native tests and performance guards on Linux and Windows.
Windows job110532628636 completed the role matrix in 3.41 seconds, the fixed
hunt comparison in 2.14 seconds and partial actor save/recovery in 8.688 seconds.
Both authored classes still lost during preparation, before reaching the hunt
or the paired coordinate probe. The individual failed hunt case took 213.500
seconds; its whole 128-test worker took 405.183 seconds. Those are different
measurements and neither establishes a completed route.

The shortest path from the recovered Rolf road to `(57,115)` crosses the occupied
catacombs at `(57,103)`. The Windows Warrior's recovered turn442 plus115 movement
steps matches its defeat at turn557. The Sorcerer's recovered turn450 plus114
steps matches its defeat at turn564. Their native defeat receipts and failed
outcomes are retained; the intended road recovery had not happened yet.

The corrected approach uses the existing connected road through `(9,39)`,
`(8,39)`, `(8,49)`, `(9,49)`, `(9,81)`, `(30,81)` and `(30,115)` before the
catacombs road pair. Every intervening source cell is a RoadTile. This takes129
or128 steps from the two Rolf road cells, only two more than their respective
grass shortcuts, within the unchanged512-step bound. Native movement, map turns,
encounters and defeat checks remain active. The cave must still exist after
full road recovery before its actual entry; its stacked battle is preserved.

The Sorcerer's failed Windows approach measured2557 full JSON calls taking
49.323 seconds out of95.274 elapsed seconds, and3393 event-loop runs taking
28.495 seconds. This identifies real work but does not measure the three-scalar
alternative. The paired probe therefore moves to the recovered Rolf checkpoint
before the risky approach. Its full JSON baseline now has an explicit reader;
the regression requires22 JSON reads and63 scalar reads, so a future coordinate
optimization cannot accidentally compare the same reader against itself.
At that head, movement coordinates still used full JSON pending paired measurements.

The cold-cache scheduler now records 607 seconds from the failed 606.600-second
coverage case, with the earlier ordinary 213.500-second failure also retained.
Both measured preparation failures are lower bounds pending a completed route.
Recorded test timings still take precedence. This changes shard placement and
the allowance calculated by the existing formula; the formula and fixed phase
and native deadlines are unchanged. The callback watchdog exception is described
below. All tests, encounters, samples and assertions remain required.

## Scoped instrumented partial-save watchdog

The unchanged `./scripts/run_coverage.sh` invocation for head `57e44f00`
(job 110531958824) supplied the first exact native-child stages. Loading and map
startup finished at 4.354 seconds. Full-map JSON ran from 4.411 to 10.719 seconds,
the first save from 10.719 to 17.197 seconds, and its reload from 17.273 to 28.482
seconds. The pulse finished at 28.578 seconds, then the inherited callback
watchdog stopped the second save at 30.090 seconds. The second complete save and
reload could not finish inside that callback-shutdown test's default 30 seconds.
The ordinary Windows child passed the same work in 8.688 seconds. Projected
instrumented work is approximately 46 seconds; this estimate is not a pass.

Only the partial actor save/recovery test uses a 60-second child watchdog when
`GAME_COVERAGE_RUN` is exactly `1`, as set by the existing coverage script.
Every other flag value uses 30 seconds. Legacy adoption, monster-role runtime
checks and all other callback children retain their 30-second defaults. The
whole coverage phase remains 1800 seconds and native performance guards are
unchanged. No production serialization, map size, assertion, full-map traversal
or either of the two save/reload cycles is removed or optimized by this change.
The timeout still reports bounded captured streams and reraises the same failure.

Regression checks exercise the real shared subprocess wrapper with default 30
and explicit 60, and prove that only the exact instrumented partial fixture opts
in. Head `eea2ab9e` supplied actual after-change evidence: the same instrumented
partial test completed in 37.972 seconds in job 110557430042. Ordinary Linux and
Windows completed it in 3.919 and 9.016 seconds. The whole coverage Python phase
still reached its 1800-second limit, so this scoped functional watchdog correction
does not establish canonical coverage or full delivery.

## Catacombs movement defect and retained failures

Head `eea2ab9e` reached the untouched catacombs after full road recovery on both
platforms. Linux Warrior then lost at turn 577 with 4750 XP and Sorcerer at
turn 601 with 4625 XP. Windows Sorcerer lost at turn 602 with 4750 XP. These actual native
defeat receipts remain failed outcomes. Windows Warrior completed the three hunt
deaths and MainQuest with 1294 adjacent steps, 6375 XP, 112 HP, 147 MP and 1200 gold;
its two special actors died after warning, before a positive pulse.

The authored catacombs at `(57,103,0)` incorrectly configured its Pritz movement
controller for `ground`. Its center and 5×5 surrounding cells are GrassTile with
tile type `grass`. The controller admits only matching terrain, so its ten timed
spawns stayed together at the entrance. Entering that occupied cell resolves the
whole stack through the ordinary `fightManyResult`; recovery cannot occur between
its internal kills. The correction changes only that controller's terrain to
`grass`, retaining the timer budget 10, chance 10, monster templates, affiliation,
stats and rewards. The Rolf cave remains configured for ground.

A native regression deserializes the actual authored controller and source
terrain into a bounded map. The old ground setting remains stationary; the
corrected setting selects real passable grass cells and commits movement under
one fixed test seed. The center remains an eligible choice, so the test requires
observed movement rather than claiming every random choice moves. Its generator
state is restored after the fixture. Actual prepared-route survival still needs
fresh CI evidence.

The instrumented Warrior also completed a natural route in the old coverage run
with 1292 steps and an actual Alpha packet of 18→17 normal+1 shadow, spending five mana.
Sorcerer subsequently lost in the catacombs at turn 591 with 4250 XP. The next test in
that worker began at 20:35:17.126Z, approximately 1370.82 seconds after this failed
case began; no exact completion-duration line was emitted for its failed subtest.
The whole coverage run failed and emitted no canonical percentage. Remote
artifact 11192049807 retains those diagnostics.

## Measured MCP coordinate reads

The unchanged paired probe used one warmup and 20 samples per prepared class,
checking identical coordinates, map turns, objective state and player resources.
Each full JSON sample used one RPC; each scalar sample used exactly three ordered
`getNumericProperty` calls for `posx`, `posy` and `posz`.

| Platform / class | Full JSON median | Three scalar reads median |
| --- | ---: | ---: |
| Linux Warrior |0.089056s|0.001749s|
| Linux Sorcerer |0.040288s|0.001365s|
| Windows Warrior |0.076328s|0.002115s|
| Windows Sorcerer |0.035393s|0.001591s|

The instrumented route's partial checkpoint recorded 400.247 seconds in full JSON
RPCs versus 241.363 seconds in map movement. The walkthrough's coordinate helper
therefore reads three scalar properties on demand, with no coordinate cache and
no extra game turns. It follows the current loaded player and preserves signed
floor coordinates and native errors. Checkpoints compare those values against
the full player JSON they already read; item and resource snapshots remain
native JSON. The explicit full-JSON paired probe remains intact. This optimizes
test RPC work, without changing production serialization or native performance
budgets. Fresh completed-route and coverage measurements remain required.

## Ordinary defensive decision replay

Automatic victories can legitimately end after warning without a positive pulse:
the earned Warrior learns Bloodlash, and Sorcerer attacks and stuns can shorten
the phase window. A phase flag alone cannot establish the shadow mechanic. Both
automatic Warrior and Sorcerer routes therefore retain their full actual-death,
partial-save, reward, MainQuest and survival checks. A separate mandatory native
replay exercises ordinary manual decisions from the Warrior's genuinely earned
partial save, after its automatic route completes.

`monster_balance_unit_tests --hunt-decision <save-slot>` loads the original unique
primary without backup repair, snapshots the exact hero, equipment, inventory,
effects, archetypes, base/level stats, resources and living registry identities,
then sets only a test-local player decision controller. The loaded enemy
controllers and combat stats remain intact. One fixed seed 100 is applied once
before the whole adjacent-movement and combat replay; no seed search or retry is
used. The native generator is restored, and the isolated process owns its C RNG.

The player walks through real passable cardinal cells and enters the production
fight and initiative. For the opening Brood window it selects its existing paid
Barrier on two player turns, then its existing ordinary Attack. If necessary,
the living Alpha uses an observed charged phase as the cue for a learned Barrier.
No pulse is called outside combat, and no phase, HP, item, stat or objective is
granted. Native payment/refund checks retain Barrier's authored 17 mana cost.
The result must prove a positive one-point shadow packet with
`normal == damage_roll - 1`, its real linked effect, and exactly five enemy mana
spent. Loaded identities, state and composition inputs are compared with the
MCP snapshot; native composed stats are reported separately.

The parent walkthrough verifies the source save's SHA256 and its active game,
player, map turn, resources and objective state are unchanged by this separate
process. Missing native replay binaries fail in CI and skip the whole case before
any route work outside CI. The child retains a 30-second watchdog, captures both
streams and reports bounded timeout diagnostics. This deterministic manual
decision proof supplements the two natural automatic victories and does not
alter their controllers or the fixed seeded balance matrices. Its native passage,
both complete authored routes and canonical coverage remain fresh CI gates.

## Exact-head results and ordinary recovery correction

Head `64c3f096`, build 36926439067, passed normal native tests and performance
guards on Linux and Windows. Windows job 110586430561 passed its full validation:
Warrior completed 1521 adjacent steps at 6375 XP/112 HP/147 MP/1200 gold, and Sorcerer
completed 1492 steps at 6375 XP/91 HP/175 MP/1200 gold. Both native defeat receipts stayed
empty. The hunt unittest total took 324.948 seconds (the progress marker measured the case at 324.953 seconds). Its deterministic native replay
also survived, used three paid Barriers, preserved the source and parent session,
and observed a Brood packet of 40→39 normal+1 shadow with 105→100 enemy MP.

Linux job 110585393750 remained failed. Its Warrior automatic route completed 1451
steps with 6375 XP/112 HP/147 MP/1200 gold, but the manual replay lost after the two
paid defensive turns and two ordinary attacks. Its genuine 16→15 normal+1 shadow
packet spent five mana, yet the hero fell from 85 HP through 69, 58 and 28 before its
next turn, leaving the Brood at 13 HP. The earned partial save still contained four
LifePotions and nine lesser heals. Those unused items establish an available
ordinary recovery choice; the positive packet does not waive the actual defeat.
Sorcerer earned level four and reached the hunt road at 91 HP/175 MP, then lost on
the Scout approach at turn 979 with 6000 XP, losing 19 carried items. The failed Linux hunt unittest total took 201.467 seconds (its progress marker measured 201.434 seconds). Different encounter outcomes prevent treating
that case duration as a matched performance ratio.

The next deterministic replay retains the same initial save and seed. After the
mandatory defensive window, a hero below 50% HP may spend a real combat turn on the
strongest currently carried disposable Heal-only potion. Selection is stable by
power, type and name, and excludes items absent from the initial loaded inventory.
Native `useItem` must consume that exact identity once, increase HP by the ordinary
capped 20%-of-maximum-per-power formula, and leave mana and enemy resources intact.
There are no direct heal calls or new items. This ordinary decision is separate
from the unchanged automatic routes and balance comparisons.

Effect proof is also strengthened: `octobogzPulseEffectApplied` alone is not enough
because the flag is set before transfer. A positive packet must observe the actual
configured effect attached to the loaded player, with its caster linked to the
same enemy, duration and total time one, and an exact shadowResist−1 bonus with all
other numeric modifiers zero. Its remaining time may be one or zero while still
attached; removal at the following effect boundary defines expiry. Regression
checks reject flag-only, wrong-endpoint, wrong-duration and wrong-bonus evidence.

Sorcerer's failed Linux inventory contained eight LifePotions, five stronger
Fountain tonics, five DarkBeers and one lesser heal. Its existing AI estimates and
consumes the least powerful Heal first: a power-one heal at 91 maximum HP restores 18,
equal to the authored OctoBogz's estimated incoming 18, so the strict net-gain gate
can skip healing while stronger stock remains. The test's ordinary preparation
therefore visits the authored market at `(106,111,0)` and sells only carried
power-one Heal-only disposable items through its actual `CMarket.buyItem`.
The same item identity must leave player inventory and enter the existing shop;
gold must increase by the native quoted price. Stronger stock, equipment, HP, MP,
XP, quests, objective state and map turn remain unchanged by the transaction.
No shop stock or gold is created, and the existing AI is retained. Fresh native
and prepared-route results must establish whether this ordinary preparation
resolves the observed failure; source tests alone do not establish survival.


The same head's completed coverage job 110585393806 passed the full native partial-save
fixture in 37.655 seconds. Warrior completed the automatic route at 6375 XP/112 HP/147 MP/1200
gold with no defeat, and its seed-100 replay survived with one paid Barrier and an Alpha
packet of 18→17 normal+1 shadow spending exactly five enemy mana. That older replay still
had only the effect flag, so it does not establish the new linked-object proof. Sorcerer
completed Scout and Alpha, restored 91 HP/175 MP before Brood, then lost at turn 1317 with
6250 XP and 23 carried items in the defeat receipt. The three Python shards finished in
1363.296, 1438.149 and 1502.961 seconds; the final shard failed its Sorcerer subtest. The
coverage phase returned exit code one and produced no canonical eligible-line percentage.
Artifact `11194943840` (`linux-coverage-report`, 12,696,559 bytes) retains those diagnostics
remotely. This completed failure is separate from the earlier phase timeout.


## Finite basic brewing after the prepared Windows loss

Head `87b40884`, build 36930416096, passed Linux and canonical coverage at 90.69%
(17664/19478 lines). Linux's hunt case passed in 269.127 seconds: Warrior completed
1420 steps and Sorcerer 1513, both at 6375 XP with their full natural resources and
no defeat. The saved-hero replay survived and observed a linked Brood effect with
a 16-to-15 normal plus one shadow packet and exactly five enemy mana spent. Its
actual loaded Greater Life Potion was consumed once, restoring 21 to 88 HP at a
112 maximum without changing player mana or enemy resources.

The instrumented hunt case passed in 846.425 seconds. Both authored routes and
the linked-effect replay completed; the replay consumed an actually loaded
Fountain tonic from 41 to 40 inventory items, restoring 46 to 90 HP at a 112 maximum.
The unchanged full partial-save fixture passed in 33.440 seconds. Coverage artifact
`11196933053` preserves the completed diagnostics remotely. These outcomes do not
waive the failed Windows check.

Windows job 110599324033 passed native tests and performance guards. Warrior and
the linked-effect replay passed, and Sorcerer actually sold four Dark Beers and six
Lesser Life Potions at 320 gold each. Sorcerer entered Scout at level four with
91 HP/175 MP and five stronger heals. Scout consumed all five; the victory left
57 HP/120 MP and a genuinely looted lesser heal. After the owned portal and road
recovery, Alpha defeated the fully recovered hero at turn 1163/6125 XP. The receipt
contained only five non-healing items. This is an observed stock-exhaustion failure.

The next preparation preserves Lesser Life Potions as actual recipe inputs. At
the authored alchemy table `(105,110,0)`, the existing `brew_life_potion` recipe
consumes two Lesser Life Potions and 20 gold to produce one Life Potion. Its success
chance is 100%, with no unlock or random roll. Each invocation verifies two removed
owned ingredient identities, one new configured power-two output, exact gold
payment, and unchanged equipment, stats, HP, MP, XP, quests and hunt state.

Other weak healing-only consumables may be sold at the actual market to fund the
recipe. Purchases use the finite existing shop stock and native quoted prices,
reserve the brewing fee, and happen only in a batch that completes a pair. The
first visit can buy up to two ingredients while retaining an original third shop
identity for newly looted odd stock. After Scout's existing owned portal transit
and after later real road recovery, the hero revisits these actual services to
convert or sell new weak loot before another encounter. There is no second portal,
restock, item grant, seed search, or change to ordinary combat selection.

The measured Linux inventory with no weak heals and 17 stronger heals skips an
unaffordable purchase. The instrumented case's one lesser and one beer can fund
one real ingredient purchase and recipe. The failed Windows case's six lessers
and four beers can produce four Life Potions, leaving 600 gold and the third
original shop ingredient; Scout's actual lesser can later complete one more pair
for 420 gold. These are source-backed accounting examples, not a promised victory.
Fresh native gameplay on both platforms and canonical coverage remain required.


## Reusing all untouched original shop stock after the instrumented depletion

Head `b77f89d4`, build 36935826230, passed Linux, Windows, their native and
performance checks, and Android. Both normal automatic class routes and the
linked-effect replay passed. Canonical coverage did not pass: its completed
hunt case failed in 894.016 seconds when Sorcerer lost to Brood at 6250 XP,
1 HP/148 MP and 1160 gold. The full Python shards finished rather than reaching
the coverage phase timeout; the run produced no canonical percentage. Artifact
`11199012927` (`linux-coverage-report`, 12,723,040 bytes) retains the diagnostics.
The unchanged full partial-save fixture passed in 47.664 seconds under its scoped
instrumented watchdog.

The actual caster receipts show zero purchases throughout this failed route.
Initial preparation had one Lesser Life Potion and 200 gold, insufficient for
a quoted ingredient plus the brewing fee; it sold that owned ingredient for
320 gold and left ten stronger heals. After Scout, an actual Dark Beer sale
raised gold to 840 with three Life Potions and no Lesser ingredients. After
Alpha, another actual sale raised gold to 1160 with one Life Potion. The source
shop's three original ingredients remained untouched, as accounted for by the
configured finite stock, zero purchase receipts, and exact gold changes. Their
individual names were not logged by that head.

The later-visit helper incorrectly restricted candidates to the one reserved
third ingredient. With zero owned ingredients it needed two, so it skipped the
otherwise affordable 800-gold pair plus the 20-gold brewing fee. The correction
records all original shop names before the initial cleanup can add a sold earned
ingredient. Later visits intersect those names with current actual stock and
exclude every name previously purchased. They may buy one or two ingredients
only to complete an owned pair and only with quoted prices plus the real fee
available. The first visit still reserves the third original ingredient. A
partial reload replaces handles without changing these original names; a sold,
returned or newly created stock identity cannot enter the whitelist.

Two regressions fail against the previous helper and pass after the correction:
an initial unaffordable visit followed by the measured affordable late pair,
and an initial odd pair followed by both untouched remaining originals. They
also cover reload handles, sold earned stock, purchased-name re-enrollment and
repeated visits. Exact 419/420 and 819/820 funding boundaries remain tested.
New bounded receipts report original, purchased and available names, quotes,
gold and the reason for a skipped purchase. This repairs a demonstrated unused
stock gap; it does not promise that one extra Life Potion ensures survival.
Fresh complete native routes and canonical coverage remain required. Enemy
stats, ordinary AI, encounters, fixed comparisons and deadlines are unchanged.

## Owned recovery before the road departure

The `4a88713e` Linux job `110720338624` remained failed. After Alpha's actual
defeat, the Sorcerer was at `(165,20,0)`, turn 1132, with 62/91 HP, 143 MP,
960 gold and 6250 XP. The actual inventory contained one Fountain of Youth
Tonic, a Spiced Beer, four Magic Well Draughts and the retained quest/Scroll
items. Its defeat receipt was empty. The receipt first changed at turn 1134
while travelling toward the authored road at `(118,21,0)`. The route has 48
adjacent steps; this does not establish which native actor, damage channel or
individual queued action caused the loss.

Hunt road recovery now checks survival before using any inventory. Below the
existing 75% recovery threshold it may use only a currently owned, configured,
single-use LifePotion with a positive power, a heal tag and no mana or quest
tag. Supplies are considered weakest first and each captured pointer at most
once. Native `useItem` applies the item immediately without a map turn. The
observed power-two Fountain can restore 36 HP capped at 91; the helper checks
that exact formula, the one consumed identity and every remaining item. Player
composition, controllers, gold, mana and maxima, coordinates, turn, quests and
hunt registry must remain unchanged. A recorded defeat cannot be healed away.

Recovery travel can itself encounter the living Brood near the lair. After
returning to the road, the walkthrough rechecks that objective. It omits
precombat market preparation only after the retained actual actor is dead,
its name is absent from the map, and the registry marks that same slot dead.
If Brood remains living, the existing finite preparation and stronger-stock
assertion still apply. Consuming the last Fountain does not create replacement
stock or waive that gate. Final proof of all three deaths and the original
once-only reward remains mandatory.

A failure during this recovery now retains the existing bounded native tail
and read-only combat snapshot before rethrowing the original exception. The
pure regressions demonstrate owned-healing order, capped recovery, state and
identity checks, and the any-order objective boundary with simulated movement.
Their synthetic departure hazard is not a reproduction of the unknown lethal
mechanism. Fresh native automatic routes, the separate earned-save decision
replay and complete selected CI are still required to prove survival.

The preceding `c36a8122` preparation failure was a different funding gap: an
owned mana-only supply could fund a real original ingredient and brewing fee.
That correction reads the native quote, sells only enough actual owned
supplies, and preserves the finite original-name and purchased-name guards.
Neither recovery correction changes enemy stats, combat AI, recipes, seeded
comparisons or their deadlines.

## Scheduling the complete native save fixture

The `306db6c1` normal Linux and Windows jobs passed, but its coverage job failed
only because the complete native partial-save child exceeded its existing
60-second instrumented watchdog. The last marker was `reload2 begin` at
45.396 seconds; no returned marker appeared before the 60.052-second timeout.
Completed stages included the standalone full-map JSON traversal at 11.794
seconds, first save at 9.946 seconds, first reload at 9.539 seconds and second
save at 9.742 seconds. These aggregate measurements do not isolate a native
serialization hotspot or establish that concurrent work caused the timeout.
The unchanged fixture had previously completed instrumented runs in 50.343
and 53.427 seconds, compared with normal `306` runs at 2.003 and 5.766 seconds.

Only this exact partial-save test now uses the runner's existing serial worker.
That worker starts after every initial parallel and Xvfb sidecar process has
finished. The later Xvfb phase still starts after the serial worker. Legacy
adoption and other game/MCP tests remain parallel. A regression runs the actual
scheduler with mocked processes in ordinary and coverage modes, requires one
serial invocation of the fixture, checks every concurrent wait before launch,
and preserves failure propagation and the existing derived worker allowances.

The native child remains byte-for-byte unchanged: the full 40,000-tile map,
standalone JSON inspection, both complete save/load cycles, all 48 assertions,
actor/effect identity, resource recovery and once-only reward checks remain.
Its ordinary 30-second and exact coverage-flag 60-second watchdogs, native
performance guards and outer 1,800-second coverage phase are unchanged. The
failed run's slowest parallel worker finished in 1,518.430 seconds and its
existing four serial tests took 0.813 seconds, indicating room for this intact
fixture within the phase budget. Fresh selected CI must establish timely
completion; moving the fixture removes overlapping test work without claiming
a native speedup or guaranteeing its elapsed time.
