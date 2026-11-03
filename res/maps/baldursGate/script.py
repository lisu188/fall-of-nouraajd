# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""One persistent city; original-resource facts and native adaptation rules remain distinct."""

"""Private source-model prototype. Native activation and shipping UI are deliberately closed.

Only json is imported so the pure evaluator can eventually live in a map plugin's load closure.
ModelWorld is an internal port, not an assertion that similarly named engine APIs exist.
"""

import json


class SourceGap(RuntimeError):
    pass


class UncertainAction(SourceGap):
    pass


def require(value, message):
    if not value:
        raise SourceGap(message)


def copyData(value):
    return json.loads(json.dumps(value, sort_keys=True))


CONDITIONS = {
    "Dead": ("identifier",),
    "False": (),
    "True": (),
    "Global": ("identifier", "identifier", "integer"),
    "GlobalGT": ("identifier", "identifier", "integer"),
    "GlobalLT": ("identifier", "identifier", "integer"),
    "GlobalTimerNotExpired": ("identifier", "identifier"),
    "HasItem": ("identifier", "symbol"),
    "NumberOfTimesTalkedTo": ("integer",),
    "OR": ("integer",),
    "PartyGoldGT": ("integer",),
    "PartyHasItem": ("identifier",),
    "ReactionGT": ("symbol", "symbol"),
    "ReactionLT": ("symbol", "symbol"),
    "StateCheck": ("symbol", "symbol"),
}
ACTIONS = {
    "ActionOverride": ("identifier", "action"),
    "AddexperienceParty": ("integer",),
    "CreateCreature": ("identifier", "point", "symbol"),
    "CreateItem": ("identifier", "integer", "integer", "integer"),
    "Dialog": ("selectorSymbol",),
    "DialogueInterrupt": ("symbol",),
    "Enemy": (),
    "EscapeArea": (),
    "EscapeAreaMove": ("identifier", "integer", "integer", "symbol"),
    "Face": ("symbol",),
    "GiveItem": ("identifier", "recipient"),
    "GiveItemCreate": ("identifier", "recipient", "integer", "integer", "integer"),
    "MoveToPoint": ("point",),
    "SetGlobal": ("identifier", "identifier", "integer"),
    "SetGlobalTimer": ("identifier", "identifier", "symbol"),
    "Shout": ("integer",),
    "StartStore": ("identifier", "recipient"),
    "TakePartyGold": ("integer",),
    "TakePartyItem": ("identifier",),
    "Wait": ("integer",),
}
GLOBAL_NAMES = {
    "boybody",
    "chapter",
    "divinerasked",
    "helpjalantha",
    "helplothander",
    "helptenya",
    "helptremain",
    "jalappear",
    "lothandermove",
    "marekmove",
    "returnedbook",
    "tenappear",
    "talkedtotenya",
    "talkedtoulbright",
    "tremainquest",
    "partycured",
    "poisonwarning",
    "poisonpartyicon",
}
TIMERS = {"diviner", "poisonparty", "poisonparty2"}
ITEMS = {"BOOK08", "LOPOTN20", "MISC54", "POTN47", "SCRLJALA"}
DEATH_NAMES = {"jalantha", "jebadoh", "rieltar", "tenya", "tenya2", "pumberl", "marek", "lothander"}
TIMER_CONSTANTS = {"ONE_DAY": 7200, "TEN_DAYS": 72000}

# Exact dialogue identity projection of the retained eight-CRE fixture dc91ffb9.
CRE_DIALOGUE_BINDINGS = {
    "MAREK": ("MAREK.DLG", "Marek", "729e111011af223a067351ff53d6cfe0c5ae1c78656aa3be7da2a58954b443e9"),
    "MAREK1": ("MAREK.DLG", "Marek", "b8fbac2cb9b1da5aca5f47d83b148e496498b0287be90f635f4f1f5f54da26b5"),
    "LOTHAN": ("LOTHAN.DLG", "Lothander", "7fe53962a8fb41b909803946b20568e968adf67d70a86df41f7cb90a93283eaa"),
    "DIVINE": ("DIVINE.DLG", "None", "49963dad72be7a3aa92e36b9034d3621423f04ae478e1cc21989e578812a74e1"),
    "JALANT": ("JALANT.DLG", "Jalantha", "bfa02cdc0445a4005be37e9adef0469260563f06e30829cd130036eb9f651b66"),
    "PUMBERL": ("PUMBERL.DLG", "pumberl", "be4e5fed1c0ba1fff92696d99ef541d4d3d905da0ebfdeab00157e3ce67754da"),
    "CHANTH": ("CHANTH.DLG", "None", "294cd5c1722c4ac31688c2ee7c211b5f1632760530bd52d173686029e2ab8296"),
    "TENYA2": ("TENYA2.DLG", "Tenya2", "a5bc5c9091c5b0a48d4855feca65b663b0c75e30375714c817622e0b0b5aee0e"),
}


class SourceGraphs:
    """Validate every retained record, including False and unlinked branches, before execution."""

    def __init__(self, dialogues):
        self.graphs = {}
        self.condition_operations = set()
        self.action_operations = set()
        for raw in copyData(dialogues):
            resource = raw["resource"]
            require(resource not in self.graphs and resource.endswith(".DLG"), "duplicate or invalid graph")
            states, edges = raw["states"], raw["edges"]
            require([s["index"] for s in states] == list(range(len(states))), "noncanonical states")
            require([e["index"] for e in edges] == list(range(len(edges))), "noncanonical edges")
            source_ids = set()
            for state in states:
                require(state["sourceId"] == resource + ":state" + str(state["index"]), "state identity")
                require(state["sourceId"] not in source_ids, "duplicate source identity")
                source_ids.add(state["sourceId"])
                self.validateConditions(state["entryConditions"])
                require(len(state["edges"]) == len(set(state["edges"])), "duplicate state edge")
                for index in state["edges"]:
                    require(type(index) is int and 0 <= index < len(edges), "invalid state edge")
            for edge in edges:
                require(edge["sourceId"] == resource + ":edge" + str(edge["index"]), "edge identity")
                require(edge["sourceId"] not in source_ids, "duplicate source identity")
                source_ids.add(edge["sourceId"])
                expected = [s["index"] for s in states if edge["index"] in s["edges"]]
                require(edge["owners"] == expected, "edge owner mismatch")
                self.validateConditions(edge["conditions"])
                for action in edge["actions"]:
                    self.validateCall(action, False)
                target = edge["targetState"]
                if target is not None:
                    require(edge["targetResource"] == resource[:-4], "unmapped external graph")
                    require(type(target) is int and 0 <= target < len(states), "invalid target state")
                else:
                    require(not edge["targetResource"], "terminal edge with external target")
                require(type(edge["rawFlags"]) is int, "invalid edge flags")
            if "entryPriority" in raw:
                priority = raw["entryPriority"]
                indices = [row["conditionIndex"] for row in priority]
                require(indices == sorted(set(indices)), "invalid condition-index priority")
                entries = [i for row in priority for i in row["states"]]
                require(len(entries) == len(set(entries)), "duplicate entry state")
                require(set(entries) == {s["index"] for s in states if s["entryConditions"]}, "entry coverage")
                require(all(len(row["states"]) == 1 for row in priority), "unresolved tied entry priority")
                raw["compiledEntries"] = entries
                raw["priorityProven"] = True
            else:
                entries = raw["entryCandidatesInStateOrder"]
                require(entries == [s["index"] for s in states if s.get("hasEntryTrigger")], "entry coverage")
                require(raw["nullEntryTriggerIsNotTrue"] is True, "null entry semantics missing")
                raw["compiledEntries"] = entries
                raw["priorityProven"] = False
            self.graphs[resource] = raw

    def validateArgument(self, node, kind):
        require(type(node) is dict, "invalid typed argument")
        if kind == "action":
            self.validateCall(node, False)
            return
        if kind == "recipient":
            if node.get("type") == "symbol":
                require(node.get("value") == "LastTalkedToBy", "unmapped recipient")
            else:
                require(
                    node.get("type") == "call"
                    and node.get("operation") == "LastTalkedToBy"
                    and node.get("negated") is False,
                    "unmapped recipient call",
                )
                require(node.get("arguments") == [{"type": "symbol", "value": "Myself"}], "recipient owner")
                self.action_operations.add("LastTalkedToBy")
            return
        require(node.get("type") == kind, "argument type mismatch: " + kind)
        if kind == "integer":
            require(type(node.get("value")) is int, "boolean or absent integer")
        elif kind == "point":
            require(type(node.get("x")) is int and type(node.get("y")) is int, "invalid point")
        else:
            require(type(node.get("value")) is str and bool(node["value"]), "invalid identifier/symbol")

    def validateCall(self, node, condition):
        require(type(node) is dict and node.get("type") == "call", "untyped source operation")
        operation = node.get("operation")
        signatures = CONDITIONS if condition else ACTIONS
        require(operation in signatures, "unmapped source operation: " + str(operation))
        require(type(node.get("negated")) is bool and (condition or not node["negated"]), "action negation")
        args = node.get("arguments")
        require(type(args) is list and len(args) == len(signatures[operation]), "source operation arity")
        for index, arg in enumerate(args):
            self.validateArgument(arg, signatures[operation][index])
        (self.condition_operations if condition else self.action_operations).add(operation)
        values = [arg.get("value") for arg in args]
        if operation in ("Global", "GlobalGT", "GlobalLT", "SetGlobal"):
            require(values[1] == "GLOBAL" and values[0].casefold() in GLOBAL_NAMES, "unmapped global scope/name")
        if operation in ("GlobalTimerNotExpired", "SetGlobalTimer"):
            require(values[1] == "GLOBAL" and values[0].casefold() in TIMERS, "unmapped timer scope/name")
        if operation == "SetGlobalTimer":
            require(values[2] in TIMER_CONSTANTS, "unmapped timer constant")
        if operation in ("HasItem", "PartyHasItem", "GiveItem", "GiveItemCreate", "CreateItem", "TakePartyItem"):
            require(values[0] in ITEMS, "unmapped item")
        if operation == "HasItem":
            require(values[1] == "Myself", "unmapped item holder")
        if operation == "StateCheck":
            require(values == ["Myself", "STATE_CHARMED"], "unmapped state check")
        if operation == "Dead":
            require(values[0].casefold() in DEATH_NAMES, "unmapped death lineage")
        if operation in ("ReactionGT", "ReactionLT"):
            bounds = (
                ("HOSTILE_UPPER", "NEUTRAL_UPPER") if operation == "ReactionGT" else ("NEUTRAL_LOWER", "FRIENDLY_LOWER")
            )
            require(values[0] == "LastTalkedToBy" and values[1] in bounds, "unmapped reaction comparison")
        if operation == "OR":
            require(not node["negated"] and values[0] in (2, 3), "unmapped OR")
        if operation == "ActionOverride":
            require(values[0] in ("Jalantha", "Lothander", "Tenya2"), "unmapped override owner")
        if operation == "CreateCreature":
            require(values[0] in ("JALANT", "TENYA2") and values[2] == "S", "unmapped creature factory")
        if operation in ("CreateItem", "GiveItemCreate"):
            require(values[-3:] == [0, 0, 0], "unmapped source item creation parameters")
        if operation == "DialogueInterrupt":
            require(values == ["FALSE"], "unmapped dialogue interrupt")
        if operation == "Dialog":
            require(values == ["PC"], "unmapped dialogue selector")
        if operation == "StartStore":
            require(values[0] == "tem0132", "unmapped store")
        if operation == "Face":
            require(values == ["SSW"], "unmapped facing")
        if operation == "EscapeAreaMove":
            require(values == ["AR0106", 259, 198, "S"], "unmapped area move")
        if operation == "Shout":
            require(values == [99], "unmapped shout")
        finite_numbers = {
            "AddexperienceParty": (1500,),
            "TakePartyGold": (50, 100, 500, 2000),
            "PartyGoldGT": (49, 99, 499, 1999),
            "NumberOfTimesTalkedTo": (0,),
            "Wait": (10,),
        }
        if operation in finite_numbers:
            require(values[0] in finite_numbers[operation], "unmapped numeric operation variant")

    def validateConditions(self, nodes):
        require(type(nodes) is list, "invalid conditions")
        cursor = 0
        while cursor < len(nodes):
            node = nodes[cursor]
            self.validateCall(node, True)
            if node["operation"] == "OR":
                count = node["arguments"][0]["value"]
                require(cursor + count < len(nodes), "incomplete OR group")
                for child in nodes[cursor + 1 : cursor + count + 1]:
                    self.validateCall(child, True)
                    require(child["operation"] != "OR", "unmapped nested OR group")
                cursor += count
            cursor += 1

    def matches(self, nodes, world, speaker):
        cursor, result = 0, True
        while cursor < len(nodes):
            node = nodes[cursor]
            if node["operation"] == "OR":
                count = node["arguments"][0]["value"]
                matches = [self.matchOne(c, world, speaker) for c in nodes[cursor + 1 : cursor + 1 + count]]
                value = any(matches)
                cursor += count
            else:
                value = self.matchOne(node, world, speaker)
            result = result and value
            cursor += 1
        return result

    def matchOne(self, node, world, speaker):
        op, args = node["operation"], [a.get("value") for a in node["arguments"]]
        actor = world.actor(speaker)
        if op == "True":
            result = True
        elif op == "False":
            result = False
        elif op in ("Global", "GlobalGT", "GlobalLT"):
            value = world.globalValue(args[0])
            result = value == args[2] if op == "Global" else value > args[2] if op == "GlobalGT" else value < args[2]
        elif op == "Dead":
            result = world.isDead(args[0])
        elif op == "GlobalTimerNotExpired":
            result = world.timerNotExpired(args[0])
        elif op == "HasItem":
            result = bool(world.ownedItems(speaker, args[0]))
        elif op == "PartyHasItem":
            result = bool(world.partyItems(args[0]))
        elif op == "PartyGoldGT":
            result = world.data["gold"] > args[0]
        elif op == "NumberOfTimesTalkedTo":
            result = actor["talks"] == args[0]
        elif op == "StateCheck":
            result = actor["charmed"]
        elif op in ("ReactionGT", "ReactionLT"):
            score = world.data["social"]
            threshold = 7 if args[1] in ("HOSTILE_UPPER", "NEUTRAL_LOWER") else 12
            result = score >= threshold if op == "ReactionGT" else score < threshold
        else:
            raise SourceGap("unmapped condition evaluation: " + op)
        return not result if node["negated"] else result

    def entry(self, resource, world, speaker):
        graph = self.graphs[resource]
        candidates = [
            i for i in graph["compiledEntries"] if self.matches(graph["states"][i]["entryConditions"], world, speaker)
        ]
        if not graph["priorityProven"]:
            require(len(candidates) <= 1, "TENYA2 entry priority not retained; ambiguous admission refused")
        return candidates[0] if candidates else None

    def coverage(self):
        return {
            "graphs": len(self.graphs),
            "states": sum(len(d["states"]) for d in self.graphs.values()),
            "edges": sum(len(d["edges"]) for d in self.graphs.values()),
            "conditionOperations": sorted(self.condition_operations),
            "actionOperations": sorted(self.action_operations),
        }


CITY_JSON_PREFIX = "city-json:"


def decodeData(encoded):
    import json

    return json.loads(encoded.removeprefix(CITY_JSON_PREFIX))


def itemId(source):
    return "cityItem" + source[:1].upper() + source[1:].lower()


def questId(key):
    return "city" + key[:1].upper() + key[1:] + "Quest"


