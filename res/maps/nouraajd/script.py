def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import CQuest
    from game import CPlayer
    from game import CDialog
    from game import Coords
    from game import LegacyBoolFlag
    from game import PlayerQuestRegistry
    from game import QuestStateStore
    from game import claim_once
    from game import remove_runtime_actors
    from game import ensure_quest
    from game import register, trigger

    import campaign

    # Scenario outcomes this map reports through campaign.complete_scenario;
    # campaign manifests route them (see docs/design/multilevel_campaign.md).
    CAMPAIGN_OUTCOMES = ("completed",)

    VICTOR_COURTYARD_TIMEOUT_TURNS = 75
    VICTOR_CULTIST_PREFIX = "victorCultist"
    VICTOR_COURTYARD_SPAWNS = [(44, 100, 0), (46, 100, 0), (45, 99, 0), (45, 101, 0)]
    VICTOR_COURTYARD_LEADER_SPAWN = (45, 100, 0)
    VICTOR_COURTYARD_FALLBACK_RADIUS = 3
    MAIN_QUEST_GOLD_REWARD = 200

    def _clear_victor_encounter(game_map):
        remove_runtime_actors(game_map, names=("cultLeaderQuest",), prefixes=(VICTOR_CULTIST_PREFIX,))
        game_map.setNumericProperty("VICTOR_COURTYARD_TURN", -1)
        game_map.setNumericProperty("VICTOR_CULTISTS_PLACED", 0)

    def _coords_key(coords):
        return coords.x, coords.y, coords.z

    def _victor_spawn_candidates(preferred):
        x, y, z = preferred
        yield preferred
        for radius in range(1, VICTOR_COURTYARD_FALLBACK_RADIUS + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    yield x + dx, y + dy, z

    def _find_victor_spawn_coords(game_map, preferred, reserved):
        for candidate in _victor_spawn_candidates(preferred):
            coords = Coords(*candidate)
            key = _coords_key(coords)
            if key in reserved:
                continue
            if game_map.canStep(coords):
                reserved.add(key)
                return coords
        return None

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

    def _spawn_victor_encounter(dialog):
        game = dialog.getGame()
        game_map = game.getMap()
        quest_system = _quest_system_from(dialog)
        victor_state = quest_system.get_state("victor")
        if quest_system.victor_good_end():
            game.getGuiHandler().showMessage(
                "Victor has already reclaimed his daughter; the courtyard now keeps a reverent quiet."
            )
            return False
        if victor_state == "bad_end":
            game.getGuiHandler().showMessage(
                "The mayor mutters that the Cult of Marumi Baso vanished with Victor's daughter before help arrived."
            )
            return False
        if victor_state == "encounter_active":
            _expire_victor_search(game_map)
            return False

        _clear_victor_encounter(game_map)
        reserved = set()
        leader_coords = _find_victor_spawn_coords(game_map, dialog.COURTYARD_LEADER_SPAWN, reserved)
        if leader_coords is None:
            game.getGuiHandler().showMessage(
                "The courtyard is choked with bodies and barricades; the cult's hidden door cannot be reached yet."
            )
            return False

        leader = game.createObject("CultLeader")
        leader.setStringProperty("name", "cultLeaderQuest")
        target_ctrl = game.createObject("CTargetController")
        target_ctrl.setTarget("player")
        leader.setController(target_ctrl)
        game_map.addObject(leader)
        if game_map.getObjectByName("cultLeaderQuest") is None:
            game.getGuiHandler().showMessage(
                "The cult door shudders open, then slams shut before the leader can be drawn into the courtyard."
            )
            return False
        leader.moveTo(leader_coords.x, leader_coords.y, leader_coords.z)

        placed_cultists = 0
        for index, preferred in enumerate(dialog.COURTYARD_SPAWNS, start=1):
            coords = _find_victor_spawn_coords(game_map, preferred, reserved)
            if coords is None:
                continue
            mon = game.createObject("Cultist")
            target_ctrl = game.createObject("CTargetController")
            target_ctrl.setTarget("player")
            mon.setController(target_ctrl)
            mon.setStringProperty("name", f"{VICTOR_CULTIST_PREFIX}{index}")
            game_map.addObject(mon)
            mon.moveTo(coords.x, coords.y, coords.z)
            placed_cultists += 1

        if placed_cultists == 0:
            _clear_victor_encounter(game_map)
            game.getGuiHandler().showMessage(
                "The cult leader vanishes back through the branded door; the courtyard is too choked for a fight."
            )
            return False

        game_map.setNumericProperty("VICTOR_CULTISTS_PLACED", placed_cultists)
        quest_system.mark_victor_encounter_active()
        game.getGuiHandler().showMessage(
            "The cultists reel toward the stained-glass door. Break their rite before Victor's daughter is taken."
        )
        return True

    _player_quest_registry = PlayerQuestRegistry()
    _player_quest_registry.install_on(CPlayer)

    def _reset_player_quests(player):
        _player_quest_registry.reset(player)

    def _grant_quest(player, quest_name):
        ensure_quest(player, quest_name, registry=_player_quest_registry)

    def _set_numeric_property_default(obj, name, value):
        if not hasattr(obj, name):
            obj.setNumericProperty(name, value)

    def _set_bool_property_default(obj, name, value):
        if not hasattr(obj, name):
            obj.setBoolProperty(name, value)

    def _get_quest_system(game_map):
        return QuestSystem(game_map)

    def _quest_system_from(obj):
        return _get_quest_system(obj.getGame().getMap())

    class QuestSystem(QuestStateStore):
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

        QUEST_NUMERIC_DEFAULTS = {
            "VICTOR_COURTYARD_TURN": -1,
        }

        LEGACY_BOOL_FLAGS = (
            LegacyBoolFlag("completed_rolf", "rolf", states=("skull_recovered",)),
            LegacyBoolFlag("completed_gooby", "main", states=("gooby_slain",)),
            LegacyBoolFlag(
                "DELIVERED_LETTER",
                "beren_chain",
                excluded_states=("letter_pending", "letter_in_hand", "octobogz_slain_pending_letter"),
            ),
            LegacyBoolFlag(
                "RELIC_RETURNED",
                "beren_chain",
                states=("relic_returned_waiting_kill", "ready_to_report", "purged"),
            ),
            LegacyBoolFlag(
                "OCTOBOGZ_SLAIN",
                "beren_chain",
                states=("octobogz_slain_pending_letter", "octobogz_slain_no_relic", "ready_to_report", "purged"),
            ),
            LegacyBoolFlag("OCTOBOGZ_CLEARED", "beren_chain", states=("ready_to_report", "purged")),
            LegacyBoolFlag("CAVE_PURGED", "beren_chain", states=("purged",)),
            LegacyBoolFlag("completed_octobogz", "octobogz_contract", states=("completed",)),
            LegacyBoolFlag("AMULET_QUEST_STARTED", "amulet", states=("active",)),
            LegacyBoolFlag("AMULET_RETURNED", "amulet", states=("returned",)),
            LegacyBoolFlag(
                "VICTOR_QUEST_STARTED",
                "victor",
                states=("met_victor", "records_reviewed", "courtyard_known", "encounter_active", "good_end", "bad_end"),
            ),
            LegacyBoolFlag(
                "VICTOR_COURTYARD_FOUND",
                "victor",
                states=("courtyard_known", "encounter_active", "good_end", "bad_end"),
            ),
            LegacyBoolFlag("VICTOR_CULTISTS_SPAWNED", "victor", states=("encounter_active",)),
            LegacyBoolFlag("VICTOR_GOOD_END", "victor", states=("good_end",)),
            LegacyBoolFlag("VICTOR_BAD_END", "victor", states=("bad_end",)),
            LegacyBoolFlag("VICTOR_HELP", "victor", states=("good_end",)),
            LegacyBoolFlag("VICTOR_REWARD_CLAIMED", "victor", states=("good_end",)),
        )

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
            if state == "octobogz_slain_pending_letter":
                _grant_quest(player, "deliverLetterQuest")
                return True
            if state == "letter_in_hand":
                _grant_quest(player, "deliverLetterQuest")
                return True
            return False

        def mark_letter_delivered(self, player):
            prior = self.get_state("beren_chain")
            if prior == "octobogz_slain_pending_letter":
                self._set_state("beren_chain", "octobogz_slain_no_relic")
                _grant_quest(player, "retrieveRelicQuest")
            elif prior in ("letter_pending", "letter_in_hand"):
                next_state = (
                    "relic_obtained" if player.hasItem(lambda it: it.getName() == "holyRelic") else "letter_delivered"
                )
                self._set_state("beren_chain", next_state)
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
            elif state in ("letter_pending", "letter_in_hand", "octobogz_slain_pending_letter"):
                self._set_state("beren_chain", "octobogz_slain_pending_letter")

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
            return not self.state_in(
                "beren_chain", ("letter_pending", "letter_in_hand", "octobogz_slain_pending_letter")
            )

        def is_relic_returned(self):
            return self.state_in("beren_chain", ("relic_returned_waiting_kill", "ready_to_report", "purged"))

        def is_cave_purged(self):
            return self.state_in("beren_chain", ("purged",))

        def is_octobogz_contract_completed(self):
            return self.get_state("octobogz_contract") == "completed"

        def is_amulet_returned(self):
            return self.get_state("amulet") == "returned"

        def victor_has_ended(self):
            return self.get_state("victor") in ("good_end", "bad_end")

        def victor_good_end(self):
            return self.get_state("victor") == "good_end"

        def needs_letter_delivery(self):
            return self.get_state("beren_chain") in (
                "letter_pending",
                "letter_in_hand",
                "octobogz_slain_pending_letter",
            )

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
                _set_numeric_property_default(player, "warrior_barricades", 0)
                _set_numeric_property_default(player, "assasin_trails", 0)
                _set_numeric_property_default(player, "inquisitor_clues", 0)
                _set_numeric_property_default(player, "sorcerer_sigils", 0)
                _set_numeric_property_default(player, "wayfarer_routes", 0)
                _set_bool_property_default(player, "braced_nouraajd_gate", False)
                _set_bool_property_default(player, "shadowed_robed_men", False)
                _set_bool_property_default(player, "inspected_stained_glass", False)
                _set_bool_property_default(player, "decoded_stained_glass_ward", False)
                _set_bool_property_default(player, "charted_smuggler_route", False)
                _grant_quest(player, "rolfQuest")
                player.addItem("letterFromRolf")

    @register(context)
    class ChangeMap(CEvent):
        def onEnter(self, event):
            campaign.complete_scenario(self.getMap().getGame(), "completed", fallback_map="ritual")

    @register(context)
    class MainQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).get_state("main") == "gooby_slain"

        def getObjective(self):
            return "Follow Sergeant Rolf's trail, recover his skull, then slay Gooby beneath Nouraajd."

        def getReward(self):
            return "200 gold from relieved townsfolk."

        def getHint(self):
            return "Search the cave outside town for the first sign of Rolf."

        def onComplete(self):
            game_map = self.getGame().getMap()
            # Claim-first: set the claim flag before granting so a repeated dialog/trigger run cannot
            # grant the gold twice.
            if claim_once(game_map, "GOOBY_REWARD_CLAIMED"):
                game_map.getPlayer().addGold(MAIN_QUEST_GOLD_REWARD)
            self.getGame().getGuiHandler().showMessage("Gooby lies butchered, and weary townsfolk dare a ragged cheer.")

    @register(context)
    class RolfQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).get_state("rolf") == "skull_recovered"

        def getObjective(self):
            return "Recover Sergeant Rolf's skull from the Pritscher cave."

        def getReward(self):
            return "Starts the Gooby hunt."

        def getHint(self):
            return "The cave entrance lies beyond Nouraajd's roads."

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage(
                "Sergeant Rolf's skull proves his doom; Gooby still prowls the caverns beneath Nouraajd."
            )

    @register(context)
    class DeliverLetterQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_letter_delivered()

        def getObjective(self):
            return "Carry Mayor Irvin's sealed letter to Father Beren at the chapel."

        def getReward(self):
            return "Unlocks scribe-desk scroll crafting."

        def getHint(self):
            return "Ask at town hall, then visit the chapel."

        def onComplete(self):
            pass

    @register(context)
    class RetrieveRelicQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_relic_returned()

        def getObjective(self):
            return "Recover the holy relic from the catacombs and return it to Father Beren."

        def getReward(self):
            return "Unlocks greater potion brewing at the alchemy table."

        def getHint(self):
            return "The catacombs hide the relic Beren needs."

        def onComplete(self):
            pass

    @register(context)
    class CleanseCaveQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_cave_purged()

        def getObjective(self):
            return "Use the returned relic to cleanse the OctoBogz cave, then report to Beren."

        def getReward(self):
            return "Opens the road to the ritual chapel."

        def getHint(self):
            return "Clear the OctoBogz lair after the relic is back in Beren's hands."

        def onComplete(self):
            pass

    @register(context)
    class VictorQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).victor_has_ended()

        def getObjective(self):
            state = _quest_system_from(self).get_state("victor")
            if state == "encounter_active":
                return "Defeat the cultists in the courtyard before Victor's daughter is taken."
            if state == "good_end":
                return "Victor's daughter survived the courtyard rite."
            if state == "bad_end":
                return "Victor's daughter was taken when the courtyard rite ended."
            if state in ("met_victor", "records_reviewed", "courtyard_known"):
                return "Follow Victor's clue from the tavern to the town hall records, then to the courtyard."
            return "Find Victor's missing daughter."

        def getReward(self):
            if _quest_system_from(self).get_state("victor") == "bad_end":
                return "No reward if Victor's daughter is taken."
            return (
                "500 gold, healing, and one-time access to buy Victor's remaining potions "
                "if you reach the courtyard in time."
            )

        def getHint(self):
            state = _quest_system_from(self).get_state("victor")
            if state == "encounter_active":
                return f"The cultists began their rite; you have {VICTOR_COURTYARD_TIMEOUT_TURNS} turns from first contact."
            if state == "good_end":
                return "Victor and his daughter have fled the courtyard alive."
            if state == "bad_end":
                return "The courtyard is empty now, scrubbed clean by Marumi Baso's servants."
            return "Ask Victor at the tavern, search the town hall ledgers, then hurry to the courtyard."

        def onComplete(self):
            pass

    @register(context)
    class OctoBogzQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_octobogz_contract_completed()

        def getObjective(self):
            return "Destroy the OctoBogz in the cave east of Nouraajd."

        def getReward(self):
            return "1000 gold and the Shadow Blade."

        def getHint(self):
            return "The travelers in Nouraajd know the route."

        def onComplete(self):
            game = self.getGame()
            game_map = game.getMap()
            # Claim-first: claim the reward before handing out gold and the item so the payout
            # cannot repeat if onComplete runs again.
            if not claim_once(game_map, "OCTOBOGZ_REWARD_CLAIMED"):
                return
            player = game_map.getPlayer()
            player.addGold(1000)
            player.addItem("ShadowBlade")
            game.getGuiHandler().showMessage("The refugees press 1000 gold and the Shadow Blade into your hands.")

    @register(context)
    class AmuletQuest(CQuest):
        def isCompleted(self):
            return _quest_system_from(self).is_amulet_returned()

        def getObjective(self):
            return "Recover the old woman's stolen amulet from the goblin thief."

        def getReward(self):
            return "50 gold."

        def getHint(self):
            return "The thief lurks near the village edge."

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

    @trigger(context, "onEnter", "nouraajdDoor")
    class NouraajdDoorTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getBoolProperty("opened"):
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("doorDialog"))

    @register(context)
    class DoorDialog(CDialog):
        def can_brace_gate(self):
            player = self.getGame().getMap().getPlayer()
            return player.getPlayerClassId() == "Warrior" and not player.getBoolProperty("braced_nouraajd_gate")

        def brace_gate(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_brace_gate():
                return
            player.incProperty("warrior_barricades", 1)
            player.setBoolProperty("braced_nouraajd_gate", True)
            player.addExp(750)
            self.open_door()
            self.getGame().getGuiHandler().showMessage(
                "You shoulder the warped gate back onto its braces; Rolf's last chalk marks point east."
            )

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

        def can_shadow_robed_men(self):
            player = self.getGame().getMap().getPlayer()
            return player.getPlayerClassId() == "Assasin" and not player.getBoolProperty("shadowed_robed_men")

        def shadow_robed_men(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_shadow_robed_men():
                return
            player.incProperty("assasin_trails", 1)
            player.setBoolProperty("shadowed_robed_men", True)
            player.addExp(750)
            self.asked_about_girl()
            self.getGame().getGuiHandler().showMessage(
                "You ghost after the robed men long enough to mark their courtyard turn and the child's yellow ribbon."
            )

    @register(context)
    class TavernDialog2(CDialog):
        COURTYARD_SPAWNS = VICTOR_COURTYARD_SPAWNS
        COURTYARD_LEADER_SPAWN = VICTOR_COURTYARD_LEADER_SPAWN

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

        def spawn_cultists(self):
            self._ensure_victor_quest()
            _spawn_victor_encounter(self)

    @trigger(context, "onEnter", "nouraajdTownHall")
    class TownHallTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("townHallDialog"))

    @register(context)
    class TownHallDialog(CDialog):
        COURTYARD_SPAWNS = VICTOR_COURTYARD_SPAWNS
        COURTYARD_LEADER_SPAWN = VICTOR_COURTYARD_LEADER_SPAWN
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
            # Gate on the class identity (playerClassId) rather than the raw type id; getPlayerClassId
            # falls back to the type id for players saved before the identity model, so existing
            # Wayfarer saves keep working while explicit class identities are honored.
            return player.getPlayerClassId() == "Wayfarer" and not player.getBoolProperty("charted_smuggler_route")

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
            return player.hasItem(self._is_letter_to_beren)

        def can_offer_letter_work(self):
            quest_system = _quest_system_from(self)
            return quest_system.needs_letter_delivery() and not self.has_letter_quest()

        def talked_to_victor(self):
            return self.getGame().getMap().getBoolProperty("TALKED_TO_VICTOR")

        def can_discuss_victor_records(self):
            if not self.talked_to_victor():
                return False
            state = _quest_system_from(self).get_state("victor")
            return state in ("not_started", "met_victor", "records_reviewed", "courtyard_known")

        def victor_encounter_active(self):
            return _quest_system_from(self).get_state("victor") == "encounter_active"

        def victor_good_end(self):
            return _quest_system_from(self).get_state("victor") == "good_end"

        def victor_bad_end(self):
            return _quest_system_from(self).get_state("victor") == "bad_end"

        def start_victor_quest(self):
            quest_system = _quest_system_from(self)
            if quest_system.get_state("victor") == "not_started" and self.talked_to_victor():
                quest_system.record_met_victor()
            quest_system.record_victor_records()
            self._ensure_quest("victorQuest")

        def spawn_cultists(self):
            self.start_victor_quest()
            quest_system = _quest_system_from(self)
            quest_system.mark_courtyard_known()
            _spawn_victor_encounter(self)

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
            # Gate on the class identity (playerClassId) with type-id fallback for pre-identity saves.
            return player.getPlayerClassId() == "Inquisitor" and not player.getBoolProperty(
                "inspected_stained_glass"
            )

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

        def can_decode_stained_glass_ward(self):
            player = self.getGame().getMap().getPlayer()
            return player.getPlayerClassId() == "Sorcerer" and not player.getBoolProperty("decoded_stained_glass_ward")

        def decode_stained_glass_ward(self):
            player = self.getGame().getMap().getPlayer()
            if not self.can_decode_stained_glass_ward():
                return
            player.incProperty("sorcerer_sigils", 1)
            player.setBoolProperty("decoded_stained_glass_ward", True)
            player.addItem("Scroll")
            player.addExp(750)
            self.getGame().getGuiHandler().showMessage(
                "You unwind a cold ward from the stained glass and copy its safest stroke onto a blank scroll."
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
            player.setBoolProperty("CAN_CRAFT_SCROLLS", True)
            self.getGame().getGuiHandler().showMessage(
                "Beren opens the chapel scriptorium to you; town portal scrolls can now be crafted."
            )
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
            player.setBoolProperty("CAN_BREW_GREATER_POTIONS", True)
            self.getGame().getGuiHandler().showMessage(
                "Relic dust settles into the alchemist's notes; stronger draughts are now possible."
            )
            if game_map.getBoolProperty("OCTOBOGZ_SLAIN"):
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
            if not quest_system.is_cave_purged():
                self._ensure_quest("cleanseCaveQuest")

        def finish_cleanse(self):
            quest_system = _quest_system_from(self)
            if self.can_finish_cleanse():
                quest_system.mark_cave_purged()
                self.getGame().getGuiHandler().showMessage(
                    "For a breath, the town is spared. Beren points you toward the abandoned ritual chapel."
                )
                self.getGame().getMap().getPlayer().checkQuests()
                campaign.complete_scenario(self.getGame(), "completed", fallback_map="ritual")
            else:
                self.getGame().getGuiHandler().showMessage("The cave still writhes with OctoBogz corruption.")

    @register(context)
    class OctoBogzDialog(CDialog):
        # QuestSystem.get_state("octobogz_contract") is the single authority for which
        # branch of the dialog is shown. The verified states are "not_started", "active",
        # and "completed"; each condition below maps one state to one ENTRY branch so the
        # quest is only offered before it starts, merely acknowledged while active, and
        # never re-offered once completed (even in the same session right after the reward
        # is granted, since complete_octobogz_contract runs before this dialog re-opens).
        def contract_not_started(self):
            return _quest_system_from(self).get_state("octobogz_contract") == "not_started"

        def contract_active(self):
            return _quest_system_from(self).get_state("octobogz_contract") == "active"

        def contract_completed(self):
            return _quest_system_from(self).is_octobogz_contract_completed()

        def accept_quest(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            quest_system = _quest_system_from(self)
            # No state guard here: accept_quest must still process a "late" claim where the
            # OctoBogz were cleared before the contract was formally accepted (state already
            # "completed"), granting the outstanding reward exactly once. Re-entry is safe --
            # activate_octobogz_contract only acts from "not_started" and the reward is
            # protected by the OCTOBOGZ_REWARD_CLAIMED guard. Re-offering in normal play is
            # prevented at the dialog layer: the OFFER_HELP accept option is gated by
            # contract_not_started, so active/completed states never surface the offer.
            _grant_quest(player, "octoBogzQuest")
            quest_system.activate_octobogz_contract()
            if quest_system.is_octobogz_contract_completed():
                player.checkQuests()

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
            # Claim-first: claim the Victor payout before handing out gold, healing, the reward dialog
            # and the one-time vendor panel so a re-entered trigger cannot grant the reward twice.
            # VICTOR_REWARD_CLAIMED is a state-derived legacy flag, so a dedicated non-derived key is
            # used for the claim to avoid sync_legacy_flags overwriting the guard.
            if not claim_once(game_map, "VICTOR_REWARD_GRANTED"):
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
                    remove_runtime_actors(game_map, names=("oldWoman",))
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
            quest_system = _quest_system_from(self)
            if quest_system.get_state("amulet") != "active":
                return
            if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                # Claim-first: claim the amulet return reward before consuming the amulet, paying the
                # gold and cleaning up the quest actors so a re-run cannot grant it twice. AMULET_RETURNED
                # is a state-derived legacy flag, so a dedicated non-derived key backs the claim.
                if not claim_once(game_map, "AMULET_REWARD_CLAIMED"):
                    return
                player.removeItem(lambda it: it.getName() == "preciousAmulet", True)
                player.addGold(50)
                quest_system.finish_amulet()
                remove_runtime_actors(game_map, names=("amuletGoblin", "oldWoman"))
                game.getGuiHandler().showMessage(
                    "The old woman presses 50 gold upon you, tears streaking her dust-caked cheeks."
                )

    if context.getMap():
        _get_quest_system(context.getMap()).initialize_defaults()
