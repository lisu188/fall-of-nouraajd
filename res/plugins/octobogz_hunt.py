# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import json

REGISTRY_PROPERTY = "octobogzHuntRegistry"
SLOT_NAMES = ("scout", "brood", "alpha")
ACTOR_NAMES = ("octobogzScout", "octobogzShadowBrood", "octobogzAlpha")
SPAWN_CELLS = ((165, 21, 0), (165, 20, 0), (166, 20, 0))
PHASE_PROPERTY = "octobogzCombatPhase"
RECOVERY_FLAGS = ("octobogzPulseUsed", "octobogzPulseEffectApplied", "enemyRoleUsed", "enemyRoleEffectApplied")


def huntState(game_map):
    text = game_map.getStringProperty(REGISTRY_PROPERTY)
    return json.loads(text) if text else None


def saveHuntState(game_map, state):
    game_map.setStringProperty(REGISTRY_PROPERTY, json.dumps(state, sort_keys=True))


def load(self, context):
    from game import CBuilding, CEffect, CEvent, CInteraction, CTrigger, Coords, event_loop, register

    def snapshot(actor):
        data = {
            "hp": actor.getHp(),
            "mana": actor.getMana(),
            "level": actor.getLevel(),
            "exp": actor.getNumericProperty("exp"),
            "phase": actor.getStringProperty(PHASE_PROPERTY),
        }
        for flag in RECOVERY_FLAGS:
            data[flag] = actor.getBoolProperty(flag)
        return data

    @register(context)
    class OctobogzHuntDirector(CEvent):
        def isActive(self, game_map):
            return game_map is not None and self.getGame().getMap() == game_map and game_map.mapName == "nouraajd"

        def readState(self, game_map):
            state = huntState(game_map)
            if state is not None:
                if state.get("version") != 1:
                    raise ValueError("Unsupported OctoBogz hunt registry version")
                return state
            cleared = (
                game_map.getBoolProperty("OCTOBOGZ_SLAIN")
                or game_map.getBoolProperty("completed_octobogz")
                or game_map.getStringProperty("quest_state_octobogz_contract") == "completed"
            )
            state = {"version": 1, "stage": "cleared" if cleared else "dormant", "slots": {}}
            for index, slot in enumerate(SLOT_NAMES):
                name = ACTOR_NAMES[index]
                state["slots"][slot] = {"name": name, "status": "dead" if cleared else "pending"}
            if not cleared:
                candidates = []
                for actor in game_map.getObjects():
                    if (
                        actor.getTypeId() == "OctoBogz"
                        and actor.isAlive()
                        and actor.getStringProperty("affiliation") == "bogz"
                    ):
                        coords = actor.getCoords()
                        distance = abs(coords.x - 166) + abs(coords.y - 21)
                        if coords.z == 0 and distance <= 10:
                            candidates.append((distance, actor.getName(), actor))
                candidates.sort(key=lambda entry: (entry[0], entry[1]))
                adopted = candidates[:3]
                if adopted:
                    state["stage"] = "scout" if len(adopted) < 3 else "brood"
                for index, (_, name, actor) in enumerate(adopted):
                    slot = SLOT_NAMES[index]
                    self.configureActor(actor, slot)
                    state["slots"][slot] = {"name": name, "status": "living", "recovery": snapshot(actor)}
            saveHuntState(game_map, state)
            game_map.setBoolProperty("octobogzHuntCleared", cleared)
            return state

        def configureActor(self, actor, slot):
            actor.setStringProperty("octobogzHuntSlot", slot)
            actor.setStringProperty("affiliation", "bogz")
            if slot in ("brood", "alpha"):
                actor.setStringProperty("octobogzCombatRole", "alpha" if slot == "alpha" else "shadow")
                if not actor.getStringProperty(PHASE_PROPERTY):
                    actor.setStringProperty(PHASE_PROPERTY, "predator")
                action_ids = {action.getTypeId() for action in actor.getActions()}
                for action_id in ("octobogzCharge", "octobogzShadowPulse"):
                    if action_id not in action_ids:
                        actor.addAction(self.getGame().createObject(action_id))
                if slot == "alpha":
                    actor.setStringProperty("label", "OctoBogz Alpha")
            player = actor.getMap().getPlayer() if actor.getMap() else self.getGame().getMap().getPlayer()
            if player is not None and (
                actor.getController() is None or actor.getStringProperty("octobogzHuntTarget") != player.getName()
            ):
                controller = self.getGame().createObject("CTargetController")
                controller.setTarget(player.getName())
                actor.setController(controller)
                actor.setStringProperty("octobogzHuntTarget", player.getName())

        def registerDefeat(self, game_map, slot, actor):
            trigger = self.getGame().createObject("OctobogzHuntDefeatTrigger")
            trigger.setStringProperty("name", "octobogzHuntDefeat" + slot.capitalize())
            trigger.setStringProperty("object", actor.getName())
            trigger.setStringProperty("event", "onDestroy")
            game_map.getEventHandler().registerTrigger(trigger)

        def findPlacement(self, game_map, preferred):
            for radius in range(4):
                cells = [
                    (preferred[0] + dx, preferred[1] + dy, preferred[2])
                    for dx in range(-radius, radius + 1)
                    for dy in range(-radius, radius + 1)
                    if abs(dx) + abs(dy) == radius
                ]
                for x, y, z in sorted(cells):
                    coords = Coords(x, y, z)
                    if game_map.canStep(coords) and not game_map.getObjectsAtCoords(coords):
                        return coords
            return None

        def ensureActor(self, game_map, state, slot):
            record = state["slots"][slot]
            actor = game_map.getObjectByName(record["name"])
            if record["status"] == "dead":
                return
            if actor is not None:
                if actor.getTypeId() != "OctoBogz" or actor.getStringProperty("octobogzHuntSlot") != slot:
                    return
                if (
                    record["status"] == "pending"
                    and actor.isAlive()
                    and actor.getStringProperty("octobogzHuntSlot") == slot
                ):
                    record["status"] = "living"
                if record["status"] == "living":
                    self.configureActor(actor, slot)
                    self.registerDefeat(game_map, slot, actor)
                    record["recovery"] = snapshot(actor)
                return
            if record["status"] == "living":
                record["status"] = "pending"
            coords = self.findPlacement(game_map, SPAWN_CELLS[SLOT_NAMES.index(slot)])
            if coords is None:
                if not state.get("placementWarning"):
                    self.getGame().getGuiHandler().notify(
                        "The lair stirs, but its creatures cannot emerge until a nearby cell is clear."
                    )
                    state["placementWarning"] = True
                return
            actor = self.getGame().createObject("OctoBogz")
            actor.setStringProperty("name", record["name"])
            recovery = record.get("recovery")
            if recovery:
                actor.setNumericProperty("level", recovery["level"])
                actor.setNumericProperty("exp", recovery["exp"])
                actor.setStringProperty(PHASE_PROPERTY, recovery["phase"])
                for flag in RECOVERY_FLAGS:
                    actor.setBoolProperty(flag, recovery.get(flag, False))
            actor.relocateWithoutMoveHooks(coords)
            self.configureActor(actor, slot)
            game_map.addObject(actor)
            if recovery:
                actor.setHp(max(1, min(recovery["hp"], actor.getHpMax())))
                actor.setMana(max(0, min(recovery["mana"], actor.getManaMax())))
            record["status"] = "living"
            record["recovery"] = snapshot(actor)
            self.registerDefeat(game_map, slot, actor)

        def synchronize(self, game_map):
            if not self.isActive(game_map):
                return
            state = self.readState(game_map)
            if state["stage"] == "cleared":
                game_map.setBoolProperty("octobogzHuntCleared", True)
                return
            enabled = ("scout",) if state["stage"] == "scout" else SLOT_NAMES if state["stage"] == "brood" else ()
            for slot in SLOT_NAMES:
                record = state["slots"][slot]
                if record["status"] == "living":
                    actor = game_map.getObjectByName(record["name"])
                    if actor is None:
                        record["status"] = "pending"
                    elif slot not in enabled:
                        self.configureActor(actor, slot)
                        self.registerDefeat(game_map, slot, actor)
                        record["recovery"] = snapshot(actor)
            for slot in enabled:
                self.ensureActor(game_map, state, slot)
            saveHuntState(game_map, state)
            if game_map.getObjectByName("cave2") is None:
                lair = self.getGame().createObject("cave2")
                lair.setStringProperty("name", "cave2")
                lair.relocateWithoutMoveHooks(Coords(166, 21, 0))
                game_map.addObject(lair)

        def start(self, game_map):
            if not self.isActive(game_map):
                return
            state = self.readState(game_map)
            if state["stage"] == "dormant":
                state["stage"] = "scout"
                saveHuntState(game_map, state)
                self.getGame().getGuiHandler().notify(
                    "A scout rises from the mire. Slay it to draw out the shadow brood and its Alpha."
                )
            self.synchronize(game_map)

        def actorRemoved(self, actor):
            game_map = actor.getMap()
            if not self.isActive(game_map):
                return
            state = self.readState(game_map)
            slot = actor.getStringProperty("octobogzHuntSlot")
            if state["stage"] == "cleared" or slot not in state["slots"]:
                return
            record = state["slots"][slot]
            current = game_map.getObjectByName(record["name"])
            if (
                record["name"] != actor.getName()
                or record["status"] != "living"
                or (current is not None and current != actor)
            ):
                return
            if actor.isAlive():
                record["recovery"] = snapshot(actor)
                record["status"] = "pending"
            else:
                record["status"] = "dead"
                if slot == "scout" and state["stage"] == "scout":
                    state["stage"] = "brood"
            completed = all(record["status"] == "dead" for record in state["slots"].values())
            if completed:
                state["stage"] = "cleared"
                game_map.setBoolProperty("octobogzHuntCleared", True)
            saveHuntState(game_map, state)
            if completed:
                lair = game_map.getObjectByName("cave2")
                if lair is None:
                    lair = self.getGame().createObject("cave2")
                    lair.setStringProperty("name", "cave2")
                    lair.relocateWithoutMoveHooks(Coords(166, 21, 0))
                    game_map.addObject(lair)
                game_map.removeObject(lair)
                player = game_map.getPlayer()
                if player is not None:
                    player.checkQuests()
            else:
                event_loop.instance().invoke(lambda: self.synchronize(game_map))

        def objectiveText(self, game_map):
            if not self.isActive(game_map):
                return "Return to the eastern lair in Nouraajd and defeat its scout, shadow brood, and Alpha."
            state = self.readState(game_map)
            count = sum(record["status"] == "dead" for record in state["slots"].values())
            return (
                "Clear the eastern lair: " + str(count) + "/3 threats slain; defeat the scout, shadow brood, and Alpha."
            )

    @register(context)
    class OctobogzLair(CBuilding):
        def onEnter(self, event):
            game_map = self.getMap()
            player = event.getCause() if event else None
            if (
                game_map is None
                or player is None
                or not player.isPlayer()
                or not player.isAlive()
                or game_map.getPlayer() != player
                or game_map.getObjectByName(self.getName()) != self
            ):
                return
            here, there = player.getCoords(), self.getCoords()
            if (here.x, here.y, here.z) != (there.x, there.y, there.z):
                return
            self.getGame().createObject("OctobogzHuntDirector").start(game_map)

    @register(context)
    class OctobogzHuntDefeatTrigger(CTrigger):
        def trigger(self, actor, event):
            self.getGame().createObject("OctobogzHuntDirector").actorRemoved(actor)

    def ordinaryAttack(first, second):
        if second is None or not first.isAlive() or not second.isAlive():
            return None
        for action in first.getEffectiveInteractions():
            if action.getTypeId() == "Attack":
                return action
        return None

    @register(context)
    class OctobogzCharge(CInteraction):
        def performAction(self, first, second):
            phase = first.getStringProperty(PHASE_PROPERTY)
            if phase in ("charged", "spent"):
                return
            attack = ordinaryAttack(first, second)
            if attack is None:
                return
            first.setStringProperty(PHASE_PROPERTY, "charged")
            first.getGame().getGuiHandler().notify(
                (first.getStringProperty("label") or first.getTypeId())
                + " gathers shadow while striking. Its next attack may release a shadow pulse."
            )
            try:
                attack.performAction(first, second)
            except Exception:
                first.setStringProperty(PHASE_PROPERTY, phase)
                raise

    @register(context)
    class OctobogzShadowPulse(CInteraction):
        def performAction(self, first, second):
            self.setBoolProperty("octobogzPulseCommitted", False)
            if first.getBoolProperty("octobogzPulseUsed") or first.getStringProperty(PHASE_PROPERTY) != "charged":
                return
            attack = ordinaryAttack(first, second)
            if attack is None:
                return
            first.setStringProperty(PHASE_PROPERTY, "spent")
            first.setBoolProperty("octobogzPulseUsed", True)
            first.setObjectProperty("enemyRoleDamagePacket", self.getObjectProperty("roleDamage"))
            first.setStringProperty("enemyRoleDamageChannel", "shadow")
            first.setBoolProperty("enemyRoleArcaneAttack", True)
            try:
                attack.performAction(first, second)
                self.setBoolProperty("octobogzPulseCommitted", True)
            except Exception:
                first.setStringProperty(PHASE_PROPERTY, "charged")
                first.setBoolProperty("octobogzPulseUsed", False)
                raise
            finally:
                first.setBoolProperty("enemyRoleArcaneAttack", False)
                first.setStringProperty("enemyRoleDamageChannel", "")
            if not first.getBoolProperty("octobogzPulseEffectApplied") and second.isAlive():
                first.setBoolProperty("octobogzPulseEffectApplied", True)
                effect = self.getObjectProperty("roleEffect")
                self.setObjectProperty("roleEffect", None)
                effect.setCaster(first)
                effect.setVictim(second)
                second.addEffect(effect)

        def getCommittedManaRefund(self, caster):
            return 0 if self.getBoolProperty("octobogzPulseCommitted") else self.getNumericProperty("manaCost")

    @register(context)
    class OctobogzShadowPulseEffect(CEffect):
        def onEffect(self):
            pass
