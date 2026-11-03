# Immutable native terrain

Maps may opt into a position-dependent native tile raster with the `staticTerrainData` string property in
`map.json`. An absent or empty property preserves the existing tile and fallback behavior. No shipped map currently
enables this capability; the Baldur's Gate maze conversion remains separate work.

The string contains a version-1 JSON descriptor with a `levels` array. Each level supplies `area`, `level`, `width`,
`height`, `palette` and `rows`. Rows contain one lowercase hexadecimal palette index per cell. Palette entries contain
the exact resource `type` and its native `configuration`. For example, a development builder can construct this
descriptor with `json.dumps` and place that resulting string in the map property.

Admission accepts only unchanged, primitive `CTile` configurations. Supported properties are boolean `canStep`,
nonnegative integer `movementCost`, and string `animation`, `label`, `description` and `tileType`. A palette cannot
contain references, effects or scripted tile behavior. Resource-handler identity and its configuration revision bind
the admitted palette. Changed or replaced resources must be revalidated before an unmaterialized cell is read.

Descriptors are bounded to 131,072 bytes, eight levels, sixteen palette entries per level and 65,536 cells in total.
Dimensions and integers are checked before narrowing, and a depth preflight precedes JSON parsing. Each raster needs
enclosing authored bounds with wrapping disabled. A level can cover part of its enclosing bounds; undeclared cells
retain the authored fallback policy.

Navigation reads scalar collision and cost without creating tile objects. A fallback outside the raster may use a
scalar only when its exact resource ID belongs to that level's already validated palette. Other fallbacks and
unopted maps retain their constructor behavior. A materialized tile always takes precedence over the immutable base.
The existing minimum movement cost of one is retained.

`getTile` creates the normal canonical tile at the queried coordinate. Subsequent queries return that same object,
and its complete mutable state remains in the ordinary serialized tile set. Mutating a promoted tile invalidates
navigation. The descriptor is immutable after admission and is saved alongside that overlay. Verified restore checks
it against the authored descriptor; an altered saved descriptor cannot replace the active map. Empty descriptors are
omitted from legacy serialized maps.

The native map regressions cover position-dependent collision, the six-step test maze, canonical promotion,
configuration and bounds rejection, legacy behavior, real save/reload and changed-descriptor rejection. The native
performance guard counts factory callbacks and recipes, checks snapshot/chunk reuse and routing epochs, bounds search
work, and counts actual serialization getter visits. Its small fixed fixture establishes those work contracts; it
does not establish a city-wide workload, performance speedup or original-game fidelity.

Fine AR0146 activation still requires its coordinate/transition migration, existing city cell-budget checks,
minimap behavior, escaped tile aliases, deletion/tombstone policy, RNG review, current-head gameplay and visual
evidence. This foundation does not relax those requirements or the interaction ledger.
