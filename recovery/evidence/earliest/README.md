# Earliest recovered game: verified startup

Source commit: `b9ae428bb65478f78f5e7e883ba3b2dd9e0af8ae` (2013-12-07).

The recovered game compiled and linked with GCC 15.2.0 and Qt 5.15.18 on Linux. Its original game entry point ran
on an isolated Xvfb display, loaded the generated map and a healthy player, rendered the attached 1278 × 718 PNG,
and exited normally with status zero. This verifies startup; it does not establish complete historical gameplay
equivalence or successful builds for other snapshots.

`verification.json` records the exact command, input hashes, compiler/qmake identities, restoration provenance,
build output, and startup result. `configure.log`, `build.log`, and `startup.log` contain the actual command output.
`startup.json` and `startup.png` retain the readiness checks and captured viewport. Paths inside those original
records identify the machine and temporary directories used for the check; copied artifacts are beside this file.

This focused check used rootless system Qt packages and the diagnostic recipe in `recipe.json`. The separate pinned
historical toolchain recipes remain the reproducible CI path. Xvfb required execution outside this session's sandbox
because the sandbox denied connecting to the virtual display socket; no test window opened on the user's desktop.
