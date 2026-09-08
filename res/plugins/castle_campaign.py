# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared, save-safe objectives for the Long Live the Queen adaptation."""

import json


def decodeMission(text):
    return json.loads((text or "{}").removeprefix("castleMission:"))


def missionData(game_map):
    mission = game_map.getObjectByName("castleMission") if game_map else None
    if not mission:
        return {}
    return decodeMission(mission.getStringProperty("campaign_mission"))


def objectiveFlag(object_id):
    return "campaign_castleCaptured_" + object_id


def defeatedFlag(actor_id):
    return "campaign_castleDefeated_" + actor_id


def canInteract(marker, player):
    game_map = marker.getMap() if marker else None
    if not game_map or not player or not player.isPlayer() or not player.isAlive():
        return False
    if game_map.getGame().getMap() != game_map or game_map.getPlayer() != player or player.getMap() != game_map:
        return False
    here, there = marker.getCoords(), player.getCoords()
    return here.z == there.z and max(abs(here.x - there.x), abs(here.y - there.y)) <= 1


def finishMission(game_map):
    from game import campaign

    data = missionData(game_map)
    player = game_map.getPlayer() if game_map else None
    if not data or not player or not player.isAlive() or game_map.getGame().getMap() != game_map:
        return False
    finished_flag = "campaign_castleFinished_" + data["scenarioId"]
    if game_map.getBoolProperty(finished_flag):
        return False
    objectives = data.get("objectiveIds", [])
    if not objectives or not all(game_map.getBoolProperty(objectiveFlag(name)) for name in objectives):
        return False
    if not all(game_map.getBoolProperty(defeatedFlag(name)) for name in data.get("enemyHeroIds", [])):
        return False
    # Old retained map handles must never advance a later active campaign chapter.
    store = campaign.state(game_map.getGame())
    if (
        store
        and store.active()
        and (store.campaign_id() != "longLiveTheQueen" or store.scenario() != data["scenarioId"])
    ):
        return False
    game_map.setBoolProperty(finished_flag, True)
    player.setBoolProperty("campaign_castleCompleted_" + data["scenarioId"], True)
    player.addQuest(data["questId"])
    player.addGold(data.get("victoryGold", 0))
    player.checkQuests()
    campaign.complete_scenario(game_map.getGame(), "completed", fallback_map=data.get("nextMap") or None)
    return True


def captureObjective(marker, player):
    if not canInteract(marker, player):
        return False
    game_map = marker.getMap()
    object_id = marker.getStringProperty("campaign_objectiveId")
    data = missionData(game_map)
    captures = data.get("captureIds", data.get("objectiveIds", []))
    if object_id not in captures or game_map.getBoolProperty(objectiveFlag(object_id)):
        return False
    guards = [name for name in marker.getStringProperty("campaign_guards").split(",") if name]
    if any(not game_map.getBoolProperty(defeatedFlag(name)) for name in guards):
        game_map.getGame().getGuiHandler().showMessage(
            "The garrison still holds this position. Defeat its defenders first."
        )
        return False
    game_map.setBoolProperty(objectiveFlag(object_id), True)
    marker.setStringProperty("animation", "images/castle/liberatedBanner")
    player.addGold(marker.getNumericProperty("campaign_rewardGold"))
    game_map.getGame().getGuiHandler().showMessage(marker.getStringProperty("label") + " now flies Erathia's banner.")
    finishMission(game_map)
    return True


def markDefeated(actor):
    game_map = actor.getMap() if actor else None
    if not game_map or actor.isAlive() or game_map.getGame().getMap() != game_map:
        return False
    data = missionData(game_map)
    if actor.getName() not in data.get("defenderIds", []):
        return False
    flag = defeatedFlag(actor.getName())
    if game_map.getBoolProperty(flag):
        return False
    game_map.setBoolProperty(flag, True)
    finishMission(game_map)
    return True


