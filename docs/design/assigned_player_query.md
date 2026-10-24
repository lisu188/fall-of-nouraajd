# Read-only assigned player cache observation

`CMap::getAssignedPlayer() const` returns the current private `player` shared pointer as-is. It may return null
even when a named CPlayer is registered, may differ from the named registry object and may retain a dead player.
It neither calls lazy
`getPlayer` nor adopts, restores, repairs controllers, registers triggers, moves or reassigns an actor.

The API follows engine owner-thread semantics. Existing assignment writers are not uniformly protected by
`navigationMutex`, so this getter adds no getter-only lock or thread-safety claim. Returning a shared pointer
retains the observed identity for the caller; it is not a transaction, freshness receipt or authority across awaits.

The existing lazy `getPlayer` and all assignment, attach/detach, defeat, registry and save behavior remain unchanged.
Only a const declaration, one return statement and the Python World binding are added. No V_PROPERTY, save field,
new type, general party/stat API or MCP allowlist entry is added.

The native cases use public APIs only. One registers a real CPlayer with non-player controllers but no assignment,
then verifies repeated queries do not adopt or repair it, removes it normally, and contrasts explicit lazy adoption.
The other uses two public `setPlayer` calls with the same canonical name to produce a real cache/registry mismatch,
observes it without repair, then tests explicit detach/attach identity. No friend or private test-only API is used.

The deterministic existing performance target receives a 512-query guard: two fixed phases of 256 reads with zero
registry/controller/hook/turn/navigation-revision/queue/callback delta. It explicitly registers existing controller
types so the attach fixture is independent of prior performance-test registration order. Counts are authored gates,
not measured runtime evidence here. The isolated extension test is authored to use the real `test` map with no GUI,
and to contrast detached-then-registered-but-unassigned state with explicit reattachment.

The binding fixture changes only the `bindGraphicsAndWorld` digest plus a deliberate review note. The published
Foundation epoch digest and all other binding groups remain intact. Source tests are fast; the extension class
delegates to the existing `PythonCallbackLifecycleTest.runChild` isolated subprocess harness and is selected in
gameplay/full/coverage-safe. It imports no native module in the discovery process. Missing native support may skip
only when no build is configured. Explicit `required=True`, `GAME_BUILD_DIR`, `GAME_BUILD_CONFIG` or
`GAME_MCP_BRANCH_REQUIRED=1` makes a missing native child fail. The harness retains dummy video/audio and software
rendering. One pure regression mocks only this child boundary and checks optional and required behavior without
launching a child. Native profile case names are additive; original catalog order and baseline digests are retained.

This proposal is based on exact published support `1c6b1d9129f6fda0eec142660dab6e3199cfc647`, with separately rendered
additive working images preserving all unrelated source and raw newline policy. Task-local output only: no feature,
index, refs, builds, game/native tests, full runner, city generator, map/config parser or dependency changes.
Source checks and mutation evidence do not establish compilation, native performance, extension runtime or coverage.
Applicable native/extension/performance/coverage CI remains required. No custody consumer is integrated in this cut.

Callers must validate the observed pointer against their own captured game, context generation, binding epoch,
registered player, type and alive policy. The query does not certify that those identities agree. It intentionally
does not resolve the separate native operation-admission or durable receipt requirements.

Focused retained evidence is in `validation-5`: each committed and working variant passes eight actual source
methods and one selected actual native-profile order method, with zero errors/skips. Against the corresponding
unmodified beforeimages, the same eight source methods produce six assertion failures, zero errors/skips. No full
runner, native profile suite or native module is imported. The selected catalog method reads candidate map source
and an exact retained unchanged handler source input; that supporting input is not a publication target.

`mutations-2` rejects five isolated in-memory mutations: lazy-player fallback, registry fallback, non-const
declaration, stale World binding digest and silently skipping a configured native build. Every mutation produces
assertion failures with zero errors/skips. Earlier `mutations-1` retains a validator setup error for provenance;
that failed harness is not counted as regression evidence. Earlier validation receipts are retained separately.

The two C++ fixture templates were formatted by root using its approved WSL formatter invocation. The author's
earlier WSL distribution-selection attempt was denied and was not retried. Python proposal helpers and the new
test module use the existing Black installation. No compiler or formatter dependency was installed.

Read-only reproduction uses the existing interpreter:

```powershell
& 'C:\Users\andrz\AppData\Local\Programs\Python\Python311\python.exe' -B build/city-story-outcomes-review/map-assigned-player-proposal/verify.py
```

To reproduce only the selected source checks and mutants, supply new absolute evidence directories to
`validate.py --output <new-absolute-directory>` and `mutations.py --output <new-absolute-directory>`. These runners
reject existing output paths and never launch the authored extension child. Do not run `prepare.py` or modify
artifacts after the freeze. The verifier reconstructs both image sets from their retained inputs in memory.
