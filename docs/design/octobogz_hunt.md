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
pulse and reward checks. The original48 assertions and30-second child limit
remain. A timeout exposes bounded captured stdout/stderr tails and reraises
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
Current movement coordinates still use full JSON pending paired measurements.

The cold-cache scheduler also records214 seconds as a transparent rounded lower
bound from that failed213.500-second case. Recorded test timings still take
precedence. This changes shard placement and the allowance calculated by the
existing formula; the formula and fixed child, phase and native deadlines are
unchanged. All tests, encounters, samples and assertions remain required.
