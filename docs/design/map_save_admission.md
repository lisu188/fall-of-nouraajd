# Map save admission

Native operations that can suspend after changing map state can explicitly exclude
save snapshots until their domain work and cleanup have settled. This mechanism
provides admission and ownership; callers remain responsible for their gameplay
state, receipts and interruption policy.

```cpp
auto operation = map->tryBeginUnsafeOperation();
if (!operation) {
    // Return before changing gameplay state.
    return;
}
// Perform the operation, validate its captured bindings, clean temporary state,
// and commit its domain receipt.
operation->finish();
```

`UnsafeOperationLease` is move-only. `isCurrent()` checks the captured game,
context, transition generation and map. It keeps the map and admission markers
alive and holds the game/context weakly. A caller must check its own player,
actor and coordinator identities around callbacks and awaits. Multiple owners
can coexist, including a native encounter and its surrounding authored flow.
Finishing one owner leaves the others active.

`finish()` releases one known-settled owner and is idempotent. `quarantine()`
releases it while blocking further saves and operations on its captured map and
session. Destruction of an unsettled owner quarantines by default. Moving over
an existing unsettled lease also quarantines the displaced operation. An
exception alone does not establish whether partial gameplay state is settled.

`CMapLoader::saveWithResult` acquires exclusive snapshot admission before journal
capture, reflected graph access, encoding or provider writes. It returns `false`
when an unsafe owner, another snapshot, a restore or quarantine blocks admission.
Snapshot teardown releases its reservation on failure as well as success. The
same fixed map-local marker protects detached maps after the game owner expires.
Admission locks are released before serialization, callbacks and I/O.

`guardNativeEncounterSaves` is an optional authored boolean, defaulting to
`false`. Explicit `true` and `false` are accepted; an explicit non-boolean rejects
the malformed map policy. The loader applies it before object creation hooks and
reapplies the authored declaration after restore, including resetting saved
ad-hoc values when the declaration is absent or `false`. An opted-in ordinary
native encounter holds its own lease through effects, actions, awaited domain
work and controller cleanup. A surrounding authored flow can retain an
independent owner through its receipt commit. Deferred callbacks outside that
resolver remain a separate integration boundary.

The markers are runtime-only, outside reflected map metadata. Maps without an
explicit unsafe operation preserve ordinary snapshot behavior. A safe wait does
not acquire an unsafe lease merely because a clock is running. This change does
not serialize coroutine stacks, add a save-format field, or make unrelated
engine mutation transactional.

Recovery is private to `CGameLoader::loadSavedGame`. An exclusive restore token
requires zero unsafe owners and remains held through candidate loading, actual
map installation and best-effort backup repair. Only the same active context,
generation, exact installed map, zero owners, unchanged quarantine revision and
fresh local marker can clear session quarantine. Failed, candidate-only, manual
or superseded installation cannot clear it. A verified backup is a checkpoint
even if best-effort repair of its primary file fails. Earlier quarantined maps
retain their own markers after recovery.

`verifiedLoadResumeReceiver` is an optional authored string naming one exact
registered object on the loaded map. An absent or empty value disables dispatch.
An explicit non-string, a name longer than 256 UTF-8 bytes, or an ASCII control
character rejects the malformed declaration. The loader applies this policy
before object hooks and reapplies its authoritative authored value on restore;
saved ad-hoc receiver names cannot opt a map into resumption.

Only successful `CGameLoader::loadSavedGame` installation can schedule the
receiver's `resumeAfterVerifiedLoadFlow` method through the existing `UiFlow`
dispatcher. Candidate loading or manual `setMap` does not schedule it. The
loader captures the authored name and exact registered receiver before install
callbacks, completes installation and best-effort backup repair, commits recovery,
explicitly releases restore exclusivity, then queues one task. That task first
posts to the event loop and retains only weak game, context, map and receiver
bindings while queued. Before dispatch it rechecks the active context, captured
generation, current map, authored receiver metadata and exact registration. A
failed, superseded, rebound or destroyed binding dispatches nothing.

The hook does not advance turns, convert time spent offline into game time, or
resume a serialized coroutine. The map-local consumer must validate its saved
receipt and wait state before issuing new work; pending or interrupted native
actions must never be replayed automatically. Safe waits remain savable and
retain their own remaining-time semantics. Source checks and authored native
fixtures alone do not establish compiled resume behavior, a real saved pause,
visual behavior or city gameplay acceptance; those checks remain required.

The native regressions cover early rejection, multiple owners and moves,
serialization failure, map/last-owner changes, primary and backup recovery, and
reentrant or superseded installation. The deterministic serialization performance
guard attempts 256 rejected saves and requires zero journal captures, graph visits
and primary/backup outputs. A released positive control must reach journal and
graph work once. Timing is not its acceptance criterion.

Callers must still integrate this API at every relevant mutation boundary.
The Baldur's Gate city flow receipts, saved pause/controller restoration,
map-local resume consumer and deferred callbacks require their own integration
and runtime evidence. Admission and a posted hook alone do not establish safe
saving throughout those operations or complete city gameplay parity.
