def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import CPlayer
    from game import CDialog
    from game import Coords
    from game import register, trigger

    VICTOR_COURTYARD_TIMEOUT_TURNS = 75
    VICTOR_CULTIST_PREFIX = "victorCultist"

    def _clear_victor_encounter(game_map):
        def should_remove(obj):
            name = obj.getName()
            return bool(name) and (name == "cultLeaderQuest" or name.startswith(VICTOR_CULTIST_PREFIX))

        game_map.removeAll(should_remove)
        game_map.setNumericProperty("VICTOR_COURTYARD_TURN", -1)

    def _expire_victor_search(game_map):
        quest_system = _get_quest_system(game_map)
        if quest_system.get_state("victor") != "encounter_active":
            return False
        spawn_turn = game_map.getNumericProperty("VICTOR_COURTYARD_TURN")
        if spawn_turn < 0:
            return False
        if game_map.getTurn() - spawn_turn < VICTOR_COURTYARD_TIMEOUT_TURNS:
            return False
        quest_system.mark_victor_bad_end()
        _clear_victor_encounter(game_map)
        game_map.getGame().getGuiHandler().showMessage(
            "You find the courtyard scrubbed bare; Victor's daughter is gone, carried off with the cult's hush."
        )
        return True

    class _TrackedQuest:
        def __init__(self, name):
            self._name = name

        def getName(self):
            return self._name

    _player_quests = {}

    def _reset_player_quests(player):
        _player_quests.clear()

    def _ensure_player_quest_api(player):
        if not isinstance(_player_quests, dict):
            _player_quests.clear()

    def _player_has_quest(player, quest_name):
        _ensure_player_quest_api(player)
        return quest_name in _player_quests

    def _grant_quest(player, quest_name):
        if _player_has_quest(player, quest_name):
            return
        _player_quests[quest_name] = _TrackedQuest(quest_name)
        player.addQuest(quest_name)

    def _python_get_quests(self):
        _ensure_player_quest_api(self)
        return list(_player_quests.values())

    CPlayer.getQuests = _python_get_quests

    _QUEST_SYSTEMS = {}

    def _quest_state_key(game_map):
        return game_map.getName()

    def _get_quest_system(game_map):
        key = _quest_state_key(game_map)
        system = _QUEST_SYSTEMS.get(key)
        if system is None or system.is_stale(game_map):
            system = QuestSystem(game_map)
            _QUEST_SYSTEMS[key] = system
        return system

    def _quest_system_from(obj):
        return _get_quest_system(obj.getGame().getMap())

    class QuestSystem:
        QUEST_KEYS = {
            "rolf": "quest_state_rolf",
            "main": "quest_state_main",
            "beren_chain": "quest_state_beren_chain",
            "octobogz_contract": "quest_state_octobogz_contract",
            "amulet": "quest_state_amulet",
            "victor": "quest_state_victor",
        }

        QUEST_DEFAULTS = {
            "rolf": "awaiting_skull",
            "main": "locked",
            "beren_chain": "letter_pending",
            "octobogz_contract": "not_started",
            "amulet": "not_started",
            "victor": "not_started",
        }

        def __init__(self, game_map):
            self.map = game_map

        def is_stale(self, game_map):
            return self.map != game_map

        def _key(self, quest):
            return self.QUEST_KEYS[quest]

        def get_state(self, quest):
            state = self.map.getStringProperty(self._key(quest))
            if not state:
                state = self.QUEST_DEFAULTS[quest]
                self.map.setStringProperty(self._key(quest), state)
            return state

        def _set_state(self, quest, state, sync=True):
            self.map.setStringProperty(self._key(quest), state)
            if sync:
                self._sync_legacy_flags()

        def reset_all(self):
            for quest, state in self.QUEST_DEFAULTS.items():
                self.map.setStringProperty(self._key(quest), state)
            self.map.setNumericProperty("VICTOR_COURTYARD_TURN", -1)
            self._sync_legacy_flags()

        def initialize_defaults(self):
            changed = False
            for quest, state in self.QUEST_DEFAULTS.items():
                if not self.map.getStringProperty(self._key(quest)):
                    self.map.setStringProperty(self._key(quest), state)
                    changed = True
            if changed:
                self.map.setNumericProperty("VICTOR_COURTYARD_TURN", -1)
                self._sync_legacy_flags()

        # --- Compatibility helpers ---
        def _beren_flags(self):
            state = self.get_state("beren_chain")
            delivered = state not in ("letter_pending", "letter_in_hand")
            relic_returned = state in (
                "relic_returned_waiting_kill",
                "ready_to_report",
                "purged",
            )
            octobogz_slain = state in ("octobogz_slain_no_relic", "ready_to_report", "purged")
            octobogz_cleared = state in ("ready_to_report", "purged")
            cave_purged = state == "purged"
            return delivered, relic_returned, octobogz_slain, octobogz_cleared, cave_purged

        def _victor_flags(self):
            state = self.get_state("victor")
            started = state in ("records_reviewed", "courtyard_known", "encounter_active", "good_end", "bad_end")
            courtyard_found = state in ("courtyard_known", "encounter_active", "good_end", "bad_end")
            encounter_active = state == "encounter_active"
            good_end = state == "good_end"
            bad_end = state == "bad_end"
            return started, courtyard_found, encounter_active, good_end, bad_end

        def _sync_legacy_flags(self):
            self.map.setBoolProperty("completed_rolf", self.get_state("rolf") == "skull_recovered")
            self.map.setBoolProperty("completed_gooby", self.get_state("main") == "gooby_slain")

            (
                delivered,
                relic_returned,
                octobogz_slain,
                octobogz_cleared,
                cave_purged,
            ) = self._beren_flags()
            self.map.setBoolProperty("DELIVERED_LETTER", delivered)
            self.map.setBoolProperty("RELIC_RETURNED", relic_returned)
            self.map.setBoolProperty("OCTOBOGZ_SLAIN", octobogz_slain)
            self.map.setBoolProperty("OCTOBOGZ_CLEARED", octobogz_cleared)
            self.map.setBoolProperty("CAVE_PURGED", cave_purged)

            contract_state = self.get_state("octobogz_contract")
            self.map.setBoolProperty("completed_octobogz", contract_state == "completed")

            amulet_state = self.get_state("amulet")
            self.map.setBoolProperty("AMULET_QUEST_STARTED", amulet_state == "active")
            self.map.setBoolProperty("AMULET_RETURNED", amulet_state == "returned")

            (
                victor_started,
                courtyard_found,
                encounter_active,
                victor_good,
                victor_bad,
            ) = self._victor_flags()
            self.map.setBoolProperty("VICTOR_QUEST_STARTED", victor_started)
            self.map.setBoolProperty("VICTOR_COURTYARD_FOUND", courtyard_found)
            self.map.setBoolProperty("VICTOR_CULTISTS_SPAWNED", encounter_active)
            self.map.setBoolProperty("VICTOR_GOOD_END", victor_good)
            self.map.setBoolProperty("VICTOR_BAD_END", victor_bad)
            self.map.setBoolProperty("VICTOR_HELP", victor_good)
            self.map.setBoolProperty("VICTOR_REWARD_CLAIMED", victor_good)

        # --- Rolf / Gooby ---
        def ensure_main_quest(self, player):
            if self.get_state("main") == "locked":
                self._set_state("main", "awaiting_gooby")
                _grant_quest(player, "mainQuest")

        def mark_rolf_skull_found(self, player):
            if self.get_state("rolf") != "skull_recovered":
                self._set_state("rolf", "skull_recovered")
                self.ensure_main_quest(player)

        def mark_gooby_slain(self):
            if self.get_state("main") != "gooby_slain":
                self._set_state("main", "gooby_slain")

        # --- Letter / relic / cleanse chain ---
        def give_letter(self, player):
            state = self.get_state("beren_chain")
            if state == "letter_pending":
                self._set_state("beren_chain", "letter_in_hand")
                _grant_quest(player, "deliverLetterQuest")
                return True
            if state == "letter_in_hand":
                return True
            return False

        def mark_letter_delivered(self, player):
            prior = self.get_state("beren_chain")
            if prior in ("letter_pending", "letter_in_hand"):
                self._set_state("beren_chain", "letter_delivered")
                _grant_quest(player, "retrieveRelicQuest")
            elif prior == "relic_obtained":
                self._set_state("beren_chain", "relic_obtained")
                _grant_quest(player, "retrieveRelicQuest")
            else:
                self._sync_legacy_flags()

        def mark_relic_obtained(self):
            state = self.get_state("beren_chain")
            if state in ("letter_delivered", "relic_obtained"):
                self._set_state("beren_chain", "relic_obtained")

        def mark_relic_returned(self):
            state = self.get_state("beren_chain")
            if state in ("relic_obtained", "relic_returned_waiting_kill"):
                self._set_state("beren_chain", "relic_returned_waiting_kill")
            elif state == "octobogz_slain_no_relic":
                self._set_state("beren_chain", "ready_to_report")

        def mark_octobogz_slain(self):
            state = self.get_state("beren_chain")
            if state in ("relic_returned_waiting_kill", "ready_to_report", "purged"):
                self._set_state("beren_chain", "ready_to_report")
            elif state in ("relic_obtained", "letter_delivered"):
                self._set_state("beren_chain", "octobogz_slain_no_relic")

        def mark_cave_purged(self):
            if self.get_state("beren_chain") == "ready_to_report":
                self._set_state("beren_chain", "purged")

        # --- OctoBogz travelers ---
        def activate_octobogz_contract(self):
            if self.get_state("octobogz_contract") == "not_started":
                self._set_state("octobogz_contract", "active")
            else:
                self._sync_legacy_flags()

        def complete_octobogz_contract(self):
            if self.get_state("octobogz_contract") != "completed":
                self._set_state("octobogz_contract", "completed")

        # --- Amulet quest ---
        def start_amulet(self):
            if self.get_state("amulet") == "not_started":
                self._set_state("amulet", "active")

        def finish_amulet(self):
            self._set_state("amulet", "returned")

        # --- Victor quest ---
        def record_met_victor(self):
            state = self.get_state("victor")
            if state == "not_started":
                self._set_state("victor", "met_victor")

        def record_victor_records(self):
            state = self.get_state("victor")
            if state in ("met_victor", "records_reviewed"):
                self._set_state("victor", "records_reviewed")

        def mark_courtyard_known(self):
            state = self.get_state("victor")
            if state in ("records_reviewed", "courtyard_known"):
                self._set_state("victor", "courtyard_known")

        def mark_victor_encounter_active(self):
            self._set_state("victor", "encounter_active")
            self.map.setNumericProperty("VICTOR_COURTYARD_TURN", self.map.getTurn())

        def mark_victor_good_end(self):
            self._set_state("victor", "good_end")
            self.map.setBoolProperty("VICTOR_BAD_END", False)
            self.map.setBoolProperty("VICTOR_GOOD_END", True)
            self.map.setBoolProperty("VICTOR_REWARD_CLAIMED", True)

        def mark_victor_bad_end(self):
            if self.get_state("victor") == "encounter_active":
                self._set_state("victor", "bad_end")
                self.map.setBoolProperty("VICTOR_GOOD_END", False)
                self.map.setBoolProperty("VICTOR_BAD_END", True)
                self.map.setBoolProperty("VICTOR_REWARD_CLAIMED", False)

        # --- Query helpers ---
        def is_letter_delivered(self):
            return self._beren_flags()[0]

        def is_relic_returned(self):
            return self._beren_flags()[1]

        def is_cave_purged(self):
            return self._beren_flags()[4]

        def is_octobogz_contract_completed(self):
            return self.get_state("octobogz_contract") == "completed"

        def is_amulet_returned(self):
            return self.get_state("amulet") == "returned"

        def victor_has_ended(self):
            return self.get_state("victor") in ("good_end", "bad_end")

        def victor_good_end(self):
            return self.get_state("victor") == "good_end"

        def needs_letter_delivery(self):
            return self.get_state("beren_chain") in ("letter_pending", "letter_in_hand")

        def needs_relic_return(self):
            return self.get_state("beren_chain") in ("relic_obtained", "octobogz_slain_no_relic")

        def ready_to_finish_cleanse(self):
            return self.get_state("beren_chain") == "ready_to_report"

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                game_map = self.getMap()
                game = game_map.getGame()
                player = game_map.getPlayer()
                quest_system = _get_quest_system(game_map)
                _reset_player_quests(player)
                game.getGuiHandler().showMessage(self.getStringProperty("text"))
                game_map.removeAll(lambda ob: ob.getStringProperty("type") == self.getStringProperty("type"))
                quest_system.reset_all()
                game_map.setBoolProperty("ASKED_ABOUT_GIRL", False)
                game_map.setBoolProperty("TALKED_TO_VICTOR", False)
                player.setNumericProperty("inquisitor_clues", 0)
                player.setNumericProperty("wayfarer_routes", 0)
                player.setBoolProperty("inspected_stained_glass", False)
                player.setBoolProperty("charted_smuggler_route", False)
                _grant_quest(player, "rolfQuest")
                player.addItem("letterFromRolf")

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            self.getMap().getGame().changeMap("map2")

    @register(context)
    class MainQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).get_state("main") == "gooby_slain"

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage("Gooby lies butchered, and weary townsfolk dare a ragged cheer.")

    @register(context)
    class RolfQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).get_state("rolf") == "skull_recovered"

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                "Sergeant Rolf's skull proves his doom; Gooby still prowls the caverns beneath Nouraajd."
            )

    @register(context)
    class DeliverLetterQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_letter_delivered()

        def onComplete(self):
            pass

    @register(context)
    class RetrieveRelicQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_relic_returned()

        def onComplete(self):
            pass

    @register(context)
    class CleanseCaveQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_cave_purged()

        def onComplete(self):
            pass

    @register(context)
    class VictorQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).victor_has_ended()

        def onComplete(self):
            pass

    @register(context)
    class OctoBogzQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_octobogz_contract_completed()

        def onComplete(self):
            game = self.getGame()
            player = game.getMap().getPlayer()
            player.addGold(1000)
            player.addItem("ShadowBlade")
            game.getGuiHandler().showMessage("The refugees press 1000 gold and the Shadow Blade into your hands.")

    @register(context)
    class AmuletQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_amulet_returned()

        def onComplete(self):
            pass

    @trigger(context, "onDestroy", "gooby1")
    class GoobyTrigger(CTrigger):
        def trigger(self, object, event):
            game = self.getGame()
            game.getGuiHandler().showMessage("Gooby is felled; the tunnels exhale a foul breath.")
            _quest_system_from(self).mark_gooby_slain()

    @trigger(context, "onDestroy", "cave1")
    class CaveTrigger(CTrigger):
        def trigger(self, object, event):
            game = self.getGame()
            game.getGuiHandler().showMessage(object.getStringProperty("message"))
            game_map = game.getMap()
            player = game_map.getPlayer()
            quest_system = _quest_system_from(self)
            gooby = game.createObject("gooby")
            gooby.setStringProperty("name", "gooby1")
            game_map.addObject(gooby)
            gooby.moveTo(100, 100, 0)
            player.addItem("skullOfRolf")
            quest_system.mark_rolf_skull_found(player)

    @trigger(context, "onDestroy", "catacombs")
    class CatacombsTrigger(CTrigger):
        def trigger(self, obj, event):
            game = self.getGame()
            game_map = game.getMap()
            player = game_map.getPlayer()
            player.addItem("holyRelic")
            _quest_system_from(self).mark_relic_obtained()
            game.getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "cave2")
    class OctoBogzCaveTrigger(CTrigger):
        def trigger(self, object, event):
            game = self.getGame()
            game_map = game.getMap()
            relic_returned = game_map.getBoolProperty("RELIC_RETURNED")
            quest_system = _quest_system_from(self)
            quest_system.mark_octobogz_slain()
            quest_system.complete_octobogz_contract()
            game_map.setBoolProperty("OCTOBOGZ_SLAIN", True)
            if relic_returned:
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
            if quest_system.is_relic_returned():
                game.getGuiHandler().showMessage(object.getStringProperty("message"))
            else:
                game.getGuiHandler().showMessage("The OctoBogz lie broken, yet their lair remains befouled.")

    @trigger(context, "onEnter", "market1")
    class MarketTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showTrade(object.getObjectProperty("market"))

    @trigger(context, "onEnter", "nouraajdDoor")
    class NouraajdDoorTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getBoolProperty("opened"):
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("doorDialog"))

    @register(context)
    class DoorDialog(CDialog):
        def open_door(self):
            self.getGame().getMap().removeAll(lambda ob: ob.getName().startswith("nouraajdDoorTrigger"))
            self.getGame().getMap().getObjectByName("nouraajdDoor").setBoolProperty("opened", True)

    @trigger(context, "onEnter", "nouraajdTavern")
    class NouraajdTavernTrigger(CTrigger):
        def trigger(self, tavern, event):
            if tavern.getNumericProperty("visited") == 0 and tavern.getNumericProperty("time_visited") == 0:
                tavern.getGame().getGuiHandler().showDialog(tavern.getGame().createObject("tavernDialog1"))
                tavern.setNumericProperty("time_visited", tavern.getGame().getMap().getTurn())
                tavern.incProperty("visited", 1)
            elif (
                tavern.getNumericProperty("visited") == 1
                and tavern.getGame().getMap().getTurn() - tavern.getNumericProperty("time_visited") > 50
            ):
                tavern.getGame().getGuiHandler().showDialog(tavern.getGame().createObject("tavernDialog2"))
                tavern.incProperty("visited", 1)

    @register(context)
    class TavernDialog1(CDialog):
        def sell_beer(self):
            game = self.getGame()
            game.getGuiHandler().showTrade(game.createObject("tavernBeerMarket"))

        def asked_about_girl(self):
            self.getGame().getMap().setBoolProperty("ASKED_ABOUT_GIRL", True)

    @register(context)
    class TavernDialog2(CDialog):
        def _ensure_victor_quest(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            _quest_system_from(self).record_met_victor()
            _grant_quest(player, "victorQuest")

        def asked_about_girl(self):
            return self.getGame().getMap().getBoolProperty("ASKED_ABOUT_GIRL")

        def talked_to_victor(self):
            self._ensure_victor_quest()
            self.getGame().getMap().setBoolProperty("TALKED_TO_VICTOR", True)

    @trigger(context, "onEnter", "nouraajdTownHall")
    class TownHallTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("townHallDialog"))

    @register(context)
    class TownHallDialog(CDialog):
        COURTYARD_SPAWNS = [(44, 100, 0), (46, 100, 0), (45, 99, 0), (45, 101, 0)]
        COURTYARD_LEADER_SPAWN = (45, 100, 0)
        COURTYARD_TIMEOUT_TURNS = VICTOR_COURTYARD_TIMEOUT_TURNS

        def _is_letter_to_beren(self, item):
            return item.getName() == "letterToBeren" or (
                hasattr(item, "getLabel") and item.getLabel() == "Sealed Letter"
            )

        def _ensure_quest(self, quest_name):
            player = self.getGame().getMap().getPlayer()
            _grant_quest(player, quest_name)

        def can_chart_wayfarer_route(self):
            player = self.getGame().getMap().getPlayer()
            return player.getType() == "Wayfarer" and not player.getBoolProperty("charted_smuggler_route")

        def chart_wayfarer_route(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_chart_wayfarer_route():
                return
            player.incProperty("wayfarer_routes", 1)
            player.setBoolProperty("charted_smuggler_route", True)
            player.addExp(750)
            self.getGame().getGuiHandler().showMessage(
                "You chart forgotten courier alleys through Nouraajd; each hidden turn steadies your stride when the lane rots away."
            )

        def give_letter(self):
            quest_system = _quest_system_from(self)
            player = self.getGame().getMap().getPlayer()
            if not quest_system.needs_letter_delivery():
                return
            issued = quest_system.give_letter(player)
            if issued and not player.hasItem(self._is_letter_to_beren):
                player.addItem("letterToBeren")
                self.getGame().getGuiHandler().showMessage("You accept the mayor's sealed missive, wax still warm.")

        def has_letter_quest(self):
            quest_system = _quest_system_from(self)
            if not quest_system.needs_letter_delivery():
                return False
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(self._is_letter_to_beren):
                return True
            return _player_has_quest(player, "deliverLetterQuest")

        def talked_to_victor(self):
            return self.getGame().getMap().getBoolProperty("TALKED_TO_VICTOR")

        def start_victor_quest(self):
            quest_system = _quest_system_from(self)
            quest_system.record_victor_records()
            self._ensure_quest("victorQuest")

        def spawn_cultists(self):
            game = self.getGame()
            game_map = game.getMap()
            self.start_victor_quest()
            quest_system = _quest_system_from(self)
            quest_system.mark_courtyard_known()
            victor_state = quest_system.get_state("victor")
            if quest_system.victor_good_end():
                game.getGuiHandler().showMessage(
                    "Victor has already reclaimed his daughter; the courtyard now keeps a reverent quiet."
                )
                return
            if victor_state == "bad_end":
                game.getGuiHandler().showMessage(
                    "The mayor mutters that the Cult of Marumi Baso vanished with Victor's daughter before help arrived."
                )
                return
            if victor_state == "encounter_active":
                _expire_victor_search(game_map)
                return
            spawned = False
            for index, (x, y, z) in enumerate(self.COURTYARD_SPAWNS, start=1):
                coords = Coords(x, y, z)
                if game_map.canStep(coords):
                    mon = game.createObject("Cultist")
                    target_ctrl = game.createObject("CTargetController")
                    target_ctrl.setTarget("player")
                    mon.setController(target_ctrl)
                    mon.setStringProperty("name", f"{VICTOR_CULTIST_PREFIX}{index}")
                    game_map.addObject(mon)
                    mon.moveTo(coords.x, coords.y, coords.z)
                    spawned = True

            coords = Coords(*self.COURTYARD_LEADER_SPAWN)
            if game_map.canStep(coords):
                leader = game.createObject("CultLeader")
                leader.setStringProperty("name", "cultLeaderQuest")
                target_ctrl = game.createObject("CTargetController")
                target_ctrl.setTarget("player")
                leader.setController(target_ctrl)
                game_map.addObject(leader)
                leader.moveTo(coords.x, coords.y, coords.z)
                spawned = True
            if spawned:
                quest_system.mark_victor_encounter_active()

    @trigger(context, "onTurn", "nouraajdTownHall")
    class VictorCourtyardTimerTrigger(CTrigger):
        def trigger(self, obj, event):
            game_map = obj.getGame().getMap()
            if _quest_system_from(obj).get_state("victor") != "encounter_active":
                return
            _expire_victor_search(game_map)

    @trigger(context, "onEnter", "nouraajdChapel")
    class ChapelTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("berenDialog"))

    @register(context)
    class BerenDialog(CDialog):
        def _is_letter_to_beren(self, item):
            return item.getName() == "letterToBeren" or (
                hasattr(item, "getLabel") and item.getLabel() == "Sealed Letter"
            )

        def _ensure_quest(self, quest_name):
            player = self.getGame().getMap().getPlayer()
            _grant_quest(player, quest_name)

        def can_inspect_stained_glass(self):
            player = self.getGame().getMap().getPlayer()
            return player.getType() == "Inquisitor" and not player.getBoolProperty("inspected_stained_glass")

        def inspect_stained_glass(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_inspect_stained_glass():
                return
            player.incProperty("inquisitor_clues", 1)
            player.setBoolProperty("inspected_stained_glass", True)
            player.addExp(750)
            self.getGame().getGuiHandler().showMessage(
                "The stained glass hides a Marumi Baso seal; zeal hardens as you memorize the cult's patient cipher."
            )

        def can_deliver_letter(self):
            quest_system = _quest_system_from(self)
            player = self.getGame().getMap().getPlayer()
            return quest_system.needs_letter_delivery() and player.hasItem(self._is_letter_to_beren)

        def can_return_relic(self):
            quest_system = _quest_system_from(self)
            player = self.getGame().getMap().getPlayer()
            return quest_system.needs_relic_return() and player.hasItem(lambda it: it.getName() == "holyRelic")

        def can_finish_cleanse(self):
            return _quest_system_from(self).ready_to_finish_cleanse()

        def deliver_letter(self):
            player = self.getGame().getMap().getPlayer()
            quest_system = _quest_system_from(self)
            if not self.can_deliver_letter():
                return
            player.removeItem(self._is_letter_to_beren, True)
            quest_system.mark_letter_delivered(player)
            if not quest_system.is_relic_returned():
                self._ensure_quest("retrieveRelicQuest")

        def return_relic(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            quest_system = _quest_system_from(self)
            if not self.can_return_relic():
                return
            player.removeItem(lambda it: it.getName() == "holyRelic", True)
            quest_system.mark_relic_returned()
            if game_map.getBoolProperty("OCTOBOGZ_SLAIN"):
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
            if not quest_system.is_cave_purged():
                self._ensure_quest("cleanseCaveQuest")

        def finish_cleanse(self):
            quest_system = _quest_system_from(self)
            if self.can_finish_cleanse():
                quest_system.mark_cave_purged()
                self.getGame().getGuiHandler().showMessage(
                    "For a breath, the town is spared and the OctoBogz lie quiet."
                )
            else:
                self.getGame().getGuiHandler().showMessage("The cave still writhes with OctoBogz corruption.")

    @register(context)
    class OctoBogzDialog(CDialog):
        def accept_quest(self):
            game_map = self.getGame().getMap()
            _grant_quest(game_map.getPlayer(), "octoBogzQuest")
            _quest_system_from(self).activate_octobogz_contract()

    @trigger(context, "onEnter", "questGiver")
    class QuestGiverTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game.getGuiHandler().showDialog(game.createObject("dialog"))

    @trigger(context, "onDestroy", "cultLeaderQuest")
    class CultLeaderQuestTrigger(CTrigger):
        def trigger(self, leader, event):
            game = self.getGame()
            game_map = game.getMap()
            quest_system = _quest_system_from(self)
            if quest_system.get_state("victor") != "encounter_active":
                return
            if game_map.getBoolProperty("VICTOR_REWARD_CLAIMED") or game_map.getBoolProperty("VICTOR_GOOD_END"):
                return
            player = game.getMap().getPlayer()
            player.addGold(500)
            player.healProc(100)
            game.getGuiHandler().showDialog(game.createObject("victorRewardDialog"))
            game.getGuiHandler().showTrade(game.createObject("victorMarket"))
            quest_system.mark_victor_good_end()
            _clear_victor_encounter(game_map)

    @trigger(context, "onEnter", "oldWoman")
    class OldWomanTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game_map = game.getMap()
                quest_system = _quest_system_from(obj)
                amulet_state = quest_system.get_state("amulet")
                if amulet_state == "returned":
                    game_map.removeObject(obj)
                    return
                player = game_map.getPlayer()
                if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                    game.getGuiHandler().showDialog(game.createObject("questReturnDialog"))
                elif amulet_state == "not_started":
                    game.getGuiHandler().showDialog(game.createObject("questDialog"))
                else:
                    game.getGuiHandler().showMessage("The goblin still clutches my amulet; please bring it back!")

    @register(context)
    class QuestDialog(CDialog):
        def start_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            quest_system = _quest_system_from(self)
            if quest_system.get_state("amulet") != "not_started":
                return
            player = game_map.getPlayer()
            _grant_quest(player, "amuletQuest")
            goblin = game.createObject("goblinThief")
            goblin.setStringProperty("name", "amuletGoblin")
            game_map.addObject(goblin)
            # spawn near the old woman within map bounds
            goblin.moveTo(195, 8, 0)
            quest_system.start_amulet()

    @register(context)
    class QuestReturnDialog(CDialog):
        def complete_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            player = game_map.getPlayer()
            if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                player.removeItem(lambda it: it.getName() == "preciousAmulet", True)
                player.addGold(50)
                _quest_system_from(self).finish_amulet()
                amulet_goblin = game_map.getObjectByName("amuletGoblin")
                if amulet_goblin:
                    game_map.removeObject(amulet_goblin)
                old_woman = game_map.getObjectByName("oldWoman")
                if old_woman:
                    game_map.removeObject(old_woman)
                game.getGuiHandler().showMessage(
                    "The old woman presses 50 gold upon you, tears streaking her dust-caked cheeks."
                )

    if context.getMap():
        _get_quest_system(context.getMap()).initialize_defaults()
