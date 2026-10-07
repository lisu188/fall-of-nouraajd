# C++ language and library guidelines

First-party C++ targets require C++23 with compiler extensions disabled, as configured by
`configure_cpp_target()` in `CMakeLists.txt`. Keep new code compatible with the Linux and Visual Studio 2022
toolchains exercised by the build workflow. Do not change vendored libraries or submodules merely to apply these rules.

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
Selecting C++23 does not imply every library facility is available in every compiler release. Avoid draft language
features or unnecessary compatibility layers for facilities already supported by both CI toolchains.

Follow `AGENTS.md` for focused local checks and required PR validation. Lifetime and path-handling changes need
regression coverage; algorithmic or hot-path changes also need the project's performance evidence. Preserve public
Python/resource interfaces, dependency state, and authored gameplay behavior during mechanical modernization.
