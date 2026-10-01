# Native routine profiling

The normal `build` workflow runs the required native tests, performance guards,
Python suites and coverage. Native CTest entries retain their 60-second limits.
Case and setup timing records are retained under `coverage/native-test-profiles/`.

The separate **Native routine profiling** workflow runs the complete handler or
map native executable under Callgrind to identify instruction costs and call
chains. It does not replace normal validation. Run it manually with the desired
branch and suite after the workflow is available on `main`; PR changes to its
own workflow, script or regression also run the diagnostic for review.

The diagnostic uses `RelWithDebInfo`, existing engine dependencies and Valgrind
on an isolated GitHub runner. Each complete binary runs through Xvfb with
software rendering and dummy audio. No native test cases, encounter trials,
map dimensions or assertions are removed. The separate 1800-second diagnostic
limit accommodates instrumentation overhead; it does not change CTest limits.
An interrupted or failing run is recorded as partial evidence and cannot pass.

For an existing Linux build and existing tools:

```sh
python3 scripts/profile_native_tests.py \
    --build-dir cmake-build-relwithdebinfo \
    --output-dir test/native-callgrind/manual-unique-run \
    --suite both
```

Existing nonempty output directories are rejected to preserve earlier evidence.
Before executing a binary, the driver also rejects an existing selected
`coverage/native-test-profiles/handler.tsv` or `map.tsv`, which the native
timing recorder would otherwise overwrite. Retain those earlier records with
their run provenance before using the same checkout for another diagnostic.
Artifacts include raw profiles, native stdout/stderr, Callgrind logs, inclusive
and exclusive instruction summaries, and selected commit/build/tool metadata.
The runner does not dump environment variables. Check artifact sizes and retain
only small summaries locally when disk space is constrained; raw evidence stays
in the Actions artifact. Treat case wall time, instruction counts and normal
performance-guard results as separate evidence.
