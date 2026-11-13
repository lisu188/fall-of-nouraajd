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
1,958 removed blob hashes across 412 paths; 72 originals still exist locally.
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
