# Historical recovery checkpoint

The recovery branch is `recovery/bfg-history`. Existing branches, tags, and `main`
are preserved. This is work in progress; historical builds have not passed yet.

## Objective and acceptance

Recover every BFG-damaged historical project tree, including reconstructed files
when exact originals cannot be found. Each distinct repaired tree must compile
and start its real game on Linux under Xvfb, with a loaded map/player, a rendered
frame, and clean shutdown. Exact originals and reconstructions are recorded
separately. Compiled binaries, installers, and IDE state are inventoried rather
than recreated.

The read-only audit found 367 affected commits and 365 distinct trees. There are
1,958 removed blob hashes across 747 historical paths; 72 originals still exist locally.
The earlier 412-path estimate used representative object names and missed renames.
`git fsck --full --no-reflogs --unreachable` found no unreachable objects.

The affected history is a closed graph with these maximal tips:

- `4b3902d44f874a1fae86054d7240a2af76901bb4` (2015-04-28)
- `108bdcbeda04cefeba5e1895f91df023cea8487f` (existing 2013 reconstruction)
- `8965c542530e1e58bb2917bf8d6b756735f57561` (existing 2014 reconstruction)

## Implementation in progress

- Recovery inventory, safe restoration, and separate history replay tooling.
- Reconstruction overlays and per-file provenance.
- Isolated Qt 5 toolchains with historical Python/Boost ABIs.
- Headless startup verification and per-tree CI results.

The existing reconstruction commits are donors, not proven original content.
The intact April-2015 donor is `55e6516e`. Python ABI selection must inspect each
tree: this history switches Python 3 to Python 2 and back to Python 3.

## Resume

```sh
git fetch origin
git switch recovery/bfg-history
git pull --ff-only
git status --short
```

Read this file and the newest commit before continuing. All required recovery
payloads, recipes, and resume instructions will be committed to this branch.
Every logical implementation increment and completed validation shard is pushed.
During longer reconstruction work, checkpoints are pushed at least every fifteen
minutes. Pending, blocked, and failed validation stays explicit.

## Remaining work

Generate the machine-readable inventory, implement and test restoration/replay,
establish the build recipes, reconstruct missing required inputs, and run all
historical build/startup checks. Publish the repaired graph under versioned
`recovery/bfg/` refs and verify a portable bundle. The tooling PR remains draft
until its required checks and the historical acceptance checks have succeeded.

## Latest checkpoint

The complete audit is in `recovery/catalog.json`, frozen to the original refs in
`recovery/original-refs.json`. It identifies 636 generated/IDE blob versions and
1,250 unresolved required blob versions. Recovery and smoke regression tests pass
locally; historical native compilation has not run.

Local Qt installation is blocked: `sudo -n apt-get install -y qtbase5-dev
libqt5opengl5-dev` requires interactive authentication. The CI toolchain is the
primary historical build path.

## Earliest version verified

The December-2013 root (`b9ae428b`) has passed real compilation/linking and
headless startup with a loaded map/player and rendered 1278x718 screenshot.
Evidence is in `recovery/evidence/earliest/`. This focused local reproduction
used rootless Qt 5.15.18 and GCC 15.2; it does not establish the pinned historical
Qt 5.5.1/GCC 5.4 container or the remaining historical versions.

The generator currently proposes 5,420 tree/path replacements; 7,783 required
file occurrences still lack donors, mostly bundled upstream libraries. These
proposals remain unverified until the corresponding builds/startups pass.

Every published repaired version must include a README and its actual startup
screenshot. Publication must reject any remaining `.REMOVED.git-id` marker.

Draft PR: https://github.com/lisu188/fall-of-nouraajd/pull/1653
