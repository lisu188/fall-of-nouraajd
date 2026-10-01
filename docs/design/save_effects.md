# Active effects in saves and clones

Save schema 2 preserves an active effect's configured duration, remaining time,
stat bonus, caster, and victim. Reloading a partially elapsed effect continues
from that state; it does not recast the originating interaction.

Effect actor references use IDs local to one serialized snapshot. They do not use
object names or look up actors in the currently active map. References between
actors in a saved map resolve to the restored actors, regardless of their order
in the snapshot.

An effect can retain a caster that has died, left the map, or otherwise been
removed from its object list. The snapshot includes that detached actor's state
once, along with any further actor references its effects need. Loading retains
the actor as detached. It does not spawn the actor back onto the map or make it
eligible for combat rewards. Mutual effects are recorded through references so
they do not cause recursive serialization of the same actors.

Cloning distinguishes the cloned object from external actors. A creature's
self-effects refer to the cloned creature, while effects from another creature
retain that external caster. A standalone effect clone retains its actor
references; casting code can then assign its new caster and victim. Cloning a
map remaps references to actors included in that map.

Reference resolution is scoped to the save/load or clone operation. Invalid or
duplicate actor IDs in a new snapshot are rejected during strict loading, so the
existing saved-game backup recovery can handle the failed load.

Cycles through ordinary reflected ownership properties remain unsupported and
are rejected when they revisit an actor still being serialized or loaded. This
does not restrict self-effects or mutual effect references.

## Compatibility

Legacy unversioned saves and schema 0/1 saves remain readable. Their missing
effect runtime state cannot be reconstructed reliably: the old format did not
record remaining time, configured bonuses, or actor identity. Loading preserves
their existing initialization behavior instead of guessing an originating spell
or changing which effects are active.

New saves use schema 2. Older game builds reject that version rather than load it
and silently discard effect references. The campaign-manifest schema is
independent and remains unchanged.
