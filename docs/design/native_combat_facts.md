# Native combat facts

`nativeCombatFacts` is an opt-in map property, absent or `false` by default. No scenario resource currently enables it.
Coverage includes the migrated Attack, MagicMissile and Melf's acid-arrow producers. Other damage producers require
explicit migration and an audited operation boundary.

## Capture and delivery

The native producers capture facts at the actual payment, attack-roll and damage-packet points. Observers receive them
after the enclosing native operation completes:

- `CCreature::useAction` includes the interaction and its nested weapon and armor responses.
- A direct `CInteraction::onAction` provides a fallback boundary for that interaction and its nested work.
- `CEffect::apply` delivers after one complete pulse and duration decrement. The enclosing effect runner then validates
  its original receiver before processing another pulse or death/result work.

Nested scopes capture into the same transient, context-owned batch. Native actions started by an observer append to the
batch being drained, without recursively invoking observers. A scope abandoned by an exception discards its pending
observations. Capture requires an active operation scope; a standalone numeric helper retains its normal result or
damage behavior without publishing before an unknown caller consumes that result.

`CInteraction.offensive` defaults to `false`. When explicitly authored as offensive, a fully paid interaction captures
an attempt before performing its action. Negative costs and insufficient mana do not commit an attempt. These captures
describe completed engine operations; they cannot interrupt the damage or responses that produced them.

## Producer API and event fields

`CCreature.getDmgFor(victim, allowCrit=True)` returns the ordinary integer damage result using the existing three native
dice draws, while retaining the actual hit boolean for a roll fact. `CCreature.hurtFrom(cause, amount)` accepts an
integer, float or `CDamage` and applies the existing damage path once. `CEffect.hurtVictim(amount)` accepts the same
overloads and supplies its stored caster, victim and effect instance. Existing `getDmg` and `hurt` calls remain available.

Observers receive `CGameEventCaused`. Read `event.getCause()` for the explicit creature cause and
`event.getStringProperty("combatKind")` for the kind. `combatProducer` is an object property containing the interaction
for an attempt, the effect for an effect packet, or `None` where no producer object was supplied.

| Kind | Captured fields |
|---|---|
| `onCombatAttempt` | `combatManaAtCommit`: actor mana immediately after payment |
| `onCombatRoll` | `combatConnected`: actual native hit boolean; `combatDamage`: resulting integer damage |
| `onCombatPacket` | Input channels `combatNormal`, `combatThunder`, `combatFrost`, `combatFire`, `combatShadow`; `combatHpBefore`, `combatHpAfter` |

The channel values describe the packet entering the existing resistance, armor and block path. A zero-damage hit, a
miss and a fully blocked or resisted packet remain distinct. HP changes alone do not establish a hit.

## Observer and lifecycle contract

Combat delivery snapshots matching listeners for each fact. Registration during a callback affects subsequent fact
deliveries. Each listener receives a fresh event copied from the immutable native capture. Before and after every
listener, the engine checks the active map/context/generation and the exact registered cause and receiver instances.
Cancellation, map replacement or actor removal/transfer/replacement stops the remaining stale deliveries.

In opted-in mode, the effect runner also captures its original receiver's game, map, context and generation. Receiver
invalidation interrupts the phase before later effects, controller actions or defeat/reward processing. Ordinary maps
retain the existing effect algorithm and damage rules.

A batch permits at most **128 facts** and **32 nested scopes**. Overflow raises a runtime error at outer completion;
committed damage and resource changes remain applied. These limits bound captures and scope nesting. Callback work and
the number of registered listeners have their own costs. A throwing observer stops delivery and releases the batch for
a later operation.

Observers run synchronously. Scenario code should queue plain observations and handle dialogs, movement and source
script consequences at a separately audited boundary. This layer supplies no BG1 `AttackedBy`, `HitBy`, `Heard` or
`SHOUT` consumer. Their source timing, listener ownership, conditions and consequences still require implementation and
independent acceptance before any source-equivalence claim.
