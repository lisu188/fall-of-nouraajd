# Testing

## Repository prep
Run from the repository root after a fresh checkout:

```bash
git submodule update --init --recursive
./configure.sh
```

## Normal test workflow
Run from the repository root:

```bash
cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
python3 test.py
```

## Coverage workflow
Run from the repository root when a change touches tests (for example
`test.py` or `tests/unit/**`), `src/core/**`, `src/handler/**`,
`src/object/**`, or the coverage tooling:

```bash
./scripts/run_coverage.sh
```

The script:
- configures a dedicated coverage build (`cmake-build-coverage`)
- builds `_game` with GCC/Clang coverage flags
- runs `python3 test.py` against the coverage build
- generates reports in `coverage/coverage.txt` and `coverage/coverage.html`
- uses `gcovr` when available and falls back to the repo-local `gcov` parser otherwise
- fails if line coverage in the scoped target is below 80%

## Coverage scope
Included paths:
- `src/core/**`
- `src/handler/**`
- `src/object/**`

Explicit exclusions:
- `src/gui/**` (out of scope for this runtime target)
- `vstd/**` (external utility library)
- `random-dungeon-generator/**` (external generator dependency)
- build/package directories (`cmake-build*`, `build*`, `package*`)
- generated/binding boilerplate that is not realistic to unit test directly:
  - `src/core/CModule.cpp`
  - `src/core/CWrapper.h`
  - `src/core/CTypes.cpp`
  - `src/core/CTypes.h`
  - `src/core/CJsonUtil.h`
