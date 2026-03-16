def load(self, context):
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import register
    from game import trigger

    def ensure_quest(game_map, quest_name):
        player = game_map.getPlayer()
        for quest in player.getQuests():
            if quest.getName() == quest_name:
                return
        player.addQuest(quest_name)

    def start_ritual(game_map):
        if game_map.getBoolProperty("ritual_active"):
            return
        game_map.setBoolProperty("ritual_active", True)
        game_map.setBoolProperty("ritual_started", True)
        game_map.setNumericProperty("ritual_last_wave_turn", game_map.getTurn())
        game_map.setNumericProperty("ritual_last_tick_turn", game_map.getTurn())
        game_map.getGame().getGuiHandler().showMessage("The sanctum erupts. The soul-binding ritual has begun.")

    def spawn_wave(game_map):
        spawn_points = ["waveSpawnNorth", "waveSpawnWest", "waveSpawnEast"]
        countdown = game_map.getNumericProperty("ritual_countdown")
        if countdown <= 4:
            wave = ["ritualMage", "ritualPritz", "ritualCultist"]
        elif countdown <= 8:
            wave = ["ritualPritz", "ritualCultist"]
        else:
            wave = ["ritualCultist"]

        for i, unit in enumerate(wave):
            marker = game_map.getObjectByName(spawn_points[i % len(spawn_points)])
            if marker:
                game_map.addObjectByName(unit, marker.getCoords())

    def try_spawn_leader(game_map):
        if game_map.getBoolProperty("leader_spawned"):
            return
        spawn_marker = game_map.getObjectByName("bossSpawn")
        if not spawn_marker:
            return
        leader = game_map.getGame().createObject("ritualLeaderTemplate")
        if leader:
            leader.setStringProperty("name", "ritualLeader")
            game_map.addObject(leader)
            leader.moveTo(spawn_marker.getCoords().x, spawn_marker.getCoords().y, spawn_marker.getCoords().z)
            game_map.setBoolProperty("leader_spawned", True)
            game_map.getGame().getGuiHandler().showMessage("The Ritual Leader descends into the sanctum!")

    def set_bad_outcome(game_map, message):
        if game_map.getBoolProperty("good_ending") or game_map.getBoolProperty("bad_ending"):
            return
        game_map.setBoolProperty("bad_ending", True)
        game_map.setBoolProperty("ritual_finished", True)
        game_map.getGame().getGuiHandler().showMessage(message)

    def update_anchor_progress(game_map):
        if game_map.getNumericProperty("anchors_destroyed_count") >= 3 and not game_map.getBoolProperty(
            "anchors_destroyed"
        ):
            game_map.setBoolProperty("anchors_destroyed", True)
            game_map.getGame().getGuiHandler().showMessage("All anchors are down. The leader is exposed.")
            try_spawn_leader(game_map)

    @register(context)
    class StartEvent(CEvent):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            game_map = self.getMap()
            if game_map.getBoolProperty("ritual_initialized"):
                return

            game_map.getGame().getGuiHandler().showMessage(self.getStringProperty("text"))
            game_map.removeAll(lambda ob: ob.getName() == self.getName())

            game_map.setBoolProperty("ritual_initialized", True)
            game_map.setBoolProperty("ritual_started", False)
            game_map.setBoolProperty("ritual_active", False)
            game_map.setBoolProperty("ritual_finished", False)
            game_map.setBoolProperty("anchors_destroyed", False)
            game_map.setBoolProperty("anchor_north_destroyed", False)
            game_map.setBoolProperty("anchor_crypt_destroyed", False)
            game_map.setBoolProperty("anchor_sanctum_destroyed", False)
            game_map.setBoolProperty("leader_spawned", False)
            game_map.setBoolProperty("leader_defeated", False)
            game_map.setBoolProperty("captive_lost", False)
            game_map.setBoolProperty("captive_freed", False)
            game_map.setBoolProperty("good_ending", False)
            game_map.setBoolProperty("bad_ending", False)
            game_map.setBoolProperty("reward_claimed", False)
            game_map.setNumericProperty("anchors_destroyed_count", 0)
            game_map.setNumericProperty("ritual_countdown", 14)
            game_map.setNumericProperty("ritual_last_wave_turn", 0)
            game_map.setNumericProperty("ritual_last_tick_turn", 0)

            ensure_quest(game_map, "ritualQuest")
            ensure_quest(game_map, "destroyAnchorsQuest")
            ensure_quest(game_map, "rescueCaptiveQuest")
            ensure_quest(game_map, "finalResolutionQuest")

    @register(context)
    class RitualQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("ritual_started")

        def onComplete(self):
            pass

    @register(context)
    class DestroyAnchorsQuest(CQuest):
        def isCompleted(self):
            return self.getGame().getMap().getBoolProperty("anchors_destroyed")

        def onComplete(self):
            pass

    @register(context)
    class RescueCaptiveQuest(CQuest):
        def isCompleted(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty("captive_freed") or game_map.getBoolProperty("captive_lost")

        def onComplete(self):
            pass

    @register(context)
    class FinalResolutionQuest(CQuest):
        def isCompleted(self):
            game_map = self.getGame().getMap()
            return game_map.getBoolProperty("good_ending") or game_map.getBoolProperty("bad_ending")

        def onComplete(self):
            pass

    @register(context)
    class ChapelWarningDialog(CDialog):
        pass

    @register(context)
    class RecordsDialog(CDialog):
        pass

    @register(context)
    class CapturedSoulDialog(CDialog):
        def can_free_captive(self):
            game_map = self.getGame().getMap()
            return (
                game_map.getBoolProperty("anchors_destroyed")
                and game_map.getBoolProperty("leader_defeated")
                and not game_map.getBoolProperty("captive_lost")
                and not game_map.getBoolProperty("captive_freed")
            )

        def is_captive_lost(self):
            return self.getGame().getMap().getBoolProperty("captive_lost")

        def need_more_work(self):
            game_map = self.getGame().getMap()
            return not self.can_free_captive() and not game_map.getBoolProperty("captive_lost")

        def free_captive(self):
            game_map = self.getGame().getMap()
            if not self.can_free_captive():
                return

            game_map.setBoolProperty("captive_freed", True)
            game_map.setBoolProperty("good_ending", True)
            game_map.setBoolProperty("ritual_finished", True)

            if not game_map.getBoolProperty("reward_claimed"):
                player = game_map.getPlayer()
                player.addGold(300)
                player.addItem("LifePotion")
                game_map.setBoolProperty("reward_claimed", True)
                self.getGame().getGuiHandler().showMessage(
                    "You earn 300 gold and a Life Potion for saving the captive."
                )

    @trigger(context, "onTurn", "ritualTurnAnchor")
    class RitualTurnTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            if not game_map.getBoolProperty("ritual_active") or game_map.getBoolProperty("ritual_finished"):
                return

            current_turn = game_map.getTurn()
            last_tick = game_map.getNumericProperty("ritual_last_tick_turn")
            if current_turn - last_tick >= 5:
                countdown = game_map.getNumericProperty("ritual_countdown") - 1
                game_map.setNumericProperty("ritual_countdown", countdown)
                game_map.setNumericProperty("ritual_last_tick_turn", current_turn)

                if countdown == 8:
                    game_map.getGame().getGuiHandler().showMessage("The chant quickens. The stained glass darkens.")
                if countdown == 4:
                    game_map.getGame().getGuiHandler().showMessage("The chapel trembles. The captive is almost lost.")
                if countdown <= 0:
                    game_map.setBoolProperty("captive_lost", True)
                    set_bad_outcome(game_map, "The final verse completes. The captive soul is bound forever.")

            last_wave = game_map.getNumericProperty("ritual_last_wave_turn")
            if current_turn - last_wave >= 4 and not game_map.getBoolProperty("anchors_destroyed"):
                spawn_wave(game_map)
                game_map.setNumericProperty("ritual_last_wave_turn", current_turn)

            if game_map.getBoolProperty("anchors_destroyed") and not game_map.getBoolProperty("leader_spawned"):
                try_spawn_leader(game_map)

    @trigger(context, "onEnter", "ritualWitness")
    class WitnessTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("chapelWarningDialog"))

    @trigger(context, "onEnter", "chapelRecords")
    class RecordsTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("recordsDialog"))

    @trigger(context, "onEnter", "sanctumThreshold")
    class SanctumTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                start_ritual(object.getMap())

    @trigger(context, "onDestroy", "anchorNorth")
    class AnchorNorthTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            if game_map.getBoolProperty("anchor_north_destroyed"):
                return
            game_map.setBoolProperty("anchor_north_destroyed", True)
            game_map.incProperty("anchors_destroyed_count", 1)
            start_ritual(game_map)
            game_map.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
            spawn_wave(game_map)
            update_anchor_progress(game_map)

    @trigger(context, "onDestroy", "anchorCrypt")
    class AnchorCryptTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            if game_map.getBoolProperty("anchor_crypt_destroyed"):
                return
            game_map.setBoolProperty("anchor_crypt_destroyed", True)
            game_map.incProperty("anchors_destroyed_count", 1)
            start_ritual(game_map)
            game_map.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
            spawn_wave(game_map)
            update_anchor_progress(game_map)

    @trigger(context, "onDestroy", "anchorSanctum")
    class AnchorSanctumTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            if game_map.getBoolProperty("anchor_sanctum_destroyed"):
                return
            game_map.setBoolProperty("anchor_sanctum_destroyed", True)
            game_map.incProperty("anchors_destroyed_count", 1)
            start_ritual(game_map)
            game_map.getGame().getGuiHandler().showMessage(object.getStringProperty("message"))
            update_anchor_progress(game_map)

    @trigger(context, "onDestroy", "ritualLeader")
    class RitualLeaderTrigger(CTrigger):
        def trigger(self, object, event):
            game_map = object.getMap()
            game_map.setBoolProperty("leader_defeated", True)
            game_map.setBoolProperty("ritual_active", False)

            if game_map.getBoolProperty("captive_lost"):
                set_bad_outcome(game_map, "The leader falls, but the soul-binding is already complete.")
                if not game_map.getBoolProperty("reward_claimed"):
                    game_map.getPlayer().addGold(100)
                    game_map.setBoolProperty("reward_claimed", True)
                return

            game_map.getGame().getGuiHandler().showMessage(
                "The leader is dead. Reach the stained glass prison and free the captive."
            )

    @trigger(context, "onEnter", "ritualCaptive")
    class CaptiveTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer():
                object.getGame().getGuiHandler().showDialog(object.getGame().createObject("capturedSoulDialog"))

    @trigger(context, "onEnter", "hazardNorth")
    class HazardNorthTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and object.getMap().getBoolProperty("ritual_active"):
                object.getGame().getGuiHandler().showMessage("Soulfire erupts from the floor. Move quickly.")
                object.getMap().addObjectByName(
                    "ritualCultist", object.getMap().getObjectByName("waveSpawnNorth").getCoords()
                )

    @trigger(context, "onEnter", "hazardCenter")
    class HazardCenterTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and object.getMap().getBoolProperty("ritual_active"):
                object.getGame().getGuiHandler().showMessage("The glass hums and drains your strength.")

    @trigger(context, "onEnter", "hazardSouth")
    class HazardSouthTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and object.getMap().getBoolProperty("ritual_active"):
                object.getGame().getGuiHandler().showMessage("Crypt vents exhale poison. More defenders gather.")
                object.getMap().addObjectByName(
                    "ritualPritz", object.getMap().getObjectByName("waveSpawnWest").getCoords()
                )

    @trigger(context, "onEnter", "entryCourtyard")
    class EntryCourtyardTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getMap().getBoolProperty("seen_entry_courtyard"):
                object.getMap().setBoolProperty("seen_entry_courtyard", True)
                object.getGame().getGuiHandler().showMessage(
                    "You step into the chapel courtyard, where rain masks whispered chants."
                )

    @trigger(context, "onEnter", "outerChapel")
    class OuterChapelTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getMap().getBoolProperty("seen_outer_chapel"):
                object.getMap().setBoolProperty("seen_outer_chapel", True)
                object.getGame().getGuiHandler().showMessage("The outer chapel reeks of incense and blood.")

    @trigger(context, "onEnter", "sideCrypt")
    class SideCryptTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getMap().getBoolProperty("seen_side_crypt"):
                object.getMap().setBoolProperty("seen_side_crypt", True)
                object.getGame().getGuiHandler().showMessage("The side crypt is lined with fresh ritual carvings.")

    @trigger(context, "onEnter", "ritualSanctum")
    class SanctumAreaTrigger(CTrigger):
        def trigger(self, object, event):
            if event.getCause().isPlayer() and not object.getMap().getBoolProperty("seen_ritual_sanctum"):
                object.getMap().setBoolProperty("seen_ritual_sanctum", True)
                object.getGame().getGuiHandler().showMessage(
                    "The ritual sanctum burns with violet fire around the prison."
                )
