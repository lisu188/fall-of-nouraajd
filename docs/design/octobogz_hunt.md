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
configured Attack. The shadow brood warns on its first eligible attack; the
Alpha warns only at or below half health. Warning still executes that Attack.
The next eligible affordable attack costs five mana once, converts one point of
that same damage roll from normal to shadow, and applies shadow resistance -1
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
source terrain, checks native walkability, queues that single step in the real
player controller, calls `CMap.move`, pumps its event loop, and verifies one
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

The user approved this distinction after the fixed original route proved
all-losing for three Linux classes. Only that universal no-rest victory witness
was corrected; all five classes,11 paired seeds,positive-HP witnesses,absolute
10-percent resource gates and every original winning seed remain unchanged.
The prior Windows Assasin mana120 to140 failure is still a strict mechanic
failure requiring resolution, not covered by the witness correction. The
disabled hunt callback fixture also explicitly retains all five baseline mana
points, alongside the used-pulse assertion that exactly five are spent.