def scheduleSlot(ticks):
    return ((480 + ticks * 6 // 5 - 30) // 60) % 24


def firstMatch(values, default=None):
    for value in values:
        return value
    return default


def pairedValues(left, right):
    for index in range(min(len(left), len(right))):
        yield left[index], right[index]


def load(self, context):
    import json

    from game import CBuilding, CCreature, CDialog, CEvent, CQuest, CTrigger, Coords
    from game import claim_once, flowGame, mapQuest, register, resumableHook, uiRequest

    region_indices = {}
    poison_compiled = {}
    poison_live_actors = {}

    class NativePoisonPort:
        def __init__(self, coordinator, binding, state):
            self.clock, self.binding, self.state = coordinator, binding, state
            self.native = binding["objectClass"]
            self.last_created = {}
            stats = CCreature.getStats(binding["player"])
            self.data = {
                "gold": CCreature.getGold(binding["player"]),
                "social": self.native.getNumericProperty(stats, "intelligence")
                + self.native.getNumericProperty(binding["map"], "plugin_cityStanding"),
            }
            coordinator.poisonRequire(binding)

        def resolve(self, identity, active=True, witness_required=True):
            row = self.state["actors"].get(identity)
            if not row:
                raise SourceGap("Source actor was not enrolled by its placement/factory")
            expected = CRE_DIALOGUE_BINDINGS.get(row["resource"])
            actor = self.binding["mapClass"].getObjectByName(self.binding["map"], identity)
            self.clock.poisonRequire(self.binding)
            if (
                expected is None
                or not isinstance(actor, CCreature)
                or self.native.getTypeId(actor) != row["typeId"]
                or self.native.getGame(actor) is not self.binding["game"].resolve()
                or self.binding["mapObjectClass"].getMap(actor) is not self.binding["map"]
                or self.native.getStringProperty(actor, "sourceCreature") != row["resource"]
                or self.native.getStringProperty(actor, "sourceDialogue") + ".DLG" != expected[0]
                or self.native.getStringProperty(actor, "plugin_cityPoisonOwnerCreation") != row["lineage"]
                or self.native.getStringProperty(actor, "sourceArea") != row["area"]
                or active
                and (row.get("retired") or row.get("dead") or not CCreature.isAlive(actor))
            ):
                raise SourceGap("Genuine source actor binding changed")
            witness = poison_live_actors.get(row["lineage"])
            if witness_required and (
                witness is None
                or witness["actor"] is not actor
                or witness["game"].resolve() is not self.binding["game"].resolve()
                or witness["epoch"] != self.binding["epoch"]
            ):
                raise SourceGap("Actual source actor differs from its prospective native owner witness")
            return actor

        def actor(self, identity):
            actor = self.resolve(identity)
            from game import CEffect

            # Only a real active native effect can satisfy STATE_CHARMED. No dialogue/debug boolean qualifies.
            charmed = any(
                self.native.hasTag(effect, "cityPoisonCharmed")
                and self.native.getNumericProperty(effect, "timeLeft") > 0
                for effect in CCreature.getEffects(actor)
                if isinstance(effect, CEffect)
            )
            row = self.state["actors"][identity]
            return {
                "resource": row["resource"],
                "lineage": row["lineage"],
                "area": row["area"],
                "talks": self.native.getNumericProperty(actor, "plugin_cityPoisonTalkCount"),
                "charmed": charmed,
            }

        def globalValue(self, name):
            if name == "Chapter":
                return self.native.getNumericProperty(self.binding["map"], "plugin_cityPhase") or 5
            keys = [key for key in self.state["globals"] if key.casefold() == name.casefold()]
            if len(keys) > 1:
                raise SourceGap("Ambiguous saved source global aliases")
            return self.state["globals"].get(keys[0], 0) if keys else 0

        def setGlobal(self, name, value):
            if type(value) is not int or name.casefold() not in GLOBAL_NAMES:
                raise SourceGap("Unmapped source global mutation")
            keys = [key for key in self.state["globals"] if key.casefold() == name.casefold()]
            if len(keys) > 1:
                raise SourceGap("Ambiguous saved source global aliases")
            self.state["globals"][keys[0] if keys else name] = value

        def ownedItems(self, identity, resref):
            actor = self.resolve(identity)
            return [
                item
                for item in self.clock.poisonItems(self.binding, actor)
                if self.native.getStringProperty(item, "plugin_citySourceItem") == resref
                and not self.native.getBoolProperty(item, "plugin_citySoldToStore")
            ]

        def partyItems(self, resref):
            return [
                (owner, item)
                for owner in self.clock.poisonPartyOwners(self.binding)
                for item in self.clock.poisonItems(self.binding, owner)
                if self.native.getStringProperty(item, "plugin_citySourceItem") == resref
            ]

        def isDead(self, script_name):
            # Only prospective actual owner death events or separately authored outside-history transformations write this.
            return bool(self.state["deadAliases"].get(script_name.casefold(), []))

        def ownerFor(self, script_name, speaker):
            area = self.state["actors"][speaker]["area"]
            recent = self.last_created.get(script_name.casefold())
            if recent:
                self.resolve(recent)
                return recent
            rows = [
                identity
                for identity, row in self.state["actors"].items()
                if row["scriptName"].casefold() == script_name.casefold()
                and row["area"] == area
                and not row.get("retired")
                and not row.get("dead")
            ]
            if len(rows) != 1:
                raise SourceGap("Source named owner selector is missing or ambiguous")
            self.resolve(rows[0])
            return rows[0]

        def timerNotExpired(self, name):
            deadline = self.state["timers"].get(name.casefold())
            if deadline is None:
                return False  # Explicit native conversion: an unset timer has not been started.
            return self.clock.poisonSourceTime(self.binding) < deadline

        def applyAction(self, node, speaker, operation):
            op, raw = node["operation"], node["arguments"]
            args = [value.get("value") for value in raw]
            actor = self.resolve(speaker)
            player = self.binding["player"]
            result = {"operation": op}
            if op == "ActionOverride":
                return self.applyAction(raw[1], self.ownerFor(args[0], speaker), operation + ":override")
            if op == "SetGlobal":
                self.setGlobal(args[0], args[2])
            elif op == "SetGlobalTimer":
                self.state["timers"][args[0].casefold()] = (
                    self.clock.poisonSourceTime(self.binding) + TIMER_CONSTANTS[args[2]]
                )
            elif op == "AddexperienceParty":
                CCreature.addExp(player, args[0])
            elif op == "TakePartyGold":
                # Source choices have strict PartyGoldGT guards; a later insolvency is a separate unresolved admission case.
                if CCreature.getGold(player) < args[0]:
                    raise SourceGap("Post-admission insufficient-gold action semantics need source reconciliation")
                CCreature.addGold(player, -args[0])
            elif op == "TakePartyItem":
                items = self.partyItems(args[0])
                if items:
                    owner, item = items[0]
                    self.clock.poisonRemoveOwnedItem(self.binding, owner, item)
                    CCreature.addItem(actor, item)
                    result["transferred"] = self.native.getName(item)
                    result["toActor"] = speaker
                else:
                    result["missing"] = args[0]  # No new XP guard and no rollback of a preceding award.
            elif op == "GiveItem":
                items = self.ownedItems(speaker, args[0])
                if items:
                    item = items[0]
                    self.clock.poisonRemoveOwnedItem(self.binding, actor, item)
                    CCreature.addItem(player, item)
                    result["transferred"] = self.native.getName(item)
                else:
                    result["missing"] = args[0]  # Actual donor stock is shared with theft. Never mint a replacement.
            elif op in ("GiveItemCreate", "CreateItem"):
                if operation in self.state["itemCreations"]:
                    raise SourceGap("Source creation action was replayed under a different receipt")
                recipient = actor if op == "CreateItem" else player
                item = makeSourceItem(self.clock, {"item": args[0], "charges": [0, 0, 0], "flags": 0, "expiration": 0})
                self.native.setStringProperty(item, "plugin_cityPoisonCreation", operation)
                CCreature.addItem(recipient, item)
                self.state["itemCreations"][operation] = {"item": args[0], "name": self.native.getName(item)}
            elif op == "CreateCreature":
                identity = self.clock.poisonCreateSourceActor(
                    self.binding,
                    self.state,
                    args[0],
                    operation,
                    self.state["actors"][speaker]["area"],
                    [raw[1]["x"], raw[1]["y"]],
                )
                self.last_created[self.state["actors"][identity]["scriptName"].casefold()] = identity
                result["createdActor"] = identity
            elif op == "Dialog":
                self.state["queuedDialogs"].append(speaker)
            elif op == "DialogueInterrupt":
                self.native.setBoolProperty(actor, "plugin_cityPoisonDialogueInterrupt", False)
            elif op == "Enemy":
                self.native.setBoolProperty(actor, "npc", False)
                self.native.setStringProperty(actor, "affiliation", "cityHostile")
                controller = self.binding["game"].resolve().createObject("CTargetController")
                self.native.setStringProperty(controller, "target", "player")
                CCreature.setController(actor, controller)
            elif op in ("MoveToPoint", "EscapeAreaMove"):
                from game import CMapObject

                destination = self.state["actors"][speaker]["area"] if op == "MoveToPoint" else args[0]
                point = [raw[0]["x"], raw[0]["y"]] if op == "MoveToPoint" else args[1:3]
                coords = self.clock.poisonSourcePosition(self.binding, destination, point)
                CMapObject.relocateWithoutMoveHooks(actor, Coords(*coords))
                self.state["actors"][speaker]["area"] = destination
                self.native.setStringProperty(actor, "sourceArea", destination)
                self.native.setStringProperty(actor, "simulationRegion", destination)
            elif op == "Face":
                self.native.setStringProperty(actor, "plugin_citySourceFacing", args[0])
            elif op == "EscapeArea":
                self.state["actors"][speaker]["retired"] = True
                self.native.setBoolProperty(actor, "plugin_cityDeparted", True)
                self.clock.poisonWrite(self.binding, self.state)
                self.binding["mapClass"].removeObject(self.binding["map"], actor)
                poison_live_actors.pop(self.state["actors"][speaker]["lineage"], None)
            elif op == "StartStore":
                if self.native.getStringProperty(actor, "sourceStore").upper() != args[0].upper():
                    raise SourceGap("Source StartStore has no matching staged native service dialog")
                self.state["queuedStores"].append({"actorId": speaker, "store": args[0].upper()})
            elif op == "Wait":
                # Explicit native conversion; no nested event loop is pumped inside an ordered source receipt.
                self.state["nativeWaitRequests"].append(
                    {"sourceUnits": args[0], "actorId": speaker, "operation": operation}
                )
                result["waitUntil"] = self.clock.poisonSourceTime(self.binding) + args[0]
            elif op == "Shout":
                raise SourceGap("Retained Shout99 listeners have not been bound to genuine native source owners")
            else:
                raise SourceGap("Unmapped native poison source action: " + op)
            self.clock.poisonRequire(self.binding)
            return result

    custody_definitions = {}

    def world(obj):
        return obj.getGame().getMap()

    def hero(obj):
        return world(obj).getPlayer()

    def clock(obj):
        return world(obj).getObjectByName("cityClock")

    def optionalObjectProperty(owner, key, getter=None):
        if not hasattr(owner, key):
            return None
        if getter is not None:
            return getter(owner, key)
        return owner.getObjectProperty(key)

    def read(obj, key, default):
        return decodeData(obj.getStringProperty(key) or json.dumps(default))

    def write(obj, key, value):
        obj.setStringProperty(key, CITY_JSON_PREFIX + json.dumps(value, separators=(",", ":")))

    def notify(obj, text):
        obj.getGame().getGuiHandler().notify(text)

    def freezeHistory(obj):
        game_map = world(obj)
        if game_map.getBoolProperty("plugin_cityHistoryFrozen"):
            return
        history = read(game_map, "plugin_cityHistory", {})
        for key in ("aldeth", "tenya", "eldoth"):
            history.setdefault(key, "unspecified")
        write(game_map, "plugin_cityHistory", history)
        profile = read(game_map, "plugin_cityStartingProfile", {})
        profile.update(history=history, historyFrozen=True)
        write(game_map, "plugin_cityStartingProfile", profile)
        game_map.setBoolProperty("plugin_cityHistoryFrozen", True)

    def definitions(obj):
        document = read(clock(obj), "questDefinitions", [])
        return document.get("quests", []) if isinstance(document, dict) else document

    def quest(obj, key):
        return firstMatch((entry for entry in definitions(obj) if entry["id"] == key), None)

    def stage(obj, key):
        return world(obj).getStringProperty("plugin_cityQuest_" + key) or "notStarted"

    def setStage(obj, key, value):
        world(obj).setStringProperty("plugin_cityQuest_" + key, value)

    def matches(actor, selector):
        return bool(
            actor
            and (not selector.get("area") or actor.getStringProperty("sourceArea") == selector["area"])
            and (not selector.get("creature") or actor.getStringProperty("sourceCreature") == selector["creature"])
            and (
                not selector.get("label")
                or actor.getStringProperty("label").strip().casefold() == selector["label"].strip().casefold()
                or actor.getName() == selector["label"]
            )
        )

    def actors(obj, selector):
        return [actor for actor in world(obj).getObjects() if matches(actor, selector)]

    def possessions(owner):
        return list(
            {
                item.getName(): item
                for item in (*owner.getItems(), *(item for item in owner.getEquipped().values() if item))
            }.values()
        )

    def sourceCode(item):
        return item.getStringProperty("plugin_citySourceItem")

    def quantity(item):
        return max(1, item.getNumericProperty("plugin_cityQuantity"))

    def findItems(owner, requirement):
        codes = requirement.get("anyOf", [requirement.get("item", "")])
        return [item for item in owner.getItems() if sourceCode(item) in codes]

    def hasItems(owner, requirement):
        return sum(quantity(item) for item in findItems(owner, requirement)) >= requirement.get("count", 1)

    def releaseReward(owner, requirement):
        if hasItems(owner, requirement):
            return
        codes = requirement.get("anyOf", [requirement.get("item", "")])
        for slot, item in tuple(owner.getEquipped().items()):
            if item and sourceCode(item) in codes and not item.hasTag("cursed"):
                owner.equipItem(slot, None)
                if hasItems(owner, requirement):
                    return

    def takeItems(owner, requirement, recipient=None):
        if not hasItems(owner, requirement):
            return False
        remaining = requirement.get("count", 1)
        for item in tuple(findItems(owner, requirement)):
            amount = min(remaining, quantity(item))
            if amount == quantity(item):
                owner.removeQuestItem(lambda candidate: candidate == item)
                if item in owner.getItems():
                    return False
                if recipient:
                    recipient.addItem(item)
            else:
                item.setNumericProperty("plugin_cityQuantity", quantity(item) - amount)
                if recipient:
                    transferred = makeSourceItem(
                        owner,
                        {
                            "item": sourceCode(item),
                            "quantity": amount,
                            "flags": item.getNumericProperty("plugin_citySourceFlags"),
                            "expiration": item.getNumericProperty("plugin_cityExpiration"),
                            "charges": read(item, "plugin_cityCharges", [0, 0, 0]),
                        },
                    )
                    transferred.setBoolProperty("plugin_cityStolen", item.getBoolProperty("plugin_cityStolen"))
                    recipient.addItem(transferred)
            remaining -= amount
            if not remaining:
                return True
        return False

    def makeSourceItem(obj, row):
        item = obj.getGame().createObject(itemId(row.get("item", "")))
        stack = row.get("quantity", 0)
        if "quantity" not in row and (
            item.getNumericProperty("plugin_cityStackSize") > 1 or row.get("item") == "MISC07"
        ):
            stack = (row.get("charges") or [1])[0]
        item.setNumericProperty("plugin_cityQuantity", max(1, stack))
        item.setNumericProperty("plugin_citySourceFlags", row.get("flags", 0))
        item.setNumericProperty("plugin_cityExpiration", row.get("expiration", 0))
        write(item, "plugin_cityCharges", row.get("charges", [0, 0, 0]))
        item.setBoolProperty("plugin_cityUnstealable", bool(row.get("flags", 0) & 2))
        item.setBoolProperty(
            "plugin_cityUndroppable", item.getBoolProperty("plugin_cityItemImmovable") or bool(row.get("flags", 0) & 8)
        )
        item.setBoolProperty("plugin_cityStolen", bool(row.get("flags", 0) & 4))
        item.setBoolProperty("plugin_cityUnidentified", not bool(row.get("flags", 0) & 1))
        if row.get("flags", 0) & 8:
            item.addTag("quest")
        return item

    def setStanding(obj, delta):
        game_map = world(obj)
        game_map.setNumericProperty("plugin_cityStanding", game_map.getNumericProperty("plugin_cityStanding") + delta)
        value = game_map.getNumericProperty("plugin_cityReputation") or 10
        game_map.setNumericProperty("plugin_cityReputation", max(1, min(20, value + delta)))

    def social(obj):
        return hero(obj).getStats().getNumericProperty("intelligence") + world(obj).getNumericProperty(
            "plugin_cityStanding"
        )

    def currentArea(obj):
        point = hero(obj).getCoords()
        for key, entry in read(clock(obj), "areaAtlas", {}).items():
            x, y, z, width, height = entry["bounds"]
            if point.z == z and x <= point.x < x + width and y <= point.y < y + height:
                return key
        return world(obj).getStringProperty("activeSimulationRegion")

    def observeArea(obj, area):
        game_map = world(obj)
        visited = read(game_map, "plugin_cityVisitedAreas", [])
        if area and area not in visited:
            visited.append(area)
            write(game_map, "plugin_cityVisitedAreas", visited)
        game_map.setStringProperty("activeSimulationRegion", area)

    def applyCondition(obj, condition):
        game_map, player = world(obj), hero(obj)
        if condition.get("not") and applyCondition(obj, condition["not"]):
            return False
        if condition.get("all") and not all(applyCondition(obj, row) for row in condition["all"]):
            return False
        if condition.get("any") and not any(applyCondition(obj, row) for row in condition["any"]):
            return False
        if hero(obj).getStats().getNumericProperty("agility") < condition.get("minAgility", 0):
            return False
        actor = obj.actor() if hasattr(obj, "actor") else None
        if condition.get("minTalks") and (
            not actor or actor.getNumericProperty("plugin_cityTalkCount") < condition["minTalks"]
        ):
            return False
        if any(stage(obj, key) != value for key, value in condition.get("questStages", {}).items()):
            return False
        if any(not game_map.getBoolProperty("plugin_cityFlag_" + name) for name in condition.get("flags", [])):
            return False
        if any(game_map.getBoolProperty("plugin_cityFlag_" + name) for name in condition.get("absentFlags", [])):
            return False
        if any(not hasItems(player, row) for row in condition.get("items", [])):
            return False
        score, reputation = social(obj), game_map.getNumericProperty("plugin_cityReputation") or 10
        if score < condition.get("minSocial", -1000) or score > condition.get("maxSocial", 1000):
            return False
        if reputation < condition.get("minReputation", 1) or reputation > condition.get("maxReputation", 20):
            return False
        if player.getNumericProperty("level") < condition.get("minLevel", 0):
            return False
        history = read(game_map, "plugin_cityHistory", {})
        if any(history.get(key) != value for key, value in condition.get("history", {}).items()):
            return False
        if condition.get("thiefInParty"):
            party = [player] + [actor for actor in companions(obj) if actor and actor.isAlive()]
            if not any(actor.getStats().getNumericProperty("agility") >= 12 for actor in party):
                return False
        dead = read(game_map, "plugin_cityDeaths", {})
        for selector in condition.get("kills", []):
            if sum(recordMatches(record, selector) for record in dead.values()) < selector.get("minimum", 1):
                return False
        for selector in condition.get("alive", []):
            if not any(isinstance(actor, CCreature) and actor.isAlive() for actor in actors(obj, selector)):
                return False
        talked = read(game_map, "plugin_cityTalked", {})
        for selector in condition.get("talked", []):
            if not any(recordMatches(record, selector) for record in talked.values()):
                return False
        visited = read(game_map, "plugin_cityVisitedAreas", [])
        if any(area not in visited for area in condition.get("visitedAreas", [])):
            return False
        for area in condition.get("clearedAreas", []):
            if any(
                isinstance(actor, CCreature)
                and actor.isAlive()
                and not actor.isNpc()
                and actor.getStringProperty("sourceArea") == area
                and actor.getStringProperty("affiliation") != player.getStringProperty("affiliation")
                for actor in game_map.getObjects()
            ) or not game_map.getBoolProperty("plugin_cityCombatObserved_" + area):
                return False
        guard_kills = game_map.getNumericProperty("plugin_cityGuardKills")
        return not (condition.get("noGuardKills") and guard_kills or condition.get("guardKills") and not guard_kills)

    def recordMatches(record, selector):
        return (
            (not selector.get("area") or record.get("area") == selector["area"])
            and (not selector.get("creature") or record.get("creature") == selector["creature"])
            and (not selector.get("label") or record.get("label", "").casefold() == selector["label"].casefold())
        )

    def actorRecord(actor):
        return {
            "label": actor.getStringProperty("label"),
            "creature": actor.getStringProperty("sourceCreature"),
            "area": actor.getStringProperty("sourceArea"),
        }

    def companions(obj):
        owner = clock(obj)
        return [
            owner.getObjectProperty("plugin_cityCompanion_" + name) for name in read(owner, "plugin_cityRoster", [])
        ]

    def updateAlliedRoster(obj):
        game_map = world(obj)
        game_map.setBoolProperty("plugin_cityAlliedCombat", True)
        game_map.setStringProperty("plugin_cityCompanionNames", ",".join(actor.getName() for actor in companions(obj)))
        game_map.setNumericProperty("plugin_cityCompanionCombatRadius", 8)

    def joinCompanion(obj, actor):
        roster = read(clock(obj), "plugin_cityRoster", [])
        if actor.getName() in roster:
            return True
        if len(roster) >= 5 or not actor.isAlive():
            return False
        actor.setStringProperty("plugin_cityOriginalAffiliation", actor.getStringProperty("affiliation"))
        actor.setStringProperty("affiliation", hero(obj).getStringProperty("affiliation"))
        actor.setBoolProperty("npc", False)
        actor.setBoolProperty("alwaysSimulate", True)
        controller = obj.getGame().createObject("CTargetController")
        controller.setStringProperty("target", "player")
        actor.setController(controller)
        roster.append(actor.getName())
        clock(obj).setObjectProperty("plugin_cityCompanion_" + actor.getName(), actor)
        write(clock(obj), "plugin_cityRoster", roster)
        updateAlliedRoster(obj)
        return True

    def crime(obj, actor=None):
        freezeHistory(obj)
        game_map = world(obj)
        setStanding(obj, -2)
        game_map.setNumericProperty("plugin_cityCrimes", game_map.getNumericProperty("plugin_cityCrimes") + 1)
        game_map.setBoolProperty("plugin_cityFlag_guardsAlerted", True)
        guards = [
            resident
            for resident in game_map.getObjects()
            if isinstance(resident, CCreature)
            and resident.isAlive()
            and resident.getStringProperty("sourceArea") == currentArea(obj)
            and "flaming fist" in resident.getStringProperty("label").casefold()
        ]
        for guard in guards[:2]:
            guard.setBoolProperty("npc", False)
            guard.setStringProperty("affiliation", "cityWatch")
            controller = obj.getGame().createObject("CTargetController")
            controller.setStringProperty("target", "player")
            guard.setController(controller)
        notify(obj, "The city watch has been alerted. Your local standing falls.")

    def seedRewardStock(obj, actor):
        if actor.getBoolProperty("plugin_cityRewardSeeded"):
            return
        required = {}
        for entry in definitions(obj):
            if clock(obj).getBoolProperty("plugin_cityPoisonSourceEnabled") and entry["id"] in (
                "marekPoison",
                "lothanderGeas",
                "jalanthaBook",
                "chanthalasTome",
                "divinerPoison",
            ):
                continue
            effects = []
            if any(matches(actor, selector) for selector in entry.get("givers", [])):
                effects.append(entry.get("acceptEffects", {}))
            for outcome in entry["outcomes"]:
                if any(matches(actor, selector) for selector in outcome.get("at", entry.get("givers", []))):
                    effects.append(outcome.get("effects", {}))
            for effect in effects:
                for row in effect.get("items", []):
                    required[row["item"]] = max(required.get(row["item"], 0), row.get("count", 1))
        for code, count in required.items():
            present = sum(quantity(item) for item in possessions(actor) if sourceCode(item) == code)
            if present < count:
                item = makeSourceItem(obj, {"item": code, "quantity": count - present, "flags": 1})
                item.setBoolProperty("plugin_cityQuestRewardStock", True)
                actor.addItem(item)
        actor.setBoolProperty("plugin_cityRewardSeeded", True)

    def applyEffects(obj, effects, owner):
        player = hero(obj)
        cost = -min(0, effects.get("gold", 0))
        if player.getGold() < cost or any(not hasItems(player, row) for row in effects.get("takeItems", [])):
            return False
        for row in effects.get("takeItems", []):
            if not takeItems(player, row, owner if isinstance(owner, CCreature) else None):
                return False
        player.addGold(effects.get("gold", 0))
        player.addExp(effects.get("xp", 0))
        setStanding(obj, effects.get("standing", 0))
        for row in effects.get("items", []):
            # Rewards and pickpocketing draw from the same persistent owner inventory.
            releaseReward(owner, {"item": row["item"], "count": row.get("count", 1)})
            takeItems(owner, {"item": row["item"], "count": row.get("count", 1)}, player)
        for key, value in effects.get("flags", {}).items():
            world(obj).setBoolProperty("plugin_cityFlag_" + key, value)
        for selector in effects.get("departActors", []):
            for actor in actors(obj, selector):
                actor.setBoolProperty("plugin_cityDeparted", True)
        for selector in effects.get("hostile", []):
            for actor in actors(obj, selector):
                if isinstance(actor, CCreature) and actor.isAlive():
                    actor.setBoolProperty("npc", False)
                    actor.setStringProperty("affiliation", "cityHostile")
                    controller = obj.getGame().createObject("CTargetController")
                    controller.setStringProperty("target", "player")
                    actor.setController(controller)
        if effects.get("clearTimer"):
            world(obj).setBoolProperty("plugin_cityFlag_partyPoisoned", False)
        return True

    def initializeInventory(actor):
        if actor.getBoolProperty("plugin_cityInventoryInitialized"):
            return
        items = {}
        for index, row in enumerate(read(actor, "sourceInventory", [])):
            source_index = row.get("sourceIndex", index)
            if row.get("item") == "MISC07":
                actor.addGold(max(1, row.get("quantity", (row.get("charges") or [1])[0])))
                items[source_index] = None
                continue
            item = makeSourceItem(actor, row)
            actor.addItem(item)
            items[source_index] = item
        slots = read(actor, "sourceItemSlots", [])
        equipped_indices = {index for index in slots[:21] if index in items}
        configuration = actor.getGame().getSlotConfiguration()
        for index in sorted(equipped_indices):
            item = items[index]
            if not item:
                continue
            for native_slot in configuration.getFittingSlots(item):
                if not actor.getEquipped().get(native_slot):
                    actor.equipItem(native_slot, item)
                    break
        actor.setBoolProperty("plugin_cityInventoryInitialized", True)

    def custody(obj):
        return world(obj).getObjectByName("cityCustody")

    @register(context)
    @mapQuest("baldursGate")
    class BaldursGateCustodyQuest(CQuest):
        def isCompleted(self):
            return world(self).getStringProperty("plugin_cityCustodyState") in ("escaped", "released")

        def getObjective(self):
            state = world(self).getStringProperty("plugin_cityCustodyState")
            return {
                "hearing": "The Flaming Fist has arrested you; answer Angelo's accusations.",
                "jailed": "Angelo has imprisoned you; find a way out of the headquarters.",
                "escaped": "You escaped with Neb through a hidden route.",
                "released": "Angelo released your company after Shar-Teel intervened.",
                "fought": "You resisted the arrest patrol; the Flaming Fist is hostile.",
            }.get(state, "The Flaming Fist is hunting your company.")

        def getReward(self):
            return "Arrest and escape grant no gold, experience, or equipment."

        def getHint(self):
            return "Speak to the people in the headquarters; the cell door starts open."

        def onComplete(self):
            pass

    @register(context)
    class BaldursGateCustody(CBuilding):
        """Bounded, saved coordinator for the audited arrest dialogue and cutscenes."""

        def data(self):
            encoded = self.getStringProperty("custodyDefinitions")
            if encoded not in custody_definitions:
                custody_definitions.clear()
                custody_definitions[encoded] = decodeData(encoded or "{}")
            return custody_definitions[encoded]

        def participant(self, name, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            if isinstance(name, dict):
                name = name.get("symbol", "")
            if name == "Player1":
                return binding["player"]
            if name.startswith("Player") and self.custodyCall(binding, name[6:], "isdigit"):
                party = self.custodyParty(binding)
                slot = int(name[6:]) - 2
                return party[slot] if 0 <= slot < len(party) else None
            if name.casefold() == "sharteel":
                return firstMatch(
                    (
                        actor
                        for actor in self.custodyParty(binding)
                        if actor
                        and self.custodyCall(binding, actor, "getStringProperty", "sourceCreature").startswith("SHARTE")
                    ),
                    None,
                )
            native_id = firstMatch(
                (
                    value
                    for key, value in binding["data"].get("namedActors", {}).items()
                    if key.casefold() == name.casefold()
                ),
                name,
            )
            return self.custodyCall(binding, binding["map"], "getObjectByName", native_id) or self.custodyCall(
                binding, self, "getObjectProperty", "plugin_cityActor_" + native_id
            )

        def globalValue(self, name, scope, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            if scope == "GLOBAL" and name == "Chapter":
                return self.custodyCall(binding, binding["map"], "getNumericProperty", "plugin_cityPhase") or 5
            return self.custodyRead(binding, binding["map"], "plugin_cityCustodyGlobals", {}).get(scope + ":" + name, 0)

        def setGlobal(self, name, scope, value, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            values = self.custodyRead(binding, binding["map"], "plugin_cityCustodyGlobals", {})
            values[scope + ":" + name] = value
            self.custodyWrite(binding, binding["map"], "plugin_cityCustodyGlobals", values)

        def condition(self, row, actor, roll=None, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            if "not" in row:
                return not self.custodyCall(binding, self, "condition", row["not"], actor, roll, binding=binding)
            op, args = (row["op"], row.get("args", []))
            alive = sum(
                (
                    self.custodyCall(binding, member, "isAlive")
                    for member in [binding["player"], *self.custodyParty(binding)]
                    if member
                )
            )
            if op == "True":
                return True
            if op == "False":
                return False
            if op == "Global":
                return self.custodyCall(binding, self, "globalValue", *args[:2], binding=binding) == args[2]
            if op == "NumberOfTimesTalkedTo":
                return self.custodyCall(binding, actor, "getNumericProperty", "plugin_cityTalkCount") == args[0]
            if op == "InParty":
                return self.custodyCall(binding, self, "participant", args[0], binding=binding) is not None
            if op == "NumInPartyAlive":
                return alive == args[0]
            if op == "NumInPartyAliveGT":
                return alive > args[0]
            if op == "NumInPartyAliveLT":
                return alive < args[0]
            if op == "RandomNum":
                return roll == args[1]
            if op == "StateCheck":
                return self.custodyCall(binding, actor, "getBoolProperty", "plugin_cityCharmed")
            raise ValueError("Unaudited custody condition: " + op)

        def spawnActor(self, native_id, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            existing = self.custodyCall(binding, self, "participant", native_id, binding=binding)
            if existing:
                self.custodyCall(binding, existing, "getName")
                return existing
            rows = self.custodyRead(binding, binding["clock"], "actorDefinitions", [])
            matches = [row for row in rows if row["id"] == native_id]
            if len(matches) != 1:
                raise self.CustodyBindingChanged("Custody requires one authored construction row")
            row = matches[0]
            actor = self.custodyCall(binding, binding["game"].resolve(), "createObject", native_id)
            self.stageCustodyActor(binding, actor, row)
            self.placeCustodyActor(binding, actor, "setStringProperty", "name", native_id)
            for key, axis in (("posx", "x"), ("posy", "y"), ("posz", "z")):
                self.placeCustodyActor(binding, actor, "setNumericProperty", key, row[axis])
            add_object = getattr(binding["map"], "addObject")
            self.requireCustodyStage(binding, actor)
            add_object(actor)
            self.requireCustodyStage(binding, actor, registered=True)
            self.custodyCall(binding, binding["clock"], "initializeActor", actor)
            self.requireCustodyStage(binding, actor, registered=True)
            self.custodyCall(binding, self, "setObjectProperty", "plugin_cityActor_" + native_id, actor)
            self.requireCustodyStage(binding, actor, registered=True)
            del binding["stagedActors"][actor]
            return actor

        def retire(self, actor, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            if actor:
                self.allowCustodyDetach(binding, actor)
                self.custodyCall(binding, actor, "setBoolProperty", "plugin_cityDeparted", True)
                self.custodyCall(
                    binding,
                    self,
                    "setObjectProperty",
                    "plugin_cityActor_" + self.custodyCall(binding, actor, "getName"),
                    actor,
                )
                if self.custodyCall(
                    binding, binding["map"], "getObjectByName", self.custodyCall(binding, actor, "getName")
                ):
                    self.custodyCall(binding, binding["map"], "removeObject", actor)

        def relocateParty(self, stage_name, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            target = binding["data"][stage_name]
            party = [binding["player"], *self.custodyParty(binding)]
            for member, point in pairedValues(party, target["partyPositions"]):
                if member and self.custodyCall(binding, member, "isAlive"):
                    self.custodyCall(binding, member, "relocateWithoutMoveHooks", self.custodyPoint(binding, *point))
                    if not member is binding["player"]:
                        self.custodyCall(binding, member, "setStringProperty", "simulationRegion", target["area"])
            self.custodyObserveArea(binding, target["area"])

        def journal(self, number, erase=False, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            entries = self.custodyRead(binding, binding["map"], "plugin_cityCustodyJournal", [])
            if erase:
                entries = [value for value in entries if value != number]
            elif number not in entries:
                entries.append(number)
            self.custodyWrite(binding, binding["map"], "plugin_cityCustodyJournal", entries)

        def ensureQuest(self, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            player = binding["player"]
            if not any(
                (
                    self.custodyCall(binding, entry, "getTypeId") == "cityCustodyQuest"
                    for entry in (
                        *self.custodyCall(binding, player, "getQuests"),
                        *self.custodyCall(binding, player, "getCompletedQuests"),
                    )
                )
            ):
                self.custodyCall(binding, player, "addQuest", "cityCustodyQuest")

        def makeHostile(self, actor, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            if actor and self.custodyCall(binding, actor, "isAlive"):
                self.custodyCall(binding, actor, "setBoolProperty", "npc", False)
                self.custodyCall(binding, actor, "setStringProperty", "affiliation", "cityWatch")
                controller = self.custodyCall(binding, actor, "getController")
                if (
                    not controller
                    or self.custodyCall(binding, controller, "getTypeId") != "CTargetController"
                    or self.custodyCall(binding, controller, "getStringProperty", "target") != "player"
                ):
                    controller = self.custodyCall(
                        binding, binding["game"].resolve(), "createObject", "CTargetController"
                    )
                    self.custodyCall(binding, controller, "setStringProperty", "target", "player")
                    self.custodyCall(binding, actor, "setController", controller)

        def updatePatrols(self):
            from game import CGame, CMap, CPlayer

            game = self.getGame()
            if not game:
                raise ValueError("Custody patrol ownership changed")
            map_epoch = CGame.getMapBindingEpoch(game)
            game_map = game.getMap()
            if not isinstance(game_map, CMap):
                raise ValueError("Custody patrol ownership changed")
            player = CMap.getAssignedPlayer(game_map)
            if not isinstance(player, CPlayer) or CMap.getObjectByName(game_map, "player") is not player:
                raise ValueError("Custody patrol ownership changed")
            context = game.getContext()
            if not game_map or not context:
                raise ValueError("Custody patrol ownership changed")
            generation = context.getTransitionGeneration()
            owner_name = self.getName()
            owner = game_map.getObjectByName("cityClock")
            actor_areas = {}

            def requireCurrent():
                if (
                    CGame.getMapBindingEpoch(game) != map_epoch
                    or CMap.getAssignedPlayer(game_map) is not player
                    or self.getGame() is not game
                    or game.getContext() is not context
                    or game.getMap() is not game_map
                    or not context.isTransitionGenerationCurrent(generation)
                    or game_map.getObjectByName(owner_name) is not self
                    or not isinstance(owner, BaldursGateClock)
                    or owner.getGame() is not game
                    or owner.getName() != "cityClock"
                    or game_map.getObjectByName("cityClock") is not owner
                    or not isinstance(player, CPlayer)
                    or not player.isAlive()
                    or player.getGame() is not game
                    or player.getName() != "player"
                    or game_map.getObjectByName("player") is not player
                    or game_map.getObjectByName(owner_name) is not self
                    or game_map.getObjectByName("cityClock") is not owner
                    or game.getMap() is not game_map
                    or not context.isTransitionGenerationCurrent(generation)
                    or CGame.getMapBindingEpoch(game) != map_epoch
                    or CMap.getAssignedPlayer(game_map) is not player
                ):
                    raise ValueError("Custody patrol ownership changed")

            def requirePatrol(actor, native_id, staged=False, registered=False):
                requireCurrent()
                if not isinstance(actor, CCreature) or isinstance(actor, CPlayer):
                    raise ValueError("Invalid custody patrol creature binding")
                actor_game = actor.getGame()
                requireCurrent()
                actor_name = actor.getName()
                requireCurrent()
                creature = actor.getStringProperty("sourceCreature")
                requireCurrent()
                area = actor.getStringProperty("sourceArea")
                requireCurrent()
                current = game_map.getObjectByName(native_id)
                requireCurrent()
                cached = optionalObjectProperty(self, "plugin_cityActor_" + native_id)
                requireCurrent()
                if (
                    actor_game is not game
                    or actor_name != native_id
                    or creature != "FFHUNT"
                    or area != actor_areas[native_id]
                    or current is not None
                    and current is not actor
                    or registered
                    and current is not actor
                    or not staged
                    and current is None
                    and cached is not actor
                    or actor.getGame() is not game
                    or game_map.getObjectByName(native_id) is not current
                ):
                    raise ValueError("Custody patrol actor ownership changed")
                requireCurrent()

            def globalsNow():
                values = read(game_map, "plugin_cityCustodyGlobals", {})
                requireCurrent()
                if not isinstance(values, dict):
                    raise ValueError("Invalid custody patrol globals")
                return values

            def globalValue(name):
                if name == "Chapter":
                    value = game_map.getNumericProperty("plugin_cityPhase") or 5
                else:
                    value = globalsNow().get("GLOBAL:" + name, 0)
                requireCurrent()
                if type(value) is not int:
                    raise ValueError("Invalid custody patrol global value: " + name)
                return value

            def retained(native_id):
                actor = game_map.getObjectByName(native_id)
                requireCurrent()
                if not actor:
                    actor = optionalObjectProperty(self, "plugin_cityActor_" + native_id)
                    requireCurrent()
                if actor:
                    requirePatrol(actor, native_id)
                return actor

            def retire(actor):
                if not actor:
                    return
                name = actor.getName()
                requirePatrol(actor, name)
                actor.setBoolProperty("plugin_cityDeparted", True)
                requirePatrol(actor, name)
                self.setObjectProperty("plugin_cityActor_" + name, actor)
                requireCurrent()
                registered = game_map.getObjectByName(name)
                requireCurrent()
                if registered is actor:
                    game_map.removeObject(actor)
                    requireCurrent()
                elif registered:
                    raise ValueError("Custody patrol was replaced during retirement")

            def spawn(native_id):
                existing = retained(native_id)
                if existing:
                    return existing
                rows = read(owner, "actorDefinitions", [])
                requireCurrent()
                matches = [row for row in rows if row.get("id") == native_id]
                if len(matches) != 1 or any(type(matches[0].get(axis)) is not int for axis in ("x", "y", "z")):
                    raise ValueError("Missing audited custody patrol actor row")
                actor = game.createObject(native_id)
                requireCurrent()
                if not isinstance(actor, CCreature) or actor.getGame() is not game:
                    raise ValueError("Invalid native custody patrol constructor")
                requireCurrent()
                actor.setStringProperty("name", native_id)
                requireCurrent()
                for axis in ("x", "y", "z"):
                    actor.setNumericProperty("pos" + axis, matches[0][axis])
                    requireCurrent()
                requirePatrol(actor, native_id, staged=True)
                self.setObjectProperty("plugin_cityActor_" + native_id, actor)
                requireCurrent()
                game_map.addObject(actor)
                requireCurrent()
                if game_map.getObjectByName(native_id) is not actor:
                    raise ValueError("Custody patrol was replaced during creation")
                requireCurrent()
                owner.initializeActor(actor)
                requirePatrol(actor, native_id, registered=True)
                return actor

            def makeHostile(actor):
                if not actor:
                    return
                name = actor.getName()
                requirePatrol(actor, name)
                if game_map.getObjectByName(name) is not actor:
                    requireCurrent()
                    return
                requirePatrol(actor, name, registered=True)
                alive = actor.isAlive()
                requirePatrol(actor, name, registered=True)
                if not alive:
                    return
                actor.setBoolProperty("npc", False)
                requirePatrol(actor, name, registered=True)
                actor.setStringProperty("affiliation", "cityWatch")
                requirePatrol(actor, name, registered=True)
                controller = actor.getController()
                requirePatrol(actor, name, registered=True)
                type_id = controller.getTypeId() if controller else ""
                requirePatrol(actor, name, registered=True)
                target = controller.getStringProperty("target") if controller else ""
                requirePatrol(actor, name, registered=True)
                if type_id != "CTargetController" or target != "player":
                    controller = game.createObject("CTargetController")
                    requirePatrol(actor, name, registered=True)
                    controller.setStringProperty("target", "player")
                    requirePatrol(actor, name, registered=True)
                    actor.setController(controller)
                    requirePatrol(actor, name, registered=True)

            requireCurrent()
            data = self.data()
            requireCurrent()
            if not data:
                return
            patrols = data.get("patrols")
            if not isinstance(patrols, dict) or len(patrols) > 9:
                raise ValueError("Invalid bounded custody patrol definitions")
            validated = []
            audited_areas = ("AR0100", "AR0200", "AR0300", "AR0600", "AR0700", "AR0800", "AR1100", "AR1200", "AR1300")
            if tuple(sorted(patrols)) != audited_areas:
                raise ValueError("Unsupported custody patrol source area")
            for area, row in patrols.items():
                if not isinstance(row, dict):
                    raise ValueError("Invalid audited custody patrol response")
                conditions = row.get("conditions")
                one_shot = row.get("oneShotGlobal")
                actors = row.get("actors")
                if (
                    not isinstance(area, str)
                    or not area.startswith("AR")
                    or not area[2:].isdigit()
                    or one_shot != "Capture" + str(int(area[2:]))
                    or type(row.get("oneShotValue")) is not int
                    or row["oneShotValue"] != 1
                    or not isinstance(actors, list)
                    or len(actors) != 2
                    or any(not isinstance(name, str) or not name for name in actors)
                    or len(set(actors)) != 2
                    or not isinstance(conditions, list)
                    or len(conditions) != 3
                ):
                    raise ValueError("Invalid audited custody patrol response")
                if actors != ["cityCustodyPatrol" + area.title() + suffix for suffix in ("One", "Two")]:
                    raise ValueError("Unsupported custody patrol source actor")
                actor_areas.update((native_id, area) for native_id in actors)
                expected = (("Chapter", 7), (one_shot, 0), ("DukeThanks", 0))
                for condition, (name, value) in pairedValues(conditions, expected):
                    if (
                        not isinstance(condition, dict)
                        or type(condition.get("opcode")) is not int
                        or condition.get("opcode") != 16399
                        or condition.get("signature") != "Global(S:Name*,S:Area*,I:Value*)"
                        or condition.get("strings") != ["GLOBAL" + name, ""]
                        or condition.get("integerFields") != [value, 0, 0, 0]
                        or any(type(number) is not int for number in condition["integerFields"])
                        or condition.get("negated") is not False
                    ):
                        raise ValueError("Unsupported custody patrol source condition")
                validated.append((area, tuple(actors), one_shot, row["oneShotValue"], expected))

            phase = globalValue("Chapter")
            thanks = globalValue("DukeThanks") == 1
            palace_cleared = game_map.getBoolProperty("plugin_cityFlag_palaceCleared")
            requireCurrent()
            thanks = thanks or palace_cleared
            point = player.getCoords()
            requireCurrent()
            atlas = read(owner, "areaAtlas", {})
            requireCurrent()
            active_area = None
            for area, entry in atlas.items():
                x, y, z, width, height = entry["bounds"]
                if point.z == z and x <= point.x < x + width and y <= point.y < y + height:
                    active_area = area
                    break
            if active_area is None:
                active_area = game_map.getStringProperty("activeSimulationRegion")
            requireCurrent()
            captured = globalValue("Captured") == 1
            for area, actor_ids, one_shot, assigned_value, conditions in validated:
                if thanks:
                    for native_id in actor_ids:
                        retire(retained(native_id))
                    continue
                if active_area != area:
                    continue
                if not palace_cleared and all(globalValue(name) == value for name, value in conditions):
                    values = globalsNow()
                    values["GLOBAL:" + one_shot] = assigned_value
                    write(game_map, "plugin_cityCustodyGlobals", values)
                    requireCurrent()
                    if globalValue(one_shot) != assigned_value:
                        raise ValueError("Custody patrol one-shot assignment did not persist")
                    # The audited SetGlobal precedes both CreateCreature actions. Failure must not replay them.
                    for native_id in actor_ids:
                        spawn(native_id)
                if captured:
                    for native_id in actor_ids:
                        makeHostile(retained(native_id))
            requireCurrent()
            hearing = game_map.getBoolProperty("plugin_cityFlag_custodyHearing")
            requireCurrent()
            if phase == 7 and hearing:
                binding = self.captureCustodyBinding()
                requireCurrent()
                if (
                    binding["game"].resolve() is not game
                    or binding["map"] is not game_map
                    or binding["context"] is not context
                    or binding["generation"] != generation
                    or binding["mapEpoch"] != map_epoch
                    or binding["player"] is not player
                    or binding["clock"] is not owner
                    or binding["data"] != data
                ):
                    raise ValueError("Custody patrol hearing ownership changed")
                self.requireCustodyBinding(binding)
                requireCurrent()
                self.relocateParty("hearing", binding=binding)
                requireCurrent()

        def beginCustody(self, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            game_map = binding["map"]
            if self.custodyCall(binding, game_map, "getStringProperty", "plugin_cityCustodyState") == "hearing":
                return
            self.custodyCall(binding, self, "ensureQuest", binding=binding)
            self.custodyCall(binding, game_map, "setStringProperty", "plugin_cityCustodyState", "hearing")
            self.custodyCall(binding, game_map, "setBoolProperty", "plugin_cityFlag_custodyHearing", True)
            self.custodyCall(binding, self, "relocateParty", "hearing", binding=binding)
            for key in ("CHIMP5", "FERGUS"):
                self.custodyCall(
                    binding,
                    self,
                    "retire",
                    self.custodyCall(binding, self, "participant", key, binding=binding),
                    binding=binding,
                )
            old_guard = self.custodyCall(binding, self, "participant", "DICKSMOK", binding=binding)
            if old_guard:
                self.custodyCall(binding, old_guard, "setNumericProperty", "plugin_cityTalkCount", 1)
            for native_id in [*binding["data"]["actorIds"]["escorts"], binding["data"]["actorIds"]["angelo"]]:
                self.custodyCall(binding, self, "spawnActor", native_id, binding=binding)
            self.custodyCall(
                binding, binding["clock"], "advanceTicks", binding["data"]["hearing"].get("advanceMinutes", 0) * 5 // 6
            )
            self.custodyCall(binding, self, "updatePatrols")

        def finishCustody(self, stage_name, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            self.custodyCall(binding, self, "ensureQuest", binding=binding)
            state = {"jail": "jailed", "escape": "escaped", "release": "released"}[stage_name]
            self.custodyCall(binding, binding["map"], "setStringProperty", "plugin_cityCustodyState", state)
            self.custodyCall(binding, binding["map"], "setBoolProperty", "plugin_cityFlag_custodyHearing", False)
            self.custodyCall(binding, self, "relocateParty", stage_name, binding=binding)
            for native_id in [*binding["data"]["actorIds"]["escorts"], binding["data"]["actorIds"]["angelo"]]:
                self.custodyCall(
                    binding,
                    self,
                    "retire",
                    self.custodyCall(binding, self, "participant", native_id, binding=binding),
                    binding=binding,
                )
            if stage_name == "escape":
                self.custodyCall(
                    binding,
                    self,
                    "journal",
                    (
                        32175
                        if self.custodyCall(binding, self, "globalValue", "AttackNEB", "AR0607", binding=binding)
                        else 27317
                    ),
                    binding=binding,
                )
                self.custodyCall(
                    binding,
                    self,
                    "retire",
                    self.custodyCall(binding, self, "participant", "NEB", binding=binding),
                    binding=binding,
                )
            self.custodyCall(binding, binding["clock"], "applySchedules")

        def killByAngelo(self, victim, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            if victim and self.custodyCall(binding, victim, "isAlive"):
                self.allowCustodyDetach(binding, victim)
                self.custodyCall(binding, victim, "setBoolProperty", "plugin_cityPlotExecution", True)
                self.custodyCall(binding, victim, "setStringProperty", "plugin_cityDeathCause", "Angelo")
                self.custodyCall(binding, victim, "setHp", 0)
                self.custodyCall(
                    binding,
                    self,
                    "setObjectProperty",
                    "plugin_cityExecuted_" + self.custodyCall(binding, victim, "getName"),
                    victim,
                )
                if victim in self.custodyParty(binding):
                    self.custodyCall(binding, self, "setObjectProperty", "plugin_cityExecutedCompanion", victim)
                if self.custodyCall(
                    binding, binding["map"], "getObjectByName", self.custodyCall(binding, victim, "getName")
                ):
                    self.custodyCall(binding, binding["map"], "removeObject", victim)

        def releaseScene(self, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            for name in ("FLAME3", "FLAME4", "DICKSMOK"):
                self.custodyCall(
                    binding,
                    self,
                    "retire",
                    self.custodyCall(binding, self, "participant", name, binding=binding),
                    binding=binding,
                )
            for name, symbol in (("FLAME1", "[718.1027]"), ("FLAME2", "[773.1047]"), ("ANGELO", "[765.1010]")):
                actor = self.custodyCall(binding, self, "participant", name, binding=binding)
                if actor:
                    self.custodyCall(
                        binding,
                        actor,
                        "relocateWithoutMoveHooks",
                        self.custodyPoint(binding, *binding["data"]["points"][symbol]),
                    )
            for name in ("FLAME1", "FLAME2"):
                self.custodyCall(
                    binding,
                    self,
                    "killByAngelo",
                    self.custodyCall(binding, self, "participant", name, binding=binding),
                    binding=binding,
                )
            angelo = self.custodyCall(binding, self, "participant", "ANGELO", binding=binding)
            if angelo:
                self.custodyCall(
                    binding,
                    angelo,
                    "relocateWithoutMoveHooks",
                    self.custodyPoint(binding, *binding["data"]["points"]["[543.1173]"]),
                )

        def applyAction(self, row, actor, binding=None):
            binding = binding if binding is not None else self.captureCustodyBinding()
            op, args = (row["op"], row.get("args", []))
            if op == "SetGlobal":
                self.custodyCall(binding, self, "setGlobal", *args, binding=binding)
            elif op in ("AddJournalEntry", "EraseJournalEntry"):
                self.custodyCall(binding, self, "journal", args[0], op == "EraseJournalEntry", binding=binding)
            elif op == "ActionOverride":
                target = self.custodyCall(binding, self, "participant", args[0], binding=binding)
                if target:
                    self.custodyCall(binding, self, "applyAction", args[1], target, binding=binding)
            elif op in ("JumpToPoint", "MoveToPoint"):
                point = binding["data"]["points"][args[0]["symbol"]]
                self.custodyCall(binding, actor, "relocateWithoutMoveHooks", self.custodyPoint(binding, *point))
            elif op == "Kill":
                self.custodyCall(
                    binding,
                    self,
                    "killByAngelo",
                    self.custodyCall(binding, self, "participant", args[0], binding=binding),
                    binding=binding,
                )
            elif op == "DestroySelf":
                self.custodyCall(binding, self, "retire", actor, binding=binding)
            elif op == "Enemy":
                self.custodyCall(binding, self, "makeHostile", actor, binding=binding)
            elif op == "Shout":
                area = self.custodyCall(binding, actor, "getStringProperty", "sourceArea")
                for native_id in binding["data"]["patrols"].get(area, {}).get("actors", []):
                    self.custodyCall(
                        binding,
                        self,
                        "makeHostile",
                        self.custodyCall(binding, self, "participant", native_id, binding=binding),
                        binding=binding,
                    )
                self.custodyCall(binding, binding["map"], "setStringProperty", "plugin_cityCustodyState", "fought")
                self.custodyCall(binding, self, "ensureQuest", binding=binding)
            elif op in ("ApplyDamagePercent", "CreateCreature"):
                pass
            elif op not in ("StartCutScene", "StartDialogNoSet"):
                raise ValueError("Unaudited custody action: " + op)

        @resumableHook
        def conversation(self, actor, forced_code="", forced_state=None):
            try:
                binding = self.captureCustodyBinding(actor)
                data = binding["data"]
                cursor = self.custodyRead(binding, binding["map"], "plugin_cityCustodyDialogue", {})
                if cursor and cursor["actorId"] != binding["actorName"] and not forced_code:
                    return
                if forced_code:
                    code, state_id = forced_code, forced_state
                elif cursor:
                    code, state_id = cursor["code"], cursor["state"]
                else:
                    code = binding["sourceDialogue"]
                    if code not in data.get("dialogues", {}):
                        return
                    entries = sorted(
                        (row for row in data["dialogues"][code] if row.get("entryWeight") is not None),
                        key=lambda row: row["entryWeight"],
                    )
                    entry = firstMatch(
                        (
                            row
                            for row in entries
                            if all(
                                self.custodyCall(binding, self, "condition", test, actor, binding=binding)
                                for test in row["conditions"]
                            )
                        ),
                        None,
                    )
                    if not entry:
                        return
                    state_id = entry["id"]
                    self.custodyCall(
                        binding, actor, "setNumericProperty", "plugin_cityTalkCount", binding["talkCount"] + 1
                    )
                for _step in range(64):
                    state = firstMatch(row for row in data["dialogues"][code] if row["id"] == state_id)
                    self.custodyWrite(
                        binding,
                        binding["map"],
                        "plugin_cityCustodyDialogue",
                        {"actorId": binding["actorName"], "code": code, "state": state_id},
                    )
                    request = self.custodyRequest(binding, "showReader", state.get("speaker", code), state["text"])
                    yield request
                    self.requireCustodyBinding(binding)
                    roll = None
                    if any(
                        test.get("op") == "RandomNum" for edge in state["transitions"] for test in edge["conditions"]
                    ):
                        from game import randint

                        roll = randint(1, 5)
                        self.requireCustodyBinding(binding)
                    eligible = [
                        edge
                        for edge in state["transitions"]
                        if all(
                            self.custodyCall(binding, self, "condition", test, actor, roll, binding=binding)
                            for test in edge["conditions"]
                        )
                    ]
                    automatic = [edge for edge in eligible if edge.get("replyStrref") is None]
                    if automatic:
                        edge = max(automatic, key=lambda row: row["id"])
                    else:
                        request = self.custodyRequest(
                            binding,
                            "choose",
                            state["text"],
                            [{"id": str(edge["id"]), "label": edge["reply"]} for edge in eligible],
                            "Answer",
                            "Continue later",
                        )
                        choice = yield request
                        self.requireCustodyBinding(binding)
                        edge = firstMatch(
                            (edge for edge in eligible if type(choice) is str and str(edge["id"]) == choice), None
                        )
                        if edge is None:
                            return
                    if not all(
                        self.custodyCall(binding, self, "condition", test, actor, roll, binding=binding)
                        for test in edge["conditions"]
                    ):
                        return
                    self.requireCustodyBinding(binding)
                    trace = self.custodyRead(binding, binding["map"], "plugin_cityCustodyTrace", [])
                    trace.append({"dialogue": code, "state": state_id, "edge": edge["id"], "roll": roll})
                    self.custodyWrite(binding, binding["map"], "plugin_cityCustodyTrace", trace[-256:])
                    self.custodyCall(
                        binding,
                        binding["map"],
                        "setNumericProperty",
                        "plugin_cityCustodyTransitionCount",
                        binding["counter"] + 1,
                    )
                    if edge.get("journalStrref") is not None:
                        self.journal(edge["journalStrref"], binding=binding)
                    for action in edge["effects"]:
                        self.applyAction(action, actor, binding=binding)
                    target = edge.get("next")
                    cutscene = firstMatch(
                        (action["args"][0].upper() for action in edge["effects"] if action["op"] == "StartCutScene"), ""
                    )
                    if cutscene == "CAPCUT01":
                        self.beginCustody(binding=binding)
                        actor = self.custodyCall(binding, self, "participant", "FLAME4")
                        self.bindCustodyActor(binding, actor)
                        self.custodyCall(
                            binding, actor, "setNumericProperty", "plugin_cityTalkCount", binding["talkCount"] + 1
                        )
                        target = ["FLAMC7", 8]
                    elif cutscene in ("CAPCUT02", "CAPCUT04"):
                        self.finishCustody("escape" if cutscene == "CAPCUT02" else "release", binding=binding)
                    elif cutscene == "CAPCUT05":
                        self.releaseScene(binding=binding)
                        target = ["ANGELO", 7]
                    if not target and code == "ANGELO" and state_id in (1, 9):
                        target = ["ANGELO", 4]
                    if not target and code == "ANGELO" and state_id in (3, 4):
                        self.finishCustody("jail", binding=binding)
                    if not target:
                        self.custodyWrite(binding, binding["map"], "plugin_cityCustodyDialogue", {})
                        yield self.custodyRequest(binding, "gui.checkQuests")
                        self.requireCustodyBinding(binding)
                        return True
                    code, state_id = target
                    if code == "ANGELO":
                        actor = self.custodyCall(binding, self, "participant", "ANGELO")
                        self.bindCustodyActor(binding, actor)
                        if state_id == 0:
                            self.custodyCall(
                                binding, actor, "setNumericProperty", "plugin_cityTalkCount", binding["talkCount"] + 1
                            )
                    elif code == "SHARTJ":
                        actor = self.custodyCall(binding, self, "participant", "Sharteel")
                        self.bindCustodyActor(binding, actor)
                    self.requireCustodyBinding(binding)
                raise ValueError("Custody dialogue exceeded its audited bounded transition budget")
            except self.CustodyBindingChanged:
                return

        class CustodyBindingChanged(RuntimeError):
            pass

        def captureCustodyBinding(self, actor=None):
            from game import CGame, CGameObject, CMap, CPlayer

            game = self.getGame()
            map_epoch = CGame.getMapBindingEpoch(game) if game else None
            game_map = game.getMap() if game else None
            if not isinstance(game_map, CMap):
                raise self.CustodyBindingChanged("Custody has no current map")
            player = CMap.getAssignedPlayer(game_map)
            if not isinstance(player, CPlayer) or CMap.getObjectByName(game_map, "player") is not player:
                raise self.CustodyBindingChanged("Custody assigned player changed")
            native_context = game.getContext()
            generation = native_context.getTransitionGeneration()
            registry = game_map.getObjectByName("cityClock")
            encoded = self.getStringProperty("custodyDefinitions")
            binding = {
                "game": flowGame(game),
                "gameClass": CGame,
                "mapEpoch": map_epoch,
                "context": native_context,
                "generation": generation,
                "map": game_map,
                "player": player,
                "playerName": player.getName() if player else "",
                "playerClass": CPlayer,
                "objectClass": CGameObject,
                "mapClass": CMap,
                "clock": registry,
                "encoded": encoded,
                "actorDefinitions": registry.getStringProperty("actorDefinitions") if registry else "",
                "questDefinitions": registry.getStringProperty("questDefinitions") if registry else "",
                "phase": game_map.getNumericProperty("plugin_cityPhase"),
                "cursor": game_map.getStringProperty("plugin_cityCustodyDialogue"),
                "counter": game_map.getNumericProperty("plugin_cityCustodyTransitionCount"),
                "actor": None,
                "detached": set(),
                "stagedActors": {},
                "data": decodeData(encoded or "{}"),
            }
            self.requireCustodyBinding(binding)
            if actor is not None:
                self.bindCustodyActor(binding, actor)
            return binding

        def custodyBindingCurrent(self, binding):
            game, game_map = binding["game"].resolve(), binding["map"]
            player, registry = binding["player"], binding["clock"]
            native_context, generation = binding["context"], binding["generation"]
            if (
                not game
                or not isinstance(player, binding["playerClass"])
                or not isinstance(registry, BaldursGateClock)
                or type(generation) is not int
            ):
                return False
            if (
                type(binding["mapEpoch"]) is not int
                or binding["gameClass"].getMapBindingEpoch(game) != binding["mapEpoch"]
                or binding["mapClass"].getAssignedPlayer(game_map) is not player
            ):
                return False
            for _pass in range(2):
                if (
                    binding["mapClass"].getAssignedPlayer(game_map) is not player
                    or self.getGame() is not game
                    or game.getMap() is not game_map
                    or game.getContext() is not native_context
                    or not native_context.isTransitionGenerationCurrent(generation)
                    or self.getMap() is not game_map
                    or game_map.getObjectByName(binding["playerName"]) is not player
                    or binding["playerName"] != "player"
                    or player.getName() != "player"
                    or game_map.getObjectByName("cityCustody") is not self
                    or game_map.getObjectByName("cityClock") is not registry
                    or player.getGame() is not game
                    or player.getMap() is not game_map
                    or not player.isAlive()
                    or registry.getGame() is not game
                    or registry.getMap() is not game_map
                    or self.getStringProperty("custodyDefinitions") != binding["encoded"]
                    or registry.getStringProperty("actorDefinitions") != binding["actorDefinitions"]
                    or registry.getStringProperty("questDefinitions") != binding["questDefinitions"]
                    or game_map.getNumericProperty("plugin_cityPhase") != binding["phase"]
                    or game_map.getStringProperty("plugin_cityCustodyDialogue") != binding["cursor"]
                    or game_map.getNumericProperty("plugin_cityCustodyTransitionCount") != binding["counter"]
                ):
                    return False
                actor = binding["actor"]
                if actor is not None:
                    registered = game_map.getObjectByName(binding["actorName"])
                    if (
                        actor.getGame() is not game
                        or actor.getMap() is not game_map
                        or actor.getName() != binding["actorName"]
                        or actor.getStringProperty("sourceCreature") != binding["sourceCreature"]
                        or actor.getStringProperty("sourceArea") != binding["sourceArea"]
                        or actor.getStringProperty("sourceDialogue") != binding["sourceDialogue"]
                        or actor.getNumericProperty("plugin_cityTalkCount") != binding["talkCount"]
                        or registered is not actor
                        and not (registered is None and actor in binding["detached"])
                        or not actor.isAlive()
                        and actor not in binding["detached"]
                    ):
                        return False
                if (
                    binding["gameClass"].getMapBindingEpoch(game) != binding["mapEpoch"]
                    or binding["mapClass"].getAssignedPlayer(game_map) is not player
                ):
                    return False
            return self.custodyNativeSnapshotCurrent(binding)

        def requireCustodyBinding(self, binding):
            if not self.custodyBindingCurrent(binding):
                raise self.CustodyBindingChanged("Custody conversation binding changed")

        def bindCustodyActor(self, binding, actor):
            self.requireCustodyBinding(binding)
            if not isinstance(actor, CCreature):
                raise self.CustodyBindingChanged("Custody needs an actual creature")
            name = actor.getName()
            properties = {
                key: actor.getStringProperty(key) for key in ("sourceCreature", "sourceArea", "sourceDialogue")
            }
            talk_count, alive = actor.getNumericProperty("plugin_cityTalkCount"), actor.isAlive()
            self.requireCustodyBinding(binding)
            if (
                not alive
                or actor.getGame() is not binding["game"].resolve()
                or binding["map"].getObjectByName(name) is not actor
            ):
                raise self.CustodyBindingChanged("Custody speaker is no longer registered")
            binding.update(actor=actor, actorName=name, talkCount=talk_count, **properties)
            self.requireCustodyBinding(binding)

        def custodyCall(self, scope, target, method, *args, **kwargs):
            self.requireCustodyBinding(scope)
            bound = getattr(target, method)
            self.requireCustodyBinding(scope)
            if isinstance(target, CCreature):
                name = target.getName()
                registered = scope["map"].getObjectByName(name)
                if (
                    target.getGame() is not scope["game"].resolve()
                    or registered is not target
                    and not (registered is None and target in scope["detached"])
                ):
                    raise self.CustodyBindingChanged("Custody action target was replaced")
                self.requireCustodyBinding(scope)
            result = bound(*args, **kwargs)
            if target is scope["actor"] and method == "setNumericProperty" and args[0] == "plugin_cityTalkCount":
                scope["talkCount"] = args[1]
            if target is scope["map"] and method == "setStringProperty" and args[0] == "plugin_cityCustodyDialogue":
                scope["cursor"] = args[1]
            if (
                target is scope["map"]
                and method == "setNumericProperty"
                and args[0] == "plugin_cityCustodyTransitionCount"
            ):
                scope["counter"] = args[1]
            self.requireCustodyBinding(scope)
            return result

        def custodyRead(self, binding, target, key, default):
            encoded = self.custodyCall(binding, target, "getStringProperty", key)
            result = decodeData(encoded or json.dumps(default))
            self.requireCustodyBinding(binding)
            return result

        def custodyWrite(self, binding, target, key, value):
            encoded = CITY_JSON_PREFIX + json.dumps(value, separators=(",", ":"))
            self.requireCustodyBinding(binding)
            self.custodyCall(binding, target, "setStringProperty", key, encoded)

        def custodyParty(self, binding):
            roster = self.custodyRead(binding, binding["clock"], "plugin_cityRoster", [])
            party = [
                self.custodyCall(binding, binding["clock"], "getObjectProperty", "plugin_cityCompanion_" + name)
                for name in roster
            ]
            self.requireCustodyBinding(binding)
            return party

        def allowCustodyDetach(self, binding, actor):
            self.requireCustodyBinding(binding)
            name = actor.getName()
            registered = binding["map"].getObjectByName(name)
            retained = optionalObjectProperty(self, "plugin_cityActor_" + name)
            departed = actor.getBoolProperty("plugin_cityDeparted")
            self.requireCustodyBinding(binding)
            if registered is not actor and not (registered is None and retained is actor and departed):
                raise self.CustodyBindingChanged("Custody cannot retire a replaced actor")
            binding["detached"].add(actor)
            self.requireCustodyBinding(binding)

        def custodyPoint(self, binding, *point):
            self.requireCustodyBinding(binding)
            result = Coords(*point)
            self.requireCustodyBinding(binding)
            return result

        def custodyObserveArea(self, binding, area):
            game_map = binding["map"]
            visited = self.custodyRead(binding, game_map, "plugin_cityVisitedAreas", [])
            if area and area not in visited:
                visited.append(area)
                self.custodyWrite(binding, game_map, "plugin_cityVisitedAreas", visited)
            self.custodyCall(binding, game_map, "setStringProperty", "activeSimulationRegion", area)

        def custodyRequest(self, binding, operation, *args):
            self.requireCustodyBinding(binding)
            request = uiRequest(
                operation, binding["player"] if operation == "gui.checkQuests" else binding["game"], *args
            )
            self.requireCustodyBinding(binding)
            return request

        def custodyNativeSnapshotCurrent(self, binding):
            """Only audited dynamic values and concrete identities bypass instance getter overrides."""
            native, native_map = binding["objectClass"], binding["mapClass"]
            game, game_map = binding["game"].resolve(), binding["map"]
            player, registry, actor = binding["player"], binding["clock"], binding["actor"]
            if (
                not game
                or binding["gameClass"].getMapBindingEpoch(game) != binding["mapEpoch"]
                or native_map.getAssignedPlayer(game_map) is not player
            ):
                return False
            strings = [
                (self, "custodyDefinitions", binding["encoded"]),
                (registry, "actorDefinitions", binding["actorDefinitions"]),
                (registry, "questDefinitions", binding["questDefinitions"]),
                (game_map, "plugin_cityCustodyDialogue", binding["cursor"]),
            ]
            numbers = [
                (game_map, "plugin_cityPhase", binding["phase"]),
                (game_map, "plugin_cityCustodyTransitionCount", binding["counter"]),
            ]
            if actor is not None:
                strings.extend((actor, key, binding[key]) for key in ("sourceCreature", "sourceArea", "sourceDialogue"))
                numbers.append((actor, "plugin_cityTalkCount", binding["talkCount"]))
            if any(native.getStringProperty(target, key) != value for target, key, value in strings):
                return False
            if any(native.getNumericProperty(target, key) != value for target, key, value in numbers):
                return False
            if (
                not game
                or game.getMap() is not game_map
                or game.getContext() is not binding["context"]
                or not binding["context"].isTransitionGenerationCurrent(binding["generation"])
                or native.getGame(self) is not game
                or native.getMap(self) is not game_map
                or native.getName(self) != "cityCustody"
                or native_map.getObjectByName(game_map, "cityCustody") is not self
                or native.getGame(registry) is not game
                or native.getMap(registry) is not game_map
                or native.getName(registry) != "cityClock"
                or native_map.getObjectByName(game_map, "cityClock") is not registry
                or native.getGame(player) is not game
                or native.getMap(player) is not game_map
                or native.getName(player) != "player"
                or native_map.getObjectByName(game_map, "player") is not player
                or native_map.getAssignedPlayer(game_map) is not player
                or not CCreature.isAlive(player)
            ):
                return False
            if actor is not None:
                registered = native_map.getObjectByName(game_map, binding["actorName"])
                if (
                    native.getGame(actor) is not game
                    or native.getMap(actor) is not game_map
                    or native.getName(actor) != binding["actorName"]
                    or registered is not actor
                    and not (registered is None and actor in binding["detached"])
                    or not CCreature.isAlive(actor)
                    and actor not in binding["detached"]
                ):
                    return False
            return (
                binding["gameClass"].getMapBindingEpoch(game) == binding["mapEpoch"]
                and native_map.getAssignedPlayer(game_map) is player
            )

        def stageCustodyActor(self, binding, actor, row):
            self.requireCustodyBinding(binding)
            native = binding["objectClass"]
            if (
                not isinstance(actor, CCreature)
                or isinstance(actor, binding["playerClass"])
                or actor in binding["stagedActors"]
                or native.getTypeId(actor) != row["id"]
                or not row.get("custodyRole")
            ):
                raise self.CustodyBindingChanged("Custody factory returned an unexpected actor")
            staged = {
                "id": row["id"],
                "name": native.getName(actor),
                "row": dict(row),
                "source": {
                    key: native.getStringProperty(actor, key)
                    for key in ("sourceCreature", "sourceArea", "sourceDialogue")
                },
            }
            if not staged["source"]["sourceCreature"] or not staged["source"]["sourceArea"]:
                raise self.CustodyBindingChanged("Custody factory actor has no source identity")
            binding["stagedActors"][actor] = staged
            self.requireCustodyStage(binding, actor)

        def requireCustodyStage(self, binding, actor, registered=False):
            self.requireCustodyBinding(binding)
            native, native_map = binding["objectClass"], binding["mapClass"]
            staged = binding["stagedActors"].get(actor)
            if staged is None:
                raise self.CustodyBindingChanged("Custody actor has no construction authority")
            rows = decodeData(binding["actorDefinitions"] or "[]")
            matching = [row for row in rows if row.get("id") == staged["id"]]
            expected = actor if registered else None
            if (
                matching != [staged["row"]]
                or native.getGame(actor) is not binding["game"].resolve()
                or native.getTypeId(actor) != staged["id"]
                or native.getName(actor) != staged["name"]
                or native.getMap(actor) is not binding["map"]
                or not CCreature.isAlive(actor)
                or native_map.getObjectByName(binding["map"], staged["id"]) is not expected
                or native_map.getObjectByName(binding["map"], staged["name"]) is not expected
                or any(native.getStringProperty(actor, key) != value for key, value in staged["source"].items())
            ):
                raise self.CustodyBindingChanged("Custody construction binding changed")

        def placeCustodyActor(self, binding, actor, method, key, value):
            self.requireCustodyStage(binding, actor)
            staged = binding["stagedActors"][actor]
            allowed = {("setStringProperty", "name"): staged["id"]}
            allowed.update(
                {
                    ("setNumericProperty", key): staged["row"][axis]
                    for key, axis in (("posx", "x"), ("posy", "y"), ("posz", "z"))
                }
            )
            if (method, key) not in allowed or value != allowed[(method, key)]:
                raise self.CustodyBindingChanged("Custody construction permits only authored placement")
            bound = getattr(actor, method)
            self.requireCustodyStage(binding, actor)
            bound(key, value)
            if key == "name":
                staged["name"] = value
            self.requireCustodyStage(binding, actor)

    @register(context)
    @mapQuest("baldursGate")
    class BaldursGateQuest(CQuest):
        def isCompleted(self):
            return stage(self, self.getStringProperty("questKey")) in ("completed", "failed", "refused")

        def getObjective(self):
            source_row = clock(self).poisonQuestPresentation(self.getStringProperty("questKey"))
            if source_row is not None:
                return source_row["objective"]
            row = quest(self, self.getStringProperty("questKey")) or {}
            return row.get("title", self.getStringProperty("description")) + ": " + stage(self, row.get("id", ""))

        def getReward(self):
            source_row = clock(self).poisonQuestPresentation(self.getStringProperty("questKey"))
            if source_row is not None:
                return source_row["reward"]
            return self.getStringProperty("rewardText") or "The recorded choice determines the reward."

        def getHint(self):
            source_row = clock(self).poisonQuestPresentation(self.getStringProperty("questKey"))
            if source_row is not None and source_row.get("hint"):
                return source_row["hint"]
            return self.getStringProperty("hint") or "Follow the named people, source items and city journal."

        def onComplete(self):
            pass

    @register(context)
    class BaldursGateStart(CEvent):
        @resumableHook
        def onEnter(self, event):
            if not event or not event.getCause() or not event.getCause().isPlayer():
                return
            clock(self).ensureCitySourceKillXp()
            if claim_once(world(self), "plugin_cityInitialized"):
                world(self).setBoolProperty("plugin_cityFlag_custodyHearing", False)
                player = hero(self)
                player.addExp(10000)
                player.addGold(1000)
                world(self).setNumericProperty("plugin_cityStartingExpGrant", 10000)
                world(self).setNumericProperty("plugin_cityStartingGoldGrant", 1000)
                world(self).setNumericProperty("plugin_cityPhase", 5)
                world(self).setNumericProperty("plugin_cityReputation", 10)
                world(self).setNumericProperty("plugin_cityHour", 8)
                world(self).setBoolProperty("plugin_cityFixedLoot", True)
                stats = player.getStats()
                inventory = [
                    {
                        "name": item.getName(),
                        "typeId": item.getTypeId(),
                        "sourceItem": sourceCode(item),
                        "quantity": quantity(item),
                        "charges": read(item, "plugin_cityCharges", [0, 0, 0]),
                        "sourceFlags": item.getNumericProperty("plugin_citySourceFlags"),
                        "expiration": item.getNumericProperty("plugin_cityExpiration"),
                    }
                    for item in possessions(player)
                ]
                write(
                    world(self),
                    "plugin_cityStartingProfile",
                    {
                        "playerName": player.getName(),
                        "typeId": player.getTypeId(),
                        "classId": player.getPlayerClassId(),
                        "level": player.getNumericProperty("level"),
                        "stats": {
                            name: stats.getNumericProperty(name)
                            for name in ("strength", "agility", "stamina", "intelligence")
                        },
                        "gold": player.getGold(),
                        "experience": player.getNumericProperty("exp"),
                        "items": inventory,
                        "equipped": {slot: item.getName() for slot, item in player.getEquipped().items() if item},
                        "history": {},
                        "historyFrozen": False,
                    },
                )
                if not player.getStringProperty("affiliation"):
                    player.setStringProperty("affiliation", "cityParty")
                clock(self).initializeActors()
                if clock(self).getBoolProperty("plugin_cityPoisonSourceEnabled"):
                    clock(self).poisonInitializeSource()
                observeArea(self, currentArea(self))
                clock(self).applySchedules()
                yield uiRequest(
                    "showReader",
                    flowGame(self.getGame()),
                    "Baldur's Gate",
                    "Chapter 5. You enter Baldur's Gate with 1000 gold and 10000 experience added. "
                    "The city clock advances one hour per 50 turns. Quests, belongings and choices persist. "
                    "Use the history conversation before pursuing branches that depend on earlier journeys.",
                )
            yield uiRequest("gui.showDialog", self.getGame().createObject("cityStartDialog"))

    @register(context)
    class BaldursGatePortal(CBuilding):
        def target(self):
            return Coords(
                self.getNumericProperty("targetX"),
                self.getNumericProperty("targetY"),
                self.getNumericProperty("targetZ"),
            )

        def usable(self):
            if world(self).getStringProperty("plugin_cityCustodyState") == "hearing":
                return False
            if not self.getStringProperty("destinationArea") or not hasattr(self, "targetX"):
                return False
            phase = world(self).getNumericProperty("plugin_cityPhase") or 5
            minimum = self.getNumericProperty("phaseMin") or 5
            maximum = self.getNumericProperty("phaseMax") or 7
            required = self.getStringProperty("requiredFlag")
            if required and not world(self).getBoolProperty("plugin_cityFlag_" + required):
                return False
            if self.getStringProperty("destinationArea") == "AR0108":
                if phase == 5 and not world(self).getBoolProperty("plugin_cityFlag_palaceCourtyardOpen"):
                    return False
                if phase == 7 and not hasItems(hero(self), {"item": "MISC78", "count": 1}):
                    return False
            return minimum <= phase <= maximum and not self.getBoolProperty("locked")

        def publishEdge(self):
            game_map = self.getMap()
            if not game_map:
                return
            if not self.usable() or not game_map.canStep(self.target()):
                game_map.unregisterNavigationEdgesForObject(self.getName())
                return
            if not game_map.hasNavigationEdge(self.getCoords(), self.target(), self.getName()):
                game_map.unregisterNavigationEdgesForObject(self.getName())
                game_map.registerNavigationEdge(self.getCoords(), self.target(), True, False, 1, self.getName())

        def onCreate(self, event):
            self.publishEdge()

        def onTurn(self, event):
            self.publishEdge()

        def onDestroy(self, event):
            self.getMap().unregisterNavigationEdgesForObject(self.getName())

        @resumableHook
        def onEnter(self, event):
            player = event.getCause() if event else None
            if not player or not player.isPlayer():
                return
            if player.getStringProperty("plugin_cityPortalGuard") == self.getName():
                player.setStringProperty("plugin_cityPortalGuard", "")
                return
            if not self.usable():
                if self.getBoolProperty("locked"):
                    yield uiRequest("gui.showDialog", self.getGame().createObject(self.getName() + "Dialog"))
                else:
                    notify(self, "This route leaves the selected city. Its excursion must be chosen explicitly.")
                return
            target = self.target()
            arrival = firstMatch(
                (
                    obj
                    for obj in world(self).getObjects()
                    if isinstance(obj, BaldursGatePortal) and obj.getCoords() == target
                ),
                None,
            )
            player.setStringProperty("plugin_cityPortalGuard", arrival.getName() if arrival else "")
            observeArea(self, self.getStringProperty("destinationArea"))
            yield uiRequest("gui.moveTo", player, target.x, target.y, target.z)
            for follower in companions(self):
                if follower.isAlive() and world(self).getObjectByName(follower.getName()):
                    follower.setStringProperty("simulationRegion", self.getStringProperty("destinationArea"))
                    yield uiRequest("gui.moveTo", follower, target.x, target.y, target.z)
            clock(self).applySchedules()

    @register(context)
    class BaldursGateContainer(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if event and event.getCause() and event.getCause().isPlayer():
                yield uiRequest("gui.showDialog", self.getGame().createObject(self.getName() + "Dialog"))

    @register(context)
    class BaldursGateDoor(BaldursGateContainer):
        pass

    @register(context)
    class BaldursGateSwitch(BaldursGateContainer):
        pass

    @register(context)
    class BaldursGateRegion(CBuilding):
        @resumableHook
        def onEnter(self, event):
            if event and event.getCause() and event.getCause().isPlayer():
                yield from clock(self).observeRegionsFlow()

    @register(context)
    class BaldursGateDialog(CDialog):
        def actor(self):
            return world(self).getObjectByName(self.getStringProperty("actorId"))

        def canInteract(self, resume_custody=False):
            actor, player = self.actor(), hero(self)
            if (
                not actor
                or world(self).getBoolProperty("plugin_cityFlag_cityCompleted")
                or world(self).getBoolProperty("plugin_cityFlag_poisonFatal")
            ):
                return False
            if isinstance(actor, CCreature) and not actor.isAlive():
                return False
            if world(self).getStringProperty("plugin_cityCustodyState") == "hearing":
                cursor = read(world(self), "plugin_cityCustodyDialogue", {})
                return bool(
                    resume_custody and cursor.get("actorId") == actor.getName() and currentArea(self) == "AR0607"
                )
            phase = world(self).getNumericProperty("plugin_cityPhase") or 5
            if not (actor.getNumericProperty("phaseMin") or 5) <= phase <= (actor.getNumericProperty("phaseMax") or 7):
                return False
            here, there = player.getCoords(), actor.getCoords()
            return here.z == there.z and abs(here.x - there.x) + abs(here.y - there.y) <= 1

        def canAcceptQuest(self, key):
            if clock(self).getBoolProperty("plugin_cityPoisonSourceEnabled") and key in (
                "marekPoison",
                "lothanderGeas",
                "jalanthaBook",
                "chanthalasTome",
                "divinerPoison",
            ):
                return False
            row = quest(self, key)
            if not row or not self.canInteract() or stage(self, key) != "notStarted":
                return False
            if self.actor().getBoolProperty("plugin_cityPetrified"):
                return False
            if not any(matches(self.actor(), selector) for selector in row["givers"]):
                return False
            phase = world(self).getNumericProperty("plugin_cityPhase") or 5
            return row.get("phase", 5) <= phase <= row.get("phaseMax", 7) and applyCondition(
                self, row.get("acceptConditions", {})
            )

        def acceptQuest(self, key):
            if not self.canAcceptQuest(key):
                return False
            row = quest(self, key)
            freezeHistory(self)
            seedRewardStock(self, self.actor())
            if not applyEffects(self, row.get("acceptEffects", {}), self.actor()):
                return False
            setStage(self, key, "active")
            hero(self).addQuest(questId(key))
            clock(self).spawnActors()
            clock(self).applySchedules()
            if row.get("deadlineHours"):
                deadlines = read(world(self), "plugin_cityDeadlines", {})
                deadlines[key] = world(self).getNumericProperty("plugin_cityTicks") + row["deadlineHours"] * 50
                write(world(self), "plugin_cityDeadlines", deadlines)
            notify(self, row["title"] + " is recorded in your journal.")
            return True

        def canQuestOutcome(self, key, outcome_key):
            if clock(self).getBoolProperty("plugin_cityPoisonSourceEnabled") and key in (
                "marekPoison",
                "lothanderGeas",
                "jalanthaBook",
                "chanthalasTome",
                "divinerPoison",
            ):
                return False
            row = quest(self, key)
            if not row or not self.canInteract() or stage(self, key) != "active":
                return False
            if self.actor().getBoolProperty("plugin_cityPetrified"):
                return False
            outcome = firstMatch((entry for entry in row["outcomes"] if entry["id"] == outcome_key), None)
            if not outcome or not any(matches(self.actor(), selector) for selector in outcome.get("at", row["givers"])):
                return False
            return applyCondition(self, outcome.get("conditions", {})) and not world(self).getBoolProperty(
                "plugin_cityOutcome_" + key + "_" + outcome_key
            )

        @resumableHook
        def performQuestOutcome(self, key, outcome_key):
            if not self.canQuestOutcome(key, outcome_key):
                return False
            row = quest(self, key)
            outcome = firstMatch(entry for entry in row["outcomes"] if entry["id"] == outcome_key)
            if not applyEffects(self, outcome.get("effects", {}), self.actor()):
                return False
            if not row.get("repeatable"):
                world(self).setBoolProperty("plugin_cityOutcome_" + key + "_" + outcome_key, True)
                if outcome.get("terminal", True):
                    setStage(self, key, "completed")
            yield uiRequest("gui.checkQuests", hero(self))
            clock(self).spawnActors()
            clock(self).applySchedules()
            notify(self, "Your choice is recorded: " + outcome["text"])
            if outcome.get("effects", {}).get("finale"):
                yield uiRequest(
                    "showReader",
                    flowGame(self.getGame()),
                    "Baldur's Gate",
                    "Sarevok has fallen in the Temple of Bhaal. The city adventure is complete. "
                    "Your journal, companions, possessions and choices remain in this saved city.",
                )
            return True

        @resumableHook
        def talk(self):
            if (
                clock(self).getBoolProperty("plugin_cityPoisonSourceEnabled")
                and self.canInteract()
                and self.actor().getBoolProperty("plugin_cityPoisonManaged")
            ):
                yield from clock(self).poisonDialogueFlow(self.actor())
                return
            if not self.canInteract(resume_custody=True):
                return
            actor = self.actor()
            coordinator = custody(self)
            if coordinator and actor.getStringProperty("sourceDialogue") in coordinator.data().get("dialogues", {}):
                yield from coordinator.conversationFlow(actor)
                return
            if actor.getName() != "cityStart":
                freezeHistory(self)
            if actor.getBoolProperty("plugin_cityPetrified"):
                notify(self, "The stone figure cannot answer you.")
                return
            talked = read(world(self), "plugin_cityTalked", {})
            talked[actor.getName()] = actorRecord(actor)
            write(world(self), "plugin_cityTalked", talked)
            count = actor.getNumericProperty("plugin_cityTalkCount") + 1
            actor.setNumericProperty("plugin_cityTalkCount", count)
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                actor.getStringProperty("label") or "City",
                self.getStringProperty("talkText")
                or "Keep your purse close in Baldur's Gate. The inns offer a bed and city news; "
                "the Flaming Fist keeps watch, and the Iron Throne's business troubles the streets.",
            )

        @resumableHook
        def attack(self):
            if not self.canInteract() or not isinstance(self.actor(), CCreature):
                return False
            if custody(self) and self.actor().getStringProperty("sourceCreature") == "NEB":
                custody(self).setGlobal("AttackNEB", "AR0607", 1)
                yield from custody(self).conversationFlow(self.actor(), "NEB", 17)
                return True
            freezeHistory(self)
            self.actor().setBoolProperty("npc", False)
            self.actor().setStringProperty("affiliation", "cityHostile")
            crime(self, self.actor())
            return True

        @resumableHook
        def inspect(self):
            return (yield from self.showInventoryFlow())

        @resumableHook
        def steal(self):
            return (yield from self.pickPocketFlow())

        @resumableHook
        def showInventory(self):
            if not self.canInteract() or not isinstance(self.actor(), CCreature):
                return
            rows = [
                f"{item.getStringProperty('label') or sourceCode(item)} x{quantity(item)}"
                for item in possessions(self.actor())
            ]
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                self.actor().getStringProperty("label"),
                "\n".join(rows) or "No carried belongings.",
            )

        def canPickpocket(self):
            return (
                self.canInteract()
                and isinstance(self.actor(), CCreature)
                and bool(
                    [
                        item
                        for item in self.actor().getItems()
                        if not item.getBoolProperty("plugin_cityUnstealable")
                        and not item.getBoolProperty("plugin_cityUndroppable")
                    ]
                )
            )

        @resumableHook
        def pickPocket(self):
            if not self.canPickpocket():
                return False
            owner = self.actor()
            available = [
                item
                for item in owner.getItems()
                if not item.getBoolProperty("plugin_cityUnstealable")
                and not item.getBoolProperty("plugin_cityUndroppable")
            ]
            rows = [
                {"id": item.getName(), "label": item.getStringProperty("label") or sourceCode(item)}
                for item in available
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Pick a pocket", rows, "Attempt theft")
            item = firstMatch((item for item in available if item.getName() == selected), None)
            if not item or not self.canInteract() or item not in owner.getItems():
                return False
            freezeHistory(self)
            threshold = owner.getNumericProperty("plugin_cityTheftAgility") or 16
            if hero(self).getStats().getNumericProperty("agility") < threshold or owner.getBoolProperty(
                "plugin_cityUnavoidableDetection"
            ):
                crime(self, owner)
                return False
            if clock(self).getBoolProperty("plugin_cityPoisonSourceEnabled") and sourceCode(item) == "POTN47":
                clock(self).transferPoisonSourceItem(owner, hero(self), item)
            else:
                owner.removeQuestItem(lambda candidate: candidate == item)
                hero(self).addItem(item)
            item.setBoolProperty("plugin_cityStolen", True)
            world(self).setBoolProperty("plugin_cityTheft_" + owner.getName(), True)
            return True

        def canUnlock(self):
            actor = self.actor()
            return bool(
                self.canInteract()
                and actor.getBoolProperty("locked")
                and not actor.getBoolProperty("magicallyLocked")
                and not actor.getBoolProperty("disabled")
                and not actor.getBoolProperty("forbidPicking")
                and hero(self).getStats().getNumericProperty("agility")
                >= (actor.getNumericProperty("lockAgility") or 12)
            )

        def unlock(self):
            if not self.canUnlock():
                return False
            self.actor().setBoolProperty("locked", False)
            self.actor().setBoolProperty("plugin_cityPicked", True)
            if isinstance(self.actor(), BaldursGatePortal):
                self.actor().publishEdge()
            return True

        def unlockContainer(self):
            return self.unlock()

        def canForce(self):
            actor = self.actor()
            return bool(
                self.canInteract()
                and actor.getBoolProperty("locked")
                and not actor.getBoolProperty("magicallyLocked")
                and not actor.getBoolProperty("disabled")
                and not actor.getBoolProperty("forbidForcing")
                and hero(self).getStats().getNumericProperty("strength")
                >= (actor.getNumericProperty("forceStrength") or 12)
            )

        def force(self):
            if not self.canForce():
                return False
            self.actor().setBoolProperty("locked", False)
            self.actor().setBoolProperty("plugin_cityForced", True)
            if self.actor().getStringProperty("sourceOwner") or self.actor().getBoolProperty("owned"):
                crime(self)
            if isinstance(self.actor(), BaldursGatePortal):
                self.actor().publishEdge()
            return True

        def forceContainer(self):
            return self.force()

        def useKey(self):
            if not self.canInteract():
                return False
            key = (
                self.actor().getStringProperty("lockKey")
                or self.actor().getStringProperty("sourceKey")
                or self.actor().getStringProperty("key")
            )
            if not key or not hasItems(hero(self), {"item": key, "count": 1}):
                return False
            self.actor().setBoolProperty("locked", False)
            if isinstance(self.actor(), BaldursGatePortal):
                self.actor().publishEdge()
            return True

        def canDisarm(self):
            return bool(
                self.canInteract()
                and (
                    not isinstance(self.actor(), BaldursGateRegion)
                    or self.actor().getBoolProperty("regionEffectApproved")
                )
                and self.actor().getBoolProperty("trapped")
                and not self.actor().getBoolProperty("plugin_cityUndisarmable")
                and hero(self).getStats().getNumericProperty("agility")
                >= (
                    18
                    if self.actor().getNumericProperty("sourceTrapRemoval") >= 80
                    else 16 if self.actor().getNumericProperty("sourceTrapRemoval") >= 40 else 12
                )
            )

        def disarm(self):
            if not self.canDisarm():
                return False
            self.actor().setBoolProperty("trapped", False)
            self.actor().setBoolProperty("plugin_cityDisarmed", True)
            return True

        def canOpen(self):
            return bool(
                self.canInteract()
                and not self.actor().getBoolProperty("locked")
                and not self.actor().getBoolProperty("disabled")
                and not self.actor().getBoolProperty("looted")
            )

        def open(self):
            if not self.canOpen():
                return False
            freezeHistory(self)
            owner = self.actor()
            if owner.getBoolProperty("trapped"):
                owner.setBoolProperty("trapped", False)
                hero(self).hurt(owner.getNumericProperty("plugin_cityNativeTrapDamage") or 10)
                owner.setBoolProperty("plugin_cityTrapTriggered", True)
                if not hero(self).isAlive():
                    world(self).removeObject(hero(self))
                    return False
            if isinstance(owner, BaldursGateDoor) or isinstance(owner, BaldursGatePortal):
                owner.setBoolProperty("open", True)
                owner.setBoolProperty("canStep", True)
                return True
            for row in read(owner, "contents", []):
                if row.get("item") == "MISC07":
                    hero(self).addGold(max(1, row.get("quantity", (row.get("charges") or [1])[0])))
                else:
                    item = makeSourceItem(self, row)
                    hero(self).addItem(item)
            owner.setBoolProperty("looted", True)
            write(owner, "contents", [])
            if owner.getStringProperty("sourceOwner") or owner.getBoolProperty("owned"):
                threshold = owner.getNumericProperty("plugin_cityTheftAgility") or 16
                if hero(self).getStats().getNumericProperty("agility") < threshold or owner.getBoolProperty(
                    "alwaysGuard"
                ):
                    crime(self)
            return True

        def openContainer(self):
            return self.open()

        def stealContainer(self):
            return self.open()

        def close(self):
            if not self.canInteract() or not isinstance(self.actor(), (BaldursGateDoor, BaldursGatePortal)):
                return False
            if self.actor().getBoolProperty("forbidClosing"):
                return False
            self.actor().setBoolProperty("open", False)
            return True

        def canTamokoFirstMeeting(self):
            return (
                self.canInteract()
                and matches(self.actor(), {"creature": "TAMOKO", "area": "AR0800"})
                and (world(self).getNumericProperty("plugin_cityPhase") or 5) == 7
                and not world(self).getBoolProperty("plugin_cityFlag_tamokoMove1")
            )

        @resumableHook
        def finishTamokoFirstMeeting(self, listen):
            if not self.canTamokoFirstMeeting():
                return False
            world(self).setStringProperty("plugin_cityTamokoFirstChoice", "listen" if listen else "refuse")
            world(self).setBoolProperty("plugin_cityFlag_tamokoMove1", True)
            world(self).setNumericProperty("plugin_cityTamokoMove", 1)
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                "Tamoko",
                (
                    "Tamoko asks you to meet her near the Flaming Fist headquarters. "
                    "She knows more about Sarevok than she is ready to reveal here."
                    if listen
                    else "You end the conversation. Tamoko leaves the eastern streets."
                ),
            )
            clock(self).applySchedules()
            return True

        @resumableHook
        def hearTamokoWarning(self):
            return (yield from self.finishTamokoFirstMeetingFlow(True))

        @resumableHook
        def declineTamokoFirstMeeting(self):
            return (yield from self.finishTamokoFirstMeetingFlow(False))

        def canTamokoSecondMeeting(self):
            return (
                self.canInteract()
                and matches(self.actor(), {"creature": "TAMOKO", "area": "AR1100"})
                and world(self).getBoolProperty("plugin_cityFlag_tamokoMove1")
                and not world(self).getBoolProperty("plugin_cityFlag_tamokoMove2")
            )

        @resumableHook
        def discussTamokoRequest(self):
            if not self.canTamokoSecondMeeting():
                return False
            rescued = world(self).getBoolProperty("plugin_cityFlag_eltanCarried") or world(self).getBoolProperty(
                "plugin_cityFlag_eltanSafe"
            )
            world(self).setStringProperty("plugin_cityTamokoEltanDiscussion", "rescued" if rescued else "notRescued")
            world(self).setBoolProperty("plugin_cityFlag_tamokoDiscussed", True)
            world(self).setNumericProperty("plugin_cityTamokoMove", 3)
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                "Tamoko",
                ("You tell Tamoko that Eltan has been rescued. " if rescued else "Eltan remains in danger. ")
                + "She wants Cythandria, Sarevok's other lover, removed from his side. "
                "She asks you to spare Sarevok's life.",
            )
            return True

        def canFinishTamokoSecondMeeting(self):
            return self.canTamokoSecondMeeting() and world(self).getBoolProperty("plugin_cityFlag_tamokoDiscussed")

        @resumableHook
        def finishTamokoSecondMeeting(self, accept):
            if not self.canFinishTamokoSecondMeeting():
                return False
            if accept and stage(self, "cythandriaDiary") == "notStarted" and not self.acceptQuest("cythandriaDiary"):
                return False
            world(self).setStringProperty("plugin_cityTamokoSecondChoice", "accept" if accept else "refuse")
            world(self).setBoolProperty("plugin_cityFlag_tamokoMove2", True)
            world(self).setNumericProperty("plugin_cityTamokoMove", 2)
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                "Tamoko",
                (
                    "You agree to deal with Cythandria. Tamoko leaves to follow Sarevok."
                    if accept
                    else "You refuse her request. Tamoko leaves to follow Sarevok."
                ),
            )
            clock(self).applySchedules()
            return True

        @resumableHook
        def acceptTamokoRequest(self):
            return (yield from self.finishTamokoSecondMeetingFlow(True))

        @resumableHook
        def refuseTamokoRequest(self):
            return (yield from self.finishTamokoSecondMeetingFlow(False))

        def canHelpAlora(self):
            if not self.canInteract() or self.actor().getStringProperty("sourceCreature") != "ALORA":
                return False
            minute = (480 + world(self).getNumericProperty("plugin_cityTicks") * 6 // 5) % 1440
            return (
                (minute >= 1290 or minute < 210)
                and social(self) >= 7
                and self.actor().getNumericProperty("plugin_cityTalkCount") >= 1
                and not self.actor().getBoolProperty("plugin_cityLeftForever")
            )

        def helpAloraLookout(self):
            if not self.canHelpAlora():
                return False
            self.actor().setBoolProperty("plugin_cityAloraLoots", True)
            notify(self, "You agree to keep watch while Alora searches the museum.")
            return True

        def canRestoreStatue(self):
            return (
                self.canInteract()
                and self.actor().getBoolProperty("plugin_cityPetrified")
                and hasItems(hero(self), {"item": "SCRLPET"})
            )

        def restoreStatue(self):
            if not self.canRestoreStatue():
                return False
            actor = self.actor()
            if not takeItems(hero(self), {"item": "SCRLPET"}):
                return False
            actor.setBoolProperty("plugin_cityPetrified", False)
            actor.setStringProperty("label", actor.getStringProperty("sourceCreature").capitalize())
            return True

        def requestJalanthaAudience(self):
            if (
                not self.canInteract()
                or self.actor().getStringProperty("sourceCreature") != "PUMBERL"
                or self.actor().getStringProperty("sourceArea") != "AR0609"
            ):
                return False
            if world(self).getBoolProperty("plugin_cityFlag_jalanthaSummoned"):
                return True
            if hero(self).getGold() < 50:
                notify(self, "The priestess asks for50gold before granting an audience.")
                return False
            hero(self).addGold(-50)
            world(self).setBoolProperty("plugin_cityFlag_jalanthaSummoned", True)
            clock(self).spawnActors()
            return True

        def recruit(self):
            actor = self.actor()
            if not self.canInteract() or not isinstance(actor, CCreature):
                return False
            code = actor.getStringProperty("sourceCreature")
            if not actor.getBoolProperty("plugin_cityRecruitable") and not code.startswith(
                ("ALORA", "SKIE", "TIAX", "QUAYLE", "ELDOTH")
            ):
                return False
            roster = read(clock(self), "plugin_cityRoster", [])
            if actor.getName() in roster:
                return True
            if len(roster) >= 5 or actor.getBoolProperty("plugin_cityLeftForever"):
                return False
            if social(self) < 7:
                actor.setBoolProperty("plugin_cityLeftForever", True)
                return False
            if code.startswith("ALORA"):
                minute = (480 + world(self).getNumericProperty("plugin_cityTicks") * 6 // 5) % 1440
                if (
                    not (minute >= 1290 or minute < 210)
                    or actor.getNumericProperty("plugin_cityTalkCount") < 3
                    or not actor.getBoolProperty("plugin_cityAloraLoots")
                ):
                    notify(
                        self, "Alora has more to say before she considers joining you. Find her at the museum at night."
                    )
                    return False
            here = actor.getCoords()
            if code.startswith("SKIE") and not any(
                member.isAlive()
                and member.getStringProperty("sourceCreature").startswith("ELDOTH")
                and member.getCoords().z == here.z
                and (member.getCoords().x - here.x) ** 2 + (member.getCoords().y - here.y) ** 2 <= 64
                for member in companions(self)
            ):
                crime(self)
                actor.setBoolProperty("plugin_cityLeftForever", True)
                return False
            freezeHistory(self)
            return joinCompanion(self, actor)

        def dismiss(self):
            if not self.canInteract():
                return False
            actor = self.actor()
            roster = read(clock(self), "plugin_cityRoster", [])
            if actor.getName() not in roster:
                return False
            roster.remove(actor.getName())
            write(clock(self), "plugin_cityRoster", roster)
            actor.setBoolProperty("npc", True)
            actor.setBoolProperty("alwaysSimulate", False)
            actor.setStringProperty("affiliation", actor.getStringProperty("plugin_cityOriginalAffiliation"))
            actor.setStringProperty("simulationRegion", currentArea(self))
            actor.setController(self.getGame().createObject("CController"))
            if (
                actor.getStringProperty("sourceCreature").startswith("TIAX")
                and world(self).getNumericProperty("plugin_cityReputation") >= 19
            ):
                actor.setBoolProperty("plugin_cityLeftForever", True)
            updateAlliedRoster(self)
            return True

        @resumableHook
        def inspectCompanion(self):
            return (yield from self.showInventoryFlow())

        @resumableHook
        def takeCompanionItem(self):
            if not self.canInteract() or self.actor() not in companions(self):
                return False
            owner = self.actor()
            available = [item for item in owner.getItems() if not item.getBoolProperty("plugin_cityUndroppable")]
            rows = [
                {"id": item.getName(), "label": item.getStringProperty("label") or sourceCode(item)}
                for item in available
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Companion belongings", rows, "Take")
            item = firstMatch((item for item in available if item.getName() == selected), None)
            if not item or item not in owner.getItems():
                return False
            owner.removeQuestItem(lambda candidate: candidate == item)
            hero(self).addItem(item)
            return True

        def recordHistory(self, key, value):
            if self.getStringProperty("actorId") != "cityStart" or not self.canInteract():
                return False
            if world(self).getBoolProperty("plugin_cityHistoryFrozen"):
                return False
            history = read(world(self), "plugin_cityHistory", {})
            if key in history:
                return False
            history[key] = value
            write(world(self), "plugin_cityHistory", history)
            if key == "aldeth":
                world(self).setBoolProperty("plugin_cityFlag_aldethSaved", value == "helped")
                clock(self).spawnActors()
            return True

        def canFinishHistoryChoices(self):
            return (
                self.getStringProperty("actorId") == "cityStart"
                and self.canInteract()
                and not world(self).getBoolProperty("plugin_cityHistoryFrozen")
            )

        def finishHistoryChoices(self):
            if not self.canFinishHistoryChoices():
                return False
            freezeHistory(self)
            return True

        def historyAldethHelped(self):
            return self.recordHistory("aldeth", "helped")

        def historyAldethKilled(self):
            return self.recordHistory("aldeth", "killed")

        def historyTenyaHelped(self):
            return self.recordHistory("tenya", "helped")

        def historyTenyaKilled(self):
            return self.recordHistory("tenya", "killed")

        def historyEldothJoined(self):
            if len(read(clock(self), "plugin_cityRoster", [])) >= 5:
                return False
            if not self.recordHistory("eldoth", "joined"):
                return False
            world(self).setBoolProperty("plugin_cityFlag_eldothJoined", True)
            clock(self).spawnActors()
            actor = firstMatch(
                (actor for actor in world(self).getObjects() if actor.getStringProperty("sourceCreature") == "ELDOTH"),
                None,
            )
            return bool(actor and joinCompanion(self, actor))

        def historyEldothAbsent(self):
            return self.recordHistory("eldoth", "absent")

        @resumableHook
        def encounterQuayle(self):
            if self.getStringProperty("actorId") != "cityStart" or not self.canInteract():
                return False
            world(self).setBoolProperty("plugin_cityFlag_quayleAtGate", True)
            clock(self).spawnActors()
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                "At Wyrm's Crossing",
                "You take a short walk to Wyrm's Crossing, where Quayle offers his company. "
                "You return to the city gate together; speak with him to decide whether he joins.",
            )
            return True

        def canExcursion(self, key):
            document = read(clock(self), "questDefinitions", {})
            row = firstMatch((entry for entry in document.get("excursions", []) if entry["id"] == key), None)
            return bool(
                row
                and self.canInteract()
                and stage(self, row["quest"]) == "active"
                and not world(self).getBoolProperty("plugin_cityExcursion_" + key)
                and any(matches(self.actor(), selector) for selector in row["at"])
            )

        @resumableHook
        def excursion(self, key, choice):
            if not self.canExcursion(key):
                return False
            document = read(clock(self), "questDefinitions", {})
            row = firstMatch(entry for entry in document["excursions"] if entry["id"] == key)
            outcome = firstMatch((entry for entry in row["choices"] if entry["id"] == choice), None)
            if not outcome:
                return False
            if outcome.get("pending"):
                yield uiRequest("showReader", flowGame(self.getGame()), row["title"], outcome["text"])
                return True
            if not applyCondition(self, outcome.get("conditions", {})):
                notify(self, "You cannot carry out that plan with your present skills.")
                return False
            clock(self).advanceTicks(row.get("hours", 24) * 50)
            if world(self).getBoolProperty("plugin_cityFlag_poisonFatal"):
                return False
            for item in outcome.get("items", []):
                hero(self).addItem(makeSourceItem(self, item))
            for name, value in outcome.get("flags", {}).items():
                world(self).setBoolProperty("plugin_cityFlag_" + name, value)
            if outcome.get("crime"):
                setStanding(self, outcome["crime"])
            world(self).setStringProperty("plugin_cityExcursionChoice_" + key, choice)
            world(self).setBoolProperty("plugin_cityExcursion_" + key, True)
            yield uiRequest("showReader", flowGame(self.getGame()), row["title"], outcome["text"])
            return True

        @resumableHook
        def cityInterlude(self):
            if not self.canInteract() or not world(self).getBoolProperty("plugin_cityFlag_cityInterludeReady"):
                return False
            world(self).setBoolProperty("plugin_cityFlag_interludeOffered", True)
            yield uiRequest(
                "showReader",
                flowGame(self.getGame()),
                "The Candlekeep interlude",
                "Eltan's evidence points back to Candlekeep. The separate Chapter 6 journey is represented "
                "as this explicit interlude. Return through its next choice when ready; no quest or battle "
                "in the persistent city is automatically resolved.",
            )
            return True

        def returnFromInterlude(self):
            if not self.canInteract() or not world(self).getBoolProperty("plugin_cityFlag_interludeOffered"):
                return False
            if world(self).getNumericProperty("plugin_cityPhase") == 7:
                return False
            world(self).setNumericProperty("plugin_cityPhase", 7)
            world(self).setBoolProperty("plugin_cityFlag_fugitive", True)
            clock(self).spawnActors()
            clock(self).applySchedules()
            return True

        def warnNarlen(self):
            hour = (8 + world(self).getNumericProperty("plugin_cityTicks") // 50) % 24
            if (
                self.canInteract()
                and stage(self, "narlenLookout") == "active"
                and matches(self.actor(), {"creature": "NARLEN", "area": "AR0300"})
                and (hour > 21 or hour < 4)
                and world(self).getBoolProperty("plugin_cityFlag_narlenLookoutStarted")
                and any(
                    actor.isAlive()
                    and actor.getStringProperty("sourceSpawnFact")
                    in ("AR0300.BCS#spawn5", "AR0300.BCS#spawn6", "AR0300.BCS#spawn7")
                    for actor in actors(self, {"creature": "WATCHM", "area": "AR0300"})
                    if isinstance(actor, CCreature)
                )
            ):
                world(self).setBoolProperty("plugin_cityFlag_narlenWarning", True)
                clock(self).applySchedules()
                return True
            return False

        def canBeginNarlenLookout(self):
            hour = (8 + world(self).getNumericProperty("plugin_cityTicks") // 50) % 24
            return (
                self.canInteract()
                and stage(self, "narlenLookout") == "active"
                and matches(self.actor(), {"creature": "NARLEN", "area": "AR0300"})
                and (hour > 21 or hour < 4)
                and applyCondition(self, {"thiefInParty": True})
                and not world(self).getBoolProperty("plugin_cityFlag_narlenLookoutStarted")
            )

        def beginNarlenLookout(self):
            if not self.canBeginNarlenLookout():
                return False
            freezeHistory(self)
            world(self).setBoolProperty("plugin_cityFlag_narlenLookoutStarted", True)
            world(self).setNumericProperty(
                "plugin_cityNarlenOfficerAt", world(self).getNumericProperty("plugin_cityTicks") + 20
            )
            return True

        def waitHour(self):
            if not self.canInteract():
                return False
            freezeHistory(self)
            clock(self).advanceTicks(50)
            return True

        def pressPalaceSwitch(self, index):
            if not self.canInteract() or self.actor().getNumericProperty("palaceSwitch") != index:
                return False
            world(self).setBoolProperty("plugin_cityFlag_palaceSwitch" + str(index), True)
            if all(world(self).getBoolProperty("plugin_cityFlag_palaceSwitch" + str(number)) for number in (1, 2)):
                world(self).setBoolProperty("plugin_cityFlag_palaceCourtyardOpen", True)
                for obj in world(self).getObjects():
                    if isinstance(obj, BaldursGatePortal) and obj.getStringProperty("destinationArea") == "AR0108":
                        obj.publishEdge()
            return True

        def pressPalaceSwitchOne(self):
            return self.pressPalaceSwitch(1)

        def pressPalaceSwitchTwo(self):
            return self.pressPalaceSwitch(2)

        def store(self, store_id):
            return read(clock(self), "storeDefinitions", {}).get(store_id)

        def canUseStore(self, store_id):
            if not self.canInteract():
                return False
            configured = self.getStringProperty("sourceStore") or self.actor().getStringProperty("sourceStore")
            return configured == store_id and self.store(store_id) is not None

        def canStoreAction(self, store_id, capability):
            return self.canUseStore(store_id) and bool(self.store(store_id).get("flags", 0) & capability)

        def buyStock(self, store_id, index):
            if not self.canStoreAction(store_id, 1):
                return False
            stock = self.store(store_id).get("stock", [])
            if not 0 <= index < len(stock):
                return False
            row = stock[index]
            price = max(0, int(row.get("price", -1)))
            if "price" not in row:
                notify(self, "The source price has not been staged; no gold is taken.")
                return False
            sold_key = "plugin_cityStockSold_" + store_id + "_" + str(index)
            sold = world(self).getNumericProperty(sold_key)
            if not row.get("infinite") and sold >= row.get("stock", 0):
                notify(self, "That source stock is exhausted.")
                return False
            if hero(self).getGold() < price:
                notify(self, "You do not have enough gold.")
                return False
            freezeHistory(self)
            item = makeSourceItem(self, row)
            if row.get("infinite"):
                item.setBoolProperty("plugin_cityUnidentified", False)
            hero(self).addGold(-price)
            hero(self).addItem(item)
            world(self).setNumericProperty(sold_key, sold + 1)
            return True

        def buyDrink(self, store_id, index):
            if not self.canStoreAction(store_id, 64):
                return False
            rows = self.store(store_id).get("drinks", [])
            if not 0 <= index < len(rows) or hero(self).getGold() < rows[index]["price"]:
                return False
            row = rows[index]
            freezeHistory(self)
            hero(self).addGold(-row["price"])
            game_map = world(self)
            game_map.setNumericProperty(
                "plugin_cityIntoxication",
                game_map.getNumericProperty("plugin_cityIntoxication") + row.get("strength", 0),
            )
            game_map.setStringProperty("plugin_cityLastDrink", row.get("displayName", ""))
            notify(
                self,
                row.get("displayName", "A drink")
                + ": "
                + row.get("rumour", "The tavern's rumors are recorded in the source interaction ledger."),
            )
            return True

        def rest(self, store_id, tier):
            if (
                not 0 <= tier < 4
                or not self.canUseStore(store_id)
                or not self.store(store_id).get("room_flags", 0) & (1 << tier)
            ):
                return False
            price = self.store(store_id)["room_prices"][tier]
            if hero(self).getGold() < price:
                return False
            freezeHistory(self)
            hero(self).addGold(-price)
            hero(self).heal(0)
            hero(self).addMana(0)
            world(self).setNumericProperty("plugin_cityLastRoomTier", tier)
            clock(self).advanceTicks(400)
            return True

        def identify(self, store_id):
            if not self.canStoreAction(store_id, 4):
                return False
            price = self.store(store_id).get("identify_price", 100)
            unknown = firstMatch(
                (item for item in possessions(hero(self)) if item.getBoolProperty("plugin_cityUnidentified")), None
            )
            if not unknown or hero(self).getGold() < price:
                return False
            freezeHistory(self)
            hero(self).addGold(-price)
            unknown.setBoolProperty("plugin_cityUnidentified", False)
            world(self).setNumericProperty(
                "plugin_cityIdentifications", world(self).getNumericProperty("plugin_cityIdentifications") + 1
            )
            return True

        def buyService(self, store_id, index):
            if not self.canStoreAction(store_id, 32):
                return False
            rows = self.store(store_id).get("cures", [])
            if not 0 <= index < len(rows):
                return False
            row, player = rows[index], hero(self)
            if player.getGold() < row["price"]:
                return False
            spell = row["spell"]
            freezeHistory(self)
            if spell == "SPPR103":
                if player.getHp() >= player.getHpMax():
                    return False
                player.heal(0)
            elif spell == "SPPR307":
                cursed = [item for item in possessions(player) if item.hasTag("cursed")]
                if not cursed:
                    return False
                for item in cursed:
                    item.removeTag("cursed")
            elif spell in ("SPPR303", "SPPR401"):
                kind = "disease" if spell == "SPPR303" else "poison"
                effects = {
                    effect
                    for effect in player.getEffects()
                    if kind in effect.getTypeId().lower()
                    or effect.getBoolProperty("plugin_city" + kind[:1].upper() + kind[1:])
                }
                if not effects:
                    return False
                player.setEffects(set(player.getEffects()) - effects)
            elif spell == "SPPR504":
                fallen = firstMatch((actor for actor in companions(self) if not actor.isAlive()), None)
                if not fallen:
                    return False
                # Revive the same actor. Native fixed-loot defeat already transferred its droppable belongings.
                fallen.setHp(1)
                world(self).addObject(fallen)
                point = player.getCoords()
                fallen.relocateWithoutMoveHooks(point)
                fallen.setBoolProperty("alwaysSimulate", True)
                fallen.setStringProperty("simulationRegion", currentArea(self))
                fallen.setStringProperty("affiliation", player.getStringProperty("affiliation"))
                world(self).setBoolProperty("plugin_cityDeath_" + fallen.getName(), False)
                controller = self.getGame().createObject("CTargetController")
                controller.setStringProperty("target", "player")
                fallen.setController(controller)
                updateAlliedRoster(self)
            else:
                notify(self, "This source service has no equivalent native status rule; no gold is taken.")
                return False
            player.addGold(-row["price"])
            world(self).setStringProperty("plugin_cityLastService", spell)
            return True

        @resumableHook
        def sell(self):
            store_id = self.getStringProperty("sourceStore") or (
                self.actor().getStringProperty("sourceStore") if self.actor() else ""
            )
            if not self.canStoreAction(store_id, 2):
                return False
            player = hero(self)
            store = self.store(store_id)
            available = [
                item
                for item in player.getItems()
                if item.getBoolProperty("plugin_cityTradeable")
                and not item.getBoolProperty("plugin_cityUndroppable")
                and not item.hasTag("quest")
                and item.getNumericProperty("plugin_cityItemType") in store.get("purchased_types", [])
                and (not item.getBoolProperty("plugin_cityStolen") or store.get("flags", 0) & 4096)
            ]
            rows = [
                {"id": item.getName(), "label": item.getStringProperty("label") or sourceCode(item)}
                for item in available
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Sell a possession", rows, "Sell")
            item = firstMatch((item for item in available if item.getName() == selected), None)
            if not item or item not in player.getItems():
                return False
            value = max(0, item.getNumericProperty("plugin_cityValue"))
            if item.getNumericProperty("plugin_cityStackSize") > 1:
                value *= quantity(item)
            price = value * self.store(store_id).get("buy_markup", 50) // 100
            freezeHistory(self)
            player.removeItem(lambda candidate: candidate == item, False)
            if item in player.getItems():
                return False
            self.actor().addItem(item)
            item.setBoolProperty("plugin_citySoldToStore", True)
            player.addGold(price)
            return True

        def donate(self):
            store_id = self.getStringProperty("sourceStore") or (
                self.actor().getStringProperty("sourceStore") if self.actor() else ""
            )
            if not self.canStoreAction(store_id, 16):
                return False
            document = read(clock(self), "questDefinitions", {})
            thresholds = document.get("donations", {}).get("baseChurch", [])
            reputation = world(self).getNumericProperty("plugin_cityReputation") or 10
            cost = thresholds[reputation - 1] if 1 <= reputation <= len(thresholds) else 0
            if cost <= 0:
                notify(self, "The temple can offer no further improvement to your standing.")
                return False
            if hero(self).getGold() < cost:
                notify(self, "A donation that improves your standing costs " + str(cost) + " gold.")
                return False
            freezeHistory(self)
            hero(self).addGold(-cost)
            setStanding(self, 1)
            world(self).setNumericProperty(
                "plugin_cityDonations", world(self).getNumericProperty("plugin_cityDonations") + cost
            )
            return True

        # Buying back retains the exact sold instance; it is distinct from finite source stock.
        @resumableHook
        def buyBack(self):
            store_id = self.getStringProperty("sourceStore") or (
                self.actor().getStringProperty("sourceStore") if self.actor() else ""
            )
            if not self.canStoreAction(store_id, 1):
                return False
            owner = self.actor()
            available = [item for item in owner.getItems() if item.getBoolProperty("plugin_citySoldToStore")]
            rows = [
                {"id": item.getName(), "label": item.getStringProperty("label") or sourceCode(item)}
                for item in available
            ]
            selected = yield uiRequest("choose", flowGame(self.getGame()), "Buy back belongings", rows, "Buy back")
            item = firstMatch((item for item in available if item.getName() == selected), None)
            if not item or item not in owner.getItems():
                return False
            value = max(0, item.getNumericProperty("plugin_cityValue"))
            if item.getNumericProperty("plugin_cityStackSize") > 1:
                value *= quantity(item)
            price = max(1, value * self.store(store_id).get("sell_markup", 100) // 100)
            if hero(self).getGold() < price:
                return False
            freezeHistory(self)
            owner.removeQuestItem(lambda candidate: candidate == item)
            hero(self).addGold(-price)
            hero(self).addItem(item)
            item.setBoolProperty("plugin_citySoldToStore", False)
            return True

        # QUEST_CALLBACKS_BEGIN
        def canAcceptQuinnDagger(self):
            return self.canAcceptQuest("quinnDagger")

        def acceptQuinnDagger(self):
            return self.acceptQuest("quinnDagger")

        def canQuestQuinnDaggerComplete(self):
            return self.canQuestOutcome("quinnDagger", "complete")

        @resumableHook
        def questQuinnDaggerComplete(self):
            return (yield from self.performQuestOutcomeFlow("quinnDagger", "complete"))

        def canAcceptRinnieBook(self):
            return self.canAcceptQuest("rinnieBook")

        def acceptRinnieBook(self):
            return self.acceptQuest("rinnieBook")

        def canQuestRinnieBookFavorable(self):
            return self.canQuestOutcome("rinnieBook", "favorable")

        @resumableHook
        def questRinnieBookFavorable(self):
            return (yield from self.performQuestOutcomeFlow("rinnieBook", "favorable"))

        def canQuestRinnieBookComplete(self):
            return self.canQuestOutcome("rinnieBook", "complete")

        @resumableHook
        def questRinnieBookComplete(self):
            return (yield from self.performQuestOutcomeFlow("rinnieBook", "complete"))

        def canAcceptPetrineRing(self):
            return self.canAcceptQuest("petrineRing")

        def acceptPetrineRing(self):
            return self.acceptQuest("petrineRing")

        def canQuestPetrineRingComplete(self):
            return self.canQuestOutcome("petrineRing", "complete")

        @resumableHook
        def questPetrineRingComplete(self):
            return (yield from self.performQuestOutcomeFlow("petrineRing", "complete"))

        def canQuestPetrineRingCatKilled(self):
            return self.canQuestOutcome("petrineRing", "catKilled")

        @resumableHook
        def questPetrineRingCatKilled(self):
            return (yield from self.performQuestOutcomeFlow("petrineRing", "catKilled"))

        def canAcceptBherenCat(self):
            return self.canAcceptQuest("bherenCat")

        def acceptBherenCat(self):
            return self.acceptQuest("bherenCat")

        def canQuestBherenCatComplete(self):
            return self.canQuestOutcome("bherenCat", "complete")

        @resumableHook
        def questBherenCatComplete(self):
            return (yield from self.performQuestOutcomeFlow("bherenCat", "complete"))

        def canQuestBherenCatLowStanding(self):
            return self.canQuestOutcome("bherenCat", "lowStanding")

        @resumableHook
        def questBherenCatLowStanding(self):
            return (yield from self.performQuestOutcomeFlow("bherenCat", "lowStanding"))

        def canAcceptBogeyman(self):
            return self.canAcceptQuest("bogeyman")

        def acceptBogeyman(self):
            return self.acceptQuest("bogeyman")

        def canQuestBogeymanVoltine(self):
            return self.canQuestOutcome("bogeyman", "voltine")

        @resumableHook
        def questBogeymanVoltine(self):
            return (yield from self.performQuestOutcomeFlow("bogeyman", "voltine"))

        def canQuestBogeymanComplete(self):
            return self.canQuestOutcome("bogeyman", "complete")

        @resumableHook
        def questBogeymanComplete(self):
            return (yield from self.performQuestOutcomeFlow("bogeyman", "complete"))

        def canAcceptPheirkasCloak(self):
            return self.canAcceptQuest("pheirkasCloak")

        def acceptPheirkasCloak(self):
            return self.acceptQuest("pheirkasCloak")

        def canQuestPheirkasCloakFavorable(self):
            return self.canQuestOutcome("pheirkasCloak", "favorable")

        @resumableHook
        def questPheirkasCloakFavorable(self):
            return (yield from self.performQuestOutcomeFlow("pheirkasCloak", "favorable"))

        def canQuestPheirkasCloakComplete(self):
            return self.canQuestOutcome("pheirkasCloak", "complete")

        @resumableHook
        def questPheirkasCloakComplete(self):
            return (yield from self.performQuestOutcomeFlow("pheirkasCloak", "complete"))

        def canAcceptDegrodelHelm(self):
            return self.canAcceptQuest("degrodelHelm")

        def acceptDegrodelHelm(self):
            return self.acceptQuest("degrodelHelm")

        def canQuestDegrodelHelmComplete(self):
            return self.canQuestOutcome("degrodelHelm", "complete")

        @resumableHook
        def questDegrodelHelmComplete(self):
            return (yield from self.performQuestOutcomeFlow("degrodelHelm", "complete"))

        def canAcceptBalduranCloak(self):
            return self.canAcceptQuest("balduranCloak")

        def acceptBalduranCloak(self):
            return self.acceptQuest("balduranCloak")

        def canQuestBalduranCloakComplete(self):
            return self.canQuestOutcome("balduranCloak", "complete")

        @resumableHook
        def questBalduranCloakComplete(self):
            return (yield from self.performQuestOutcomeFlow("balduranCloak", "complete"))

        def canQuestBalduranCloakBluff(self):
            return self.canQuestOutcome("balduranCloak", "bluff")

        @resumableHook
        def questBalduranCloakBluff(self):
            return (yield from self.performQuestOutcomeFlow("balduranCloak", "bluff"))

        def canAcceptRamazithNymph(self):
            return self.canAcceptQuest("ramazithNymph")

        def acceptRamazithNymph(self):
            return self.acceptQuest("ramazithNymph")

        def canQuestRamazithNymphComplete(self):
            return self.canQuestOutcome("ramazithNymph", "complete")

        @resumableHook
        def questRamazithNymphComplete(self):
            return (yield from self.performQuestOutcomeFlow("ramazithNymph", "complete"))

        def canAcceptRagefastNymph(self):
            return self.canAcceptQuest("ragefastNymph")

        def acceptRagefastNymph(self):
            return self.acceptQuest("ragefastNymph")

        def canQuestRagefastNymphPersuade(self):
            return self.canQuestOutcome("ragefastNymph", "persuade")

        @resumableHook
        def questRagefastNymphPersuade(self):
            return (yield from self.performQuestOutcomeFlow("ragefastNymph", "persuade"))

        def canQuestRagefastNymphComplete(self):
            return self.canQuestOutcome("ragefastNymph", "complete")

        @resumableHook
        def questRagefastNymphComplete(self):
            return (yield from self.performQuestOutcomeFlow("ragefastNymph", "complete"))

        def canQuestRagefastNymphAbduct(self):
            return self.canQuestOutcome("ragefastNymph", "abduct")

        @resumableHook
        def questRagefastNymphAbduct(self):
            return (yield from self.performQuestOutcomeFlow("ragefastNymph", "abduct"))

        def canAcceptNymphCloak(self):
            return self.canAcceptQuest("nymphCloak")

        def acceptNymphCloak(self):
            return self.acceptQuest("nymphCloak")

        def canQuestNymphCloakComplete(self):
            return self.canQuestOutcome("nymphCloak", "complete")

        @resumableHook
        def questNymphCloakComplete(self):
            return (yield from self.performQuestOutcomeFlow("nymphCloak", "complete"))

        def canQuestNymphCloakSellHair(self):
            return self.canQuestOutcome("nymphCloak", "sellHair")

        @resumableHook
        def questNymphCloakSellHair(self):
            return (yield from self.performQuestOutcomeFlow("nymphCloak", "sellHair"))

        def canAcceptArkionCorpse(self):
            return self.canAcceptQuest("arkionCorpse")

        def acceptArkionCorpse(self):
            return self.acceptQuest("arkionCorpse")

        def canQuestArkionCorpseComplete(self):
            return self.canQuestOutcome("arkionCorpse", "complete")

        @resumableHook
        def questArkionCorpseComplete(self):
            return (yield from self.performQuestOutcomeFlow("arkionCorpse", "complete"))

        def canAcceptNemphreAmulet(self):
            return self.canAcceptQuest("nemphreAmulet")

        def acceptNemphreAmulet(self):
            return self.acceptQuest("nemphreAmulet")

        def canQuestNemphreAmuletComplete(self):
            return self.canQuestOutcome("nemphreAmulet", "complete")

        @resumableHook
        def questNemphreAmuletComplete(self):
            return (yield from self.performQuestOutcomeFlow("nemphreAmulet", "complete"))

        def canAcceptOrdulinianMages(self):
            return self.canAcceptQuest("ordulinianMages")

        def acceptOrdulinianMages(self):
            return self.acceptQuest("ordulinianMages")

        def canQuestOrdulinianMagesComplete(self):
            return self.canQuestOutcome("ordulinianMages", "complete")

        @resumableHook
        def questOrdulinianMagesComplete(self):
            return (yield from self.performQuestOutcomeFlow("ordulinianMages", "complete"))

        def canAcceptBrevlikTelescope(self):
            return self.canAcceptQuest("brevlikTelescope")

        def acceptBrevlikTelescope(self):
            return self.acceptQuest("brevlikTelescope")

        def canQuestBrevlikTelescopeComplete(self):
            return self.canQuestOutcome("brevlikTelescope", "complete")

        @resumableHook
        def questBrevlikTelescopeComplete(self):
            return (yield from self.performQuestOutcomeFlow("brevlikTelescope", "complete"))

        def canQuestBrevlikTelescopeThreaten(self):
            return self.canQuestOutcome("brevlikTelescope", "threaten")

        @resumableHook
        def questBrevlikTelescopeThreaten(self):
            return (yield from self.performQuestOutcomeFlow("brevlikTelescope", "threaten"))

        def canAcceptAreanaBlackmail(self):
            return self.canAcceptQuest("areanaBlackmail")

        def acceptAreanaBlackmail(self):
            return self.acceptQuest("areanaBlackmail")

        def canQuestAreanaBlackmailComplete(self):
            return self.canQuestOutcome("areanaBlackmail", "complete")

        @resumableHook
        def questAreanaBlackmailComplete(self):
            return (yield from self.performQuestOutcomeFlow("areanaBlackmail", "complete"))

        def canAcceptAlatosTheft(self):
            return self.canAcceptQuest("alatosTheft")

        def acceptAlatosTheft(self):
            return self.acceptQuest("alatosTheft")

        def canQuestAlatosTheftComplete(self):
            return self.canQuestOutcome("alatosTheft", "complete")

        @resumableHook
        def questAlatosTheftComplete(self):
            return (yield from self.performQuestOutcomeFlow("alatosTheft", "complete"))

        def canAcceptNarlenLookout(self):
            return self.canAcceptQuest("narlenLookout")

        def acceptNarlenLookout(self):
            return self.acceptQuest("narlenLookout")

        def canQuestNarlenLookoutComplete(self):
            return self.canQuestOutcome("narlenLookout", "complete")

        @resumableHook
        def questNarlenLookoutComplete(self):
            return (yield from self.performQuestOutcomeFlow("narlenLookout", "complete"))

        def canQuestNarlenLookoutOfficerKilled(self):
            return self.canQuestOutcome("narlenLookout", "officerKilled")

        @resumableHook
        def questNarlenLookoutOfficerKilled(self):
            return (yield from self.performQuestOutcomeFlow("narlenLookout", "officerKilled"))

        def canAcceptNarlenRogueStone(self):
            return self.canAcceptQuest("narlenRogueStone")

        def acceptNarlenRogueStone(self):
            return self.acceptQuest("narlenRogueStone")

        def canQuestNarlenRogueStoneComplete(self):
            return self.canQuestOutcome("narlenRogueStone", "complete")

        @resumableHook
        def questNarlenRogueStoneComplete(self):
            return (yield from self.performQuestOutcomeFlow("narlenRogueStone", "complete"))

        def canAcceptBrielbaraBook(self):
            return self.canAcceptQuest("brielbaraBook")

        def acceptBrielbaraBook(self):
            return self.acceptQuest("brielbaraBook")

        def canQuestBrielbaraBookComplete(self):
            return self.canQuestOutcome("brielbaraBook", "complete")

        @resumableHook
        def questBrielbaraBookComplete(self):
            return (yield from self.performQuestOutcomeFlow("brielbaraBook", "complete"))

        def canAcceptGhorakSkull(self):
            return self.canAcceptQuest("ghorakSkull")

        def acceptGhorakSkull(self):
            return self.acceptQuest("ghorakSkull")

        def canQuestGhorakSkullComplete(self):
            return self.canQuestOutcome("ghorakSkull", "complete")

        @resumableHook
        def questGhorakSkullComplete(self):
            return (yield from self.performQuestOutcomeFlow("ghorakSkull", "complete"))

        def canAcceptNoraleeGauntlets(self):
            return self.canAcceptQuest("noraleeGauntlets")

        def acceptNoraleeGauntlets(self):
            return self.acceptQuest("noraleeGauntlets")

        def canQuestNoraleeGauntletsFavorable(self):
            return self.canQuestOutcome("noraleeGauntlets", "favorable")

        @resumableHook
        def questNoraleeGauntletsFavorable(self):
            return (yield from self.performQuestOutcomeFlow("noraleeGauntlets", "favorable"))

        def canQuestNoraleeGauntletsComplete(self):
            return self.canQuestOutcome("noraleeGauntlets", "complete")

        @resumableHook
        def questNoraleeGauntletsComplete(self):
            return (yield from self.performQuestOutcomeFlow("noraleeGauntlets", "complete"))

        def canAcceptNadarinBasilisk(self):
            return self.canAcceptQuest("nadarinBasilisk")

        def acceptNadarinBasilisk(self):
            return self.acceptQuest("nadarinBasilisk")

        def canQuestNadarinBasiliskFavorable(self):
            return self.canQuestOutcome("nadarinBasilisk", "favorable")

        @resumableHook
        def questNadarinBasiliskFavorable(self):
            return (yield from self.performQuestOutcomeFlow("nadarinBasilisk", "favorable"))

        def canQuestNadarinBasiliskComplete(self):
            return self.canQuestOutcome("nadarinBasilisk", "complete")

        @resumableHook
        def questNadarinBasiliskComplete(self):
            return (yield from self.performQuestOutcomeFlow("nadarinBasilisk", "complete"))

        def canAcceptGaxirFortune(self):
            return self.canAcceptQuest("gaxirFortune")

        def acceptGaxirFortune(self):
            return self.acceptQuest("gaxirFortune")

        def canQuestGaxirFortuneComplete(self):
            return self.canQuestOutcome("gaxirFortune", "complete")

        @resumableHook
        def questGaxirFortuneComplete(self):
            return (yield from self.performQuestOutcomeFlow("gaxirFortune", "complete"))

        def canAcceptNadineEuric(self):
            return self.canAcceptQuest("nadineEuric")

        def acceptNadineEuric(self):
            return self.acceptQuest("nadineEuric")

        def canQuestNadineEuricFavorable(self):
            return self.canQuestOutcome("nadineEuric", "favorable")

        @resumableHook
        def questNadineEuricFavorable(self):
            return (yield from self.performQuestOutcomeFlow("nadineEuric", "favorable"))

        def canQuestNadineEuricComplete(self):
            return self.canQuestOutcome("nadineEuric", "complete")

        @resumableHook
        def questNadineEuricComplete(self):
            return (yield from self.performQuestOutcomeFlow("nadineEuric", "complete"))

        def canQuestNadineEuricDeliver(self):
            return self.canQuestOutcome("nadineEuric", "deliver")

        @resumableHook
        def questNadineEuricDeliver(self):
            return (yield from self.performQuestOutcomeFlow("nadineEuric", "deliver"))

        def canAcceptFergusRing(self):
            return self.canAcceptQuest("fergusRing")

        def acceptFergusRing(self):
            return self.acceptQuest("fergusRing")

        def canQuestFergusRingComplete(self):
            return self.canQuestOutcome("fergusRing", "complete")

        @resumableHook
        def questFergusRingComplete(self):
            return (yield from self.performQuestOutcomeFlow("fergusRing", "complete"))

        def canAcceptFentenShells(self):
            return self.canAcceptQuest("fentenShells")

        def acceptFentenShells(self):
            return self.acceptQuest("fentenShells")

        def canQuestFentenShellsComplete(self):
            return self.canQuestOutcome("fentenShells", "complete")

        @resumableHook
        def questFentenShellsComplete(self):
            return (yield from self.performQuestOutcomeFlow("fentenShells", "complete"))

        def canAcceptCordyrSirines(self):
            return self.canAcceptQuest("cordyrSirines")

        def acceptCordyrSirines(self):
            return self.acceptQuest("cordyrSirines")

        def canQuestCordyrSirinesComplete(self):
            return self.canQuestOutcome("cordyrSirines", "complete")

        @resumableHook
        def questCordyrSirinesComplete(self):
            return (yield from self.performQuestOutcomeFlow("cordyrSirines", "complete"))

        def canQuestCordyrSirinesOrdinary(self):
            return self.canQuestOutcome("cordyrSirines", "ordinary")

        @resumableHook
        def questCordyrSirinesOrdinary(self):
            return (yield from self.performQuestOutcomeFlow("cordyrSirines", "ordinary"))

        def canAcceptVarciCasson(self):
            return self.canAcceptQuest("varciCasson")

        def acceptVarciCasson(self):
            return self.acceptQuest("varciCasson")

        def canQuestVarciCassonComplete(self):
            return self.canQuestOutcome("varciCasson", "complete")

        @resumableHook
        def questVarciCassonComplete(self):
            return (yield from self.performQuestOutcomeFlow("varciCasson", "complete"))

        def canQuestVarciCassonReward(self):
            return self.canQuestOutcome("varciCasson", "reward")

        @resumableHook
        def questVarciCassonReward(self):
            return (yield from self.performQuestOutcomeFlow("varciCasson", "reward"))

        def canAcceptLarzeAssassin(self):
            return self.canAcceptQuest("larzeAssassin")

        def acceptLarzeAssassin(self):
            return self.acceptQuest("larzeAssassin")

        def canQuestLarzeAssassinComplete(self):
            return self.canQuestOutcome("larzeAssassin", "complete")

        @resumableHook
        def questLarzeAssassinComplete(self):
            return (yield from self.performQuestOutcomeFlow("larzeAssassin", "complete"))

        def canAcceptTaxekBurglary(self):
            return self.canAcceptQuest("taxekBurglary")

        def acceptTaxekBurglary(self):
            return self.acceptQuest("taxekBurglary")

        def canQuestTaxekBurglaryComplete(self):
            return self.canQuestOutcome("taxekBurglary", "complete")

        @resumableHook
        def questTaxekBurglaryComplete(self):
            return (yield from self.performQuestOutcomeFlow("taxekBurglary", "complete"))

        def canQuestTaxekBurglaryRelease(self):
            return self.canQuestOutcome("taxekBurglary", "release")

        @resumableHook
        def questTaxekBurglaryRelease(self):
            return (yield from self.performQuestOutcomeFlow("taxekBurglary", "release"))

        def canAcceptForthelBallad(self):
            return self.canAcceptQuest("forthelBallad")

        def acceptForthelBallad(self):
            return self.acceptQuest("forthelBallad")

        def canQuestForthelBalladComplete(self):
            return self.canQuestOutcome("forthelBallad", "complete")

        @resumableHook
        def questForthelBalladComplete(self):
            return (yield from self.performQuestOutcomeFlow("forthelBallad", "complete"))

        def canAcceptNiklosGuild(self):
            return self.canAcceptQuest("niklosGuild")

        def acceptNiklosGuild(self):
            return self.acceptQuest("niklosGuild")

        def canQuestNiklosGuildComplete(self):
            return self.canQuestOutcome("niklosGuild", "complete")

        @resumableHook
        def questNiklosGuildComplete(self):
            return (yield from self.performQuestOutcomeFlow("niklosGuild", "complete"))

        def canAcceptScarSevenSuns(self):
            return self.canAcceptQuest("scarSevenSuns")

        def acceptScarSevenSuns(self):
            return self.acceptQuest("scarSevenSuns")

        def canQuestScarSevenSunsComplete(self):
            return self.canQuestOutcome("scarSevenSuns", "complete")

        @resumableHook
        def questScarSevenSunsComplete(self):
            return (yield from self.performQuestOutcomeFlow("scarSevenSuns", "complete"))

        def canAcceptScarDoppelgangers(self):
            return self.canAcceptQuest("scarDoppelgangers")

        def acceptScarDoppelgangers(self):
            return self.acceptQuest("scarDoppelgangers")

        def canQuestScarDoppelgangersComplete(self):
            return self.canQuestOutcome("scarDoppelgangers", "complete")

        @resumableHook
        def questScarDoppelgangersComplete(self):
            return (yield from self.performQuestOutcomeFlow("scarDoppelgangers", "complete"))

        def canQuestScarDoppelgangersJhassoDead(self):
            return self.canQuestOutcome("scarDoppelgangers", "jhassoDead")

        @resumableHook
        def questScarDoppelgangersJhassoDead(self):
            return (yield from self.performQuestOutcomeFlow("scarDoppelgangers", "jhassoDead"))

        def canAcceptScarSewers(self):
            return self.canAcceptQuest("scarSewers")

        def acceptScarSewers(self):
            return self.acceptQuest("scarSewers")

        def canQuestScarSewersComplete(self):
            return self.canQuestOutcome("scarSewers", "complete")

        @resumableHook
        def questScarSewersComplete(self):
            return (yield from self.performQuestOutcomeFlow("scarSewers", "complete"))

        def canQuestScarSewersWithoutRing(self):
            return self.canQuestOutcome("scarSewers", "withoutRing")

        @resumableHook
        def questScarSewersWithoutRing(self):
            return (yield from self.performQuestOutcomeFlow("scarSewers", "withoutRing"))

        def canAcceptEltanIronThrone(self):
            return self.canAcceptQuest("eltanIronThrone")

        def acceptEltanIronThrone(self):
            return self.acceptQuest("eltanIronThrone")

        def canQuestEltanIronThroneComplete(self):
            return self.canQuestOutcome("eltanIronThrone", "complete")

        @resumableHook
        def questEltanIronThroneComplete(self):
            return (yield from self.performQuestOutcomeFlow("eltanIronThrone", "complete"))

        def canAcceptCythandriaDiary(self):
            return self.canAcceptQuest("cythandriaDiary")

        def acceptCythandriaDiary(self):
            return self.acceptQuest("cythandriaDiary")

        def canQuestCythandriaDiaryComplete(self):
            return self.canQuestOutcome("cythandriaDiary", "complete")

        @resumableHook
        def questCythandriaDiaryComplete(self):
            return (yield from self.performQuestOutcomeFlow("cythandriaDiary", "complete"))

        def canAcceptRescueEltan(self):
            return self.canAcceptQuest("rescueEltan")

        def acceptRescueEltan(self):
            return self.acceptQuest("rescueEltan")

        def canQuestRescueEltanCarry(self):
            return self.canQuestOutcome("rescueEltan", "carry")

        @resumableHook
        def questRescueEltanCarry(self):
            return (yield from self.performQuestOutcomeFlow("rescueEltan", "carry"))

        def canQuestRescueEltanComplete(self):
            return self.canQuestOutcome("rescueEltan", "complete")

        @resumableHook
        def questRescueEltanComplete(self):
            return (yield from self.performQuestOutcomeFlow("rescueEltan", "complete"))

        def canAcceptDucalAssassins(self):
            return self.canAcceptQuest("ducalAssassins")

        def acceptDucalAssassins(self):
            return self.acceptQuest("ducalAssassins")

        def canQuestDucalAssassinsComplete(self):
            return self.canQuestOutcome("ducalAssassins", "complete")

        @resumableHook
        def questDucalAssassinsComplete(self):
            return (yield from self.performQuestOutcomeFlow("ducalAssassins", "complete"))

        def canAcceptDucalPalace(self):
            return self.canAcceptQuest("ducalPalace")

        def acceptDucalPalace(self):
            return self.acceptQuest("ducalPalace")

        def canQuestDucalPalaceComplete(self):
            return self.canQuestOutcome("ducalPalace", "complete")

        @resumableHook
        def questDucalPalaceComplete(self):
            return (yield from self.performQuestOutcomeFlow("ducalPalace", "complete"))

        def canAcceptThievesMaze(self):
            return self.canAcceptQuest("thievesMaze")

        def acceptThievesMaze(self):
            return self.acceptQuest("thievesMaze")

        def canQuestThievesMazeComplete(self):
            return self.canQuestOutcome("thievesMaze", "complete")

        @resumableHook
        def questThievesMazeComplete(self):
            return (yield from self.performQuestOutcomeFlow("thievesMaze", "complete"))

        def canAcceptTamokoMercy(self):
            return self.canAcceptQuest("tamokoMercy")

        def acceptTamokoMercy(self):
            return self.acceptQuest("tamokoMercy")

        def canQuestTamokoMercyComplete(self):
            return self.canQuestOutcome("tamokoMercy", "complete")

        @resumableHook
        def questTamokoMercyComplete(self):
            return (yield from self.performQuestOutcomeFlow("tamokoMercy", "complete"))

        def canQuestTamokoMercyFight(self):
            return self.canQuestOutcome("tamokoMercy", "fight")

        @resumableHook
        def questTamokoMercyFight(self):
            return (yield from self.performQuestOutcomeFlow("tamokoMercy", "fight"))

        def canAcceptSarevokFinale(self):
            return self.canAcceptQuest("sarevokFinale")

        def acceptSarevokFinale(self):
            return self.acceptQuest("sarevokFinale")

        def canQuestSarevokFinaleComplete(self):
            return self.canQuestOutcome("sarevokFinale", "complete")

        @resumableHook
        def questSarevokFinaleComplete(self):
            return (yield from self.performQuestOutcomeFlow("sarevokFinale", "complete"))

        def canAcceptAldethLeague(self):
            return self.canAcceptQuest("aldethLeague")

        def acceptAldethLeague(self):
            return self.acceptQuest("aldethLeague")

        def canQuestAldethLeagueComplete(self):
            return self.canQuestOutcome("aldethLeague", "complete")

        @resumableHook
        def questAldethLeagueComplete(self):
            return (yield from self.performQuestOutcomeFlow("aldethLeague", "complete"))

        def canAcceptMarekPoison(self):
            return self.canAcceptQuest("marekPoison")

        def acceptMarekPoison(self):
            return self.acceptQuest("marekPoison")

        def canQuestMarekPoisonComplete(self):
            return self.canQuestOutcome("marekPoison", "complete")

        @resumableHook
        def questMarekPoisonComplete(self):
            return (yield from self.performQuestOutcomeFlow("marekPoison", "complete"))

        def canAcceptLothanderGeas(self):
            return self.canAcceptQuest("lothanderGeas")

        def acceptLothanderGeas(self):
            return self.acceptQuest("lothanderGeas")

        def canQuestLothanderGeasComplete(self):
            return self.canQuestOutcome("lothanderGeas", "complete")

        @resumableHook
        def questLothanderGeasComplete(self):
            return (yield from self.performQuestOutcomeFlow("lothanderGeas", "complete"))

        def canAcceptJalanthaBook(self):
            return self.canAcceptQuest("jalanthaBook")

        def acceptJalanthaBook(self):
            return self.acceptQuest("jalanthaBook")

        def canQuestJalanthaBookComplete(self):
            return self.canQuestOutcome("jalanthaBook", "complete")

        @resumableHook
        def questJalanthaBookComplete(self):
            return (yield from self.performQuestOutcomeFlow("jalanthaBook", "complete"))

        def canAcceptChanthalasTome(self):
            return self.canAcceptQuest("chanthalasTome")

        def acceptChanthalasTome(self):
            return self.acceptQuest("chanthalasTome")

        def canQuestChanthalasTomeComplete(self):
            return self.canQuestOutcome("chanthalasTome", "complete")

        @resumableHook
        def questChanthalasTomeComplete(self):
            return (yield from self.performQuestOutcomeFlow("chanthalasTome", "complete"))

        def canQuestChanthalasTomePlead(self):
            return self.canQuestOutcome("chanthalasTome", "plead")

        @resumableHook
        def questChanthalasTomePlead(self):
            return (yield from self.performQuestOutcomeFlow("chanthalasTome", "plead"))

        def canAcceptLusselynWager(self):
            return self.canAcceptQuest("lusselynWager")

        def acceptLusselynWager(self):
            return self.acceptQuest("lusselynWager")

        def canQuestLusselynWagerComplete(self):
            return self.canQuestOutcome("lusselynWager", "complete")

        @resumableHook
        def questLusselynWagerComplete(self):
            return (yield from self.performQuestOutcomeFlow("lusselynWager", "complete"))

        def canAcceptShadePantaloons(self):
            return self.canAcceptQuest("shadePantaloons")

        def acceptShadePantaloons(self):
            return self.acceptQuest("shadePantaloons")

        def canQuestShadePantaloonsDeceived(self):
            return self.canQuestOutcome("shadePantaloons", "deceived")

        @resumableHook
        def questShadePantaloonsDeceived(self):
            return (yield from self.performQuestOutcomeFlow("shadePantaloons", "deceived"))

        def canQuestShadePantaloonsRefuse(self):
            return self.canQuestOutcome("shadePantaloons", "refuse")

        @resumableHook
        def questShadePantaloonsRefuse(self):
            return (yield from self.performQuestOutcomeFlow("shadePantaloons", "refuse"))

        def canAcceptSilenceFee(self):
            return self.canAcceptQuest("silenceFee")

        def acceptSilenceFee(self):
            return self.acceptQuest("silenceFee")

        def canQuestSilenceFeePay(self):
            return self.canQuestOutcome("silenceFee", "pay")

        @resumableHook
        def questSilenceFeePay(self):
            return (yield from self.performQuestOutcomeFlow("silenceFee", "pay"))

        def canQuestSilenceFeeFavorable(self):
            return self.canQuestOutcome("silenceFee", "favorable")

        @resumableHook
        def questSilenceFeeFavorable(self):
            return (yield from self.performQuestOutcomeFlow("silenceFee", "favorable"))

        def canQuestSilenceFeeLeave(self):
            return self.canQuestOutcome("silenceFee", "leave")

        @resumableHook
        def questSilenceFeeLeave(self):
            return (yield from self.performQuestOutcomeFlow("silenceFee", "leave"))

        def canAcceptDivinerPoison(self):
            return self.canAcceptQuest("divinerPoison")

        def acceptDivinerPoison(self):
            return self.acceptQuest("divinerPoison")

        def canQuestDivinerPoisonPay(self):
            return self.canQuestOutcome("divinerPoison", "pay")

        @resumableHook
        def questDivinerPoisonPay(self):
            return (yield from self.performQuestOutcomeFlow("divinerPoison", "pay"))

        def canAcceptVoletaMaze(self):
            return self.canAcceptQuest("voletaMaze")

        def acceptVoletaMaze(self):
            return self.acceptQuest("voletaMaze")

        def canQuestVoletaMazeHear(self):
            return self.canQuestOutcome("voletaMaze", "hear")

        @resumableHook
        def questVoletaMazeHear(self):
            return (yield from self.performQuestOutcomeFlow("voletaMaze", "hear"))

        def canAcceptWinskiMaze(self):
            return self.canAcceptQuest("winskiMaze")

        def acceptWinskiMaze(self):
            return self.acceptQuest("winskiMaze")

        def canQuestWinskiMazeHear(self):
            return self.canQuestOutcome("winskiMaze", "hear")

        @resumableHook
        def questWinskiMazeHear(self):
            return (yield from self.performQuestOutcomeFlow("winskiMaze", "hear"))

        def canAcceptVailClue(self):
            return self.canAcceptQuest("vailClue")

        def acceptVailClue(self):
            return self.acceptQuest("vailClue")

        def canQuestVailClueHear(self):
            return self.canQuestOutcome("vailClue", "hear")

        @resumableHook
        def questVailClueHear(self):
            return (yield from self.performQuestOutcomeFlow("vailClue", "hear"))

        def canExcursionNester(self):
            return self.canExcursion("nester")

        @resumableHook
        def excursionNesterRecover(self):
            return (yield from self.excursionFlow("nester", "recover"))

        @resumableHook
        def excursionNesterLater(self):
            return (yield from self.excursionFlow("nester", "later"))

        def canExcursionAlgernon(self):
            return self.canExcursion("algernon")

        @resumableHook
        def excursionAlgernonSteal(self):
            return (yield from self.excursionFlow("algernon", "steal"))

        @resumableHook
        def excursionAlgernonKill(self):
            return (yield from self.excursionFlow("algernon", "kill"))

        @resumableHook
        def excursionAlgernonLater(self):
            return (yield from self.excursionFlow("algernon", "later"))

        def canExcursionSil(self):
            return self.canExcursion("sil")

        @resumableHook
        def excursionSilKill(self):
            return (yield from self.excursionFlow("sil", "kill"))

        @resumableHook
        def excursionSilSpare(self):
            return (yield from self.excursionFlow("sil", "spare"))

        def canUseStoreTav0705(self):
            return self.canUseStore("TAV0705")

        def drinkStoreTav07050(self):
            return self.buyDrink("TAV0705", 0)

        def drinkStoreTav07051(self):
            return self.buyDrink("TAV0705", 1)

        def drinkStoreTav07052(self):
            return self.buyDrink("TAV0705", 2)

        def drinkStoreTav07053(self):
            return self.buyDrink("TAV0705", 3)

        def drinkStoreTav07054(self):
            return self.buyDrink("TAV0705", 4)

        def drinkStoreTav07055(self):
            return self.buyDrink("TAV0705", 5)

        def canUseStoreTav0133(self):
            return self.canUseStore("TAV0133")

        def drinkStoreTav01330(self):
            return self.buyDrink("TAV0133", 0)

        def drinkStoreTav01331(self):
            return self.buyDrink("TAV0133", 1)

        def drinkStoreTav01332(self):
            return self.buyDrink("TAV0133", 2)

        def drinkStoreTav01333(self):
            return self.buyDrink("TAV0133", 3)

        def drinkStoreTav01334(self):
            return self.buyDrink("TAV0133", 4)

        def drinkStoreTav01335(self):
            return self.buyDrink("TAV0133", 5)

        def drinkStoreTav01336(self):
            return self.buyDrink("TAV0133", 6)

        def restStoreTav01330(self):
            return self.rest("TAV0133", 0)

        def restStoreTav01331(self):
            return self.rest("TAV0133", 1)

        def canUseStoreTav0720(self):
            return self.canUseStore("TAV0720")

        def drinkStoreTav07200(self):
            return self.buyDrink("TAV0720", 0)

        def drinkStoreTav07201(self):
            return self.buyDrink("TAV0720", 1)

        def drinkStoreTav07202(self):
            return self.buyDrink("TAV0720", 2)

        def drinkStoreTav07203(self):
            return self.buyDrink("TAV0720", 3)

        def drinkStoreTav07204(self):
            return self.buyDrink("TAV0720", 4)

        def drinkStoreTav07205(self):
            return self.buyDrink("TAV0720", 5)

        def restStoreTav07200(self):
            return self.rest("TAV0720", 0)

        def restStoreTav07201(self):
            return self.rest("TAV0720", 1)

        def restStoreTav07202(self):
            return self.rest("TAV0720", 2)

        def restStoreTav07203(self):
            return self.rest("TAV0720", 3)

        def canUseStoreTavbar11(self):
            return self.canUseStore("TAVBAR11")

        def drinkStoreTavbar110(self):
            return self.buyDrink("TAVBAR11", 0)

        def drinkStoreTavbar111(self):
            return self.buyDrink("TAVBAR11", 1)

        def drinkStoreTavbar112(self):
            return self.buyDrink("TAVBAR11", 2)

        def drinkStoreTavbar113(self):
            return self.buyDrink("TAVBAR11", 3)

        def drinkStoreTavbar114(self):
            return self.buyDrink("TAVBAR11", 4)

        def drinkStoreTavbar115(self):
            return self.buyDrink("TAVBAR11", 5)

        def restStoreTavbar110(self):
            return self.rest("TAVBAR11", 0)

        def restStoreTavbar111(self):
            return self.rest("TAVBAR11", 1)

        def restStoreTavbar112(self):
            return self.rest("TAVBAR11", 2)

        def restStoreTavbar113(self):
            return self.rest("TAVBAR11", 3)

        def canUseStoreTav0721(self):
            return self.canUseStore("TAV0721")

        def drinkStoreTav07210(self):
            return self.buyDrink("TAV0721", 0)

        def drinkStoreTav07211(self):
            return self.buyDrink("TAV0721", 1)

        def drinkStoreTav07212(self):
            return self.buyDrink("TAV0721", 2)

        def drinkStoreTav07213(self):
            return self.buyDrink("TAV0721", 3)

        def drinkStoreTav07214(self):
            return self.buyDrink("TAV0721", 4)

        def drinkStoreTav07215(self):
            return self.buyDrink("TAV0721", 5)

        def restStoreTav07210(self):
            return self.rest("TAV0721", 0)

        def restStoreTav07211(self):
            return self.rest("TAV0721", 1)

        def restStoreTav07212(self):
            return self.rest("TAV0721", 2)

        def restStoreTav07213(self):
            return self.rest("TAV0721", 3)

        def canUseStoreTav0154(self):
            return self.canUseStore("TAV0154")

        def drinkStoreTav01540(self):
            return self.buyDrink("TAV0154", 0)

        def drinkStoreTav01541(self):
            return self.buyDrink("TAV0154", 1)

        def drinkStoreTav01542(self):
            return self.buyDrink("TAV0154", 2)

        def drinkStoreTav01543(self):
            return self.buyDrink("TAV0154", 3)

        def drinkStoreTav01544(self):
            return self.buyDrink("TAV0154", 4)

        def drinkStoreTav01545(self):
            return self.buyDrink("TAV0154", 5)

        def drinkStoreTav01546(self):
            return self.buyDrink("TAV0154", 6)

        def restStoreTav01540(self):
            return self.rest("TAV0154", 0)

        def restStoreTav01541(self):
            return self.rest("TAV0154", 1)

        def canUseStoreTav1215(self):
            return self.canUseStore("TAV1215")

        def drinkStoreTav12150(self):
            return self.buyDrink("TAV1215", 0)

        def drinkStoreTav12151(self):
            return self.buyDrink("TAV1215", 1)

        def drinkStoreTav12152(self):
            return self.buyDrink("TAV1215", 2)

        def drinkStoreTav12153(self):
            return self.buyDrink("TAV1215", 3)

        def drinkStoreTav12154(self):
            return self.buyDrink("TAV1215", 4)

        def drinkStoreTav12155(self):
            return self.buyDrink("TAV1215", 5)

        def restStoreTav12150(self):
            return self.rest("TAV1215", 0)

        def restStoreTav12151(self):
            return self.rest("TAV1215", 1)

        def restStoreTav12152(self):
            return self.rest("TAV1215", 2)

        def restStoreTav12153(self):
            return self.rest("TAV1215", 3)

        def canUseStoreInn0103(self):
            return self.canUseStore("INN0103")

        def drinkStoreInn01030(self):
            return self.buyDrink("INN0103", 0)

        def drinkStoreInn01031(self):
            return self.buyDrink("INN0103", 1)

        def drinkStoreInn01032(self):
            return self.buyDrink("INN0103", 2)

        def drinkStoreInn01033(self):
            return self.buyDrink("INN0103", 3)

        def restStoreInn01030(self):
            return self.rest("INN0103", 0)

        def restStoreInn01031(self):
            return self.rest("INN0103", 1)

        def restStoreInn01032(self):
            return self.rest("INN0103", 2)

        def restStoreInn01033(self):
            return self.rest("INN0103", 3)

        def canUseStoreInn0705(self):
            return self.canUseStore("INN0705")

        def drinkStoreInn07050(self):
            return self.buyDrink("INN0705", 0)

        def drinkStoreInn07051(self):
            return self.buyDrink("INN0705", 1)

        def drinkStoreInn07052(self):
            return self.buyDrink("INN0705", 2)

        def drinkStoreInn07053(self):
            return self.buyDrink("INN0705", 3)

        def drinkStoreInn07054(self):
            return self.buyDrink("INN0705", 4)

        def drinkStoreInn07055(self):
            return self.buyDrink("INN0705", 5)

        def restStoreInn07050(self):
            return self.rest("INN0705", 0)

        def restStoreInn07051(self):
            return self.rest("INN0705", 1)

        def restStoreInn07052(self):
            return self.rest("INN0705", 2)

        def restStoreInn07053(self):
            return self.rest("INN0705", 3)

        def canUseStoreInn0116(self):
            return self.canUseStore("INN0116")

        def drinkStoreInn01160(self):
            return self.buyDrink("INN0116", 0)

        def drinkStoreInn01161(self):
            return self.buyDrink("INN0116", 1)

        def drinkStoreInn01162(self):
            return self.buyDrink("INN0116", 2)

        def drinkStoreInn01163(self):
            return self.buyDrink("INN0116", 3)

        def drinkStoreInn01164(self):
            return self.buyDrink("INN0116", 4)

        def restStoreInn01160(self):
            return self.rest("INN0116", 0)

        def restStoreInn01161(self):
            return self.rest("INN0116", 1)

        def restStoreInn01162(self):
            return self.rest("INN0116", 2)

        def restStoreInn01163(self):
            return self.rest("INN0116", 3)

        def canUseStoreStoblack(self):
            return self.canUseStore("STOBLACK")

        def buyStoreStoblack0(self):
            return self.buyStock("STOBLACK", 0)

        def buyStoreStoblack1(self):
            return self.buyStock("STOBLACK", 1)

        def buyStoreStoblack2(self):
            return self.buyStock("STOBLACK", 2)

        def buyStoreStoblack3(self):
            return self.buyStock("STOBLACK", 3)

        def buyStoreStoblack4(self):
            return self.buyStock("STOBLACK", 4)

        def buyStoreStoblack5(self):
            return self.buyStock("STOBLACK", 5)

        def buyStoreStoblack6(self):
            return self.buyStock("STOBLACK", 6)

        def buyStoreStoblack7(self):
            return self.buyStock("STOBLACK", 7)

        def buyStoreStoblack8(self):
            return self.buyStock("STOBLACK", 8)

        def buyStoreStoblack9(self):
            return self.buyStock("STOBLACK", 9)

        def buyStoreStoblack10(self):
            return self.buyStock("STOBLACK", 10)

        def buyStoreStoblack11(self):
            return self.buyStock("STOBLACK", 11)

        def buyStoreStoblack12(self):
            return self.buyStock("STOBLACK", 12)

        def buyStoreStoblack13(self):
            return self.buyStock("STOBLACK", 13)

        def buyStoreStoblack14(self):
            return self.buyStock("STOBLACK", 14)

        def buyStoreStoblack15(self):
            return self.buyStock("STOBLACK", 15)

        def buyStoreStoblack16(self):
            return self.buyStock("STOBLACK", 16)

        def buyStoreStoblack17(self):
            return self.buyStock("STOBLACK", 17)

        def buyStoreStoblack18(self):
            return self.buyStock("STOBLACK", 18)

        def buyStoreStoblack19(self):
            return self.buyStock("STOBLACK", 19)

        def buyStoreStoblack20(self):
            return self.buyStock("STOBLACK", 20)

        def buyStoreStoblack21(self):
            return self.buyStock("STOBLACK", 21)

        def buyStoreStoblack22(self):
            return self.buyStock("STOBLACK", 22)

        def buyStoreStoblack23(self):
            return self.buyStock("STOBLACK", 23)

        def buyStoreStoblack24(self):
            return self.buyStock("STOBLACK", 24)

        def buyStoreStoblack25(self):
            return self.buyStock("STOBLACK", 25)

        def buyStoreStoblack26(self):
            return self.buyStock("STOBLACK", 26)

        def buyStoreStoblack27(self):
            return self.buyStock("STOBLACK", 27)

        def buyStoreStoblack28(self):
            return self.buyStock("STOBLACK", 28)

        def buyStoreStoblack29(self):
            return self.buyStock("STOBLACK", 29)

        def buyStoreStoblack30(self):
            return self.buyStock("STOBLACK", 30)

        def buyStoreStoblack31(self):
            return self.buyStock("STOBLACK", 31)

        def buyStoreStoblack32(self):
            return self.buyStock("STOBLACK", 32)

        def buyStoreStoblack33(self):
            return self.buyStock("STOBLACK", 33)

        def identifyStoreStoblack(self):
            return self.identify("STOBLACK")

        def canUseStoreTav0114(self):
            return self.canUseStore("TAV0114")

        def drinkStoreTav01140(self):
            return self.buyDrink("TAV0114", 0)

        def drinkStoreTav01141(self):
            return self.buyDrink("TAV0114", 1)

        def drinkStoreTav01142(self):
            return self.buyDrink("TAV0114", 2)

        def drinkStoreTav01143(self):
            return self.buyDrink("TAV0114", 3)

        def drinkStoreTav01144(self):
            return self.buyDrink("TAV0114", 4)

        def drinkStoreTav01145(self):
            return self.buyDrink("TAV0114", 5)

        def drinkStoreTav01146(self):
            return self.buyDrink("TAV0114", 6)

        def drinkStoreTav01147(self):
            return self.buyDrink("TAV0114", 7)

        def restStoreTav01140(self):
            return self.rest("TAV0114", 0)

        def restStoreTav01141(self):
            return self.rest("TAV0114", 1)

        def restStoreTav01142(self):
            return self.rest("TAV0114", 2)

        def canUseStoreTem0132(self):
            return self.canUseStore("TEM0132")

        def buyStoreTem01320(self):
            return self.buyStock("TEM0132", 0)

        def buyStoreTem01321(self):
            return self.buyStock("TEM0132", 1)

        def buyStoreTem01322(self):
            return self.buyStock("TEM0132", 2)

        def buyStoreTem01323(self):
            return self.buyStock("TEM0132", 3)

        def buyStoreTem01324(self):
            return self.buyStock("TEM0132", 4)

        def identifyStoreTem0132(self):
            return self.identify("TEM0132")

        def canUseStoreSto0703(self):
            return self.canUseStore("STO0703")

        def buyStoreSto07030(self):
            return self.buyStock("STO0703", 0)

        def buyStoreSto07031(self):
            return self.buyStock("STO0703", 1)

        def buyStoreSto07032(self):
            return self.buyStock("STO0703", 2)

        def buyStoreSto07033(self):
            return self.buyStock("STO0703", 3)

        def buyStoreSto07034(self):
            return self.buyStock("STO0703", 4)

        def buyStoreSto07035(self):
            return self.buyStock("STO0703", 5)

        def buyStoreSto07036(self):
            return self.buyStock("STO0703", 6)

        def buyStoreSto07037(self):
            return self.buyStock("STO0703", 7)

        def buyStoreSto07038(self):
            return self.buyStock("STO0703", 8)

        def buyStoreSto07039(self):
            return self.buyStock("STO0703", 9)

        def buyStoreSto070310(self):
            return self.buyStock("STO0703", 10)

        def buyStoreSto070311(self):
            return self.buyStock("STO0703", 11)

        def buyStoreSto070312(self):
            return self.buyStock("STO0703", 12)

        def buyStoreSto070313(self):
            return self.buyStock("STO0703", 13)

        def buyStoreSto070314(self):
            return self.buyStock("STO0703", 14)

        def buyStoreSto070315(self):
            return self.buyStock("STO0703", 15)

        def buyStoreSto070316(self):
            return self.buyStock("STO0703", 16)

        def buyStoreSto070317(self):
            return self.buyStock("STO0703", 17)

        def buyStoreSto070318(self):
            return self.buyStock("STO0703", 18)

        def buyStoreSto070319(self):
            return self.buyStock("STO0703", 19)

        def buyStoreSto070320(self):
            return self.buyStock("STO0703", 20)

        def buyStoreSto070321(self):
            return self.buyStock("STO0703", 21)

        def buyStoreSto070322(self):
            return self.buyStock("STO0703", 22)

        def buyStoreSto070323(self):
            return self.buyStock("STO0703", 23)

        def buyStoreSto070324(self):
            return self.buyStock("STO0703", 24)

        def buyStoreSto070325(self):
            return self.buyStock("STO0703", 25)

        def buyStoreSto070326(self):
            return self.buyStock("STO0703", 26)

        def buyStoreSto070327(self):
            return self.buyStock("STO0703", 27)

        def buyStoreSto070328(self):
            return self.buyStock("STO0703", 28)

        def buyStoreSto070329(self):
            return self.buyStock("STO0703", 29)

        def buyStoreSto070330(self):
            return self.buyStock("STO0703", 30)

        def buyStoreSto070331(self):
            return self.buyStock("STO0703", 31)

        def buyStoreSto070332(self):
            return self.buyStock("STO0703", 32)

        def buyStoreSto070333(self):
            return self.buyStock("STO0703", 33)

        def buyStoreSto070334(self):
            return self.buyStock("STO0703", 34)

        def buyStoreSto070335(self):
            return self.buyStock("STO0703", 35)

        def buyStoreSto070336(self):
            return self.buyStock("STO0703", 36)

        def buyStoreSto070337(self):
            return self.buyStock("STO0703", 37)

        def buyStoreSto070338(self):
            return self.buyStock("STO0703", 38)

        def buyStoreSto070339(self):
            return self.buyStock("STO0703", 39)

        def buyStoreSto070340(self):
            return self.buyStock("STO0703", 40)

        def buyStoreSto070341(self):
            return self.buyStock("STO0703", 41)

        def buyStoreSto070342(self):
            return self.buyStock("STO0703", 42)

        def buyStoreSto070343(self):
            return self.buyStock("STO0703", 43)

        def buyStoreSto070344(self):
            return self.buyStock("STO0703", 44)

        def buyStoreSto070345(self):
            return self.buyStock("STO0703", 45)

        def buyStoreSto070346(self):
            return self.buyStock("STO0703", 46)

        def buyStoreSto070347(self):
            return self.buyStock("STO0703", 47)

        def buyStoreSto070348(self):
            return self.buyStock("STO0703", 48)

        def buyStoreSto070349(self):
            return self.buyStock("STO0703", 49)

        def buyStoreSto070350(self):
            return self.buyStock("STO0703", 50)

        def buyStoreSto070351(self):
            return self.buyStock("STO0703", 51)

        def buyStoreSto070352(self):
            return self.buyStock("STO0703", 52)

        def buyStoreSto070353(self):
            return self.buyStock("STO0703", 53)

        def buyStoreSto070354(self):
            return self.buyStock("STO0703", 54)

        def buyStoreSto070355(self):
            return self.buyStock("STO0703", 55)

        def buyStoreSto070356(self):
            return self.buyStock("STO0703", 56)

        def buyStoreSto070357(self):
            return self.buyStock("STO0703", 57)

        def buyStoreSto070358(self):
            return self.buyStock("STO0703", 58)

        def buyStoreSto070359(self):
            return self.buyStock("STO0703", 59)

        def buyStoreSto070360(self):
            return self.buyStock("STO0703", 60)

        def buyStoreSto070361(self):
            return self.buyStock("STO0703", 61)

        def buyStoreSto070362(self):
            return self.buyStock("STO0703", 62)

        def buyStoreSto070363(self):
            return self.buyStock("STO0703", 63)

        def buyStoreSto070364(self):
            return self.buyStock("STO0703", 64)

        def buyStoreSto070365(self):
            return self.buyStock("STO0703", 65)

        def buyStoreSto070366(self):
            return self.buyStock("STO0703", 66)

        def buyStoreSto070367(self):
            return self.buyStock("STO0703", 67)

        def buyStoreSto070368(self):
            return self.buyStock("STO0703", 68)

        def buyStoreSto070369(self):
            return self.buyStock("STO0703", 69)

        def buyStoreSto070370(self):
            return self.buyStock("STO0703", 70)

        def buyStoreSto070371(self):
            return self.buyStock("STO0703", 71)

        def buyStoreSto070372(self):
            return self.buyStock("STO0703", 72)

        def buyStoreSto070373(self):
            return self.buyStock("STO0703", 73)

        def buyStoreSto070374(self):
            return self.buyStock("STO0703", 74)

        def buyStoreSto070375(self):
            return self.buyStock("STO0703", 75)

        def buyStoreSto070376(self):
            return self.buyStock("STO0703", 76)

        def buyStoreSto070377(self):
            return self.buyStock("STO0703", 77)

        def buyStoreSto070378(self):
            return self.buyStock("STO0703", 78)

        def buyStoreSto070379(self):
            return self.buyStock("STO0703", 79)

        def buyStoreSto070380(self):
            return self.buyStock("STO0703", 80)

        def buyStoreSto070381(self):
            return self.buyStock("STO0703", 81)

        def buyStoreSto070382(self):
            return self.buyStock("STO0703", 82)

        def buyStoreSto070383(self):
            return self.buyStock("STO0703", 83)

        def buyStoreSto070384(self):
            return self.buyStock("STO0703", 84)

        def buyStoreSto070385(self):
            return self.buyStock("STO0703", 85)

        def buyStoreSto070386(self):
            return self.buyStock("STO0703", 86)

        def buyStoreSto070387(self):
            return self.buyStock("STO0703", 87)

        def buyStoreSto070388(self):
            return self.buyStock("STO0703", 88)

        def buyStoreSto070389(self):
            return self.buyStock("STO0703", 89)

        def buyStoreSto070390(self):
            return self.buyStock("STO0703", 90)

        def buyStoreSto070391(self):
            return self.buyStock("STO0703", 91)

        def buyStoreSto070392(self):
            return self.buyStock("STO0703", 92)

        def buyStoreSto070393(self):
            return self.buyStock("STO0703", 93)

        def buyStoreSto070394(self):
            return self.buyStock("STO0703", 94)

        def buyStoreSto070395(self):
            return self.buyStock("STO0703", 95)

        def buyStoreSto070396(self):
            return self.buyStock("STO0703", 96)

        def buyStoreSto070397(self):
            return self.buyStock("STO0703", 97)

        def buyStoreSto070398(self):
            return self.buyStock("STO0703", 98)

        def buyStoreSto070399(self):
            return self.buyStock("STO0703", 99)

        def buyStoreSto0703100(self):
            return self.buyStock("STO0703", 100)

        def buyStoreSto0703101(self):
            return self.buyStock("STO0703", 101)

        def buyStoreSto0703102(self):
            return self.buyStock("STO0703", 102)

        def buyStoreSto0703103(self):
            return self.buyStock("STO0703", 103)

        def buyStoreSto0703104(self):
            return self.buyStock("STO0703", 104)

        def buyStoreSto0703105(self):
            return self.buyStock("STO0703", 105)

        def buyStoreSto0703106(self):
            return self.buyStock("STO0703", 106)

        def buyStoreSto0703107(self):
            return self.buyStock("STO0703", 107)

        def buyStoreSto0703108(self):
            return self.buyStock("STO0703", 108)

        def buyStoreSto0703109(self):
            return self.buyStock("STO0703", 109)

        def buyStoreSto0703110(self):
            return self.buyStock("STO0703", 110)

        def buyStoreSto0703111(self):
            return self.buyStock("STO0703", 111)

        def buyStoreSto0703112(self):
            return self.buyStock("STO0703", 112)

        def buyStoreSto0703113(self):
            return self.buyStock("STO0703", 113)

        def buyStoreSto0703114(self):
            return self.buyStock("STO0703", 114)

        def buyStoreSto0703115(self):
            return self.buyStock("STO0703", 115)

        def buyStoreSto0703116(self):
            return self.buyStock("STO0703", 116)

        def buyStoreSto0703117(self):
            return self.buyStock("STO0703", 117)

        def buyStoreSto0703118(self):
            return self.buyStock("STO0703", 118)

        def buyStoreSto0703119(self):
            return self.buyStock("STO0703", 119)

        def buyStoreSto0703120(self):
            return self.buyStock("STO0703", 120)

        def buyStoreSto0703121(self):
            return self.buyStock("STO0703", 121)

        def buyStoreSto0703122(self):
            return self.buyStock("STO0703", 122)

        def buyStoreSto0703123(self):
            return self.buyStock("STO0703", 123)

        def buyStoreSto0703124(self):
            return self.buyStock("STO0703", 124)

        def buyStoreSto0703125(self):
            return self.buyStock("STO0703", 125)

        def buyStoreSto0703126(self):
            return self.buyStock("STO0703", 126)

        def buyStoreSto0703127(self):
            return self.buyStock("STO0703", 127)

        def buyStoreSto0703128(self):
            return self.buyStock("STO0703", 128)

        def buyStoreSto0703129(self):
            return self.buyStock("STO0703", 129)

        def buyStoreSto0703130(self):
            return self.buyStock("STO0703", 130)

        def buyStoreSto0703131(self):
            return self.buyStock("STO0703", 131)

        def buyStoreSto0703132(self):
            return self.buyStock("STO0703", 132)

        def buyStoreSto0703133(self):
            return self.buyStock("STO0703", 133)

        def buyStoreSto0703134(self):
            return self.buyStock("STO0703", 134)

        def buyStoreSto0703135(self):
            return self.buyStock("STO0703", 135)

        def buyStoreSto0703136(self):
            return self.buyStock("STO0703", 136)

        def buyStoreSto0703137(self):
            return self.buyStock("STO0703", 137)

        def buyStoreSto0703138(self):
            return self.buyStock("STO0703", 138)

        def buyStoreSto0703139(self):
            return self.buyStock("STO0703", 139)

        def buyStoreSto0703140(self):
            return self.buyStock("STO0703", 140)

        def buyStoreSto0703141(self):
            return self.buyStock("STO0703", 141)

        def buyStoreSto0703142(self):
            return self.buyStock("STO0703", 142)

        def buyStoreSto0703143(self):
            return self.buyStock("STO0703", 143)

        def buyStoreSto0703144(self):
            return self.buyStock("STO0703", 144)

        def buyStoreSto0703145(self):
            return self.buyStock("STO0703", 145)

        def buyStoreSto0703146(self):
            return self.buyStock("STO0703", 146)

        def buyStoreSto0703147(self):
            return self.buyStock("STO0703", 147)

        def buyStoreSto0703148(self):
            return self.buyStock("STO0703", 148)

        def buyStoreSto0703149(self):
            return self.buyStock("STO0703", 149)

        def identifyStoreSto0703(self):
            return self.identify("STO0703")

        def canUseStoreInn0105(self):
            return self.canUseStore("INN0105")

        def drinkStoreInn01050(self):
            return self.buyDrink("INN0105", 0)

        def drinkStoreInn01051(self):
            return self.buyDrink("INN0105", 1)

        def drinkStoreInn01052(self):
            return self.buyDrink("INN0105", 2)

        def drinkStoreInn01053(self):
            return self.buyDrink("INN0105", 3)

        def drinkStoreInn01054(self):
            return self.buyDrink("INN0105", 4)

        def drinkStoreInn01055(self):
            return self.buyDrink("INN0105", 5)

        def restStoreInn01050(self):
            return self.rest("INN0105", 0)

        def restStoreInn01051(self):
            return self.rest("INN0105", 1)

        def restStoreInn01052(self):
            return self.rest("INN0105", 2)

        def restStoreInn01053(self):
            return self.rest("INN0105", 3)

        def canUseStoreStocheap(self):
            return self.canUseStore("STOCHEAP")

        def buyStoreStocheap0(self):
            return self.buyStock("STOCHEAP", 0)

        def buyStoreStocheap1(self):
            return self.buyStock("STOCHEAP", 1)

        def buyStoreStocheap2(self):
            return self.buyStock("STOCHEAP", 2)

        def buyStoreStocheap3(self):
            return self.buyStock("STOCHEAP", 3)

        def buyStoreStocheap4(self):
            return self.buyStock("STOCHEAP", 4)

        def buyStoreStocheap5(self):
            return self.buyStock("STOCHEAP", 5)

        def buyStoreStocheap6(self):
            return self.buyStock("STOCHEAP", 6)

        def buyStoreStocheap7(self):
            return self.buyStock("STOCHEAP", 7)

        def buyStoreStocheap8(self):
            return self.buyStock("STOCHEAP", 8)

        def buyStoreStocheap9(self):
            return self.buyStock("STOCHEAP", 9)

        def buyStoreStocheap10(self):
            return self.buyStock("STOCHEAP", 10)

        def buyStoreStocheap11(self):
            return self.buyStock("STOCHEAP", 11)

        def buyStoreStocheap12(self):
            return self.buyStock("STOCHEAP", 12)

        def buyStoreStocheap13(self):
            return self.buyStock("STOCHEAP", 13)

        def identifyStoreStocheap(self):
            return self.identify("STOCHEAP")

        def canUseStoreTav0810(self):
            return self.canUseStore("TAV0810")

        def buyStoreTav08100(self):
            return self.buyStock("TAV0810", 0)

        def buyStoreTav08101(self):
            return self.buyStock("TAV0810", 1)

        def buyStoreTav08102(self):
            return self.buyStock("TAV0810", 2)

        def buyStoreTav08103(self):
            return self.buyStock("TAV0810", 3)

        def buyStoreTav08104(self):
            return self.buyStock("TAV0810", 4)

        def buyStoreTav08105(self):
            return self.buyStock("TAV0810", 5)

        def buyStoreTav08106(self):
            return self.buyStock("TAV0810", 6)

        def buyStoreTav08107(self):
            return self.buyStock("TAV0810", 7)

        def buyStoreTav08108(self):
            return self.buyStock("TAV0810", 8)

        def buyStoreTav08109(self):
            return self.buyStock("TAV0810", 9)

        def buyStoreTav081010(self):
            return self.buyStock("TAV0810", 10)

        def buyStoreTav081011(self):
            return self.buyStock("TAV0810", 11)

        def buyStoreTav081012(self):
            return self.buyStock("TAV0810", 12)

        def buyStoreTav081013(self):
            return self.buyStock("TAV0810", 13)

        def buyStoreTav081014(self):
            return self.buyStock("TAV0810", 14)

        def buyStoreTav081015(self):
            return self.buyStock("TAV0810", 15)

        def buyStoreTav081016(self):
            return self.buyStock("TAV0810", 16)

        def buyStoreTav081017(self):
            return self.buyStock("TAV0810", 17)

        def buyStoreTav081018(self):
            return self.buyStock("TAV0810", 18)

        def buyStoreTav081019(self):
            return self.buyStock("TAV0810", 19)

        def buyStoreTav081020(self):
            return self.buyStock("TAV0810", 20)

        def buyStoreTav081021(self):
            return self.buyStock("TAV0810", 21)

        def buyStoreTav081022(self):
            return self.buyStock("TAV0810", 22)

        def buyStoreTav081023(self):
            return self.buyStock("TAV0810", 23)

        def buyStoreTav081024(self):
            return self.buyStock("TAV0810", 24)

        def identifyStoreTav0810(self):
            return self.identify("TAV0810")

        def canUseStoreSto0706(self):
            return self.canUseStore("STO0706")

        def buyStoreSto07060(self):
            return self.buyStock("STO0706", 0)

        def buyStoreSto07061(self):
            return self.buyStock("STO0706", 1)

        def buyStoreSto07062(self):
            return self.buyStock("STO0706", 2)

        def buyStoreSto07063(self):
            return self.buyStock("STO0706", 3)

        def buyStoreSto07064(self):
            return self.buyStock("STO0706", 4)

        def buyStoreSto07065(self):
            return self.buyStock("STO0706", 5)

        def buyStoreSto07066(self):
            return self.buyStock("STO0706", 6)

        def buyStoreSto07067(self):
            return self.buyStock("STO0706", 7)

        def buyStoreSto07068(self):
            return self.buyStock("STO0706", 8)

        def identifyStoreSto0706(self):
            return self.identify("STO0706")

        def canUseStoreInn0119(self):
            return self.canUseStore("INN0119")

        def drinkStoreInn01190(self):
            return self.buyDrink("INN0119", 0)

        def drinkStoreInn01191(self):
            return self.buyDrink("INN0119", 1)

        def drinkStoreInn01192(self):
            return self.buyDrink("INN0119", 2)

        def drinkStoreInn01193(self):
            return self.buyDrink("INN0119", 3)

        def restStoreInn01190(self):
            return self.rest("INN0119", 0)

        def restStoreInn01191(self):
            return self.rest("INN0119", 1)

        def restStoreInn01192(self):
            return self.rest("INN0119", 2)

        def restStoreInn01193(self):
            return self.rest("INN0119", 3)

        def canUseStoreTem0131(self):
            return self.canUseStore("TEM0131")

        def buyStoreTem01310(self):
            return self.buyStock("TEM0131", 0)

        def buyStoreTem01311(self):
            return self.buyStock("TEM0131", 1)

        def buyStoreTem01312(self):
            return self.buyStock("TEM0131", 2)

        def buyStoreTem01313(self):
            return self.buyStock("TEM0131", 3)

        def buyStoreTem01314(self):
            return self.buyStock("TEM0131", 4)

        def serviceStoreTem01310(self):
            return self.buyService("TEM0131", 0)

        def serviceStoreTem01311(self):
            return self.buyService("TEM0131", 1)

        def serviceStoreTem01312(self):
            return self.buyService("TEM0131", 2)

        def serviceStoreTem01313(self):
            return self.buyService("TEM0131", 3)

        def serviceStoreTem01314(self):
            return self.buyService("TEM0131", 4)

        def serviceStoreTem01315(self):
            return self.buyService("TEM0131", 5)

        def identifyStoreTem0131(self):
            return self.identify("TEM0131")

        def canUseStoreTem0002(self):
            return self.canUseStore("TEM0002")

        def buyStoreTem00020(self):
            return self.buyStock("TEM0002", 0)

        def buyStoreTem00021(self):
            return self.buyStock("TEM0002", 1)

        def buyStoreTem00022(self):
            return self.buyStock("TEM0002", 2)

        def buyStoreTem00023(self):
            return self.buyStock("TEM0002", 3)

        def serviceStoreTem00020(self):
            return self.buyService("TEM0002", 0)

        def serviceStoreTem00021(self):
            return self.buyService("TEM0002", 1)

        def serviceStoreTem00022(self):
            return self.buyService("TEM0002", 2)

        def serviceStoreTem00023(self):
            return self.buyService("TEM0002", 3)

        def serviceStoreTem00024(self):
            return self.buyService("TEM0002", 4)

        def serviceStoreTem00025(self):
            return self.buyService("TEM0002", 5)

        def identifyStoreTem0002(self):
            return self.identify("TEM0002")

        def canUseStoreTav0809(self):
            return self.canUseStore("TAV0809")

        def buyStoreTav08090(self):
            return self.buyStock("TAV0809", 0)

        def buyStoreTav08091(self):
            return self.buyStock("TAV0809", 1)

        def buyStoreTav08092(self):
            return self.buyStock("TAV0809", 2)

        def buyStoreTav08093(self):
            return self.buyStock("TAV0809", 3)

        def buyStoreTav08094(self):
            return self.buyStock("TAV0809", 4)

        def buyStoreTav08095(self):
            return self.buyStock("TAV0809", 5)

        def buyStoreTav08096(self):
            return self.buyStock("TAV0809", 6)

        def buyStoreTav08097(self):
            return self.buyStock("TAV0809", 7)

        def buyStoreTav08098(self):
            return self.buyStock("TAV0809", 8)

        def identifyStoreTav0809(self):
            return self.identify("TAV0809")

        def canUseStoreSto1112(self):
            return self.canUseStore("STO1112")

        def buyStoreSto11120(self):
            return self.buyStock("STO1112", 0)

        def buyStoreSto11121(self):
            return self.buyStock("STO1112", 1)

        def buyStoreSto11122(self):
            return self.buyStock("STO1112", 2)

        def buyStoreSto11123(self):
            return self.buyStock("STO1112", 3)

        def buyStoreSto11124(self):
            return self.buyStock("STO1112", 4)

        def buyStoreSto11125(self):
            return self.buyStock("STO1112", 5)

        def buyStoreSto11126(self):
            return self.buyStock("STO1112", 6)

        def buyStoreSto11127(self):
            return self.buyStock("STO1112", 7)

        def buyStoreSto11128(self):
            return self.buyStock("STO1112", 8)

        def buyStoreSto11129(self):
            return self.buyStock("STO1112", 9)

        def buyStoreSto111210(self):
            return self.buyStock("STO1112", 10)

        def buyStoreSto111211(self):
            return self.buyStock("STO1112", 11)

        def buyStoreSto111212(self):
            return self.buyStock("STO1112", 12)

        def buyStoreSto111213(self):
            return self.buyStock("STO1112", 13)

        def buyStoreSto111214(self):
            return self.buyStock("STO1112", 14)

        def buyStoreSto111215(self):
            return self.buyStock("STO1112", 15)

        def buyStoreSto111216(self):
            return self.buyStock("STO1112", 16)

        def buyStoreSto111217(self):
            return self.buyStock("STO1112", 17)

        def buyStoreSto111218(self):
            return self.buyStock("STO1112", 18)

        def buyStoreSto111219(self):
            return self.buyStock("STO1112", 19)

        def buyStoreSto111220(self):
            return self.buyStock("STO1112", 20)

        def buyStoreSto111221(self):
            return self.buyStock("STO1112", 21)

        def buyStoreSto111222(self):
            return self.buyStock("STO1112", 22)

        def buyStoreSto111223(self):
            return self.buyStock("STO1112", 23)

        def buyStoreSto111224(self):
            return self.buyStock("STO1112", 24)

        def buyStoreSto111225(self):
            return self.buyStock("STO1112", 25)

        def buyStoreSto111226(self):
            return self.buyStock("STO1112", 26)

        def identifyStoreSto1112(self):
            return self.identify("STO1112")

        def canUseStoreSto1115(self):
            return self.canUseStore("STO1115")

        def buyStoreSto11150(self):
            return self.buyStock("STO1115", 0)

        def buyStoreSto11151(self):
            return self.buyStock("STO1115", 1)

        def buyStoreSto11152(self):
            return self.buyStock("STO1115", 2)

        def buyStoreSto11153(self):
            return self.buyStock("STO1115", 3)

        def buyStoreSto11154(self):
            return self.buyStock("STO1115", 4)

        def buyStoreSto11155(self):
            return self.buyStock("STO1115", 5)

        def buyStoreSto11156(self):
            return self.buyStock("STO1115", 6)

        def buyStoreSto11157(self):
            return self.buyStock("STO1115", 7)

        def buyStoreSto11158(self):
            return self.buyStock("STO1115", 8)

        def buyStoreSto11159(self):
            return self.buyStock("STO1115", 9)

        def buyStoreSto111510(self):
            return self.buyStock("STO1115", 10)

        def buyStoreSto111511(self):
            return self.buyStock("STO1115", 11)

        def buyStoreSto111512(self):
            return self.buyStock("STO1115", 12)

        def buyStoreSto111513(self):
            return self.buyStock("STO1115", 13)

        def buyStoreSto111514(self):
            return self.buyStock("STO1115", 14)

        def buyStoreSto111515(self):
            return self.buyStock("STO1115", 15)

        def buyStoreSto111516(self):
            return self.buyStock("STO1115", 16)

        def buyStoreSto111517(self):
            return self.buyStock("STO1115", 17)

        def buyStoreSto111518(self):
            return self.buyStock("STO1115", 18)

        def buyStoreSto111519(self):
            return self.buyStock("STO1115", 19)

        def buyStoreSto111520(self):
            return self.buyStock("STO1115", 20)

        def buyStoreSto111521(self):
            return self.buyStock("STO1115", 21)

        def buyStoreSto111522(self):
            return self.buyStock("STO1115", 22)

        def buyStoreSto111523(self):
            return self.buyStock("STO1115", 23)

        def identifyStoreSto1115(self):
            return self.identify("STO1115")

        def canUseStoreSto1116(self):
            return self.canUseStore("STO1116")

        def buyStoreSto11160(self):
            return self.buyStock("STO1116", 0)

        def buyStoreSto11161(self):
            return self.buyStock("STO1116", 1)

        def buyStoreSto11162(self):
            return self.buyStock("STO1116", 2)

        def buyStoreSto11163(self):
            return self.buyStock("STO1116", 3)

        def buyStoreSto11164(self):
            return self.buyStock("STO1116", 4)

        def buyStoreSto11165(self):
            return self.buyStock("STO1116", 5)

        def buyStoreSto11166(self):
            return self.buyStock("STO1116", 6)

        def buyStoreSto11167(self):
            return self.buyStock("STO1116", 7)

        def buyStoreSto11168(self):
            return self.buyStock("STO1116", 8)

        def buyStoreSto11169(self):
            return self.buyStock("STO1116", 9)

        def buyStoreSto111610(self):
            return self.buyStock("STO1116", 10)

        def buyStoreSto111611(self):
            return self.buyStock("STO1116", 11)

        def buyStoreSto111612(self):
            return self.buyStock("STO1116", 12)

        def canUseStoreSto1320(self):
            return self.canUseStore("STO1320")

        def buyStoreSto13200(self):
            return self.buyStock("STO1320", 0)

        def buyStoreSto13201(self):
            return self.buyStock("STO1320", 1)

        def buyStoreSto13202(self):
            return self.buyStock("STO1320", 2)

        def buyStoreSto13203(self):
            return self.buyStock("STO1320", 3)

        def buyStoreSto13204(self):
            return self.buyStock("STO1320", 4)

        def buyStoreSto13205(self):
            return self.buyStock("STO1320", 5)

        def buyStoreSto13206(self):
            return self.buyStock("STO1320", 6)

        def buyStoreSto13207(self):
            return self.buyStock("STO1320", 7)

        def buyStoreSto13208(self):
            return self.buyStock("STO1320", 8)

        def buyStoreSto13209(self):
            return self.buyStock("STO1320", 9)

        def buyStoreSto132010(self):
            return self.buyStock("STO1320", 10)

        def buyStoreSto132011(self):
            return self.buyStock("STO1320", 11)

        def buyStoreSto132012(self):
            return self.buyStock("STO1320", 12)

        def buyStoreSto132013(self):
            return self.buyStock("STO1320", 13)

        def buyStoreSto132014(self):
            return self.buyStock("STO1320", 14)

        def buyStoreSto132015(self):
            return self.buyStock("STO1320", 15)

        def buyStoreSto132016(self):
            return self.buyStock("STO1320", 16)

        def buyStoreSto132017(self):
            return self.buyStock("STO1320", 17)

        def buyStoreSto132018(self):
            return self.buyStock("STO1320", 18)

        def buyStoreSto132019(self):
            return self.buyStock("STO1320", 19)

        def buyStoreSto132020(self):
            return self.buyStock("STO1320", 20)

        def buyStoreSto132021(self):
            return self.buyStock("STO1320", 21)

        def buyStoreSto132022(self):
            return self.buyStock("STO1320", 22)

        def buyStoreSto132023(self):
            return self.buyStock("STO1320", 23)

        def identifyStoreSto1320(self):
            return self.identify("STO1320")

        def canUseStoreSto1117(self):
            return self.canUseStore("STO1117")

        def buyStoreSto11170(self):
            return self.buyStock("STO1117", 0)

        def buyStoreSto11171(self):
            return self.buyStock("STO1117", 1)

        def buyStoreSto11172(self):
            return self.buyStock("STO1117", 2)

        def buyStoreSto11173(self):
            return self.buyStock("STO1117", 3)

        def buyStoreSto11174(self):
            return self.buyStock("STO1117", 4)

        def buyStoreSto11175(self):
            return self.buyStock("STO1117", 5)

        def buyStoreSto11176(self):
            return self.buyStock("STO1117", 6)

        def identifyStoreSto1117(self):
            return self.identify("STO1117")

        def canUseStoreSto1302(self):
            return self.canUseStore("STO1302")

        def buyStoreSto13020(self):
            return self.buyStock("STO1302", 0)

        def buyStoreSto13021(self):
            return self.buyStock("STO1302", 1)

        def buyStoreSto13022(self):
            return self.buyStock("STO1302", 2)

        def buyStoreSto13023(self):
            return self.buyStock("STO1302", 3)

        def buyStoreSto13024(self):
            return self.buyStock("STO1302", 4)

        def buyStoreSto13025(self):
            return self.buyStock("STO1302", 5)

        def buyStoreSto13026(self):
            return self.buyStock("STO1302", 6)

        def buyStoreSto13027(self):
            return self.buyStock("STO1302", 7)

        def buyStoreSto13028(self):
            return self.buyStock("STO1302", 8)

        def buyStoreSto13029(self):
            return self.buyStock("STO1302", 9)

        def buyStoreSto130210(self):
            return self.buyStock("STO1302", 10)

        def buyStoreSto130211(self):
            return self.buyStock("STO1302", 11)

        def buyStoreSto130212(self):
            return self.buyStock("STO1302", 12)

        def identifyStoreSto1302(self):
            return self.identify("STO1302")

        def canUseStoreStosilen(self):
            return self.canUseStore("STOSILEN")

        def buyStoreStosilen0(self):
            return self.buyStock("STOSILEN", 0)

        def buyStoreStosilen1(self):
            return self.buyStock("STOSILEN", 1)

        def buyStoreStosilen2(self):
            return self.buyStock("STOSILEN", 2)

        def buyStoreStosilen3(self):
            return self.buyStock("STOSILEN", 3)

        def buyStoreStosilen4(self):
            return self.buyStock("STOSILEN", 4)

        def buyStoreStosilen5(self):
            return self.buyStock("STOSILEN", 5)

        def buyStoreStosilen6(self):
            return self.buyStock("STOSILEN", 6)

        def buyStoreStosilen7(self):
            return self.buyStock("STOSILEN", 7)

        def buyStoreStosilen8(self):
            return self.buyStock("STOSILEN", 8)

        def buyStoreStosilen9(self):
            return self.buyStock("STOSILEN", 9)

        def buyStoreStosilen10(self):
            return self.buyStock("STOSILEN", 10)

        def buyStoreStosilen11(self):
            return self.buyStock("STOSILEN", 11)

        def buyStoreStosilen12(self):
            return self.buyStock("STOSILEN", 12)

        def buyStoreStosilen13(self):
            return self.buyStock("STOSILEN", 13)

        def buyStoreStosilen14(self):
            return self.buyStock("STOSILEN", 14)

        def buyStoreStosilen15(self):
            return self.buyStock("STOSILEN", 15)

        def buyStoreStosilen16(self):
            return self.buyStock("STOSILEN", 16)

        def buyStoreStosilen17(self):
            return self.buyStock("STOSILEN", 17)

        def restStoreStosilen0(self):
            return self.rest("STOSILEN", 0)

        def canUseStoreTem2601(self):
            return self.canUseStore("TEM2601")

        def buyStoreTem26010(self):
            return self.buyStock("TEM2601", 0)

        def buyStoreTem26011(self):
            return self.buyStock("TEM2601", 1)

        def buyStoreTem26012(self):
            return self.buyStock("TEM2601", 2)

        def buyStoreTem26013(self):
            return self.buyStock("TEM2601", 3)

        def serviceStoreTem26010(self):
            return self.buyService("TEM2601", 0)

        def serviceStoreTem26011(self):
            return self.buyService("TEM2601", 1)

        def serviceStoreTem26012(self):
            return self.buyService("TEM2601", 2)

        def serviceStoreTem26013(self):
            return self.buyService("TEM2601", 3)

        def serviceStoreTem26014(self):
            return self.buyService("TEM2601", 4)

        def serviceStoreTem26015(self):
            return self.buyService("TEM2601", 5)

        def identifyStoreTem2601(self):
            return self.identify("TEM2601")

        # QUEST_CALLBACKS_END

    @register(context)
    class BaldursGatePersonTrigger(CTrigger):
        @resumableHook
        def trigger(self, actor, event):
            if event and event.getCause() and event.getCause().isPlayer():
                if clock(actor).getBoolProperty("plugin_cityPoisonSourceEnabled") and actor.getBoolProperty(
                    "plugin_cityPoisonManaged"
                ):
                    dialog = clock(actor).poisonMakeActorDialog(actor)
                else:
                    dialog = actor.getGame().createObject(actor.getName() + "Dialog")
                yield uiRequest("gui.showDialog", dialog)

    @register(context)
    class BaldursGateDeathTrigger(CTrigger):
        @resumableHook
        def trigger(self, actor, event):
            if actor.isAlive():
                return
            owner, game_map = clock(actor), world(actor)
            if owner.getBoolProperty("plugin_cityPoisonSourceEnabled"):
                owner.poisonRecordDeath(actor)
            if not claim_once(game_map, "plugin_cityDeath_" + actor.getName()):
                return
            records = read(game_map, "plugin_cityDeaths", {})
            records[actor.getName()] = actorRecord(actor)
            write(game_map, "plugin_cityDeaths", records)
            owner.setObjectProperty("plugin_cityCorpse_" + actor.getName(), actor)
            if owner.getBoolProperty("plugin_cityPoisonSourceEnabled"):
                owner.observePoisonAcquisition()
            plot_execution = actor.getBoolProperty("plugin_cityPlotExecution")
            if not plot_execution:
                game_map.setBoolProperty("plugin_cityCombatObserved_" + actor.getStringProperty("sourceArea"), True)
            if not plot_execution and "flaming fist" in actor.getStringProperty("label").casefold():
                game_map.setNumericProperty(
                    "plugin_cityGuardKills", game_map.getNumericProperty("plugin_cityGuardKills") + 1
                )
            if (
                actor.getStringProperty("sourceArea") == "AR0125"
                and actor.getStringProperty("label").casefold() == "sarevok"
                and game_map.getBoolProperty("plugin_cityFlag_palaceCleared")
            ):
                setStage(actor, "sarevokFinale", "completed")
                if not game_map.getBoolProperty("plugin_cityFlag_cityCompleted"):
                    game_map.setBoolProperty("plugin_cityFlag_cityCompleted", True)
                    existing = tuple(hero(actor).getQuests()) + tuple(hero(actor).getCompletedQuests())
                    if not any(entry.getTypeId() == questId("sarevokFinale") for entry in existing):
                        hero(actor).addQuest(questId("sarevokFinale"))
                    yield uiRequest("gui.checkQuests", hero(actor))
                    yield uiRequest(
                        "showReader",
                        flowGame(actor.getGame()),
                        "Sarevok has fallen",
                        "The Temple of Bhaal is silent. Your city adventure is complete. "
                        "Your saved journal records the choices and the companions who survived.",
                    )

    @register(context)
    class BaldursGateClock(CBuilding):
        class PoisonBindingChanged(RuntimeError):
            pass

        def poisonCapture(self):
            from game import CGame, CGameObject, CMap, CMapObject, CPlayer

            game = self.getGame()
            game_map = CGame.getMap(game)
            player = CMap.getAssignedPlayer(game_map)
            context = game.getContext()
            binding = {
                "game": flowGame(game),
                "map": game_map,
                "player": player,
                "context": context,
                "epoch": CGame.getMapBindingEpoch(game),
                "generation": context.getTransitionGeneration(),
                "gameClass": CGame,
                "objectClass": CGameObject,
                "mapClass": CMap,
                "mapObjectClass": CMapObject,
                "playerClass": CPlayer,
                "stateText": CGameObject.getStringProperty(self, "plugin_cityPoisonSourceState"),
                "definitionText": CGameObject.getStringProperty(self, "poisonSourceDefinitions"),
                "authoredText": CGameObject.getStringProperty(self, "poisonAuthoredText"),
                "enabled": CGameObject.getBoolProperty(self, "plugin_cityPoisonSourceEnabled"),
                "atlasText": CGameObject.getStringProperty(self, "areaAtlas"),
                "actorText": CGameObject.getStringProperty(self, "actorDefinitions"),
                "rosterText": CGameObject.getStringProperty(self, "plugin_cityRoster"),
            }
            self.poisonRequire(binding)
            return binding

        def poisonRequire(self, binding):
            game = binding["game"].resolve()
            native, native_map = binding["objectClass"], binding["mapClass"]
            player, game_map = binding["player"], binding["map"]
            if (
                not game
                or binding["gameClass"].getMapBindingEpoch(game) != binding["epoch"]
                or binding["gameClass"].getMap(game) is not game_map
                or game.getContext() is not binding["context"]
                or not binding["context"].isTransitionGenerationCurrent(binding["generation"])
                or not isinstance(player, binding["playerClass"])
                or native_map.getAssignedPlayer(game_map) is not player
                or native_map.getObjectByName(game_map, "player") is not player
                or native_map.getObjectByName(game_map, "cityClock") is not self
                or native.getStringProperty(game_map, "mapName") != "baldursGate"
                or native.getGame(self) is not game
                or binding["mapObjectClass"].getMap(self) is not game_map
                or native.getGame(player) is not game
                or binding["mapObjectClass"].getMap(player) is not game_map
                or not CCreature.isAlive(player)
                or native.getStringProperty(self, "plugin_cityPoisonSourceState") != binding["stateText"]
                or native.getStringProperty(self, "poisonSourceDefinitions") != binding["definitionText"]
                or native.getStringProperty(self, "poisonAuthoredText") != binding["authoredText"]
                or native.getBoolProperty(self, "plugin_cityPoisonSourceEnabled") != binding["enabled"]
                or native.getStringProperty(self, "areaAtlas") != binding["atlasText"]
                or native.getStringProperty(self, "actorDefinitions") != binding["actorText"]
                or native.getStringProperty(self, "plugin_cityRoster") != binding["rosterText"]
            ):
                raise self.PoisonBindingChanged("Poison source operation lost its actual map/player binding")

        def poisonValidateState(self, binding, data):
            if not data.get("sourceVersion"):
                return
            definitions = decodeData(binding["definitionText"] or "{}")
            initial = {row["id"]: row for row in definitions["initialActors"]}
            for identity, row in data["actors"].items():
                expected = CRE_DIALOGUE_BINDINGS.get(row["resource"])
                declared = initial.get(identity)
                if declared is None:
                    declared = definitions["factories"].get(row["resource"])
                    if declared is None:
                        raise self.PoisonBindingChanged("Saved source owner has no authored placement or factory")
                    stem = declared["typeId"]
                    suffix = identity.removeprefix(stem + "Created")
                    serial = 1 if identity == stem else int(suffix) if suffix.isdigit() else 0
                    if serial < 1 or serial > data.get("factorySerials", {}).get(row["resource"], 0):
                        raise self.PoisonBindingChanged("Saved source owner lost its distinct creation serial")
                elif row["resource"] != declared["resource"] or row["lineage"] != declared["sourceActor"]:
                    raise self.PoisonBindingChanged("Saved initial source owner changed its placement lineage")
                if (
                    expected is None
                    or row["scriptName"] != expected[1]
                    or row["sha256"] != expected[2]
                    or row["typeId"] != declared["typeId"]
                    or not row["lineage"]
                    or row["originArea"] != declared["area"]
                ):
                    raise self.PoisonBindingChanged("Saved source owner changed its finite CRE/dialogue binding")
            for alias, proofs in data["deadAliases"].items():
                for proof in proofs:
                    row = data["actors"].get(proof["actorId"])
                    if (
                        row is None
                        or not row["dead"]
                        or row["scriptName"].casefold() != alias
                        or row["lineage"] != proof["lineage"]
                        or row["resource"] != proof["resource"]
                        or row["sha256"] != proof["sha256"]
                        or proof["producer"] != "prospectiveNativeOwnerOnDestroy"
                    ):
                        raise self.PoisonBindingChanged("Saved source death alias changed its genuine owner proof")
            for cursor in data["cursors"].values():
                row = data["actors"].get(cursor["actorId"])
                if (
                    row is None
                    or cursor["lineage"] != row["lineage"]
                    or cursor["resource"] != CRE_DIALOGUE_BINDINGS[row["resource"]][0]
                ):
                    raise self.PoisonBindingChanged("Saved source conversation changed its CRE/dialogue binding")

        def poisonRead(self, binding):
            self.poisonRequire(binding)
            data = decodeData(binding["stateText"] or "{}")
            if not data:
                data = {"schema": 1, "globals": {}, "receipts": {}, "antidoteStock": {}, "journal": []}
            if data.get("schema") != 1:
                raise ValueError("Unsupported poison source state")
            self.poisonValidateState(binding, data)
            if any(row.get("status") == "pending" for row in data["receipts"].values()):
                raise self.PoisonBindingChanged("An uncertain poison effect remains quarantined")
            return data

        def poisonWrite(self, binding, data):
            self.poisonRequire(binding)
            encoded = CITY_JSON_PREFIX + json.dumps(data, separators=(",", ":"))
            binding["stateText"] = encoded
            binding["objectClass"].setStringProperty(self, "plugin_cityPoisonSourceState", encoded)
            self.poisonRequire(binding)

        def poisonItems(self, binding, owner):
            self.poisonRequire(binding)
            items = list(CCreature.getItems(owner))
            for item in CCreature.getEquipped(owner).values():
                if item and not any(candidate is item for candidate in items):
                    items.append(item)
            self.poisonRequire(binding)
            return sorted(items, key=lambda item: binding["objectClass"].getName(item))

        def poisonReadItemData(self, binding, item, key, default):
            self.poisonRequire(binding)
            encoded = binding["objectClass"].getStringProperty(item, key)
            self.poisonRequire(binding)
            return decodeData(encoded or json.dumps(default))

        def poisonWriteItemData(self, binding, item, key, value):
            self.poisonRequire(binding)
            binding["objectClass"].setStringProperty(
                item, key, CITY_JSON_PREFIX + json.dumps(value, separators=(",", ":"))
            )
            self.poisonRequire(binding)

        def poisonRegisterAntidoteStock(self, actor, binding=None, data=None):
            """Called once by the AR0115 source factory after its original inventory is installed."""
            binding = binding if binding is not None else self.poisonCapture()
            native = binding["objectClass"]
            data = data if data is not None else self.poisonRead(binding)
            name = native.getName(actor)
            if (
                not isinstance(actor, CCreature)
                or not CCreature.isAlive(actor)
                or binding["mapClass"].getObjectByName(binding["map"], name) is not actor
                or native.getGame(actor) is not binding["game"].resolve()
                or binding["mapObjectClass"].getMap(actor) is not binding["map"]
                or native.getTypeId(actor) != "cityPoisonMarek1"
                or native.getStringProperty(actor, "sourceCreature") != "MAREK1"
                or native.getStringProperty(actor, "sourceArea") != "AR0115"
                or native.getStringProperty(actor, "sourceDialogue") != "MAREK"
                or native.getStringProperty(actor, "sourceSpawnFact") != "AR0115.BCS#spawn0"
            ):
                raise self.PoisonBindingChanged("Antidote registration requires the genuine source-created MAREK1")
            stock = [
                item
                for item in self.poisonItems(binding, actor)
                if native.getStringProperty(item, "plugin_citySourceItem") == "POTN47"
            ]
            if len(stock) != 1 or self.poisonReadItemData(binding, stock[0], "plugin_cityCharges", []) != [10, 0, 0]:
                raise ValueError("MAREK1 must own exactly one original ten-charge antidote")
            token = "AR0115.BCS#spawn0/MAREK1.CRE/slot6/POTN47"
            if data["antidoteStock"]:
                raise self.PoisonBindingChanged("Antidote source stock has already been registered")
            self.poisonRequire(binding)
            native.setStringProperty(stock[0], "plugin_cityPoisonCreation", token)
            self.poisonRequire(binding)
            data["antidoteStock"][token] = {"actorId": name, "sourceSpawnFact": "AR0115.BCS#spawn0", "slot": 6}
            self.poisonWrite(binding, data)
            return stock[0]

        def poisonPartyOwners(self, binding):
            """Native conversion: Player1 is the hero; source Player2..6 are saved roster slots0..4."""
            self.poisonRequire(binding)
            party = [binding["player"]]
            roster = decodeData(binding["rosterText"] or "[]")
            for name in roster[:5]:
                member = binding["objectClass"].getObjectProperty(self, "plugin_cityCompanion_" + name)
                self.poisonRequire(binding)
                if member:
                    native = binding["objectClass"]
                    if (
                        not isinstance(member, CCreature)
                        or native.getGame(member) is not binding["game"].resolve()
                        or binding["mapObjectClass"].getMap(member) is not binding["map"]
                        or binding["mapClass"].getObjectByName(binding["map"], native.getName(member)) is not member
                    ):
                        raise self.PoisonBindingChanged("Source party slot changed")
                    if any(candidate is member for candidate in party):
                        raise ValueError("Duplicate source party slot")
                    party.append(member)
            return party

        def poisonRemoveOwnedItem(self, binding, owner, item):
            """Inventory-only: never accept an equal name or manufacture a replacement object."""
            if not any(candidate is item for candidate in self.poisonItems(binding, owner)):
                raise self.PoisonBindingChanged("The actual source item is no longer owned by its transfer donor")
            for slot, candidate in CCreature.getEquipped(owner).items():
                if candidate is item:
                    self.poisonRequire(binding)
                    CCreature.equipItem(owner, slot, None)
                    self.poisonRequire(binding)

            def matches(candidate):
                self.poisonRequire(binding)
                return candidate is item

            self.poisonRequire(binding)
            CCreature.removeQuestItem(owner, matches)
            self.poisonRequire(binding)
            if any(candidate is item for candidate in self.poisonItems(binding, owner)):
                raise self.PoisonBindingChanged("Source item removal did not commit")

        def poisonOwnedAntidote(self, binding, data):
            native = binding["objectClass"]
            inventory = self.poisonItems(binding, binding["player"])
            candidates = [
                item for item in inventory if native.getStringProperty(item, "plugin_citySourceItem") == "POTN47"
            ]
            self.poisonRequire(binding)
            if not candidates:
                return None
            if len(candidates) != 1:
                raise ValueError("Multiple actual antidote instances need explicit source-ownership reconciliation")
            item = candidates[0]
            token = native.getStringProperty(item, "plugin_cityPoisonCreation")
            self.poisonRequire(binding)
            if token not in data["antidoteStock"]:
                raise self.PoisonBindingChanged("Uncertified/legacy antidote cannot be silently adopted")
            # Only run this whole-source ownership sweep on an actual candidate acquisition, never every empty turn.
            instances = self.poisonIssuedInstances(binding, data, token)
            if len(instances) != 1 or instances[0] is not item:
                raise self.PoisonBindingChanged("Antidote creation token has distinct actual owned instances")
            return item

        def poisonIssuedInstances(self, binding, data, token):
            native, native_map = binding["objectClass"], binding["mapClass"]
            self.poisonRequire(binding)
            holders = list(native_map.getObjects(binding["map"]))
            holders.extend(self.poisonPartyOwners(binding))
            names = [record["actorId"] for record in data["antidoteStock"].values()]
            names.extend(data.get("actors", {}))
            names.extend(row["id"] for row in decodeData(binding["actorText"] or "[]"))
            for name in names:
                registered = native_map.getObjectByName(binding["map"], name)
                if registered:
                    holders.append(registered)
                for prefix in ("plugin_cityCorpse_", "plugin_cityParked_", "plugin_cityCompanion_"):
                    retained = optionalObjectProperty(self, prefix + name, native.getObjectProperty)
                    if retained:
                        if native.getGame(retained) is not binding["game"].resolve():
                            raise self.PoisonBindingChanged("Retained source holder belongs to another session")
                        holders.append(retained)
            unique_holders, instances = [], []
            for holder in holders:
                if any(candidate is holder for candidate in unique_holders):
                    continue
                unique_holders.append(holder)
                owned = self.poisonItems(binding, holder) if isinstance(holder, CCreature) else [holder]
                for candidate in owned:
                    if native.getStringProperty(candidate, "plugin_cityPoisonCreation") == token and not any(
                        existing is candidate for existing in instances
                    ):
                        instances.append(candidate)
            self.poisonRequire(binding)
            return instances

        def poisonAwaitingMarekDeath(self, binding, data):
            if not data.get("sourceVersion"):
                return False
            for row in data["actors"].values():
                if row["resource"] not in ("MAREK", "MAREK1") or row["dead"] or row["retired"]:
                    continue
                witness = poison_live_actors.get(row["lineage"])
                if (
                    witness is None
                    or witness["game"].resolve() is not binding["game"].resolve()
                    or witness["epoch"] != binding["epoch"]
                ):
                    raise self.PoisonBindingChanged("Shared Marek alias needs its genuine prospective death witness")
                if not CCreature.isAlive(witness["actor"]):
                    return True  # Wait for the actual producer; absence/HP alone never writes Dead(Marek).
            return False

        def observePoisonAcquisition(self, binding=None, data=None):
            """Guide-backed acquisition producer followed by the separate source LOCAL-driven cure consumer."""
            binding = binding if binding is not None else self.poisonCapture()
            data = data if data is not None else self.poisonRead(binding)
            native = binding["objectClass"]
            if data["globals"].get("PartyCured", 0) != 0:
                return False
            if self.poisonAwaitingMarekDeath(binding, data):
                return False
            # Source BALDUR43/44 do not require quest acceptance, timers, either half, or current POTN47 ownership.
            if native.getNumericProperty(binding["player"], "plugin_cityBdmarek") == 1:
                return self.poisonResolveSourceCure(binding, data)
            item = self.poisonOwnedAntidote(binding, data)
            if item is None:
                return False
            self.poisonCurePresentation(binding, data)
            token = native.getStringProperty(item, "plugin_cityPoisonCreation")
            receipt_key = "acquire:" + token
            if native.getBoolProperty(item, "plugin_cityPoisonAcquisitionConsumed") or receipt_key in data["receipts"]:
                raise self.PoisonBindingChanged("The actual item acquisition already has an uncompleted source result")
            charges = self.poisonReadItemData(binding, item, "plugin_cityCharges", [])
            if len(charges) != 3 or type(charges[0]) is not int or not 1 <= charges[0] <= 10:
                raise ValueError("Invalid actual antidote charge state")
            self.poisonPartyOwners(binding)
            data["receipts"][receipt_key] = {"status": "pending", "steps": [], "chargeBefore": charges[0]}
            self.poisonWrite(binding, data)
            native.setBoolProperty(item, "plugin_cityPoisonAcquisitionConsumed", True)
            self.poisonRequire(binding)
            self.poisonWriteItemData(binding, item, "plugin_cityCharges", [charges[0] - 1, charges[1], charges[2]])
            data["receipts"][receipt_key]["steps"].append("automaticSourceItemCharge")
            self.poisonWrite(binding, data)
            native.setNumericProperty(binding["player"], "plugin_cityBdmarek", 1)
            self.poisonRequire(binding)
            data["receipts"][receipt_key]["steps"].append("bdmarekPlayer1Local")
            data["receipts"][receipt_key]["status"] = "complete"
            self.poisonWrite(binding, data)
            return self.poisonResolveSourceCure(binding, data)

        def poisonCurePresentation(self, binding, data):
            text = decodeData(binding["authoredText"] or "{}")
            notice = text.get("notices", {}).get("cure", "")
            if not notice:
                raise ValueError("Authored poison cure notice is required before native mutation")
            journal = None
            if data.get("sourceVersion"):
                aliases = data["deadAliases"].get("marek", [])
                for proof in aliases:
                    row = data["actors"].get(proof["actorId"])
                    if (
                        not row
                        or not row["dead"]
                        or row["resource"] not in ("MAREK", "MAREK1")
                        or row["lineage"] != proof["lineage"]
                        or row["sha256"] != proof["sha256"]
                        or proof["producer"] != "prospectiveNativeOwnerOnDestroy"
                    ):
                        raise self.PoisonBindingChanged(
                            "The shared Marek death alias has no genuine source-owner producer"
                        )
                dead_marek = bool(aliases)
                journal_id = 27253 if dead_marek else 31188
                authored = text.get("journals", {}).get("cureDead" if dead_marek else "cureAlive")
                if not authored or not authored.get("text"):
                    raise ValueError("Missing authored source cure journal")
                journal = {
                    "strref": journal_id,
                    "section": 2,
                    "text": authored["text"],
                    "sourceConsumer": 43 if dead_marek else 44,
                    "meaningBasis": authored.get("basis"),
                    "classicNoticeMeaningVerified": False,
                }
            self.poisonRequire(binding)
            return notice, journal

        def poisonResolveSourceCure(self, binding, data):
            native = binding["objectClass"]
            if (
                data["globals"].get("PartyCured", 0) != 0
                or native.getNumericProperty(binding["player"], "plugin_cityBdmarek") != 1
            ):
                return False
            notice, journal = self.poisonCurePresentation(binding, data)
            party = self.poisonPartyOwners(binding)
            halves = []
            for owner in party:
                owned = [
                    item
                    for item in self.poisonItems(binding, owner)
                    if native.getStringProperty(item, "plugin_citySourceItem") == "LOPOTN20"
                ]
                if owned:
                    halves.append((owner, owned[0]))  # Source DestroyItem169 removes one instance (stack_size is1).
            receipt_key = "cure:bdmarek"
            if receipt_key in data["receipts"]:
                raise self.PoisonBindingChanged("Source cure receipt cannot be replayed without terminal PartyCured")
            data["receipts"][receipt_key] = {"status": "pending", "steps": []}
            self.poisonWrite(binding, data)
            data["globals"]["PartyCured"] = 1
            self.poisonWrite(binding, data)
            for owner, item in halves:
                self.poisonRemoveOwnedItem(binding, owner, item)
                data["receipts"][receipt_key]["steps"].append("DestroyItemLOPOTN20PartySlot")
                self.poisonWrite(binding, data)
            if journal is not None:
                data["journal"].append(journal)
                erased = (26793, 26982, 27240, 27241, 27242, 27243, 27183)
                data["journal"] = [entry for entry in data["journal"] if entry.get("strref") not in erased]
            else:
                data["journal"].append({"kind": "cured", "sourceConsumer": "BALDUR43or44", "uiTextAuthored": True})
            self.poisonWrite(binding, data)
            notify(self, notice)
            self.poisonRequire(binding)
            data["receipts"][receipt_key]["steps"].append("displayCureNotice")
            self.poisonWrite(binding, data)
            CCreature.addExp(binding["player"], 10000)
            self.poisonRequire(binding)
            data["receipts"][receipt_key]["steps"].append("AddexperienceParty10000")
            self.poisonWrite(binding, data)
            native.setBoolProperty(binding["map"], "plugin_cityFlag_poisonCured", True)
            native.setBoolProperty(binding["map"], "plugin_cityFlag_partyPoisoned", False)
            data["receipts"][receipt_key]["status"] = "complete"
            if data.get("sourceVersion"):
                self.poisonSetQuestStage(binding, "marekPoison", "completed")
            self.poisonWrite(binding, data)
            # Journal capture invokes the real quest callbacks only after ordered source effects are terminal.
            if data.get("sourceVersion"):
                binding["playerClass"].checkQuests(binding["player"])
                self.poisonRequire(binding)
            return True

        def transferPoisonSourceItem(self, donor, recipient, item):
            """Exact-instance authored gift/theft bridge; native defeat loot is covered by the turn observer."""
            binding = self.poisonCapture()
            native = binding["objectClass"]
            data = self.poisonRead(binding)
            if recipient is not binding["player"]:
                raise self.PoisonBindingChanged("The source transfer recipient is no longer Player1")
            if not isinstance(donor, CCreature) or native.getGame(donor) is not binding["game"].resolve():
                raise self.PoisonBindingChanged("Source transfer donor lost its session")
            token = native.getStringProperty(item, "plugin_cityPoisonCreation")
            if token not in data["antidoteStock"]:
                raise self.PoisonBindingChanged("Authored transfer has no finite antidote source certificate")
            transfer_key = "transfer:" + token + ":" + str(len(data["receipts"]))
            data["receipts"][transfer_key] = {"status": "pending", "from": native.getName(donor), "to": "player"}
            self.poisonWrite(binding, data)
            self.poisonRemoveOwnedItem(binding, donor, item)
            CCreature.addItem(recipient, item)
            self.poisonRequire(binding)
            if not any(candidate is item for candidate in self.poisonItems(binding, recipient)):
                raise self.PoisonBindingChanged("Source transfer did not preserve the actual item")
            data["receipts"][transfer_key]["status"] = "complete"
            self.poisonWrite(binding, data)
            return self.observePoisonAcquisition()

        @resumableHook
        def showPoisonSourceState(self, state_id, edge_ids, held_edges=None):
            """Actual existing UI requests; caller supplies eligible source edges from the strict evaluator."""
            binding = self.poisonCapture()
            text = decodeData(binding["authoredText"] or "{}")
            state = text.get("states", {}).get(state_id)
            if not state or not state.get("text") or not state.get("speaker"):
                raise ValueError("Missing authored source dialogue text")
            choices = []
            held_edges = held_edges or {}
            for edge_id in edge_ids:
                edge = text.get("edges", {}).get(edge_id)
                if not edge or not edge.get("label"):
                    raise ValueError("Missing authored source reply; automatic transitions are not choices")
                choice_row = {"id": edge_id, "label": edge["label"]}
                if edge_id in held_edges:
                    choice_row.update(enabled=False, detail="Unavailable in this development build.")
                choices.append(choice_row)
            yield uiRequest("showReader", binding["game"], state["speaker"], state["text"])
            self.poisonRequire(binding)
            choice = yield uiRequest("choose", binding["game"], state["text"], choices, "Answer", "Continue later")
            self.poisonRequire(binding)
            return choice if choice in edge_ids and choice not in held_edges else None

        def ensureCitySourceKillXp(self):
            from game import CGame, CGameObject, CMap, CMapObject

            game = CGameObject.getGame(self)
            if game is None:
                return False
            game_map = CGame.getMap(game)
            if game_map is None or CGameObject.getStringProperty(game_map, "mapName") != "baldursGate":
                return False
            game_ref = flowGame(game)
            context = CGame.getContext(game)
            epoch = CGame.getMapBindingEpoch(game)
            generation = context.getTransitionGeneration()

            def requireCurrent():
                owner = game_ref.resolve()
                if (
                    owner is not game
                    or CGame.getMap(owner) is not game_map
                    or CGame.getMapBindingEpoch(owner) != epoch
                    or CGame.getContext(owner) is not context
                    or not context.isTransitionGenerationCurrent(generation)
                    or CGameObject.getGame(game_map) is not owner
                    or CGameObject.getGame(self) is not owner
                    or CMapObject.getMap(self) is not game_map
                    or CMap.getObjectByName(game_map, "cityClock") is not self
                    or CGameObject.getStringProperty(game_map, "mapName") != "baldursGate"
                ):
                    raise self.PoisonBindingChanged("City experience policy lost its actual game/map/clock binding")

            requireCurrent()
            CGameObject.setBoolProperty(game_map, "plugin_citySourceKillXp", True)
            requireCurrent()
            return True

        def poisonGraphs(self, binding=None):
            binding = binding if binding is not None else self.poisonCapture()
            self.poisonRequire(binding)
            encoded = binding["definitionText"]
            if encoded not in poison_compiled:
                document = decodeData(encoded or "{}")
                graphs = SourceGraphs(document["dialogues"])
                if graphs.coverage()["states"] != 84 or graphs.coverage()["edges"] != 135:
                    raise SourceGap("Incomplete retained poison graph inventory")
                poison_compiled.clear()
                poison_compiled[encoded] = graphs
            return poison_compiled[encoded]

        def poisonSourceTime(self, binding):
            self.poisonRequire(binding)
            return binding["objectClass"].getNumericProperty(binding["map"], "plugin_cityTicks") * 6

        def poisonSetQuestStage(self, binding, key, value):
            self.poisonRequire(binding)
            native, player_class, player = binding["objectClass"], binding["playerClass"], binding["player"]
            native.setStringProperty(binding["map"], "plugin_cityQuest_" + key, value)
            self.poisonRequire(binding)
            existing = list(player_class.getQuests(player)) + list(player_class.getCompletedQuests(player))
            self.poisonRequire(binding)
            if not any(native.getTypeId(quest_object) == questId(key) for quest_object in existing):
                player_class.addQuest(player, questId(key))
                self.poisonRequire(binding)

        def poisonQuestPresentation(self, key):
            from game import CGameObject

            if not CGameObject.getBoolProperty(self, "plugin_cityPoisonSourceEnabled"):
                return None
            binding = self.poisonCapture()
            if not binding["enabled"]:
                return None
            state = self.poisonRead(binding)
            if not state.get("sourceVersion"):
                return None
            if key == "marekPoison" and state["globals"].get("PartyCured", 0) == 1:
                entries = [row for row in state["journal"] if row.get("sourceConsumer") in (43, 44)]
                if not entries or not entries[-1].get("text"):
                    raise SourceGap("A completed source cure needs its genuine branch journal")
                return {"objective": entries[-1]["text"], "reward": "The cure grants 10,000 experience once."}
            if key == "lothanderGeas":
                if state.get("geasOutcome") == "scrollReturned":
                    return {
                        "objective": "The geas-removal scroll was returned to Lothander; he left an antidote half.",
                        "reward": "Returning the scroll grants 1,500 experience and an antidote half.",
                    }
                if state.get("geasOutcome") == "priestsDeadNoRelease":
                    return {
                        "objective": "The priests could not provide the scroll. Lothander left an antidote half and departed.",
                        "reward": "The geas remains unresolved. This fallback grants an antidote half and no experience.",
                    }
            globals_ = state["globals"]
            asked = globals_.get("DivinerAsked", 0)
            quest_stage = stage(self, key)
            if key == "divinerPoison" and quest_stage == "completed" and asked in (1, 2):
                return {
                    "objective": "The Diviner named Jalantha Mistmyr at the Water Queen's House as the priestess who can lift the geas.",
                    "reward": "The reading cost 50 gold and grants no experience.",
                    "hint": (
                        "Tell Lothander what the Diviner revealed."
                        if asked == 1
                        else "Follow the Diviner's lead to Jalantha at the Water Queen's House."
                    ),
                }
            if key not in ("marekPoison", "lothanderGeas") or quest_stage != "active":
                return None
            if key == "marekPoison" and state.get("geasOutcome") in ("scrollReturned", "priestsDeadNoRelease"):
                return {
                    "objective": "Lothander left his antidote half; recover the rest from Marek at the Blushing Mermaid Inn.",
                    "reward": "A successful cure grants 10,000 experience once.",
                    "hint": "Lothander named the Blushing Mermaid Inn. Find Marek there and obtain his antidote.",
                }
            if asked in (1, 2):
                objective = (
                    "Seek Jalantha Mistmyr at the Water Queen's House to arrange Lothander's release from the geas."
                )
                hint = (
                    "Tell Lothander that the Diviner named Jalantha at the Water Queen's House."
                    if asked == 1
                    else "Ask Jalantha for help, then return to Lothander at the Blade and Stars Inn with her remedy."
                )
            elif globals_.get("HelpLothander", 0) == 1:
                objective = "Help Lothander escape his geas so he can tell you how to find the antidote."
                hint = "Ask the Diviner in the market square how to lift Lothander's geas."
                if globals_.get("LothanderMove", 0) == 9:
                    objective = "The Diviner answered another question; Lothander's geas is still unresolved."
                    hint = "The Diviner can answer only one question each day. Return for a reading about Lothander's geas."
            else:
                objective = "Speak with Lothander about Marek's threat."
                hint = "Lothander may know how to survive Marek's threat; hear what he has to say."
            return {
                "objective": objective,
                "reward": (
                    "A successful cure grants 10,000 experience once."
                    if key == "marekPoison"
                    else "Lothander has offered information about the antidote in exchange for your help."
                ),
                "hint": hint,
            }

        def poisonSyncSourceQuests(self, binding, state, edge_id):
            mapping = {
                "LOTHAN.DLG:edge0": ("marekPoison", "active"),
                "LOTHAN.DLG:edge1": ("marekPoison", "active"),
                "LOTHAN.DLG:edge14": ("lothanderGeas", "active"),
                "DIVINE.DLG:edge11": ("divinerPoison", "completed"),
                "JALANT.DLG:edge12": ("jalanthaBook", "active"),
                "JALANT.DLG:edge19": ("jalanthaBook", "completed"),
                "JALANT.DLG:edge21": ("jalanthaBook", "completed"),
                "CHANTH.DLG:edge7": ("chanthalasTome", "completed"),
                "CHANTH.DLG:edge9": ("chanthalasTome", "completed"),
                "LOTHAN.DLG:edge23": ("lothanderGeas", "completed"),
                "LOTHAN.DLG:edge26": ("lothanderGeas", "failed"),
            }
            if edge_id in mapping:
                key, value = mapping[edge_id]
                self.poisonSetQuestStage(binding, key, value)
            if edge_id in ("LOTHAN.DLG:edge23", "LOTHAN.DLG:edge26"):
                state["geasOutcome"] = "scrollReturned" if edge_id.endswith("23") else "priestsDeadNoRelease"

        def poisonInitializeSource(self):
            binding = self.poisonCapture()
            data = self.poisonRead(binding)
            if data.get("sourceVersion") == 1:
                self.poisonRebindOwners(binding, data)
                return data
            migration = self.poisonMigrationPlan(binding, data)
            if migration["blocked"]:
                raise SourceGap(
                    "Existing poison progress is preserved pending explicit migration: "
                    + "; ".join(migration["blocked"])
                )
            self.poisonGraphs()
            definitions = decodeData(binding["definitionText"] or "{}")
            authored = decodeData(binding["authoredText"] or "{}")
            if len(authored.get("states", {})) != 84 or len(authored.get("edges", {})) != 135:
                raise SourceGap("All retained state/reply meanings must be authored before presentation")
            graphs = self.poisonGraphs().graphs
            if (
                set(authored["states"]) != {row["sourceId"] for graph in graphs.values() for row in graph["states"]}
                or set(authored["edges"]) != {row["sourceId"] for graph in graphs.values() for row in graph["edges"]}
                or not authored.get("notices", {}).get("cure")
                or not authored.get("journals", {}).get("cureDead", {}).get("text")
                or not authored.get("journals", {}).get("cureAlive", {}).get("text")
            ):
                raise SourceGap("Source dialogue/cure presentation mapping is incomplete")
            data.update(
                sourceVersion=1,
                factorySerials={},
                creationOccurrences={},
                actors={},
                deadAliases={},
                itemCreations={},
                timers={},
                cursors={},
                queuedDialogs=[],
                queuedStores=[],
                continuations={},
                nextSession=1,
                nativeWaitRequests=[],
                migration=migration,
            )
            data["receipts"]["sourceInitialization"] = {"status": "pending", "steps": []}
            self.poisonWrite(binding, data)
            for row in definitions["initialActors"]:
                actor = binding["mapClass"].getObjectByName(binding["map"], row["id"])
                if actor is None:
                    raise SourceGap("Initial source owner is not registered before activation")
                self.poisonEnrollOwner(binding, data, actor, row, row["sourceActor"])
                data["receipts"]["sourceInitialization"]["steps"].append(row["id"])
                self.poisonWrite(binding, data)
            data["receipts"]["sourceInitialization"]["status"] = "complete"
            self.poisonWrite(binding, data)
            return data

        def poisonMigrationPlan(self, binding, data):
            """A read-only decision first: unknown old rewards/cures are preserved and refuse destructive migration."""
            blocked = []
            related = ("marekPoison", "lothanderGeas", "jalanthaBook", "chanthalasTome", "divinerPoison")
            progress = {key: stage(self, key) for key in related}
            if any(value != "notStarted" for value in progress.values()):
                blocked.append("condensed quest progress has no complete source action receipts")
            if data["antidoteStock"] or data["receipts"] or data["globals"]:
                blocked.append("existing poison ownership/effect receipts must not be reset")
            native = binding["objectClass"]
            if any(
                native.getBoolProperty(binding["map"], "plugin_cityFlag_" + name)
                for name in ("poisonCured", "partyPoisoned", "poisonFatal")
            ):
                blocked.append("legacy poison outcome flags require a preserved outcome import")
            definitions = decodeData(binding["definitionText"] or "{}")
            owners = self.poisonPartyOwners(binding)
            owners.extend(
                actor for actor in binding["mapClass"].getObjects(binding["map"]) if isinstance(actor, CCreature)
            )
            for row in definitions.get("initialActors", []):
                actor = binding["mapClass"].getObjectByName(binding["map"], row["id"])
                if not isinstance(actor, CCreature) or not CCreature.isAlive(actor):
                    blocked.append("a prior source owner death/absence needs a genuine legacy producer import")
                elif (
                    native.getTypeId(actor) != row["typeId"]
                    or native.getStringProperty(actor, "sourceCreature") != row["resource"]
                ):
                    blocked.append("a source placement identity no longer matches the retained declaration")
            initial_ids = {row["id"] for row in definitions.get("initialActors", [])}
            for owner in binding["mapClass"].getObjects(binding["map"]):
                if (
                    isinstance(owner, CCreature)
                    and native.getStringProperty(owner, "sourceCreature") in CRE_DIALOGUE_BINDINGS
                    and native.getName(owner) not in initial_ids
                ):
                    blocked.append("an additional source graph owner needs its genuine creation lineage imported")
            for row in definitions.get("factories", {}).values():
                if binding["mapClass"].getObjectByName(binding["map"], row["typeId"]) is not None:
                    blocked.append("an existing source factory owner needs a nonduplicating creation import")
            for owner in owners:
                for item in self.poisonItems(binding, owner):
                    code = native.getStringProperty(item, "plugin_citySourceItem")
                    if code == "LOPOTN20" and not native.getStringProperty(item, "plugin_cityPoisonCreation"):
                        blocked.append("preexisting half-antidote ownership needs a nonduplicating import")
                    if code == "POTN47":
                        blocked.append("preexisting antidote needs exact instance/charge/source reconciliation")
            self.poisonRequire(binding)
            return {
                "kind": "newOrUnstartedScenario",
                "legacyQuestStages": progress,
                "blocked": sorted(set(blocked)),
                "oldNativeGenericTalkIsNotOriginalDialogueProgress": True,
                "sourceProgressInvented": False,
            }

        def poisonEnrollOwner(self, binding, state, actor, row, lineage):
            native = binding["objectClass"]
            resource = row["resource"]
            expected = CRE_DIALOGUE_BINDINGS.get(resource)
            name = native.getName(actor)
            if (
                expected is None
                or not isinstance(actor, CCreature)
                or not CCreature.isAlive(actor)
                or native.getTypeId(actor) != row["typeId"]
                or native.getGame(actor) is not binding["game"].resolve()
                or binding["mapObjectClass"].getMap(actor) is not binding["map"]
                or binding["mapClass"].getObjectByName(binding["map"], name) is not actor
                or native.getStringProperty(actor, "sourceCreature") != resource
                or native.getStringProperty(actor, "sourceDialogue") + ".DLG" != expected[0]
                or native.getStringProperty(actor, "sourceArea") != row["area"]
            ):
                raise SourceGap("Source factory/placement did not produce its genuine configured owner")
            existing = state["actors"].get(name)
            if existing and existing["lineage"] != lineage:
                raise SourceGap("Source owner name already belongs to a different creation event")
            native.setStringProperty(actor, "plugin_cityPoisonOwnerCreation", lineage)
            native.setBoolProperty(actor, "plugin_cityPoisonManaged", True)
            self.poisonRequire(binding)
            state["actors"][name] = {
                "resource": resource,
                "scriptName": expected[1],
                "sha256": expected[2],
                "typeId": row["typeId"],
                "area": row["area"],
                "originArea": row["area"],
                "lineage": lineage,
                "retired": False,
                "dead": False,
            }
            poison_live_actors[lineage] = {"actor": actor, "game": binding["game"], "epoch": binding["epoch"]}

        def poisonRebindOwners(self, binding, state):
            """Called by the verified-load receiver before its first yield; never reconstruct death from absence."""
            port = NativePoisonPort(self, binding, state)
            for identity, row in state["actors"].items():
                if row.get("retired") or row.get("dead"):
                    continue
                actor = port.resolve(identity, witness_required=False)
                prior = poison_live_actors.get(row["lineage"])
                if (
                    prior is not None
                    and prior["game"].resolve() is binding["game"].resolve()
                    and prior["epoch"] == binding["epoch"]
                    and prior["actor"] is not actor
                ):
                    raise SourceGap("A registered source owner was replaced within the same live map epoch")
                poison_live_actors[row["lineage"]] = {
                    "actor": actor,
                    "game": binding["game"],
                    "epoch": binding["epoch"],
                }

        @resumableHook
        def resumeAfterVerifiedLoad(self):
            if not self.ensureCitySourceKillXp():
                return
            if self.getBoolProperty("plugin_cityPoisonSourceEnabled"):
                self.poisonInitializeSource()
            if False:
                yield None

        def poisonRecordDeath(self, actor):
            """Native onDestroy producer must match a prospective actual-instance witness despite registry erasure."""
            binding = self.poisonCapture()
            if not binding["objectClass"].getBoolProperty(actor, "plugin_cityPoisonManaged"):
                return False
            state = self.poisonRead(binding)
            if not state.get("sourceVersion"):
                return False
            native = binding["objectClass"]
            identity = native.getName(actor)
            row = state["actors"].get(identity)
            if row is None or row.get("dead"):
                return False
            witness = poison_live_actors.get(row["lineage"])
            if (
                witness is None
                or witness["actor"] is not actor
                or witness["game"].resolve() is not binding["game"].resolve()
                or witness["epoch"] != binding["epoch"]
                or native.getGame(actor) is not binding["game"].resolve()
                or CCreature.isAlive(actor)
                or native.getTypeId(actor) != row["typeId"]
                or native.getStringProperty(actor, "sourceCreature") != row["resource"]
                or native.getStringProperty(actor, "plugin_cityPoisonOwnerCreation") != row["lineage"]
            ):
                raise SourceGap("Unbound or replaced source death producer; verified-load rebind must run first")
            if row.get("dead"):
                return False
            row["dead"] = True
            aliases = state["deadAliases"].setdefault(row["scriptName"].casefold(), [])
            aliases.append(
                {
                    "actorId": identity,
                    "lineage": row["lineage"],
                    "resource": row["resource"],
                    "sha256": row["sha256"],
                    "producer": "prospectiveNativeOwnerOnDestroy",
                }
            )
            del poison_live_actors[row["lineage"]]
            self.poisonWrite(binding, state)
            return True

        def poisonSourcePosition(self, binding, area_id, point):
            definitions = decodeData(binding["definitionText"] or "{}")
            key = area_id + "#" + str(point[0]) + "," + str(point[1])
            coords = definitions.get("positions", {}).get(key)
            if coords is None or len(coords) != 3:
                raise SourceGap("No authored walkable-cell conversion for this exact source action point")
            tile = binding["mapClass"].getTile(binding["map"], *coords)
            self.poisonRequire(binding)
            if tile is None or not binding["objectClass"].getBoolProperty(tile, "canStep"):
                raise SourceGap("Source point needs the existing builder's reviewed walkable-cell projection")
            return coords

        def poisonCreateSourceActor(self, binding, state, resource, operation, area_id, point):
            rows = decodeData(binding["definitionText"] or "{}")["factories"]
            row = rows.get(resource)
            if row is None:
                raise SourceGap("No staged source factory for " + resource)
            existing = [identity for identity, value in state["actors"].items() if value["lineage"] == operation]
            if existing:
                raise SourceGap("Creation event was replayed instead of resumed from its ordered receipt")
            position = self.poisonSourcePosition(binding, area_id, point)
            native = binding["objectClass"]
            actor = binding["game"].resolve().createObject(row["typeId"])
            self.poisonRequire(binding)
            serials = state.setdefault("factorySerials", {})
            serial = serials.get(resource, 0) + 1
            name = row["typeId"] if serial == 1 else row["typeId"] + "Created" + str(serial)
            if name in state["actors"] or binding["mapClass"].getObjectByName(binding["map"], name) is not None:
                raise SourceGap("A source creation serial already belongs to a different actual owner")
            serials[resource] = serial
            native.setStringProperty(actor, "name", name)
            native.setStringProperty(actor, "sourceArea", area_id)
            native.setStringProperty(actor, "simulationRegion", area_id)
            for key, value in ("posx", position[0]), ("posy", position[1]), ("posz", position[2]):
                native.setNumericProperty(actor, key, value)
            binding["mapClass"].addObject(binding["map"], actor)
            self.poisonRequire(binding)
            self.initializeActor(actor)
            self.poisonRequire(binding)
            self.poisonEnrollOwner(
                binding, state, actor, {"typeId": row["typeId"], "resource": resource, "area": area_id}, operation
            )
            if resource == "MAREK1":
                native.setNumericProperty(actor, "plugin_cityPoisonTalkCount", 1)
                self.poisonWrite(binding, state)
                self.poisonRegisterAntidoteStock(actor, binding=binding, data=state)
            return name

        def poisonMakeActorDialog(self, actor):
            binding = self.poisonCapture()
            state = self.poisonRead(binding)
            self.poisonRebindOwners(binding, state)
            identity = binding["objectClass"].getName(actor)
            port = NativePoisonPort(self, binding, state)
            if port.resolve(identity) is not actor:
                raise SourceGap("Source dialog no longer belongs to the clicked actual actor")
            definitions = decodeData(binding["definitionText"] or "{}")
            declared = firstMatch((row for row in definitions["initialActors"] if row["id"] == identity), None)
            if declared is None:
                declared = definitions["factories"][state["actors"][identity]["resource"]]
            template = declared["dialogId"]
            dialog = binding["game"].resolve().createObject(template)
            self.poisonRequire(binding)
            binding["objectClass"].setStringProperty(dialog, "actorId", identity)
            self.poisonRequire(binding)
            return dialog

        def poisonCursorActor(self, binding, state, cursor):
            actor = NativePoisonPort(self, binding, state).resolve(cursor["actorId"])
            row = state["actors"][cursor["actorId"]]
            expected = CRE_DIALOGUE_BINDINGS[row["resource"]]
            if cursor["lineage"] != row["lineage"] or cursor["resource"] != expected[0]:
                raise SourceGap("Saved source cursor belongs to a different actor or dialogue")
            return actor

        def poisonUpdateCreations(self):
            binding = self.poisonCapture()
            state = self.poisonRead(binding)
            if not state.get("sourceVersion"):
                return
            port = NativePoisonPort(self, binding, state)
            here = currentArea(self)
            for resource, source_area, source_point, operation, global_name, required_value, forbidden in (
                ("LOTHAN", "AR0700", [2361, 1090], "AR0700.BCS#spawn4", "LothanderMove", 3, ("Lothander", "Marek")),
                ("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0", "MarekMove", 1, ("Marek",)),
            ):
                if (
                    here != source_area
                    or port.globalValue(global_name) != required_value
                    or any(port.isDead(name) for name in forbidden)
                ):
                    continue
                alias = CRE_DIALOGUE_BINDINGS[resource][1]
                if any(
                    row["scriptName"] == alias and row["area"] == source_area and not row["dead"] and not row["retired"]
                    for row in state["actors"].values()
                ):
                    continue
                source_rule = operation
                occurrences = state.setdefault("creationOccurrences", {})
                occurrence = occurrences.get(source_rule, 0) + 1
                operation = source_rule + "#instance" + str(occurrence)
                if operation in state["receipts"]:
                    raise SourceGap("An area creation occurrence was replayed instead of resumed")
                occurrences[source_rule] = occurrence
                state["receipts"][operation] = {"status": "pending", "steps": [], "sourceRule": source_rule}
                self.poisonWrite(binding, state)
                identity = self.poisonCreateSourceActor(binding, state, resource, operation, source_area, source_point)
                state["receipts"][operation].update(status="complete", actorId=identity)
                self.poisonWrite(binding, state)

        def poisonBeginDialogue(self, actor, binding=None):
            binding = binding if binding is not None else self.poisonCapture()
            state = self.poisonRead(binding)
            if not state.get("sourceVersion"):
                raise SourceGap("Source runtime has not passed new-game/migration admission")
            self.poisonRebindOwners(binding, state)
            identity = binding["objectClass"].getName(actor)
            port = NativePoisonPort(self, binding, state)
            if port.resolve(identity) is not actor:
                raise SourceGap("Source conversation actor instance changed")
            row = state["actors"][identity]
            resource = CRE_DIALOGUE_BINDINGS[row["resource"]][0]
            for key, cursor in state["cursors"].items():
                if cursor["actorId"] == identity and not cursor["done"]:
                    self.poisonCursorActor(binding, state, cursor)
                    return key
            entry = self.poisonGraphs().entry(resource, port, identity)
            if entry is None:
                return None
            key = "sourceDialogue" + str(state["nextSession"])
            state["nextSession"] += 1
            state["cursors"][key] = {
                "actorId": identity,
                "lineage": row["lineage"],
                "resource": resource,
                "state": entry,
                "done": False,
                "sequence": 0,
            }
            native = binding["objectClass"]
            native.setNumericProperty(
                actor, "plugin_cityPoisonTalkCount", native.getNumericProperty(actor, "plugin_cityPoisonTalkCount") + 1
            )
            self.poisonWrite(binding, state)
            return key

        def poisonEdgeHoldReason(self, edge, graph=None, visited=None):
            def inspect(node):
                if node["operation"] == "Shout":
                    return "The audited Shout99 listener behavior has not been ported."
                if node["operation"] == "ActionOverride":
                    return inspect(node["arguments"][1])
                return ""

            for action in edge["actions"]:
                reason = inspect(action)
                if reason:
                    return reason
            if graph is not None and edge["targetState"] is not None:
                visited = set() if visited is None else visited
                if edge["index"] in visited:
                    raise SourceGap("Source hold admission encountered an automatic cycle")
                visited.add(edge["index"])
                outgoing = graph["states"][edge["targetState"]]["edges"]
                if len(outgoing) == 1:
                    following = graph["edges"][outgoing[0]]
                    if following["replyStrref"] is None and not following["conditions"]:
                        return self.poisonEdgeHoldReason(following, graph, visited)
            return ""

        def poisonChooseEdge(self, session_id, edge_index, binding=None):
            binding = binding if binding is not None else self.poisonCapture()
            state = self.poisonRead(binding)
            cursor = state["cursors"][session_id]
            self.poisonCursorActor(binding, state, cursor)
            if cursor["done"] or cursor.get("waiting"):
                raise SourceGap("Source dialogue has no current choice")
            graph = self.poisonGraphs().graphs[cursor["resource"]]
            if edge_index not in graph["states"][cursor["state"]]["edges"]:
                raise SourceGap("Edge does not belong to the current source state")
            edge = graph["edges"][edge_index]
            if self.poisonEdgeHoldReason(edge, graph):
                return False  # A held branch must not leave a pending effect receipt or mutate source state.
            port = NativePoisonPort(self, binding, state)
            if not self.poisonGraphs().matches(edge["conditions"], port, cursor["actorId"]):
                return False
            operation = session_id + ":edge" + str(edge_index) + ":sequence" + str(cursor["sequence"])
            if operation in state["receipts"]:
                raise SourceGap("Repeated source edge receipt")
            receipt = {"status": "pending", "source": edge["sourceId"], "steps": []}
            state["receipts"][operation] = receipt
            self.poisonWrite(binding, state)
            return self.poisonRunActions(binding, state, cursor, edge, operation, 0)

        def poisonRunActions(self, binding, state, cursor, edge, operation, first_action):
            port = NativePoisonPort(self, binding, state)
            receipt = state["receipts"][operation]
            for index in range(first_action, len(edge["actions"])):
                action = edge["actions"][index]
                self.poisonCursorActor(binding, state, cursor)
                result = port.applyAction(action, cursor["actorId"], operation + ":action" + str(index))
                receipt["steps"].append({"index": index, "operation": action["operation"], "result": result})
                if "waitUntil" in result:
                    receipt["status"] = "waiting"
                    cursor["waiting"] = operation
                    sessions = [key for key, item in state["cursors"].items() if item is cursor]
                    if len(sessions) != 1:
                        raise SourceGap("Delayed source action lost its unique session owner")
                    state["continuations"][operation] = {
                        "sessionId": sessions[0],
                        "resource": cursor["resource"],
                        "edge": edge["index"],
                        "nextAction": index + 1,
                        "due": result["waitUntil"],
                    }
                    self.poisonWrite(binding, state)
                    return True
                self.poisonWrite(binding, state)
            if edge["journalStrref"] is not None:
                state["journal"].append(
                    {"source": edge["sourceId"], "strref": edge["journalStrref"], "rawFlags": edge["rawFlags"]}
                )
            cursor.update(state=edge["targetState"], done=edge["targetState"] is None, sequence=cursor["sequence"] + 1)
            cursor.pop("waiting", None)
            receipt["status"] = "complete"
            self.poisonSyncSourceQuests(binding, state, edge["sourceId"])
            self.poisonWrite(binding, state)
            if binding["enabled"]:
                self.observePoisonAcquisition(binding=binding, data=state)
            return True

        def poisonResumeContinuations(self):
            binding = self.poisonCapture()
            state = self.poisonRead(binding)
            if not state.get("sourceVersion"):
                return
            now = self.poisonSourceTime(binding)
            for operation, continuation in list(state["continuations"].items()):
                if now < continuation["due"]:
                    continue
                cursor = state["cursors"][continuation["sessionId"]]
                if state["actors"][cursor["actorId"]]["dead"]:
                    state["receipts"][operation]["status"] = "cancelledByOwnerDeath"
                    cursor.update(done=True)
                    cursor.pop("waiting", None)
                else:
                    state["receipts"][operation]["status"] = "pending"
                    self.poisonWrite(binding, state)
                    edge = self.poisonGraphs().graphs[continuation["resource"]]["edges"][continuation["edge"]]
                    self.poisonRunActions(binding, state, cursor, edge, operation, continuation["nextAction"])
                del state["continuations"][operation]
                self.poisonWrite(binding, state)

        @resumableHook
        def poisonDialogue(self, actor):
            session_id = self.poisonBeginDialogue(actor)
            if session_id is None:
                return
            for _step in range(64):
                binding = self.poisonCapture()
                state = self.poisonRead(binding)
                cursor = state["cursors"][session_id]
                if cursor.get("waiting"):
                    return
                if cursor["done"]:
                    if state["queuedDialogs"]:
                        identity = state["queuedDialogs"].pop(0)
                        self.poisonWrite(binding, state)
                        queued_actor = NativePoisonPort(self, binding, state).resolve(identity)
                        session_id = self.poisonBeginDialogue(queued_actor, binding=binding)
                        if session_id is None:
                            return
                        continue
                    if state["queuedStores"]:
                        request = state["queuedStores"].pop(0)
                        self.poisonWrite(binding, state)
                        NativePoisonPort(self, binding, state).resolve(request["actorId"])
                        dialog_id = "cityPoisonStore" + request["store"] + "Dialog"
                        dialog = binding["game"].resolve().createObject(dialog_id)
                        self.poisonRequire(binding)
                        yield uiRequest("gui.showDialog", dialog)
                        self.poisonRequire(binding)
                    return
                self.poisonCursorActor(binding, state, cursor)
                graph = self.poisonGraphs().graphs[cursor["resource"]]
                source_state = graph["states"][cursor["state"]]
                port = NativePoisonPort(self, binding, state)
                eligible = [
                    graph["edges"][index]
                    for index in source_state["edges"]
                    if self.poisonGraphs().matches(graph["edges"][index]["conditions"], port, cursor["actorId"])
                ]
                automatic = [edge for edge in eligible if edge["replyStrref"] is None]
                if automatic:
                    if len(automatic) != 1:
                        raise SourceGap("Ambiguous automatic source transition priority")
                    authored = decodeData(binding["authoredText"] or "{}")["states"][source_state["sourceId"]]
                    yield uiRequest("showReader", binding["game"], authored["speaker"], authored["text"])
                    self.poisonRequire(binding)
                    edge = automatic[0]
                else:
                    reply_ids = [edge["sourceId"] for edge in eligible]
                    held = {
                        edge["sourceId"]: self.poisonEdgeHoldReason(edge, graph)
                        for edge in eligible
                        if self.poisonEdgeHoldReason(edge, graph)
                    }
                    choice = yield from self.showPoisonSourceStateFlow(source_state["sourceId"], reply_ids, held)
                    self.poisonRequire(binding)
                    edge = firstMatch((edge for edge in eligible if edge["sourceId"] == choice), None)
                    if edge is None:
                        return  # Saved cursor remains resumable; no fresh source entry or talk-count increment.
                if not self.poisonChooseEdge(session_id, edge["index"], binding=binding):
                    return
                yield uiRequest("gui.checkQuests", binding["player"])
                self.poisonRequire(binding)
            raise SourceGap("Source dialogue exceeded its retained transition bound")

        @resumableHook
        def observeRegions(self):
            definition_text = self.getStringProperty("regionDefinitions")
            if definition_text not in region_indices:
                document = decodeData(definition_text or "[]")
                rows = document.get("regions", []) if isinstance(document, dict) else document
                region_indices.clear()
                cell_index = {}
                for row in rows:
                    name = row.get("object", row.get("objectId", ""))
                    for cell in row.get("cells", []):
                        cell_index.setdefault(tuple(cell), []).append(name)
                region_indices[definition_text] = cell_index
                self.setNumericProperty(
                    "plugin_cityRegionIndexBuilds", self.getNumericProperty("plugin_cityRegionIndexBuilds") + 1
                )
            player = hero(self)
            if not player or not player.isAlive():
                return
            point = player.getCoords()
            occupied = []
            previous = read(self.getMap(), "plugin_cityRegionOccupancy", [])
            visits = read(self.getMap(), "plugin_cityRegionVisits", {})
            cues = []
            for name in region_indices[definition_text].get((point.x, point.y, point.z), []):
                region = self.getMap().getObjectByName(name)
                if not region or not region.getBoolProperty("regionEnabled"):
                    continue
                occupied.append(name)
                if name in previous:
                    continue
                source_id = region.getStringProperty("sourceRegion") or name
                visits[source_id] = visits.get(source_id, 0) + 1
                self.getMap().setStringProperty("plugin_cityLastRegion", source_id)
                cue = region.getStringProperty("cueText")
                if cue and not region.getBoolProperty("sourceNoString"):
                    cues.append(cue)
            write(self.getMap(), "plugin_cityRegionOccupancy", occupied)
            write(self.getMap(), "plugin_cityRegionVisits", visits)
            for cue in cues:
                yield uiRequest("showReader", flowGame(self.getGame()), "Baldur's Gate", cue)

        def advanceTicks(self, amount):
            game_map = self.getMap()
            ticks = game_map.getNumericProperty("plugin_cityTicks") + max(0, amount)
            game_map.setNumericProperty("plugin_cityTicks", ticks)
            game_map.setNumericProperty("plugin_cityHour", (8 + ticks // 50) % 24)
            game_map.setNumericProperty("plugin_cityDay", ticks // 1200)
            if (
                game_map.getBoolProperty("plugin_cityFlag_narlenLookoutStarted")
                and not game_map.getBoolProperty("plugin_cityFlag_narlenOfficerDue")
                and ticks >= game_map.getNumericProperty("plugin_cityNarlenOfficerAt")
                and stage(self, "narlenLookout") == "active"
            ):
                game_map.setBoolProperty("plugin_cityFlag_narlenOfficerDue", True)
                self.spawnActors()
            if amount > 1 or ticks % 25 == 0:
                self.applySchedules()
            for key, deadline in read(game_map, "plugin_cityDeadlines", {}).items():
                if stage(self, key) == "active" and ticks >= deadline:
                    setStage(self, key, "failed")
                    hero(self).checkQuests()
                    notify(self, "The deadline expired: " + (quest(self, key) or {}).get("title", key))
                    if key == "marekPoison" and not game_map.getBoolProperty("plugin_cityFlag_poisonCured"):
                        game_map.setBoolProperty("plugin_cityFlag_poisonFatal", True)
            return ticks

        def initializeActor(self, actor):
            if not isinstance(actor, CCreature) or actor.isPlayer():
                return
            initializeInventory(actor)
            if not actor.getBoolProperty("plugin_cityHooksInstalled"):
                if actor.getStringProperty("sourceCreature") in ("VAIL", "RANCE", "CAILAN", "FAIZAH", "ACHEN"):
                    actor.setBoolProperty("plugin_cityPetrified", True)
            if not actor.getBoolProperty("plugin_cityHooksInstalled"):
                for event_name, class_name in (
                    ("onEnter", "BaldursGatePersonTrigger"),
                    ("onDestroy", "BaldursGateDeathTrigger"),
                ):
                    hook = self.getGame().createObject(class_name)
                    hook.setStringProperty("object", actor.getName())
                    hook.setStringProperty("event", event_name)
                    self.getMap().getEventHandler().registerTrigger(hook)
                actor.setBoolProperty("plugin_cityHooksInstalled", True)
            seedRewardStock(self, actor)

        def spawnActors(self):
            spawned = read(self, "plugin_citySpawnedActors", [])
            phase = self.getMap().getNumericProperty("plugin_cityPhase") or 5
            canonical = {
                row["sourceCreature"]: row["canonicalActorId"] for row in read(self, "relocationDefinitions", [])
            }
            for row in read(self, "actorDefinitions", []):
                if (
                    self.getBoolProperty("plugin_cityPoisonSourceEnabled")
                    and row.get("sourceCreature") in CRE_DIALOGUE_BINDINGS
                ):
                    continue
                if row.get("custodyRole"):
                    continue
                if row.get("sourceCreature") in canonical and row["id"] != canonical[row["sourceCreature"]]:
                    continue
                minimum = row.get("phase", phase)
                if row["id"] in spawned or not minimum <= phase <= row.get("phaseMax", minimum):
                    continue
                needs = row.get("requiresQuest", {})
                needs = {needs: "active"} if isinstance(needs, str) else needs
                if any(stage(self, key) != value for key, value in needs.items()):
                    continue
                if row.get("requiresFlag") and not self.getMap().getBoolProperty(
                    "plugin_cityFlag_" + row["requiresFlag"]
                ):
                    continue
                actor = self.getGame().createObject(row["id"])
                actor.setStringProperty("name", row["id"])
                actor.setNumericProperty("posx", row["x"])
                actor.setNumericProperty("posy", row["y"])
                actor.setNumericProperty("posz", row["z"])
                actor.setNumericProperty("phaseMin", row.get("phase", phase))
                actor.setNumericProperty("phaseMax", row.get("phaseMax", row.get("phase", phase)))
                self.getMap().addObject(actor)
                self.initializeActor(actor)
                if row.get("sourceCreature") == "WATCHM" and self.getMap().getBoolProperty(
                    "plugin_cityFlag_narlenOfficerDue"
                ):
                    controller = self.getGame().createObject("CTargetController")
                    controller.setStringProperty("target", "player")
                    actor.setController(controller)
                if row.get("sourceCreature") == "NOBLPA" and stage(self, "ducalPalace") == "active":
                    actor.setBoolProperty("npc", False)
                    actor.setStringProperty("affiliation", "cityHostile")
                    controller = self.getGame().createObject("CTargetController")
                    controller.setStringProperty("target", "player")
                    actor.setController(controller)
                spawned.append(row["id"])
            write(self, "plugin_citySpawnedActors", spawned)

        def sceneEligible(self, scene):
            phase = self.getMap().getNumericProperty("plugin_cityPhase") or 5
            if not scene.get("phaseMin", 5) <= phase <= scene.get("phaseMax", 7):
                return False
            time = scene.get("timeHours")
            if time:
                hour = (8 + self.getMap().getNumericProperty("plugin_cityTicks") // 50) % 24
                checks = []
                if "after" in time:
                    checks.append(hour > time["after"])
                if "before" in time:
                    checks.append(hour < time["before"])
                if not checks or not (any(checks) if time.get("mode") == "or" else all(checks)):
                    return False
            return applyCondition(self, scene.get("conditions", {}))

        def relocateActors(self):
            game_map = self.getMap()
            states = read(self, "plugin_cityRelocationState", {})
            parked = read(self, "plugin_cityParkedActors", [])
            object_snapshot = None
            for row in read(self, "relocationDefinitions", []):
                name, key = row["canonicalActorId"], row["id"]
                actor = (
                    optionalObjectProperty(self, "plugin_cityRelocationActor_" + key)
                    or game_map.getObjectByName(name)
                    or optionalObjectProperty(self, "plugin_cityParked_" + name)
                    or optionalObjectProperty(self, "plugin_cityCorpse_" + name)
                )
                if not actor:
                    continue
                self.setObjectProperty("plugin_cityRelocationActor_" + key, actor)
                actor.setBoolProperty("plugin_cityRelocationManaged", True)
                state = states.setdefault(
                    key,
                    {
                        "canonicalActorId": name,
                        "homeArea": actor.getStringProperty("sourceArea"),
                        "homePosition": [actor.getCoords().x, actor.getCoords().y, actor.getCoords().z],
                        "scene": "",
                    },
                )
                # Old saves can contain former scene copies; check once, then trust canonical spawn suppression.
                if not state.get("sceneCopiesChecked"):
                    if object_snapshot is None:
                        object_snapshot = tuple(game_map.getObjects())
                    for other in object_snapshot:
                        if (
                            other.getName() != name
                            and other.getStringProperty("sourceCreature") == row["sourceCreature"]
                            and isinstance(other, CCreature)
                            and other.isAlive()
                        ):
                            other.setBoolProperty("plugin_cityDeparted", True)
                            self.setObjectProperty("plugin_cityParked_" + other.getName(), other)
                            if other.getName() not in parked:
                                parked.append(other.getName())
                            game_map.removeObject(other)
                            state.setdefault("quarantinedSceneCopies", []).append(other.getName())
                    state["sceneCopiesChecked"] = True
                if not actor.isAlive():
                    state["dead"] = True
                    continue
                if actor.getBoolProperty("alwaysSimulate"):
                    if not game_map.getObjectByName(name):
                        game_map.addObject(actor)
                    if name in parked:
                        parked.remove(name)
                    continue
                scene = firstMatch((entry for entry in row["scenes"] if self.sceneEligible(entry)), None)
                if actor.getBoolProperty("plugin_cityDeparted"):
                    scene = None
                if not scene:
                    self.setObjectProperty("plugin_cityParked_" + name, actor)
                    if name not in parked:
                        parked.append(name)
                    if game_map.getObjectByName(name):
                        game_map.removeObject(actor)
                    state["scene"] = ""
                    continue
                restored = not game_map.getObjectByName(name)
                if restored:
                    game_map.addObject(actor)
                if name in parked:
                    parked.remove(name)
                if (
                    restored
                    or state.get("scene") != scene["id"]
                    or actor.getStringProperty("sourceArea") != scene["sourceArea"]
                ):
                    actor.relocateWithoutMoveHooks(Coords(scene["x"], scene["y"], scene["z"]))
                    actor.setStringProperty("sourceArea", scene["sourceArea"])
                    actor.setStringProperty("simulationRegion", scene["sourceArea"])
                    state["scene"] = scene["id"]
                    state["lastMovedAt"] = game_map.getNumericProperty("plugin_cityTicks")
                actor.setNumericProperty("phaseMin", scene.get("phaseMin", 5))
                actor.setNumericProperty("phaseMax", scene.get("phaseMax", 7))
                actor.setStringProperty("plugin_cityScene", scene["id"])
            write(self, "plugin_cityRelocationState", states)
            write(self, "plugin_cityParkedActors", parked)

        def initializeActors(self):
            for actor in tuple(self.getMap().getObjects()):
                self.initializeActor(actor)
            self.spawnActors()

        def applySchedules(self):
            game_map = self.getMap()
            self.relocateActors()
            hour = scheduleSlot(game_map.getNumericProperty("plugin_cityTicks"))
            phase = game_map.getNumericProperty("plugin_cityPhase") or 5
            parked = read(self, "plugin_cityParkedActors", [])
            active_area = game_map.getStringProperty("activeSimulationRegion")
            for actor in tuple(game_map.getObjects()):
                if self.getBoolProperty("plugin_cityPoisonSourceEnabled") and actor.getBoolProperty(
                    "plugin_cityPoisonManaged"
                ):
                    continue
                if (
                    (not isinstance(actor, CCreature) and not actor.getBoolProperty("sourceCorpse"))
                    or (isinstance(actor, CCreature) and actor.isPlayer())
                    or actor.getBoolProperty("alwaysSimulate")
                    or actor.getBoolProperty("plugin_cityRelocationManaged")
                ):
                    continue
                minimum, maximum = actor.getNumericProperty("phaseMin") or 5, actor.getNumericProperty("phaseMax") or 7
                schedule = actor.getNumericProperty("sourceSchedule") if hasattr(actor, "sourceSchedule") else 0xFFFFFF
                visible = (
                    not actor.getBoolProperty("plugin_cityDeparted")
                    and minimum <= phase <= maximum
                    and (actor.getStringProperty("sourceArea") != active_area or bool(schedule & (1 << hour)))
                )
                if not visible and (not isinstance(actor, CCreature) or actor.isAlive()):
                    self.setObjectProperty("plugin_cityParked_" + actor.getName(), actor)
                    if actor.getName() not in parked:
                        parked.append(actor.getName())
                    game_map.removeObject(actor)
            for name in tuple(parked):
                actor = self.getObjectProperty("plugin_cityParked_" + name)
                if actor.getBoolProperty("plugin_cityRelocationManaged"):
                    continue
                minimum, maximum = actor.getNumericProperty("phaseMin") or 5, actor.getNumericProperty("phaseMax") or 7
                schedule = actor.getNumericProperty("sourceSchedule") if hasattr(actor, "sourceSchedule") else 0xFFFFFF
                if (
                    (not isinstance(actor, CCreature) or actor.isAlive())
                    and not actor.getBoolProperty("plugin_cityDeparted")
                    and minimum <= phase <= maximum
                    and (actor.getStringProperty("sourceArea") != active_area or bool(schedule & (1 << hour)))
                ):
                    game_map.addObject(actor)
                    parked.remove(name)
            write(self, "plugin_cityParkedActors", parked)

        @resumableHook
        def onTurn(self, event):
            if not self.getMap().getBoolProperty("plugin_cityInitialized"):
                return
            game_map = self.getMap()
            start = game_map.getObjectByName("cityStart")
            if start:
                point, origin = hero(self).getCoords(), start.getCoords()
                if point.z != origin.z or abs(point.x - origin.x) + abs(point.y - origin.y) > 1:
                    freezeHistory(self)
            if self.getBoolProperty("plugin_cityPoisonSourceEnabled"):
                self.poisonInitializeSource()
                self.poisonUpdateCreations()
                self.observePoisonAcquisition()
            was_fatal = game_map.getBoolProperty("plugin_cityFlag_poisonFatal")
            self.advanceTicks(1)
            if self.getBoolProperty("plugin_cityPoisonSourceEnabled"):
                self.poisonResumeContinuations()
            coordinator = custody(self)
            if coordinator:
                coordinator.updatePatrols()
            yield from self.observeRegionsFlow()
            if not was_fatal and game_map.getBoolProperty("plugin_cityFlag_poisonFatal"):
                yield uiRequest(
                    "showReader",
                    flowGame(self.getGame()),
                    "The poison",
                    "Ten days have passed without a cure. This city adventure has failed. "
                    "Load an earlier save to pursue the antidote.",
                )
