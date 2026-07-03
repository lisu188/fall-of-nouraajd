# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Compound (Heroes 3-style) artifact sets.

Set definitions live in ``res/config/artifact_sets.json``. When every piece of a
set is equipped, the player is offered to fuse them into a single combined
artifact that occupies all the pieces' slots (via the engine ``coveredSlots``
occupancy rule) and grants a stronger bonus plus an active ability. The combined
artifact can be disassembled back into its pieces by using it from the inventory.

See ``docs/design/compound_artifacts.md`` for the full design.
"""
import json

import game
from game import register

ASSEMBLE_PREFIX = "Assemble the "
DISASSEMBLE_PREFIX = "Disassemble the "
DECLINE_ASSEMBLE = "Not now"
DECLINE_DISASSEMBLE = "Keep it whole"
CURSED_TAG = "cursed"


def _read_config_json(filename):
    try:
        return json.loads(game.CResourcesProvider.getInstance().load("config/" + filename))
    except Exception:
        return {}


class ArtifactSetRuntime:
    """Loads and interprets ``artifact_sets.json`` and drives assembly."""

    def __init__(self):
        self._sets = self._load_sets()
        self._by_combined = {definition["combined"]: definition for definition in self._sets.values()}

    def _load_sets(self):
        sets = {}
        for set_id, payload in _read_config_json("artifact_sets.json").items():
            if not isinstance(payload, dict):
                continue
            pieces = payload.get("pieces") or []
            combined = payload.get("combined")
            if not pieces or not combined:
                continue
            sets[set_id] = {
                "id": set_id,
                "label": payload.get("label", set_id),
                "pieces": list(pieces),
                "combined": combined,
            }
        return sets

    def all_sets(self):
        return list(self._sets.values())

    def set_for_combined(self, item_id):
        return self._by_combined.get(item_id)

    @staticmethod
    def _equipped_by_type(player):
        equipped = {}
        for _slot, item in player.getEquipped().items():
            if item is not None:
                equipped[item.getTypeId()] = item
        return equipped

    def completed_sets(self, player):
        """Return the set definitions whose every piece is currently equipped."""
        equipped = self._equipped_by_type(player)
        completed = []
        for definition in self._sets.values():
            if all(piece_id in equipped for piece_id in definition["pieces"]):
                completed.append(definition)
        return completed

    def _has_cursed_piece(self, player, definition):
        equipped = self._equipped_by_type(player)
        return any(
            equipped[piece_id].hasTag(CURSED_TAG) for piece_id in definition["pieces"] if piece_id in equipped
        )

    def assemble(self, game_instance, player, definition):
        """Fuse an equipped set into its combined artifact. Returns True on success."""
        equipped = self._equipped_by_type(player)
        piece_items = []
        for piece_id in definition["pieces"]:
            item = equipped.get(piece_id)
            if item is None:
                return False
            # A cursed piece is locked to its slot and cannot be pulled into the
            # combined artifact; refuse the whole assembly until the curse is lifted.
            if item.hasTag(CURSED_TAG):
                return False
            piece_items.append(item)

        # Build the combined artifact first so a failed creation never consumes the
        # pieces (leaving the player with nothing).
        combined = game_instance.getObjectHandler().createObject(game_instance, definition["combined"])
        if combined is None:
            return False

        # Unequip every piece (each returns to inventory) so the combined artifact's
        # covered slots are free, then consume the piece instances.
        for item in piece_items:
            slot = player.getSlotWithItem(item)
            if slot:
                player.equipItem(slot, None)
        for piece_id in definition["pieces"]:
            player.removeItem(lambda held, target=piece_id: held.getTypeId() == target, True)

        player.addItem(combined)
        primary_slot = self._primary_slot(game_instance, combined)
        if primary_slot is not None:
            player.equipItem(primary_slot, combined)
        return True

    def disassemble(self, game_instance, player, combined_item):
        """Break a combined artifact back into its pieces. Returns True on success."""
        definition = self.set_for_combined(combined_item.getTypeId())
        if definition is None:
            return False
        slot = player.getSlotWithItem(combined_item)
        if slot:
            # A cursed combined artifact cannot leave its slot, so it cannot be split.
            if combined_item.hasTag(CURSED_TAG):
                return False
            player.equipItem(slot, None)
        combined_name = combined_item.getName()
        player.removeItem(lambda held, target=combined_name: held.getName() == target, True)
        for piece_id in definition["pieces"]:
            piece = game_instance.getObjectHandler().createObject(game_instance, piece_id)
            if piece is not None:
                player.addItem(piece)
        return True

    @staticmethod
    def _primary_slot(game_instance, combined):
        fitting = game_instance.getSlotConfiguration().getFittingSlots(combined)
        for slot in fitting:
            return slot
        return None


_RUNTIME = None


def get_runtime():
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = ArtifactSetRuntime()
    return _RUNTIME


def maybe_offer_assembly(player):
    """Offered when a set completes: prompt the player to assemble each ready set."""
    if player is None or not player.isPlayer():
        return
    runtime = get_runtime()
    game_instance = player.getGame()
    handler = game_instance.getGuiHandler()
    for definition in runtime.completed_sets(player):
        if runtime._has_cursed_piece(player, definition):
            continue
        assemble_option = ASSEMBLE_PREFIX + definition["label"]
        options = [assemble_option, DECLINE_ASSEMBLE]
        selection = handler.showSelection(game.list_string(game_instance, options))
        if selection == assemble_option and runtime.assemble(game_instance, player, definition):
            handler.showInfo("The pieces fuse into the " + definition["label"] + ".", True)


def offer_disassembly(combined_item, player):
    """Prompt to break a combined artifact back into its pieces."""
    if player is None or not player.isPlayer():
        return
    runtime = get_runtime()
    definition = runtime.set_for_combined(combined_item.getTypeId())
    if definition is None:
        return
    game_instance = player.getGame()
    handler = game_instance.getGuiHandler()
    disassemble_option = DISASSEMBLE_PREFIX + definition["label"]
    options = [disassemble_option, DECLINE_DISASSEMBLE]
    selection = handler.showSelection(game.list_string(game_instance, options))
    if selection == disassemble_option and runtime.disassemble(game_instance, player, combined_item):
        handler.showInfo("You separate the " + definition["label"] + " into its pieces.", True)


def _schedule_assembly_offer(event):
    # onEquip fires *before* the engine records the item into the equipped map, so
    # defer the completeness check to the event loop: by the time it runs, the just
    # equipped piece is in place and unequipping pieces during assembly is safe.
    player = event.getCause()
    if player is None or not player.isPlayer():
        return
    game.event_loop.instance().invoke(lambda: maybe_offer_assembly(player))


def load(self, context):
    from game import CArmor
    from game import CBelt
    from game import CBoots
    from game import CGloves
    from game import CHelmet
    from game import CPants
    from game import CShield
    from game import CSmallWeapon
    from game import CWeapon

    # --- Set pieces: equipping one offers to assemble any now-complete set. ---

    @register(context)
    class SetHelmet(CHelmet):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetArmor(CArmor):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetWeapon(CWeapon):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetSmallWeapon(CSmallWeapon):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetShield(CShield):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetBoots(CBoots):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetGloves(CGloves):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetBelt(CBelt):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    @register(context)
    class SetPants(CPants):
        def onEquip(self, event):
            _schedule_assembly_offer(event)

    # --- Combined artifacts: using one from the inventory offers to disassemble it. ---

    @register(context)
    class CompoundArmor(CArmor):
        def onUse(self, event):
            offer_disassembly(self, event.getCause())

    @register(context)
    class CompoundWeapon(CWeapon):
        def onUse(self, event):
            offer_disassembly(self, event.getCause())

    @register(context)
    class CompoundHelmet(CHelmet):
        def onUse(self, event):
            offer_disassembly(self, event.getCause())

    @register(context)
    class CompoundShield(CShield):
        def onUse(self, event):
            offer_disassembly(self, event.getCause())
