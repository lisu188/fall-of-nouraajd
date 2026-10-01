# Nouraajd player identity payoffs

The existing five player classes and four selectable races retain their stat
packages and starting actions. These optional discoveries and services use
ordinary persistent player properties and do not gate the main campaign.

## Class discoveries

| Class | Discovery | Persistent counter | Later benefit |
| --- | --- | --- | --- |
| Warrior | Brace Nouraajd's gate | `warrior_barricades` | Each paid Barrier cast returns 3 mana. It still requires 17 mana before casting; net cost is 14. |
| Assasin | Follow the robed men from the tavern | `assasin_trails` | Each paid Sneak Attack returns 3 mana. It still requires 15 mana before striking; net cost is 12. |
| Sorcerer | Decode the chapel's stained glass | `sorcerer_sigils` | Each paid Frost Bolt returns 3 mana. It still requires 20 mana before casting; net cost is 17. |
| Inquisitor | Inspect the stained glass | `inquisitor_clues` | Existing Expose Corruption and Sanctified Ward scaling continues unchanged. |
| Wayfarer | Study Irvin's courier routes | `wayfarer_routes` | Existing Smuggler's Mark and Wayfarer's Stride scaling continues unchanged. |

The first three benefits require a positive matching counter and the matching
class identity on the current map's actual player. NPCs and retained inactive
player objects receive no refund. More discoveries never increase the 3 mana
amount. Ability metadata queries are pure; only the native paid action commit
debits the full cost and applies the bounded refund. Direct `performAction`,
previews and rejected actions cannot grant mana. The original experience and
item rewards remain in place, and discovery receipts explain the later benefit.

## Irvin's one-time race aid

The town hall offers one option matching the player's race identity. Irvin's
dialogue recognizes each origin, and the option states its exact cost and limit.

| Race | Aid | Cost |
| --- | --- | --- |
| Human | Release 20 gold from the emergency ration ledger | Free |
| Outlander | Trail rations restore up to 5 health and 5 mana | 5 gold |
| Highlander | The shield bearers' medical chest restores up to 10 health | 5 gold |
| Wanderer | A quiet desk by the star charts restores up to 10 mana | 5 gold |

Recovery is capped by missing resources. Insufficient gold or no relevant
missing resources leaves the aid unclaimed and costs nothing. A successful
claim sets the shared player flag `nouraajdRaceServiceClaimed` and records its
origin in `nouraajdRaceServiceKind`; revisiting, reopening the dialogue or later
changing identity cannot grant a second aid. The receipt lists the actual
health, mana and gold changes.

Existing save serialization and map carryover preserve these properties. Map
entry initializes a missing claim flag but never resets an existing claim or
class discovery. No save schema, selectable roster, progression cap or campaign
victory requirement changes.
