# Passive effect contracts

Issue #1515's twelve configured empty `onEffect` hooks have authored behavior.
Ten effects contribute a `CStats` bonus; `Stun` and `HoldPersonEffect` supply
the `stun` tag consumed by `CFightHandler`. The empty hooks are intentional:
their behavior comes from stat composition or combat tags, with native timed
expiry. None of these twelve is a demonstrated live no-op.

The table fixes the existing contract rather than adding spell mechanics.
`L` is the caster's level and `A` is the caster's composed armor when the effect
is configured. `//` denotes integer division. Costs are paid once per cast.

| Interaction → effect | Mana | Duration | Target | Observable behavior |
| --- | ---: | ---: | --- | --- |
| `Slow` → `SlowEffect` | 25 | 3 | Opponent | Agility `−(2+L//2)`, hit `−(3+L//3)`, block `−4` |
| `ChillTouch` → `ChillTouchEffect` | 10 | 3 | Opponent | Hit `−(2+L//3)`; one immediate frost damage packet of `3..10` before mitigation |
| `Doom` → `DoomEffect` | 12 | 4 | Opponent | Armor `−(2+L//2)`, block `−2`, hit `−2` |
| `Haste` → `HasteEffect` | 30 | 3 | Caster | Agility `+(3+L//2)`, hit `+3`, crit `+2` |
| `MirrorImage` → `MirrorImageEffect` | 20 | 3 | Caster | Block `+(15+2L)` |
| `Stoneskin` → `StoneskinEffect` | 45 | 4 | Caster | Armor `+(6+A//2)`, normal resistance `+5` |
| `Bless` → `BlessEffect` | 10 | 4 | Caster | Hit `+(2+L//4)`, attack `+1` |
| `ArmorOfFaith` → `ArmorOfFaithEffect` | 12 | 4 | Caster | Armor `+(3+L//2)`, normal and shadow resistance `+3` each |
| `DrawUponHolyMight` → `DrawUponHolyMightEffect` | 25 | 3 | Caster | Strength, agility, and stamina each `+(2+L//3)` |
| `Barrier` → `BarrierEffect` | 17 | 3 | Caster | Normal resistance `+10` |
| `Stunner` → `Stun` | 40 | 2 | Opponent | Guaranteed `stun` tag; other authored interactions also use `Stun` |
| `HoldPerson` → `HoldPersonEffect` | 35 | 2 | Opponent | `stun` tag on rolls 2 or 3 of `randint(1,3)`; failed roll keeps the paid cost |

Haste does not grant extra actions, Mirror Image does not spawn actors, and
Chill Touch does not repeat its damage on effect ticks. Those additional
mechanics are outside the existing authored contracts.

## Application, expiry, and persistence

`CInteraction.onAction` rejects a caster with less than the configured mana
cost before calling the action or attaching an effect. Successful casts pay the
cost, call `performAction` once, configure a cloned effect, and route it to the
caster for `selfTarget` or a buff tag; other effects go to the opponent.

`CCreature.getStats` includes each attached effect's bonus. `CEffect.apply`
calls its hook and decreases `timeLeft` once. `CFightHandler.applyEffects`
first removes already-zero effects, then applies remaining effects. A
duration-`N` passive bonus remains attached after its `N`th decrement and is
removed at the next application. Combat checks stun after effect application,
so the two-turn stun skips exactly two victim actions. Preserve this order.

Native map serialization preserves each effect's configured type, bonus,
duration, remaining time, tags, and caster/victim object references. Restored
effects must contribute the same stats and continue toward expiry, without
replaying immediate cast damage.

## Regression coverage

`tests/test_effect_semantics.py` checks the twelve empty-hook classes and their
configuration references, exact formulas at two levels, missing-caster guards,
the immediate Chill Touch packet, and Hold Person's three possible rolls.
`EffectSemanticRuntimeTest` exercises native paid casts, target routing,
observable stats/tags, effect expiry, rejection at `cost−1` mana, a partially
expired save/load of all twelve effects, and real combat action counts for
both stun effects. The save uses a fresh UUID slot and removes only its own
files.

```sh
python3 -m unittest tests.test_effect_semantics.EffectContractTest
python3 test.py EffectSemanticRuntimeTest
```

Source tests run without `_game`. Native tests require the current compiled
module and copied resources and belong to gameplay, full, and coverage-safe
suites; discovery assertions protect that selection. Close #1515 after the
selected native and coverage checks pass and the regression PR merges. Empty
tick hooks should then be tracked as intentional passive implementations,
without promising unspecified spell redesign.
