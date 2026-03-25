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
        game_map.setBoolProperty("VICTOR_CULTISTS_SPAWNED", False)
        game_map.setNumericProperty("VICTOR_COURTYARD_TURN", 0)

    def _expire_victor_search(game_map):
        if not game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"):
            return False
        if game_map.getBoolProperty("VICTOR_GOOD_END") or game_map.getBoolProperty("VICTOR_BAD_END"):
            return False
        spawn_turn = game_map.getNumericProperty("VICTOR_COURTYARD_TURN")
        if not spawn_turn:
            return False
        if game_map.getTurn() - spawn_turn < VICTOR_COURTYARD_TIMEOUT_TURNS:
            return False
        game_map.setBoolProperty("VICTOR_BAD_END", True)
        game_map.setBoolProperty("VICTOR_HELP", False)
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

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                game_map = self.getMap()
                game = game_map.getGame()
                player = game_map.getPlayer()
                _reset_player_quests(player)
                game.getGuiHandler().showMessage(self.getStringProperty("text"))
                game_map.removeAll(lambda ob: ob.getStringProperty("type") == self.getStringProperty("type"))
                game_map.setBoolProperty("completed_gooby", False)
                game_map.setBoolProperty("completed_rolf", False)
                game_map.setBoolProperty("completed_octobogz", False)
                game_map.setBoolProperty("DELIVERED_LETTER", False)
                game_map.setBoolProperty("RELIC_RETURNED", False)
                game_map.setBoolProperty("OCTOBOGZ_SLAIN", False)
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", False)
                game_map.setBoolProperty("CAVE_PURGED", False)
                game_map.setBoolProperty("AMULET_QUEST_STARTED", False)
                game_map.setBoolProperty("AMULET_RETURNED", False)
                game_map.setBoolProperty("ASKED_ABOUT_GIRL", False)
                game_map.setBoolProperty("TALKED_TO_VICTOR", False)
                game_map.setBoolProperty("VICTOR_QUEST_STARTED", False)
                game_map.setBoolProperty("VICTOR_COURTYARD_FOUND", False)
                game_map.setBoolProperty("VICTOR_CULTISTS_SPAWNED", False)
                game_map.setBoolProperty("VICTOR_GOOD_END", False)
                game_map.setBoolProperty("VICTOR_BAD_END", False)
                game_map.setBoolProperty("VICTOR_REWARD_CLAIMED", False)
                game_map.setBoolProperty("VICTOR_HELP", False)
                game_map.setNumericProperty("VICTOR_COURTYARD_TURN", 0)
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
            return self.getGame().getMap().getBoolProperty("completed_gooby")

        def onComplete(self):
            self.getGame().getGuiHandler().showMessage("Gooby lies butchered, and weary townsfolk dare a ragged cheer.")

    @register(context)
    class RolfQuest(CQuest):
        def _ensure_main_quest(self):
            player = self.getGame().getMap().getPlayer()
            _grant_quest(player, "mainQuest")

        def isCompleted(self):
            return self.getGame().getMap().getPlayer().hasItem(lambda it: it.getName() == "skullOfRolf")

        def onComplete(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty("completed_rolf", True)
            self._ensure_main_quest()
            self.getGame().getGuiHandler().showMessage(
                "Sergeant Rolf's skull proves his doom; Gooby still prowls the caverns beneath Nouraajd."
            )

    @register(context)
    class DeliverLetterQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("DELIVERED_LETTER")

        def onComplete(self):
            pass

    @register(context)
    class RetrieveRelicQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("RELIC_RETURNED")

        def onComplete(self):
            pass

    @register(context)
    class CleanseCaveQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("CAVE_PURGED")

        def onComplete(self):
            pass

    @register(context)
    class VictorQuest(CQuest):
        def isCompleted(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty("VICTOR_GOOD_END") or game_map.getBoolProperty("VICTOR_BAD_END")

        def onComplete(self):
            pass

    @register(context)
    class OctoBogzQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("completed_octobogz")

        def onComplete(self):
            game = self.getGame()
            player = game.getMap().getPlayer()
            player.addGold(1000)
            player.addItem("ShadowBlade")
            game.getGuiHandler().showMessage("The refugees press 1000 gold and the Shadow Blade into your hands.")

    @register(context)
    class AmuletQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("AMULET_RETURNED")

        def onComplete(self):
            pass

    @trigger(context, "onDestroy", "gooby1")
    class GoobyTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage("Gooby is felled; the tunnels exhale a foul breath.")
            object.getGame().getMap().setBoolProperty("completed_gooby", True)

    @trigger(context, "onDestroy", "cave1")
    class CaveTrigger(CTrigger):
        def trigger(self, object, event):
            object.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
            game_map = object.getGame().getMap()
            player = game_map.getPlayer()
            gooby = object.getGame().createObject("gooby")
            gooby.setStringProperty("name", "gooby1")
            game_map.addObject(gooby)
            gooby.moveTo(100, 100, 0)
            game_map.setBoolProperty("completed_gooby", False)
            player.addItem("skullOfRolf")
            game_map.setBoolProperty("completed_rolf", True)

    @trigger(context, "onDestroy", "catacombs")
    class CatacombsTrigger(CTrigger):
        def trigger(self, obj, event):
            game_map = obj.getGame().getMap()
            player = game_map.getPlayer()
            player.addItem("holyRelic")
            obj.getGame().getGuiHandler().showMessage(obj.getStringProperty("message"))

    @trigger(context, "onDestroy", "cave2")
    class OctoBogzCaveTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getGame().getMap()
            game_map.setBoolProperty("OCTOBOGZ_SLAIN", True)
            if game_map.getBoolProperty("RELIC_RETURNED"):
                object.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
                game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
            else:
                object.getGame().getGuiHandler().showMessage("The OctoBogz lie broken, yet their lair remains befouled.")
            game_map.setBoolProperty("completed_octobogz", True)

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
            print("sell_beer")

        def asked_about_girl(self):
            self.getGame().getMap().setBoolProperty("ASKED_ABOUT_GIRL", True)

    @register(context)
    class TavernDialog2(CDialog):
        def _ensure_victor_quest(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            if not game_map.getBoolProperty("VICTOR_QUEST_STARTED"):
                game_map.setBoolProperty("VICTOR_QUEST_STARTED", True)
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
            game_map = self.getGame().getMap()
            player = self.getGame().getMap().getPlayer()
            if game_map.getBoolProperty("DELIVERED_LETTER"):
                return
            if not player.hasItem(self._is_letter_to_beren):
                player.addItem("letterToBeren")
                self.getGame().getGuiHandler().showMessage("You accept the mayor's sealed missive, wax still warm.")
            self._ensure_quest("deliverLetterQuest")

        def has_letter_quest(self):
            game_map = self.getGame().getMap()
            if game_map.getBoolProperty("DELIVERED_LETTER"):
                return False
            player = self.getGame().getMap().getPlayer()
            if player.hasItem(self._is_letter_to_beren):
                return True
            return _player_has_quest(player, "deliverLetterQuest")

        def talked_to_victor(self):
            return self.getGame().getMap().getBoolProperty("TALKED_TO_VICTOR")

        def start_victor_quest(self):
            game_map = self.getGame().getMap()
            game_map.setBoolProperty("VICTOR_QUEST_STARTED", True)
            self._ensure_quest("victorQuest")

        def spawn_cultists(self):
            game = self.getGame()
            game_map = game.getMap()
            self.start_victor_quest()
            game_map.setBoolProperty("VICTOR_COURTYARD_FOUND", True)
            if game_map.getBoolProperty("VICTOR_GOOD_END"):
                game.getGuiHandler().showMessage("Victor has already reclaimed his daughter; the courtyard now keeps a reverent quiet.")
                return
            if game_map.getBoolProperty("VICTOR_BAD_END"):
                game.getGuiHandler().showMessage(
                    "The mayor mutters that the Cult of Marumi Baso vanished with Victor's daughter before help arrived."
                )
                return
            if game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"):
                _expire_victor_search(game_map)
                return
            game_map.setNumericProperty("VICTOR_COURTYARD_TURN", game_map.getTurn())

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

            coords = Coords(*self.COURTYARD_LEADER_SPAWN)
            if game_map.canStep(coords):
                leader = game.createObject("CultLeader")
                leader.setStringProperty("name", "cultLeaderQuest")
                target_ctrl = game.createObject("CTargetController")
                target_ctrl.setTarget("player")
                leader.setController(target_ctrl)
                game_map.addObject(leader)
                leader.moveTo(coords.x, coords.y, coords.z)
                game_map.setBoolProperty("VICTOR_CULTISTS_SPAWNED", True)

    @trigger(context, "onTurn", "nouraajdTownHall")
    class VictorCourtyardTimerTrigger(CTrigger):
        def trigger(self, obj, event):
            game_map = obj.getGame().getMap()
            if not game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"):
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
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            return player.hasItem(self._is_letter_to_beren) and not game_map.getBoolProperty("DELIVERED_LETTER")

        def can_return_relic(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            return (
                game_map.getBoolProperty("DELIVERED_LETTER")
                and player.hasItem(lambda it: it.getName() == "holyRelic")
                and not game_map.getBoolProperty("RELIC_RETURNED")
            )

        def can_finish_cleanse(self):
            game_map = self.getGame().getMap()
            return (
                game_map.getBoolProperty("RELIC_RETURNED")
                and game_map.getBoolProperty("OCTOBOGZ_CLEARED")
                and not game_map.getBoolProperty("CAVE_PURGED")
            )

        def deliver_letter(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            if self.can_deliver_letter():
                player.removeItem(self._is_letter_to_beren, True)
                game_map.setBoolProperty("DELIVERED_LETTER", True)
                if not game_map.getBoolProperty("RELIC_RETURNED"):
                    self._ensure_quest("retrieveRelicQuest")

        def return_relic(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer()
            if self.can_return_relic():
                player.removeItem(lambda it: it.getName() == "holyRelic", True)
                game_map.setBoolProperty("RELIC_RETURNED", True)
                if game_map.getBoolProperty("OCTOBOGZ_SLAIN"):
                    game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)
                if not game_map.getBoolProperty("CAVE_PURGED"):
                    self._ensure_quest("cleanseCaveQuest")

        def finish_cleanse(self):
            game_map = self.getGame().getMap()
            if self.can_finish_cleanse():
                game_map.setBoolProperty("CAVE_PURGED", True)
                self.getGame().getGuiHandler().showMessage("For a breath, the town is spared and the OctoBogz lie quiet.")
            else:
                self.getGame().getGuiHandler().showMessage("The cave still writhes with OctoBogz corruption.")

    @register(context)
    class OctoBogzDialog(CDialog):
        def accept_quest(self):
            game_map = self.getGame().getMap()
            _grant_quest(game_map.getPlayer(), "octoBogzQuest")
            if not game_map.getBoolProperty("OCTOBOGZ_SLAIN"):
                game_map.setBoolProperty("completed_octobogz", False)

    @trigger(context, "onEnter", "questGiver")
    class QuestGiverTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game.getGuiHandler().showDialog(game.createObject("dialog"))

    @trigger(context, "onDestroy", "cultLeaderQuest")
    class CultLeaderQuestTrigger(CTrigger):
        def trigger(self, leader, event):
            game = leader.getGame()
            game_map = game.getMap()
            if not game_map.getBoolProperty("VICTOR_QUEST_STARTED"):
                return
            if not game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"):
                return
            if game_map.getBoolProperty("VICTOR_BAD_END") or game_map.getBoolProperty("VICTOR_GOOD_END"):
                return
            if game_map.getBoolProperty("VICTOR_REWARD_CLAIMED"):
                return
            player = game.getMap().getPlayer()
            player.addGold(500)
            player.healProc(100)
            game.getGuiHandler().showDialog(game.createObject("victorRewardDialog"))
            game.getGuiHandler().showTrade(game.createObject("victorMarket"))
            game_map.setBoolProperty("VICTOR_HELP", True)
            game_map.setBoolProperty("VICTOR_GOOD_END", True)
            game_map.setBoolProperty("VICTOR_BAD_END", False)
            game_map.setBoolProperty("VICTOR_REWARD_CLAIMED", True)
            _clear_victor_encounter(game_map)

    @trigger(context, "onEnter", "oldWoman")
    class OldWomanTrigger(CTrigger):
        def trigger(self, obj, event):
            if event.getCause().isPlayer():
                game = obj.getGame()
                game_map = game.getMap()
                if game_map.getBoolProperty("AMULET_RETURNED"):
                    game_map.removeObject(obj)
                    return
                player = game_map.getPlayer()
                if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                    game.getGuiHandler().showDialog(game.createObject("questReturnDialog"))
                elif not game_map.getBoolProperty("AMULET_QUEST_STARTED"):
                    game.getGuiHandler().showDialog(game.createObject("questDialog"))
                else:
                    game.getGuiHandler().showMessage("The goblin still clutches my amulet; please bring it back!")

    @register(context)
    class QuestDialog(CDialog):
        def start_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            if game_map.getBoolProperty("AMULET_QUEST_STARTED"):
                return
            player = game_map.getPlayer()
            _grant_quest(player, "amuletQuest")
            goblin = game.createObject("goblinThief")
            goblin.setStringProperty("name", "amuletGoblin")
            game_map.addObject(goblin)
            # spawn near the old woman within map bounds
            goblin.moveTo(195, 8, 0)
            game_map.setBoolProperty("AMULET_QUEST_STARTED", True)

    @register(context)
    class QuestReturnDialog(CDialog):
        def complete_amulet_quest(self):
            game = self.getGame()
            game_map = game.getMap()
            player = game_map.getPlayer()
            if player.hasItem(lambda it: it.getName() == "preciousAmulet"):
                player.removeItem(lambda it: it.getName() == "preciousAmulet", True)
                player.addGold(50)
                game_map.setBoolProperty("AMULET_RETURNED", True)
                game_map.setBoolProperty("AMULET_QUEST_STARTED", False)
                amulet_goblin = game_map.getObjectByName("amuletGoblin")
                if amulet_goblin:
                    game_map.removeObject(amulet_goblin)
                old_woman = game_map.getObjectByName("oldWoman")
                if old_woman:
                    game_map.removeObject(old_woman)
                game.getGuiHandler().showMessage("The old woman presses 50 gold upon you, tears streaking her dust-caked cheeks.")
