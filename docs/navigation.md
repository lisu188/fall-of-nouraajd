# Navigation

## Movement-cost decision

Movement cost is a route-selection contract for phase 1. It is not a turn-budget or extra turn-consumption contract.

Current source state:

- `CPathFinder` supports weighted route selection through its `StepCost` callback.
- `CMap::getMovementCost(...)` normalizes coordinates, materializes a missing default tile through `getTile(...)`, and
  currently returns `1`.
- `CNavigationEdge::movementCost` is stored and exposed, but `CMap::getNavigationNeighbors(...)` returns only neighbor
  coordinates, so the edge cost is not applied by map-owned navigation yet.
- Player and NPC map controllers currently call `CPathFinder` with map neighbors and map distance, but without a
  map-provided step-cost callback. Target-controller flow fields also add `1` per step.
- `CMap::move()` commits at most one controller-selected step per active creature and increments the map turn once after
  the simulation cycle; it does not consume turns or movement budget based on movement cost.

Future movement-cost implementation should first wire movement cost into route selection only. Any turn-budget or
multi-step-per-turn behavior needs separate source evidence, design, and regression coverage.
