# vmeta API version 2 integration

The vstd submodule is pinned to `81da44fbde24db8e50b2704038f43232147cc62f` (vstd PRs #24 and #25). Update existing checkouts with `git submodule update --init --recursive` after pulling this change.

The game now uses upstream reflection macros directly. Const getters and reference-taking setters no longer require the compatibility shim in `CGlobal.h`; a compile-time API-version check prevents accidentally building with the old submodule.

Serializer lookup, text rendering caches, list-view coordinate caches, texture masks, and the event-handler trigger multimap supply `vstd::pair_hash` explicitly. This replaces reliance on non-standard `std::hash` specializations for standard-library pair types without changing their keys or values.

Reflected method results own their values, including copies of C++ reference-returned values. Request value results from `invoke_method`; mutable reference parameters require `std::ref`. Logical property types must be non-reference, copy-constructible values, even when their C++ getters return const references. `std::any` payloads pass through reflection consistently. Duplicate normalized signatures and metadata names fail explicitly. Existing registered game type names are unchanged. The redundant explicit `CCreature::getEffects` registration has been removed; the getter remains registered by the effects property.

Conversion registration and the metadata index are synchronized. Per-object dynamic state and arbitrary user callbacks are not automatically serialized; engine callers retain responsibility for their own synchronization. Copying dynamic descriptors now copies value/callable state, while shared pointers held inside values or captures retain their ordinary sharing behavior. The engine's serialization-based clone and runtime-identity policies are unchanged.

`tests/unit/test_vstd.cpp` adds actual CGameObject integration coverage for base-pointer dispatch, const/reference accessors, owned results, any payloads, explicit mutable references, copied dynamic state, and explicit pair hashers. These tests run through the existing `for_unit_tests.vstd_unit_tests` target and unchanged native CI workflow.

## Measured library performance

The pinned version was compared with `3975b9de3ddb3106a24c420ee94410dd7161d2ea` on the same Ubuntu 24.04 AMD EPYC 7763 GitHub runner. GCC 13.3 and Clang 18.1 used C++23, `-O2 -DNDEBUG -pthread`, and libstdc++. Each case used nine alternating before/after samples of one million calls, 20,000 warmup calls, CPU affinity, expected-result checks, and compiler-verified header paths. Allocation counting was sampled separately.

| Operation | GCC before ns/call | GCC after ns/call | GCC speedup | Clang speedup | Allocations/call before → after |
|---|---:|---:|---:|---:|---:|
| Reflected integer method | 256.52 | 122.44 | 2.10x | 2.01x | 5 → 3 |
| Cached descriptor with reused arguments | 103.29 | 19.74 | 5.23x | 4.08x | 1 → 0 |
| Three integer arguments | 389.01 | 175.19 | 2.22x | 2.15x | 5 → 3 |
| Inherited method | 356.03 | 248.00 | 1.44x | 1.43x | 7 → 5 |
| Static integer property read | 123.36 | 45.20 | 2.73x | 2.69x | 2 → 1 |
| Dynamic integer property read | 62.42 | 37.29 | 1.67x | 1.69x | 1 → 1 |
| Dynamic integer method | 238.39 | 110.84 | 2.15x | 2.10x | 5 → 3 |
| 128-byte string passed by value | 434.86 | 225.80 | 1.93x | 2.03x | 15 → 7 |

These are warm, single-threaded library microbenchmarks, not measurements of game FPS, map loading, save/load, or overall engine performance. The direct-call control was approximately unchanged. Allocation bytes describe cumulative allocation traffic, not resident memory. Ordinary name-based calls still allocate; only the cached integer case was allocation-free.

The complete report is merged into [vstd main](https://github.com/lisu188/vstd/blob/c5fa3fadcbeca620e0ef7fd758a58fb3df5b8081/docs/vmeta-performance-2026-09-21.md). [Validated run 35645104587](https://github.com/lisu188/vstd/actions/runs/35645104587) provides the harness, raw samples, environment, and allocation counts. The earlier run 35644722769 was invalid because both builds selected the same headers and is excluded.
