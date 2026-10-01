# Navigation

Movement costs select routes. Each committed controller step still consumes one ordinary engine turn;
costs do not introduce movement points or additional turns.

`CMap::lookupNavigationStepCost(from, to)` is the shared cost query for player and NPC A*, target-controller
reverse flow fields, and path diagnostics. It normalizes endpoints and reads destination terrain through
the nonmaterializing `lookupMovementCost` query:

- Ordinary cardinal movement costs the destination terrain's positive `movementCost`.
- An enabled connector costs `destinationTerrainCost + max(1, edge.movementCost) - 1`.
- Default connector cost 1 adds no surcharge, preserving existing terrain pricing.
- Bidirectional connections use the reverse destination's terrain cost on the return trip.
- Duplicate connections use the cheapest eligible cost. Ordinary adjacency wins over a costlier connector
  joining those same cells. Disabled connections contribute neither neighbors nor connector costs.

For example, a connector with cost 8 entering terrain with cost 3 costs 10. The cost query does not grant
passability or create an unregistered connection. Registering/removing edges invalidates cached navigation;
replace an edge through those APIs when its cost changes.

Cost lookup leaves sparse tiles and navigation revisions unchanged. Step and accumulated costs saturate
at the integer limit; routes whose accumulated cost cannot be represented are not relaxed. This prevents
extreme authored costs from wrapping into cheap negative routes.

Maps with enabled connectors use a zero A* heuristic so distant or multilevel shortcuts remain admissible.
Ordinary maps retain their geometric heuristic. Reverse flow expansion prices the forward edge
`previous -> current`, rather than reversing its directed cost.
