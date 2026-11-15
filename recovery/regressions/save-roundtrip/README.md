# Historical save/reload regression

`history_save_roundtrip.py` launches the recovered game twice on isolated Xvfb displays. The first process creates a save;
the second loads it and saves again. Both must render a real map/player frame and exit cleanly. The complete serialized
map/state must remain equal, ignoring only tile-coordinate ordering in the unordered map.

Run inside the same pinned historical runtime used for the executable. Python 3.12, Qt, `xvfb-run`, and `xauth` are
available in the sealed recovery image. The executable must include `recovery/smoke/game_startup.cpp`. Supply the recorded
Windows file-path compatibility library on Linux if the snapshot needs it.

```sh
python3 scripts/history_save_roundtrip.py \
    --snapshot-dir /path/to/disposable-restored-runtime \
    --executable /path/to/RecoveryGame \
    --preload /path/to/libwindowspaths.so \
    --output-dir /path/to/new-regression-evidence
```

The runtime directory must be an independent disposable snapshot with no existing save data. The script refuses a
nonempty `save/` directory and any existing output directory. It creates only `save/game.sav` through normal game shutdown;
resource files are used by the real game. Retain the compact output reports, saves, and logs before disposing of the
runtime/build scratch. The optional `--preload` argument can be omitted when Windows path compatibility is unnecessary.

The committed before/after diagnostic records a #79 regression: the prior reconstructed Creature serializer saved
already-equipped stats as `initStats`, so reloading applied equipment bonuses again. The corrected reconstruction removes
bonuses using the surviving `Item::loadFromJson`/`onEquip` arithmetic. The same test fails before the correction and passes
afterward. Both binaries render and exit successfully, so the failure specifically detects persisted-state corruption.

This checks the reconstructed nested map/state format and save/reload behavior. The original missing serializer and
#79 map JSON are unavailable; the format is inferred from a later donor, and unknown world-item state is retained opaque.
This is not proof of original gameplay equivalence.
