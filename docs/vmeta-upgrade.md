# vmeta API version 2 integration

The vstd submodule is pinned to `81da44fbde24db8e50b2704038f43232147cc62f` (vstd PRs #24 and #25). Update existing checkouts with `git submodule update --init --recursive` after pulling this change.

The game now uses upstream reflection macros directly. Const getters and reference-taking setters no longer require the compatibility shim in `CGlobal.h`; a compile-time API-version check prevents accidentally building with the old submodule.

Serializer lookup, text rendering caches, list-view coordinate caches, texture masks, and the event-handler trigger multimap supply `vstd::pair_hash` explicitly. This replaces reliance on non-standard `std::hash` specializations for standard-library pair types without changing their keys or values.

Reflected method results own their values, including copies of C++ reference-returned values. Request value results from `invoke_method`; mutable reference parameters require `std::ref`. Logical property types must be non-reference, copy-constructible values, even when their C++ getters return const references. `std::any` payloads pass through reflection consistently. Duplicate normalized signatures and metadata names fail explicitly. Existing registered game type names are unchanged. The redundant explicit `CCreature::getEffects` registration has been removed; the getter remains registered by the effects property.

Conversion registration and the metadata index are synchronized. Per-object dynamic state and arbitrary user callbacks are not automatically serialized; engine callers retain responsibility for their own synchronization. Copying dynamic descriptors now copies value/callable state, while shared pointers held inside values or captures retain their ordinary sharing behavior. The engine's serialization-based clone and runtime-identity policies are unchanged.

`tests/unit/test_vstd.cpp` adds actual CGameObject integration coverage for base-pointer dispatch, const/reference accessors, owned results, any payloads, explicit mutable references, copied dynamic state, and explicit pair hashers. These tests run through the existing `for_unit_tests.vstd_unit_tests` target and unchanged native CI workflow.
