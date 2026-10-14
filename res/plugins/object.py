# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025-2026  Andrzej Lis
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


def load(self, context):
    from game import resumableHook, uiRequest, flowGame, removeObjectByNameFlow
    from game import requirementMessage
    from game import randint
    from game import claim_once
    from game import CBuilding
    from game import Coords
    from game import register
    from game import CScroll

    def acting_player(event):
        if not event:
            return None
        cause = event.getCause()
        return cause if cause and cause.isPlayer() else None

    def showInfoFlow(building, text):
        if text and building.getMap():
            (
                yield uiRequest(
                    "showReader",
                    flowGame(building.getMap().getGame()),
                    building.getStringProperty("label") or "Mapmaker's notes",
                    text,
                )
            )

    def notifyAdventure(building, text):
        if text and building.getMap():
            building.getMap().getGame().getGuiHandler().notify(text)

    def raise_base_stat(creature, stat, bonus):
        base_stats = creature.getObjectProperty("baseStats")
        if not base_stats:
            return False
        base_stats.setNumericProperty(stat, base_stats.getNumericProperty(stat) + bonus)
        return True

    @register(context)
    class WayPoint(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if not event or not event.getCause():
                return
            exit_coords = self.getExit()
            if exit_coords:
                yield uiRequest("gui.moveTo", event.getCause(), exit_coords.x, exit_coords.y, exit_coords.z)

        # merge with onEnter logic
        def onTurn(self, event):
            self.publishWaypoint()

        def onCreate(self, event):
            self.publishWaypoint()

        def onDestroy(self, event):
            self.clearNavigationEdge()

        def clearNavigationEdge(self):
            game_map = self.getMap()
            if game_map:
                game_map.unregisterNavigationEdgesForObject(self.getName())

        def publishNavigationEdge(self, exit_coords):
            game_map = self.getMap()
            if game_map:
                if game_map.hasNavigationEdge(self.getCoords(), exit_coords, self.getName()):
                    return
                game_map.unregisterNavigationEdgesForObject(self.getName())
                game_map.registerNavigationEdge(self.getCoords(), exit_coords, True, False, 1, self.getName())

        def publishWaypoint(self):
            exit_coords = self.getExit()
            if not exit_coords:
                self.setBoolProperty("waypoint", False)
                self.clearNavigationEdge()
                return
            self.setBoolProperty("waypoint", True)
            self.setNumericProperty("x", exit_coords.x)
            self.setNumericProperty("y", exit_coords.y)
            self.setNumericProperty("z", exit_coords.z)
            self.publishNavigationEdge(exit_coords)

        def getExit(self):
            pass

    @register(context)
    class Teleporter(WayPoint):
        def getExit(self):
            if self.getBoolProperty("enabled"):
                exit = self.getStringProperty("exit")
                if not exit or not self.getMap():
                    return None
                target = self.getMap().getObjectByName(exit)
                if not target:
                    return None
                loc = target.getCoords()
                if self.getMap().canStep(loc):
                    return loc
            return None

    @register(context)
    class GroundHole(WayPoint):
        def getExit(self):
            if not self.getMap():
                return None
            loc = self.getCoords()
            target = Coords(loc.x, loc.y, loc.z - 1)
            return target if self.getMap().canStep(target) else None

    @register(context)
    class Market(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if event and event.getCause() and event.getCause().isPlayer():
                market = self.getObjectProperty("market")
                if market:
                    (yield uiRequest("gui.showTrade", market))

    @register(context)
    class SignPost(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if event.getCause().isPlayer():
                (
                    yield uiRequest(
                        "showReader", flowGame(self.getMap().getGame()), "Signpost", self.getStringProperty("text")
                    )
                )

    @register(context)
    class Chest(CBuilding):
        @resumableHook
        def onEnter(self, event):
            player = acting_player(event)
            game_map = self.getMap()
            if not player or not game_map or game_map.getPlayer() != player:
                return
            if not claim_once(self, "looted"):
                return
            (yield uiRequest("gui.addRandomLoot", player, self.getNumericProperty("value")))

    @register(context)
    class Cave(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("enabled"):
                self.setBoolProperty("enabled", False)
                self.setBoolProperty("lairOpened", True)
                self.setNumericProperty("lairSpawnIndex", 0)
            if self.getBoolProperty("lairOpened"):
                yield from self.openLairFlow()

        def openLairFlow(self):
            game_map = self.getMap()
            location = self.getCoords()
            offsets = [(i, j) for i in range(-1, 2) for j in range(-1, 2) if i or j]
            index = max(0, min(int(self.getNumericProperty("lairSpawnIndex")), len(offsets)))
            while index < len(offsets):
                i, j = offsets[index]
                x, y, z = location.x + i, location.y + j, location.z
                pending_name = self.getStringProperty("lairSpawnName")
                if pending_name:
                    mon = game_map.getObjectByName(pending_name)
                elif game_map.canStep(Coords(x, y, z)):
                    mon = self.getObjectProperty("monster").clone()
                    game_map.addObject(mon)
                    self.setStringProperty("lairSpawnName", mon.getName())
                else:
                    mon = None
                if mon is not None:
                    placed = mon.getCoords() if pending_name else None
                    if placed is None or (placed.x, placed.y, placed.z) != (x, y, z):
                        yield uiRequest("gui.moveTo", mon, x, y, z)
                self.setStringProperty("lairSpawnName", "")
                index += 1
                self.setNumericProperty("lairSpawnIndex", index)
            yield from removeObjectByNameFlow(game_map, self.getName())

        @resumableHook
        def onTurn(self, event):
            if self.getBoolProperty("lairOpened"):
                yield from self.openLairFlow()
                return
            chance = self.getNumericProperty("chance")
            monsters = self.getNumericProperty("monsters")
            enabled = self.getBoolProperty("enabled")
            if enabled and monsters > 0 and (randint(1, 100)) <= chance:
                location = self.getCoords()
                mon = self.getObjectProperty("monster").clone()
                self.getMap().addObject(mon)
                self.incProperty("monsters", -1)
                (yield uiRequest("gui.moveTo", mon, location.x, location.y, location.z))

    # Heroes of Might and Magic III inspired adventure objects. Each visitable
    # location keys its one-time rewards to the visiting player through
    # claim_once, so per-player state survives saves via ordinary properties.
    # The learning stone, witch hut, and obelisk carry an Adventure prefix
    # because map scripts (ninemarches, sunderedmarch) already register
    # map-local classes under the plain names.

    @register(context)
    class AdventureLearningStone(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if claim_once(player, "learningStone_" + self.getName()):
                player.addExp(self.getNumericProperty("exp"))
                notifyAdventure(self, "Ancient runes etched into the stone sharpen your mind. You gain experience.")

    @register(context)
    class Campfire(CBuilding):
        @resumableHook
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if not claim_once(self, "looted"):
                yield from removeObjectByNameFlow(self.getMap(), self.getName())
                return
            player.addGold(self.getNumericProperty("gold"))
            (yield uiRequest("gui.addRandomLoot", player, self.getNumericProperty("value")))
            notifyAdventure(self, "You scavenge supplies abandoned around a cold campfire.")
            (yield from removeObjectByNameFlow(self.getMap(), self.getName()))

    @register(context)
    class FountainOfYouth(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if player:
                player.healProc(self.getNumericProperty("healing"))

    @register(context)
    class MagicWell(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if player:
                player.addManaProc(100)

    @register(context)
    class Windmill(CBuilding):
        def onTurn(self, event):
            if self.getNumericProperty("turns") < self.getNumericProperty("cooldown"):
                self.incProperty("turns", 1)

        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if self.getNumericProperty("turns") >= self.getNumericProperty("cooldown"):
                self.setNumericProperty("turns", 0)
                player.addGold(self.getNumericProperty("gold"))
                notifyAdventure(self, "The miller shares the profits of the last harvest with you.")

    @register(context)
    class TreeOfKnowledge(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            claim = "treeOfKnowledge_" + self.getName()
            if player.getBoolProperty(claim):
                return
            cost = self.getNumericProperty("cost")
            if player.getGold() < cost:
                requirementMessage(
                    self.getMap().getGame(),
                    self,
                    "The tree whispers of enlightenment, but demands " + str(cost) + " gold as tribute.",
                )
                return
            player.setBoolProperty(claim, True)
            player.takeGold(cost)
            level = player.getLevel()
            exp_for_next_level = level * (level + 1) * 500
            missing = exp_for_next_level - player.getNumericProperty("exp")
            if missing > 0:
                player.addExp(missing)
            notifyAdventure(self, "You meditate beneath the Tree of Knowledge and reach a new level of understanding.")

    @register(context)
    class TrainingGround(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            stat = self.getStringProperty("stat")
            bonus = self.getNumericProperty("bonus")
            if not stat or bonus <= 0:
                return
            if not player.getObjectProperty("baseStats"):
                return
            if not claim_once(player, "trained_" + self.getName()):
                return
            raise_base_stat(player, stat, bonus)
            notifyAdventure(
                self, "The training pays off. Your " + stat + " permanently increases by " + str(bonus) + "."
            )

    @register(context)
    class MercenaryCamp(TrainingGround):
        pass

    @register(context)
    class MarlettoTower(TrainingGround):
        pass

    @register(context)
    class StarAxis(TrainingGround):
        pass

    @register(context)
    class AdventureWitchHut(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            bonus = self.getNumericProperty("bonus")
            if bonus <= 0 or not player.getObjectProperty("baseStats"):
                return
            if not claim_once(player, "witchHut_" + self.getName()):
                return
            stats = ["strength", "agility", "stamina", "intelligence"]
            stat = stats[randint(0, len(stats) - 1)]
            raise_base_stat(player, stat, bonus)
            notifyAdventure(
                self, "The witch brews a pungent draught. Your " + stat + " increases by " + str(bonus) + "."
            )

    @register(context)
    class AdventureObelisk(CBuilding):
        @resumableHook
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if claim_once(player, "obelisk_" + self.getName()):
                player.incProperty("obelisksVisited", 1)
            (yield from showInfoFlow(self, self.getStringProperty("text")))

    @register(context)
    class WarriorsTomb(CBuilding):
        @resumableHook
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if not self.getBoolProperty("enabled"):
                notifyAdventure(self, "The tomb lies plundered and empty.")
                return
            self.setBoolProperty("enabled", False)
            maximum_toll = player.getHpMax() * self.getNumericProperty("damage") // 100
            try:
                (yield uiRequest("gui.addRandomLoot", player, self.getNumericProperty("value")))
            finally:
                # Loot is settled even on cancellation. Settle its toll using the
                # same player without consulting services of an inactive session.
                toll = min(player.getHp() - 1, maximum_toll)
                if toll > 0:
                    player.setHp(player.getHp() - toll)
            notifyAdventure(self, "You pry treasure from the warrior's tomb, but its restless guardian exacts a toll.")

    @register(context)
    class Sirens(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            sacrifice = min(player.getHp() - 1, player.getHpMax() * self.getNumericProperty("sacrifice") // 100)
            if sacrifice <= 0:
                return
            if not claim_once(player, "sirens_" + self.getName()):
                return
            # The song's toll cannot be armored or blocked away, so it is
            # applied straight to HP instead of through the damage pipeline.
            player.setHp(player.getHp() - sacrifice)
            player.addExp(sacrifice * self.getNumericProperty("expPerHp"))
            notifyAdventure(self, "The sirens' song drains your life, yet their secrets harden your resolve.")

    @register(context)
    class KeymastersTent(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            color = self.getStringProperty("keyColor")
            if not color:
                return
            claim = "borderPass_" + color
            if not player.getBoolProperty(claim):
                player.setBoolProperty(claim, True)
                notifyAdventure(self, "The keymaster hands you the " + color + " pass.")

    @register(context)
    class BorderGuard(CBuilding):
        @resumableHook
        def onTurn(self, event):
            game_map = self.getMap()
            if not game_map:
                return
            player = game_map.getPlayer()
            color = self.getStringProperty("keyColor")
            if not player or not color or not player.getBoolProperty("borderPass_" + color):
                return
            here = self.getCoords()
            there = player.getCoords()
            if here.z == there.z and abs(here.x - there.x) <= 1 and abs(here.y - there.y) <= 1:
                notifyAdventure(self, "The border guard honors your " + color + " pass and stands aside.")
                (yield from removeObjectByNameFlow(game_map, self.getName()))

    @register(context)
    class TownPortalScroll(CScroll):
        @resumableHook
        def onUse(self, event):
            player = event.getCause()
            cur_map = player.getMap()
            yield uiRequest("gui.moveTo", player, cur_map.getEntryX(), cur_map.getEntryY(), cur_map.getEntryZ())

        def isDisposable(self):
            return True
