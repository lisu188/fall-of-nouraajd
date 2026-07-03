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

    def show_info(building, text):
        if text and building.getMap():
            building.getMap().getGame().getGuiHandler().showInfo(text, True)

    def raise_base_stat(creature, stat, bonus):
        base_stats = creature.getObjectProperty("baseStats")
        if not base_stats:
            return False
        base_stats.setNumericProperty(stat, base_stats.getNumericProperty(stat) + bonus)
        return True

    @register(context)
    class WayPoint(CBuilding):
        def onEnter(self, event):
            if not event or not event.getCause():
                return
            exit_coords = self.getExit()
            if exit_coords:
                event.getCause().setCoords(exit_coords)

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
        def onEnter(self, event):
            if event and event.getCause() and event.getCause().isPlayer():
                market = self.getObjectProperty("market")
                if market:
                    self.getMap().getGame().getGuiHandler().showTrade(market)

    @register(context)
    class SignPost(CBuilding):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                self.getMap().getGame().getGuiHandler().showInfo(self.getStringProperty("text"), True)

    @register(context)
    class Chest(CBuilding):
        def onEnter(self, event):
            self.getGame().getRngHandler().addRandomLoot(self.getMap().getPlayer(), self.getNumericProperty("value"))

    @register(context)
    class Cave(CBuilding):
        def onEnter(self, event):
            if not event.getCause().isPlayer():
                return
            if self.getBoolProperty("enabled"):
                self.setBoolProperty("enabled", False)
                location = self.getCoords()
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        if not (j == 0 and i == 0):
                            if self.getMap().canStep(Coords(location.x + i, location.y + j, location.z)):
                                mon = self.getObjectProperty("monster").clone()
                                self.getMap().addObject(mon)
                                mon.moveTo(location.x + i, location.y + j, location.z)
                self.getMap().removeObjectByName(self.getName())

        def onTurn(self, event):
            chance = self.getNumericProperty("chance")
            monsters = self.getNumericProperty("monsters")
            enabled = self.getBoolProperty("enabled")
            if enabled and monsters > 0 and (randint(1, 100)) <= chance:
                location = self.getCoords()
                mon = self.getObjectProperty("monster").clone()
                self.getMap().addObject(mon)
                mon.moveTo(location.x, location.y, location.z)
                self.incProperty("monsters", -1)

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
                show_info(self, "Ancient runes etched into the stone sharpen your mind. You gain experience.")

    @register(context)
    class Campfire(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            player.addGold(self.getNumericProperty("gold"))
            self.getGame().getRngHandler().addRandomLoot(player, self.getNumericProperty("value"))
            show_info(self, "You scavenge supplies abandoned around a cold campfire.")
            self.getMap().removeObjectByName(self.getName())

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
                show_info(self, "The miller shares the profits of the last harvest with you.")

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
                show_info(self, "The tree whispers of enlightenment, but demands " + str(cost) + " gold as tribute.")
                return
            player.setBoolProperty(claim, True)
            player.takeGold(cost)
            level = player.getLevel()
            exp_for_next_level = level * (level + 1) * 500
            missing = exp_for_next_level - player.getNumericProperty("exp")
            if missing > 0:
                player.addExp(missing)
            show_info(self, "You meditate beneath the Tree of Knowledge and reach a new level of understanding.")

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
            show_info(self, "The training pays off. Your " + stat + " permanently increases by " + str(bonus) + ".")

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
            show_info(self, "The witch brews a pungent draught. Your " + stat + " increases by " + str(bonus) + ".")

    @register(context)
    class AdventureObelisk(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if claim_once(player, "obelisk_" + self.getName()):
                player.incProperty("obelisksVisited", 1)
            show_info(self, self.getStringProperty("text"))

    @register(context)
    class WarriorsTomb(CBuilding):
        def onEnter(self, event):
            player = acting_player(event)
            if not player:
                return
            if not self.getBoolProperty("enabled"):
                show_info(self, "The tomb lies plundered and empty.")
                return
            self.setBoolProperty("enabled", False)
            self.getGame().getRngHandler().addRandomLoot(player, self.getNumericProperty("value"))
            # The guardian's toll bypasses armor and block, so it is applied
            # straight to HP instead of through the combat damage pipeline.
            toll = min(player.getHp() - 1, player.getHpMax() * self.getNumericProperty("damage") // 100)
            if toll > 0:
                player.setHp(player.getHp() - toll)
            show_info(self, "You pry treasure from the warrior's tomb, but its restless guardian exacts a toll.")

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
            show_info(self, "The sirens' song drains your life, yet their secrets harden your resolve.")

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
                show_info(self, "The keymaster hands you the " + color + " pass.")

    @register(context)
    class BorderGuard(CBuilding):
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
                show_info(self, "The border guard honors your " + color + " pass and stands aside.")
                game_map.removeObjectByName(self.getName())

    @register(context)
    class TownPortalScroll(CScroll):
        def onUse(self, event):
            cur_map = event.getCause().getMap()
            event.getCause().moveTo(cur_map.getEntryX(), cur_map.getEntryY(), cur_map.getEntryZ())

        def isDisposable(self):
            return True
