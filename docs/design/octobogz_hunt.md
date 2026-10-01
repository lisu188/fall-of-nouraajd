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
for one turn. With insufficient mana it executes ordinary Attack and ends the
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
10 percent, including zero baselines. Every class must have baseline victories
and meaningful incoming damage; real Alpha and brood pulse/effect use must occur.
No stat, loadout, seed-count, threshold, or timer change is used to satisfy gates.

The same native executable tests ordinary Attack callbacks, a real Staff weapon
proc, both random streams, actual one-turn effect stats/endpoints/expiry, consumed
ownership slots, and exactly five mana for a used pulse. Controller and performance
fixtures preserve ordinary spell/item priority and bound 200 outer selections to
one charge, one pulse, and 198 ordinary Attack selections. Focused Python tests
exercise migration, partial saves, live removal, pending placement, late rewards,
misses, cancellation, and default hook behavior. The separate stdio MCP walkthrough
uses actual player movement and combat for Warrior and Sorcerer, with ordinary
progression and a partial save, rather than flag-only objective manipulation.

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
