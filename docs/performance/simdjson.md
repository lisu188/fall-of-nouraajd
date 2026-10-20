# JSON parsing performance

The game keeps simdjson's DOM parser and reduces the work around it: reuse a
parser and padded input buffer per thread, reserve each decoded array once, and
insert each decoded object key once. Values remain owning and object keys remain
sorted. Duplicate decoded keys and malformed documents still fail.

Inputs up to 4 MiB use retained storage. Larger inputs and reentrant calls use
temporary contexts. The limit describes input retention; simdjson's tape and
string buffers require additional memory. Diagnostic counters are compiled only
into the focused test adapter, not the production parser.

## Reproduce

The focused build needs a C++17 compiler and CMake, without SDL, Python headers,
or a complete game build. Run from the repository root:

```sh
cmake -S tests/json -B /tmp/nouraajd-json-build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/nouraajd-json-build --target json_parse_regression json_parse_benchmark -j 4
ctest --test-dir /tmp/nouraajd-json-build --output-on-failure --verbose
python3 scripts/profile_json.py --repo-root . \
    --benchmark /tmp/nouraajd-json-build/json_parse_benchmark \
    --rounds 10 --samples 9 --comparisons 3 --output /tmp/nouraajd-json-profile.json
```

The benchmark compares a test-only copy of the previous adapter with the current
implementation. Each process warms the corpus, then measures parsing and result
destruction. File reads and owning-tree fingerprints are outside the timed region.
The report records input hashes, binary hashes, commands, individual samples,
acceptance, fingerprints, allocation requests, and process peak RSS. A successful
driver invocation is not a performance pass: inspect `meets_parse_gate`.

Normal game builds register the regression under `for_unit_tests` and the
deterministic work budgets under the `performance` CTest label. The benchmark
remains opt-in. The budgets require zero parser/scratch growth after warm-up,
one decode per value, one insertion per object key, and one reservation for a
4096-element array. They also check that oversized inputs do not expand retained
storage. Timing is not a CI gate.

## Measured result

Linux x86-64, Intel Core i5-14400F, GCC 13.3, Release `-O3 -DNDEBUG`, simdjson 4.6.4
with runtime CPU dispatch. The corpus contains 79 files and 5,225,881 bytes from
map/config resources and save-compatibility fixtures. Both adapters accept 78
and reject the same invalid fixture; all accepted owning-tree fingerprints match.

| Comparison | Previous adapter, ms | Optimized DOM, ms | Reduction |
| --- | ---: | ---: | ---: |
| 1 | 716.024 | 380.733 | 46.83% |
| 2 | 707.454 | 385.007 | 45.58% |
| 3 | 698.333 | 358.070 | 48.73% |

Each median covers ten corpus rounds and nine samples; baseline/candidate process
order alternates. Requested C++ allocation bytes per ten rounds fell from
2,347,310,530 to 716,620,400 (69.5%). Peak process RSS was approximately 154.5 MB
versus 96.2 MB (37.7% lower). The allocation counters cover `new`/`new[]` requests,
including result destruction, and exclude direct `malloc`. RSS includes the
preloaded corpus. Cold-process single samples are diagnostic only.

A fully owning On-Demand decoder was also tested. It improved on the previous
adapter but was 5.7–23.7% slower than the optimized DOM stage in three direct
alternating comparisons. Exact array reservation made the DOM stage preferable
for this numeric-array-heavy corpus. The On-Demand candidate was discarded under
the staged performance gate and is not a production backend.

These are parsing results. They do not establish the same percentage improvement
for complete map or save loading, and Windows runtime performance was not measured
locally. GitHub Actions supplies the full game, Windows, and coverage validation.
