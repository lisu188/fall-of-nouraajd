# C++ language and library guidelines

First-party C++ targets require C++26 with compiler extensions disabled and no standard fallback, as configured by
`configure_cpp_target()` in `CMakeLists.txt`. CMake 4.0.2 or newer is required; CI provisions 4.3.1. Desktop CI uses
GCC 15 on Ubuntu 26.04 and LLVM 20.1.8 clang-cl with Ninja and the Visual Studio 2022 SDK/STL on Windows 2022.
Configuration probes pack indexing, deleted-function reasons, coroutines, `std::expected`, and
`std::move_only_function`, rejecting incomplete compiler/library combinations before dependency discovery.

Use the [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines) for resource safety,
interfaces, and object lifetimes. The guidelines are a living document; apply them incrementally with tests rather
than treating every recommendation as a reason to rewrite working code.

## Standard-library idioms

- Express substring membership with C++23 `std::string::contains`. Use `starts_with` and `ends_with` for prefixes
  and suffixes. Keep path normalization, root validation, and trust checks alongside these predicates.
- Represent a constant string prefix as `constexpr std::string_view` and use `.size()` when removing it.
  `sizeof` on a string pointer measures the pointer, not the text.
- Use associative-container `.contains(key)` for membership. Retain `.find(key)` when its iterator or value is
  needed and `.count(key)` when multiplicity matters.
- Use `std::ranges` algorithms and projections when they state the operation clearly. Preserve iteration order,
  comparison semantics, and error behavior.
- Use C++23 `std::to_underlying` for enum-to-underlying-value conversions. Preserve intentional conversions to
  other integer types and externally visible numeric representations.
- Default value-type equality when all members participate in equality. Review member changes against that contract.
- Include the standard header that declares each facility directly rather than relying on a precompiled header.
- Use C++26 pack indexing for compile-time argument/type selection when the existing contract is preserved.
- Add a reason to deleted lifetime-unsafe overloads when it explains the required ownership or lifetime.
- Use `std::move_only_function` for owned, one-shot work; reusable and copied observer callbacks retain `std::function`.
- Defer `std::inplace_vector`, `std::function_ref`, and saturation-library replacements until the Windows STL supplies
  them and their behavior has been validated on both desktop toolchains.

## Lifetime contracts

- Own resources with existing RAII types. Do not replace non-owning pointers or deliberately process-lifetime
  objects without understanding their lifetime requirements (Core Guidelines R.1 and R.3).
- A guard that temporarily changes state and restores it at scope exit must have one restoration obligation.
  Delete copying and moving unless a deliberate transfer protocol makes them safe (C.21 and C.81).
- A public polymorphic interface that supports base-pointer destruction needs a virtual destructor. Use a
  defaulted destructor when member cleanup suffices (C.35 and C.80).
- Test scope restoration across nesting and exceptions. Add compile-time traits for lifetime contracts that
  callers must not violate, and verify derived destruction through owning base pointers.

## Compatibility and validation

Check new facilities against the [libstdc++ implementation status](https://gcc.gnu.org/onlinedocs/libstdc++/manual/status.html)
and [Microsoft C++ conformance table](https://learn.microsoft.com/en-us/cpp/overview/visual-cpp-language-conformance).
Selecting C++26 does not imply every draft library facility is available. Use the configured feature probes and both
desktop CI toolchains as the compatibility contract. Android support is deferred and unvalidated; existing Android
checks remain authoritative and must be reported as blockers if they fail.

Use compiler-specific build directories (`cmake-build-gcc15-*` and `cmake-build-clangcl20-*`). Configure scripts
refuse to repurpose a directory for another generator or compiler, preserving cached output and save backups.
GCC coverage uses the matching `gcov-15` executable explicitly in both the Python and optional gcovr reporters.

Follow `AGENTS.md` for focused local checks and required PR validation. Lifetime and path-handling changes need
regression coverage; algorithmic or hot-path changes also need the project's performance evidence. Preserve public
Python/resource interfaces, dependency state, and authored gameplay behavior during mechanical modernization.
