# Navigation

## Gameplay and compatibility contracts

Navigation selects routes; it does not grant movement points or change turn costs. `CMap::move()` still commits at most
one selected step per active creature and increments the map turn once after the simulation cycle. Tile movement costs
affect route selection only, and are clamped to at least one. Ordinary cardinal steps pay destination terrain.
An enabled connector pays `destinationTerrainCost + max(1, edge.movementCost) - 1`; cost 1 preserves existing terrain
pricing. Duplicate connectors choose the cheapest eligible fee, bidirectional links use the return destination's
terrain, and ordinary or wrapped cardinal adjacency takes precedence over an overlapping connector. Disabled links
contribute neither routes nor fees. Cost queries do not grant passability or introduce unregistered connections.

`CMap::lookupNavigationStepCost(from, to)` exposes this rule to Python and route diagnostics. Snapshots freeze the minimum
directed connector fees in storage charged to the session budget; forward search and reverse pursuit use the same
`CNavigationSnapshot::stepCost(from, to)`. Costs and callback return values use 64-bit integers so two large authored
32-bit component costs remain exact. Registering or removing connectors invalidates snapshot and flow state; replace
an edge through those APIs when changing its fee.

The public `CPathFinder` callback API remains available for directed, sparse and negative-coordinate graphs. A successful
path excludes the start and includes the goal. Failure and start-equals-goal preserve the legacy `{start}` sentinel;
`findNextStep` returns the start on failure and retains its future-returning API. Generic callers must provide an
admissible heuristic to obtain minimum-cost paths. Custom edge costs remain edge-dependent and are evaluated for each
candidate rather than cached by destination. Python controller and map APIs retain their signatures.

Equal-cost routes are deterministic for a fixed neighbor order. The indexed heap orders by smallest total estimated
cost, then largest accumulated cost, then first discovery. This reduces expansion of equivalent prefixes; it can select
a different equally optimal route from the previous heap's smaller-accumulated-cost preference. Correctness tests compare
legality and cost, and explicit tie tests cover repeatability.

## Session service and graph snapshots

`CGame` owns a `CNavigationService`; map-owned searches use `CMap::getNavigationService()`. Navigation storage has a shared
128 MiB session budget exposed by `CNavigationBudget`. Snapshots, cached cell chunks, search workspace, flow fields and
retained player/NPC routes use that budget. Allocation failure is an ordinary routing failure, not a reason to grow the cap.
Shared allocations keep their budget alive until their storage and allocator control block have been released.

The map's routing epoch is separate from its broad spatial version. Passability, movement cost, bounds, wrapping,
navigation edges and routing-relevant object changes invalidate the graph. Cosmetic and ordinary nonblocking actor
changes do not require rebuilding static routing data. Snapshots normalize coordinates and index cells in lazily
allocated 32-by-32 chunks; a large map therefore does not require an eager dense allocation for a nearby query. A bounded
change journal supports reuse of unaffected chunks and repair of affected flow cells. When precise changes are no longer
available, consumers rebuild instead of guessing. Dynamic fallback factories use conservative nonpersistent caching.

The map heuristic uses a lower bound on walking distance, including wrapping and registered connector endpoints. A
relaxed connector graph uses each minimum connector fee as a terrain-independent lower bound, accounting for
long-distance and cross-level transitions. Unknown topology or too many
connector endpoints uses a zero heuristic. A raw geometric distance must not overestimate a route that uses a portal.

## Search and resource bounds

`CNavigationSearch` uses 64-bit accumulated costs, reusable generation-stamped records for finite map chunks and sparse
records for generic graphs. One indexed four-way heap entry per open node supports decrease-key and reopening. The
next-step operation propagates the first step and does not reconstruct a whole path.

Results distinguish `Found`, `Unreachable`, `ResourceLimit`, `Cancelled`, `InvalidInput` and `Deferred`; compatibility
adapters translate these to existing sentinel results. A result produced against a changed snapshot cannot commit a
stale route. Default search limits are one million records, one million expansions and 100,000 returned path steps, in
addition to the shared memory cap. Tests can inject smaller limits to exercise bounded failure deterministically.

The previous generic search also imposed a geometric envelope of `4 * endpoint Manhattan distance + 512`. It could
reject a valid 1,201-step directed detour whose endpoints are only one cell apart. Explicit record, expansion and byte
limits replace that correctness-breaking envelope. The unbounded-plane regression now checks those explicit limits;
this is a change in what is bounded, not a silent widening of a geometric budget. Existing finite-workload callback
budgets remain independent regression gates.

## Pursuit and committed player routes

Target controllers share bounded reverse fields keyed by map and target identity. Moving goals and local graph changes
repair the field rather than discard every computed distance. Field work is bounded per start and turn, so repeated
calls in the same turn cannot bypass the limit. `Deferred` leaves the actor in place and resumes later; a partial field
must never become an arbitrary movement decision. Changes without safe incremental provenance rebuild the field.

A player route stores a contiguous vector with a cursor. A coordinate index points to the earliest remaining occurrence
and links repeated occurrences, preserving overlay direction without scanning the entire path for every visible cell.
The route vector, occurrence links and index are charged to the session budget. Interrupting or completing a route
releases them. Legal committed routes survive unrelated routing edits; every next step still validates its destination
and neighbor relationship. A blocked or displaced route is abandoned and does not resume just because the obstacle
later disappears.

NPC wandering also retains a budgeted vector from the session search service. Re-reading the same decision does not
search again. A blocked or stale cached route returns the current cell immediately; a later wandering poll may choose
a fresh random destination, preserving autonomous wandering without resuming the abandoned route. Creature, map,
installed controller, origin and session-generation checks prevent reusing a route across owners or transitions.
Direct calls to an NPC controller that was never installed on the creature remain supported; the installed-controller
identity check applies only when that controller owned the creature's movement slot when the route was created.

World inspection plans a destination without moving the player or advancing turns. Repeated inspection of an unchanged
destination reuses that route, and explicit Enter/click commit performs no second search. A preview records map, player,
controller, session generation, origin, routing epoch and controller request serial. A change to any of them invalidates
the preview. Cancellation only interrupts the route that the preview owns; it must not cancel a newer external order.
Scene changes, interrupts and new targets advance the request identity. Movement commitment rechecks those identities
between steps.

## Validation and profiling

The focused native suites cover search-oracle agreement, weighted and directed edges, large costs, cheap portals,
wrapping, level transitions, dynamic invalidation, bounded storage, flow repair, controller continuity and preview reuse.
`navigation_preview_unit_tests` additionally drives real SDL input on a dummy/software display and checks that 20,000
overlay lookups on a 4,096-step route perform exactly 20,000 indexed probes without retained allocations or new searches.
`tests.test_navigation_mcp` drives the real authored multilevel map through stdio MCP, including a blocked committed
destination, explicit retargeting, stairs and both authored goal triggers. It uses the existing stderr-draining harness
and never creates a GUI.

The same Python module includes a 30-second isolated-process guard for a real mixed-controller map turn. An asynchronous
target controller and a synchronous range controller both query a Python fallback tile factory. The factory yields the
GIL and uses a bounded event rendezvous; worker and owner-thread callbacks must both finish without holding the map
routing lock across user code. The test verifies actual movement, the stationary player and exactly one completed turn.

Timing is supplemental evidence. The opt-in [profiling driver](../scripts/navigation_profile/README.md) fixes inputs,
warms them twice and reports seven samples and their median. Its retained pre-change measurements distinguish completed
cases from an interrupted large authored-map query. Native performance guards use deterministic expansions, callbacks,
allocation, reuse and invalidation counts; elapsed-time ratios do not replace those gates.
