# Public map-binding epoch proposal

Base: immutable support d64d87a3c125ff91fbc46516b2b72a743b9fe002.

The existing synchronous mapBindingChanged signal tells entered listeners about
public pointer publications. It does not give a suspended, non-listening consumer
a retained identity value. Context transition generation is a separate lifecycle
authority and intentionally does not advance for raw CGame.setMap calls.

getMapBindingEpoch() returns a private, nonserialized std::uint64_t under the
existing resourceMutex. It does not request/create a context, dispatch signals,
touch providers, or expose a setter. This non-creation claim is checked from the
complete getter source; tests do not pretend to observe the private context.

The counter starts at zero and advances once immediately before each actual
pointer publication in public setMap's second locked section. Comparing there
handles reentrant GUI close correctly. The existing synchronous binding signal
still follows publication; nested signal callbacks observe their own publication
epochs. The existing signal dispatcher logs and suppresses std::exception from
observers; that failure cannot undo an already published pointer/epoch.
Same-pointer calls, including repeated null, do not advance it. At uint64 maximum,
another changed publication throws before assignment instead of wrapping. That
overflow branch is source-checked and remains unexecuted in bounded native tests.

The private setMapForResourceLoad temporary resource scope is unchanged and does
not advance the epoch. Its real failed-save-load native test gains an unchanged-
epoch assertion. Context shutdown and scene transitions retain their existing
generation and callback behavior. The epoch specifically counts public setMap
publications; it does not replace map identity, context identity, generation,
active-session checks, or participant/source binding checks.

A consumer must capture an epoch before obtaining its map/binding observations,
then recheck epoch and other ownership anchors before and after reflected work and
UI suspension. Separate getter calls are not an atomic map-plus-epoch snapshot.
The raw old->other->old round trip changes this epoch twice even if pointer and
context generation again match. No compact-model property is proof of this native
authority. Custody integration is a separate reviewed change after this API exists.

The fixed native operation guard authors 128 cycles, 512 queries and 512 public
setter calls: exactly 256 changed publications/callbacks, no new event-loop work,
no generation change or actor growth. No timing or bottleneck claim is made.

Existing actual custody v2 unresolved-raw-away-back evidence remains the behavioral
before witness. Focused source contracts fail before because the publication
counter is absent, then pass against this source proposal. New native test calls
cannot compile against the old missing API; that is not reported as a behavioral
native red result. Native unit/performance, Python extension binding, full suites,
coverage and custody MCP/runtime acceptance all remain pending CI. No local native
build, game, GUI, full generator, resource regeneration or submodule change is run.

The existing reviewed Python binding contract also changes deliberately: only the
foundation registration token fingerprint and a new review note record this one
getter. Other five registration groups, historical notes, signatures, defaults and
ordering are retained. The producer requires each old foundation fingerprint to
match its actual committed/WIP before source, then computes each corresponding new
fingerprint with the unchanged exact-base token helper. This is an explicit API
addition with an authored extension test, rather than a blanket fixture refresh.
