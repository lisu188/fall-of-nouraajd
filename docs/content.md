# Content schema

Reference for author-facing content declarations validated by
`scripts/validate_content.py`. Run the validator locally with:

```
python3 scripts/validate_content.py --repo-root .
```

## Map assets (`map.json` → `assets`)

Each map lives in `res/maps/<name>/` and is described by a Tiled-style
`map.json`. A map may additionally declare the local assets it owns through an
**optional** top-level `assets` array. The declaration is descriptive metadata:
it documents and validates which files, directories, and logical resources a map
depends on. Undeclared assets are not loaded or staged differently yet — engine
loading and CMake staging rules are introduced separately — so adding `assets`
is safe and purely additive for existing maps.

### Shape

```json
{
  "width": 64,
  "height": 64,
  "layers": [ /* ... */ ],
  "assets": [
    { "path": "images/portrait.png", "kind": "file" },
    { "path": "frames", "kind": "directory" },
    { "path": "anim/walk", "kind": "animationRoot" },
    { "path": "hero.combat.idle", "kind": "logicalId", "description": "combat idle pose" }
  ]
}
```

`assets`, when present, must be a JSON array. Each entry is an object with:

| Field         | Required | Description |
| ------------- | -------- | ----------- |
| `path`        | yes      | A safe POSIX-style relative path (or logical id) — see **Path safety**. |
| `kind`        | yes      | One of the kinds below. |
| `description` | no       | Free-form note for authors and reviewers. |

### Kinds

- **`file`** — a single asset file under the map directory
  (for example `images/portrait.png`). The file must exist.
- **`directory`** — a directory of assets under the map directory. The
  directory must exist.
- **`animationRoot`** — an animation base path under the map directory. It
  resolves either to a directory (multi-frame animation) or to a sibling
  `<path>.png` file (single-frame animation), mirroring how the engine resolves
  animations. One of the two must exist.
- **`logicalId`** — a logical asset identifier rather than a filesystem path.
  It is constrained to the same safe-path character rules but is **not** checked
  against the filesystem.

### Path safety

`path` is always interpreted relative to the map's own directory and must stay
within it. The validator rejects a declaration when its `path`:

- is absolute or begins with `/`;
- contains a `..` traversal segment, a `.` segment, or an empty segment;
- contains a backslash (`\`) or a colon (`:`), including Windows drive letters;
- is empty or has surrounding whitespace.

A `path` may not be declared more than once within a single map's `assets`
array.