def load(self, context):
    from game import CBuilding
    from game import CDialog
    from game import CEvent
    from game import CQuest
    from game import CTrigger
    from game import Coords
    from game import claim_once
    from game import register

    @register(context)
    class CastleMissionStart(CEvent):
        def reportProgress(self):
            game_map = self.getMap()
            data = missionData(game_map)
            captured = sum(game_map.getBoolProperty(objectiveFlag(name)) for name in data.get("objectiveIds", []))
            defeated = sum(game_map.getBoolProperty(defeatedFlag(name)) for name in data.get("enemyHeroIds", []))
            self.getGame().getGuiHandler().showMessage(
                f"Positions secured: {captured}/{len(data.get('objectiveIds', []))}. "
                f"Enemy commanders defeated: {defeated}/{len(data.get('enemyHeroIds', []))}."
            )

        def onCreate(self, event):
            data = decodeMission(self.getStringProperty("campaign_mission"))
            game_map = self.getMap()
            if not game_map:
                return
            for actor_id in data.get("defenderIds", []):
                trigger = self.getGame().createObject("CastleDefeatTrigger")
                trigger.setStringProperty("object", actor_id)
                trigger.setStringProperty("event", "onDestroy")
                game_map.getEventHandler().registerTrigger(trigger)
            for actor_id in ("castleCatherine", "castleChristian"):
                trigger = self.getGame().createObject("CastleOfficerTrigger")
                trigger.setStringProperty("object", actor_id)
                trigger.setStringProperty("event", "onEnter")
                game_map.getEventHandler().registerTrigger(trigger)

        def initializeMission(self):
            game_map = self.getMap()
            player = game_map.getPlayer() if game_map else None
            if (
                not player
                or not player.isPlayer()
                or not player.isAlive()
                or self.getGame().getMap() != game_map
                or self.getBoolProperty("campaign_castleInitialized")
            ):
                return False
            data = missionData(game_map)
            player.addQuest(data["questId"])
            if claim_once(game_map, "campaign_castleStarted_" + data["scenarioId"]):
                player.healProc(100)
                player.addItem("LifePotion")
                player.addItem("LifePotion")
                self.getGame().getGuiHandler().showMessage(data["intro"])
            self.setBoolProperty("campaign_castleInitialized", True)
            return True

        def onTurn(self, event):
            self.initializeMission()

        def onEnter(self, event):
            if canInteract(self, event.getCause() if event else None):
                self.initializeMission()

    @register(context)
    class CastleObjective(CBuilding):
        def capture(self, player):
            return captureObjective(self, player)

        def onEnter(self, event):
            return self.capture(event.getCause() if event else None)

    @register(context)
    class CastleMissionQuest(CQuest):
        def isCompleted(self):
            game_map = self.getGame().getMap()
            player = game_map.getPlayer() if game_map else None
            completed_flag = "campaign_castleCompleted_" + self.getStringProperty("campaign_scenarioId")
            return bool(player and player.getBoolProperty(completed_flag))

        def getObjective(self):
            text = self.getStringProperty("campaign_questText")
            if self.isCompleted():
                return text + " Completed."
            game_map = self.getGame().getMap()
            data = missionData(game_map)
            if data.get("scenarioId") != self.getStringProperty("campaign_scenarioId"):
                return text
            captured = sum(game_map.getBoolProperty(objectiveFlag(name)) for name in data["objectiveIds"])
            progress = f" Positions: {captured}/{len(data['objectiveIds'])}."
            if data.get("enemyHeroIds"):
                defeated = sum(game_map.getBoolProperty(defeatedFlag(name)) for name in data["enemyHeroIds"])
                progress += f" Commanders: {defeated}/{len(data['enemyHeroIds'])}."
            if data.get("scenarioId") == "griffinCliff":
                remaining = sorted(
                    game_map.getObjectByName(name).getStringProperty("label")
                    for name in data["objectiveIds"]
                    if not game_map.getBoolProperty(objectiveFlag(name))
                )
                if remaining:
                    progress += " Remaining: " + ", ".join(remaining) + "."
            return text + progress

        def getReward(self):
            return self.getStringProperty("campaign_rewardText")

        def getHint(self):
            return self.getStringProperty("campaign_hint")

        def onComplete(self):
            pass

    @register(context)
    class CastleDefeatTrigger(CTrigger):
        def trigger(self, object, event):
            return markDefeated(object)

    @register(context)
    class CastleOfficerDialog(CDialog):
        def reportProgress(self):
            self.getGame().getMap().getObjectByName("castleMission").reportProgress()

    @register(context)
    class CastleOfficerTrigger(CTrigger):
        def trigger(self, object, event):
            player = event.getCause() if event else None
            if canInteract(object, player):
                dialog_id = object.getStringProperty("campaign_dialog")
                self.getGame().getGuiHandler().showDialog(self.getGame().createObject(dialog_id))

    @register(context)
    class CastlePortal(CBuilding):
        def target(self):
            return Coords(
                self.getNumericProperty("campaign_targetX"),
                self.getNumericProperty("campaign_targetY"),
                self.getNumericProperty("campaign_targetZ"),
            )

        def publishEdge(self):
            game_map = self.getMap()
            if not game_map:
                return
            target = self.target()
            if not game_map.canStep(target):
                game_map.unregisterNavigationEdgesForObject(self.getName())
                return
            if not game_map.hasNavigationEdge(self.getCoords(), target, self.getName()):
                game_map.unregisterNavigationEdgesForObject(self.getName())
                game_map.registerNavigationEdge(self.getCoords(), target, True, False, 1, self.getName())

        def onCreate(self, event):
            self.publishEdge()

        def onTurn(self, event):
            self.publishEdge()

        def onDestroy(self, event):
            if self.getMap():
                self.getMap().unregisterNavigationEdgesForObject(self.getName())

        def onEnter(self, event):
            player = event.getCause() if event else None
            if not canInteract(self, player):
                return
            if self.getStringProperty("campaign_portalKind") == "diagonalPassage":
                # The paired edges permit a normal movement step, including combat
                # and visits on its destination. Teleporting here would skip an
                # intermediate cell shared by two successive narrow passages.
                return
            target = self.target()
            current = self.getCoords()
            arrival = f"{current.x},{current.y},{current.z}"
            if player.getStringProperty("campaign_castlePortalArrival") == arrival:
                player.setStringProperty("campaign_castlePortalArrival", "")
                return
            if not self.getMap().canStep(target):
                self.getGame().getGuiHandler().showMessage("The landing is blocked.")
                return
            player.setStringProperty("campaign_castlePortalArrival", f"{target.x},{target.y},{target.z}")
            player.setCoords(target)

    @register(context)
    class CastleSupply(CBuilding):
        def onEnter(self, event):
            player = event.getCause() if event else None
            if canInteract(self, player) and claim_once(self.getMap(), "campaign_castleSupply_" + self.getName()):
                player.healProc(100)
                player.addItem("LifePotion")
                player.addGold(self.getNumericProperty("campaign_rewardGold"))
                message = self.getStringProperty("campaign_aidMessage")
                self.getGame().getGuiHandler().showMessage(
                    message or "The loyal garrison tends your wounds and shares its supplies."
                )
