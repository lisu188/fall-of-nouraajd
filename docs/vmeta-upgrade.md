# vmeta API version 2 integration

The vstd submodule is pinned to `32e74e0203a089b219cc3fff2c25b78d3de5d38f` (vstd PR #24). Update existing checkouts with `git submodule update --init --recursive` after pulling this change.

The game now uses upstream reflection macros directly. Const getters and reference-taking setters no longer require the compatibility shim in `CGlobal.h`; a compile-time API-version check prevents accidentally building with the old submodule.

Serializer lookup, text rendering caches, list-view coordinate caches, and texture masks supply `vstd::pair_hash` explicitly. This replaces reliance on non-standard `std::hash` specializations for standard-library pair types without changing their keys or values.

Reflected method results own their values, including copies of C++ reference-returned values. Request value results from `invoke_method`; mutable reference parameters require `std::ref`. `std::any` payloads pass through reflection consistently. Duplicate normalized signatures and metadata names fail explicitly. Existing registered game type names are unchanged.

Conversion registration and the metadata index are synchronized. Per-object dynamic state and arbitrary user callbacks are not automatically serialized; engine callers retain responsibility for their own synchronization. Copying dynamic descriptors now copies value/callable state, while shared pointers held inside values or captures retain their ordinary sharing behavior. The engine's serialization-based clone and runtime-identity policies are unchanged.

`tests/unit/test_vstd.cpp` adds actual CGameObject integration coverage for base-pointer dispatch, const/reference accessors, owned results, any payloads, explicit mutable references, copied dynamic state, and explicit pair hashers. These tests run through the existing `for_unit_tests.vstd_unit_tests` target and unchanged native CI workflow.
