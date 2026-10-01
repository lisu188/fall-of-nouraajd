# Monster role balance contract

The comparison uses the real `_game` bindings, configured Python interactions,
post-RNG-fix combat streams, five ordinary level-three player templates, seven
level-two monster templates, and paired seeds 100 through 110. There are 35
class/monster pairs and 770 fights. Both random streams reset after sample setup;
there is no production RNG seeding API.

Every pair retains absolute median health, mana and inventory expenditure limits
of 10 percent, including a zero baseline. Every seed that wins without signatures
must also win with them. Each player class must have at least one representative
Gooby, Pritz or OctoBogz pair that both wins and causes positive median incoming
damage. Requiring every pair to win or to cause damage would reject existing
baseline behavior: Sorcerer/CultLeader wins zero seeds and Assasin/Pritz receives
zero median damage. All those pairs still retain their metric and victory gates.

Resource observation forwards the configured controllers unchanged and records
positive HP/mana decreases and removed inventory identities at control/lifecycle
boundaries. Recovery and later loot do not erase earlier costs. Opposing changes
within one callback can coalesce; this limitation also applies to both baselines.

## Corrected harness evidence, before signature revision

[Linux job 110303082419](https://github.com/lisu188/fall-of-nouraajd/actions/runs/36841791157/job/110303082419)
ran the Release native fixture at role head `5881f0d7`, using the actual `_game`
module identity. The inherited-native-method regression passed. The full matrix
completed in **16.14 seconds**, with 638.315 ms of sample setup, 15,292.136 ms of
combat and 1.384 ms of cleanup. The prior aliased-module timeout and partial
measurements are invalid balance evidence: that module identity caused native
methods to be dispatched recursively as Python overrides.

The command supplied by CI was:

```sh
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
```

All 35 comparisons completed. The initial signatures failed 19 health medians,
one mana median and three winning-seed preservation checks. Two additional
failures were the overly broad witness assumptions corrected above. No budget,
seed, loadout, class count or monster count changes are authorized by that witness
correction. The native suite stopped before its separate performance and Python
phases, so those phases have no passing evidence from this run.

Lost baseline victories:

- Sorcerer/Gooby, seed 101: HP/mana/items 69/120/0 to 84/105/0.
- Sorcerer/PritzMage, seed 109: 77/135/0 to 84/120/0.
- Wayfarer/Gooby, seed 105: 69/80/0 to 81/80/0.

All item medians were zero. The following records retain the failing measurements
before any mechanic revision; they are not passing acceptance evidence.

| Class | Monster | HP before | HP after | Mana before | Mana after | Baseline wins |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Warrior | Gooby | 40 | 35 | 17 | 17 | 11/11 |
| Warrior | Pritz | 5 | 2 | 17 | 17 | 11/11 |
| Warrior | OctoBogz | 69 | 69 | 34 | 34 | 9/11 |
| Warrior | PritzMage | 40 | 41 | 17 | 17 | 11/11 |
| Warrior | GoblinThief | 5 | 4 | 17 | 17 | 11/11 |
| Warrior | Cultist | 5 | 2 | 17 | 17 | 11/11 |
| Warrior | CultLeader | 52 | 44 | 34 | 34 | 10/11 |
| Sorcerer | Gooby | 80 | 70 | 105 | 105 | 6/11 |
| Sorcerer | Pritz | 10 | 7 | 60 | 60 | 11/11 |
| Sorcerer | OctoBogz | 83 | 83 | 105 | 105 | 1/11 |
| Sorcerer | PritzMage | 80 | 84 | 105 | 105 | 6/11 |
| Sorcerer | GoblinThief | 10 | 9 | 60 | 60 | 11/11 |
| Sorcerer | Cultist | 10 | 7 | 60 | 60 | 11/11 |
| Sorcerer | CultLeader | 84 | 84 | 90 | 105 | 0/11 |
| Assasin | Gooby | 14 | 0 | 40 | 40 | 11/11 |
| Assasin | Pritz | 0 | 0 | 20 | 20 | 11/11 |
| Assasin | OctoBogz | 18 | 18 | 60 | 60 | 11/11 |
| Assasin | PritzMage | 14 | 14 | 40 | 40 | 11/11 |
| Assasin | GoblinThief | 0 | 0 | 20 | 20 | 11/11 |
| Assasin | Cultist | 0 | 0 | 20 | 20 | 11/11 |
| Assasin | CultLeader | 26 | 13 | 60 | 60 | 11/11 |
| Inquisitor | Gooby | 34 | 25 | 62 | 62 | 11/11 |
| Inquisitor | Pritz | 6 | 6 | 42 | 42 | 11/11 |
| Inquisitor | OctoBogz | 41 | 41 | 82 | 82 | 11/11 |
| Inquisitor | PritzMage | 34 | 34 | 62 | 62 | 11/11 |
| Inquisitor | GoblinThief | 6 | 5 | 42 | 42 | 11/11 |
| Inquisitor | Cultist | 6 | 2 | 42 | 42 | 11/11 |
| Inquisitor | CultLeader | 41 | 34 | 82 | 82 | 11/11 |
| Wayfarer | Gooby | 57 | 44 | 80 | 80 | 11/11 |
| Wayfarer | Pritz | 6 | 3 | 40 | 40 | 11/11 |
| Wayfarer | OctoBogz | 56 | 56 | 120 | 120 | 8/11 |
| Wayfarer | PritzMage | 57 | 57 | 80 | 80 | 11/11 |
| Wayfarer | GoblinThief | 6 | 5 | 40 | 40 | 11/11 |
| Wayfarer | Cultist | 6 | 4 | 40 | 40 | 11/11 |
| Wayfarer | CultLeader | 71 | 55 | 100 | 100 | 10/11 |

