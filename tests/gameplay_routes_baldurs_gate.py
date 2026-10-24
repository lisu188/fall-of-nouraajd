# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""City route plans. Only actual MCP movement/choice/combat receipts constitute gameplay evidence."""

from collections import Counter, defaultdict, deque
from functools import lru_cache, partial
import json
from pathlib import Path

from scripts.build_baldurs_gate_city import decodeCityData
from tests.gameplay_branch_types import RouteCase

ROOT = Path(__file__).resolve().parents[1]
MAP = "baldursGate"
ACTOR_CLASSES = frozenset({"CCreature", "BaldursGateActor"})
SOURCES = tuple(f"res/maps/{MAP}/{name}" for name in ("map.json", "config.json", "dialog.json", "script.py"))
SOURCES += ("tests/fixtures/baldurs_gate_city_source.json", "tests/fixtures/baldurs_gate_city_quests.json")
WARDS = ("AR0800", "AR0300", "AR0200", "AR0100", "AR0600", "AR0700", "AR1100", "AR1200", "AR1300")


@lru_cache(maxsize=1)
def documents():
    def read(path):
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    return {
        "config": read(f"res/maps/{MAP}/config.json"),
        "geometry": read("tests/fixtures/baldurs_gate_city_geometry.json"),
        "source": read("tests/fixtures/baldurs_gate_city_source.json"),
        "quests": read("tests/fixtures/baldurs_gate_city_quests.json")["quests"],
    }


def upperFirst(value):
    return value[:1].upper() + value[1:]


def sourceItemId(code):
    return "cityItem" + upperFirst(code.lower())


def sourceQuantity(row):
    if "quantity" in row:
        return max(1, row["quantity"])
    metadata = documents()["source"]["items"].get(row["item"], {})
    if metadata.get("stack_size", 1) > 1 or row["item"] == "MISC07":
        return max(1, (row.get("charges") or [1])[0])
    return 1


def read(d, owner, key, default):
    return decodeCityData(d.call(owner, "getStringProperty", key) or json.dumps(default))


def resources(d):
    items = Counter()
    for item in d.call(d.player, "getItems"):
        code = d.call(item, "getStringProperty", "plugin_citySourceItem")
        if code:
            items[code] += max(1, d.call(item, "getNumericProperty", "plugin_cityQuantity"))
    return d.gold(), d.call(d.player, "getNumericProperty", "exp"), items


def state(d, key):
    return d.string("plugin_cityQuest_" + key) or "notStarted"


def currentArea(d, actor=None):
    point = d.coords(actor) if actor is not None else d.coords()
    for area_id, region in documents()["geometry"]["atlas"].items():
        x, y, z, width, height = region["bounds"]
        if point[2] == z and x <= point[0] < x + width and y <= point[1] < y + height:
            return area_id
    d.test.fail(("Player left the authored city atlas", point))


def start(d):
    d.startMap(MAP)
    if not d.flag("plugin_cityInitialized"):
        d.navigateTo("cityStart")
    d.test.assertTrue(d.flag("plugin_cityInitialized"))
    d.test.assertEqual(1000, d.number("plugin_cityStartingGoldGrant"))
    d.test.assertEqual(10000, d.number("plugin_cityStartingExpGrant"))
    d.test.assertEqual(5, d.number("plugin_cityPhase"))


def pathBetween(start_area, destination, connections, allowed):
    edges = defaultdict(list)
    for link in connections:
        if allowed(link):
            edges[link["from"]].append(link)
    pending, visited = deque([(start_area, ())]), {start_area}
    while pending:
        here, route = pending.popleft()
        if here == destination:
            return route
        for link in sorted(edges[here], key=lambda entry: entry["object"]):
            if link["to"] not in visited:
                visited.add(link["to"])
                pending.append((link["to"], route + (link,)))
    raise AssertionError(f"No currently permitted source route from {start_area} to {destination}")


@lru_cache(maxsize=1)
def cityMovementCells():
    document = json.loads((ROOT / "res/maps/baldursGate/map.json").read_text(encoding="utf-8"))
    definitions = json.loads((ROOT / "res/config/tiles.json").read_text(encoding="utf-8"))
    definitions.update(documents()["config"])
    walkable_ids = {
        tileset["firstgid"] + int(index)
        for tileset in document["tilesets"]
        for index, row in tileset.get("tileproperties", {}).items()
        if definitions[row["type"]]["properties"].get("canStep", False)
    }
    walkable, portals = set(), set()
    for layer in document["layers"]:
        level = int(layer["properties"]["level"])
        if layer["type"] == "tilelayer":
            walkable.update(
                (index % document["width"], index // document["width"], level)
                for index, gid in enumerate(layer["data"])
                if gid in walkable_ids
            )
        elif layer["type"] == "objectgroup":
            portals.update(
                (int(row["x"] // document["tilewidth"]), int(row["y"] // document["tileheight"]), level)
                for row in layer["objects"]
                if definitions[row["name"]].get("class") == "BaldursGatePortal"
            )
    return frozenset(walkable), frozenset(portals)


def cityApproachParents(origin, bounds, walkable, portals):
    """Reach street cells and portal endpoints without continuing through a compulsory entrance."""
    origin = tuple(origin)
    x, y, z, width, height = bounds

    def permitted(point):
        return point in walkable and point[2] == z and x <= point[0] < x + width and y <= point[1] < y + height

    previous = {}
    if permitted(origin):
        pending, previous = deque([origin]), {origin: None}
        while pending:
            point = pending.popleft()
            px, py, pz = point
            for candidate in ((px - 1, py, pz), (px + 1, py, pz), (px, py - 1, pz), (px, py + 1, pz)):
                if candidate not in previous and permitted(candidate):
                    previous[candidate] = point
                    if candidate not in portals:
                        pending.append(candidate)
    return previous


def cityApproachPath(origin, destination, bounds, walkable, portals):
    """Plan cardinal cells within one source area; entering any other portal would force a different trip."""
    destination = tuple(destination)
    previous = cityApproachParents(origin, bounds, walkable, portals)
    if destination in previous:
        result, point = [], destination
        while previous[point] is not None:
            result.append(point)
            point = previous[point]
        return tuple(reversed(result))
    raise AssertionError(("No portal-safe city approach", origin, destination, bounds))


def cityTravelPath(origin, start_area, destination, connections, allowed, atlas, walkable, portals):
    edges = defaultdict(list)
    for link in connections:
        if allowed(link):
            edges[link["from"]].append(link)
    pending = deque([(start_area, tuple(origin), ())])
    visited = {(start_area, tuple(origin))}
    while pending:
        area_id, point, route = pending.popleft()
        if area_id not in atlas:
            continue
        reachable = cityApproachParents(point, atlas[area_id]["bounds"], walkable, portals)
        if not reachable:
            continue
        if area_id == destination:
            return route
        for link in sorted(edges[area_id], key=lambda entry: entry["object"]):
            arrival = (link["to"], tuple(link["target"]))
            if tuple(link["origin"]) in reachable and arrival not in visited:
                visited.add(arrival)
                pending.append((*arrival, route + (link,)))
    raise AssertionError(f"No currently permitted source route from {start_area} at {origin} to {destination}")


def approachCityObject(d, name, *, reenter=False):
    area_id, origin = currentArea(d), d.coords()
    target = d.coords(d.object(name))
    walkable, portals = cityMovementCells()
    bounds = documents()["geometry"]["atlas"][area_id]["bounds"]
    initial_turns = d.turns
    budget = max(128, 4 * sum(abs(a - b) for a, b in zip(origin, target)) + 128)

    def advance(point, *, final=False):
        remaining = budget - (d.turns - initial_turns)
        d.test.assertGreater(remaining, 0, ("City approach turn budget exhausted", name, budget))
        d.navigateCoords(point, limit=remaining)
        d.test.assertLessEqual(d.turns - initial_turns, budget, ("City approach turn budget exhausted", name, budget))
        if not final or point not in portals:
            d.test.assertEqual(point, d.coords(), ("City waypoint was not actually reached", name, point))
            d.test.assertEqual(area_id, currentArea(d), ("Unselected city transition during approach", name, point))

    if reenter and origin == target:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            candidate = (origin[0] + dx, origin[1] + dy, origin[2])
            if candidate in walkable and candidate not in portals and d.canStep(candidate):
                x, y, z, width, height = bounds
                if not (candidate[2] == z and x <= candidate[0] < x + width and y <= candidate[1] < y + height):
                    continue
                advance(candidate)
                origin = candidate
                break
        else:
            d.test.fail(("No portal-safe city re-entry departure", name, target))
    for point in cityApproachPath(origin, target, bounds, walkable, portals):
        advance(point, final=point == target)


def contactCityObject(d, name):
    """Approach through this ward's streets, then require the ordinary native contact witness."""
    actor = d.object(name)
    identity = actor["__handle__"]
    origin, target = d.coords(), d.coords(actor)
    area_id = currentArea(d)
    d.test.assertEqual(area_id, currentArea(d, actor), ("City contact target left its area", name))
    bounds = documents()["geometry"]["atlas"][area_id]["bounds"]
    walkable, portals = cityMovementCells()
    budget = max(128, 4 * sum(abs(a - b) for a, b in zip(origin, target)) + 128)
    initial_turns = d.turns

    def requireCurrent(*, pending=False):
        current = d.object(name, required=False)
        d.test.assertIsNotNone(current, ("City contact target disappeared", name))
        d.test.assertEqual(identity, current["__handle__"], ("City contact identity changed", name))
        d.test.assertEqual(area_id, currentArea(d), ("Unselected city transition during contact", name))
        d.test.assertEqual(area_id, currentArea(d, current), ("City contact target left its area", name))
        used = d.turns - initial_turns
        d.test.assertLessEqual(used, budget, ("City contact turn budget exhausted", name, budget))
        if pending:
            d.test.assertLess(used, budget, ("City contact turn budget exhausted", name, budget))

    for point in cityApproachPath(origin, target, bounds, walkable, portals)[:-1]:
        requireCurrent(pending=True)
        d.navigateCoords(point, limit=budget - (d.turns - initial_turns))
        requireCurrent()
        d.test.assertEqual(point, d.coords(), ("City contact waypoint was not actually reached", name, point))
    requireCurrent()
    d.navigateTo(name, after_tick=requireCurrent)
    requireCurrent()


def travel(d, destination):
    config, geometry = documents()["config"], documents()["geometry"]
    phase = d.number("plugin_cityPhase") or 5

    def allowed(link):
        properties = config[link["object"]]["properties"]
        if not properties.get("phaseMin", 5) <= phase <= properties.get("phaseMax", 7):
            return False
        if properties.get("requiredFlag") and not d.flag("plugin_cityFlag_" + properties["requiredFlag"]):
            return False
        if link["to"] == "AR0108":
            if phase == 5 and not d.flag("plugin_cityFlag_palaceCourtyardOpen"):
                return False
            if phase == 7 and not resources(d)[2]["MISC78"]:
                return False
        return True

    route = cityTravelPath(
        d.coords(),
        currentArea(d),
        destination,
        geometry["connections"],
        allowed,
        geometry["atlas"],
        *cityMovementCells(),
    )
    traversed = []
    for link in route:
        name = link["object"]
        portal = d.object(name)
        d.test.assertEqual(tuple(link["origin"]), d.coords(portal), (name, "Actual source entrance"))
        d.test.assertEqual(
            tuple(link["target"]),
            tuple(d.call(portal, "getNumericProperty", "target" + axis) for axis in "XYZ"),
            (name, "Actual source destination"),
        )
        approachCityObject(d, name)
        if currentArea(d) != link["to"]:
            portal = d.object(name)
            if d.call(portal, "getBoolProperty", "locked"):
                dialog = name + "Dialog"
                d.choose(dialog, "useKey")
                if d.call(portal, "getBoolProperty", "locked"):
                    method = "unlock" if d.condition(dialog, "canUnlock") else "force"
                    condition = "canUnlock" if method == "unlock" else "canForce"
                    d.test.assertTrue(d.condition(dialog, condition), ("Source entrance remains locked", name))
                    d.choose(dialog, method)
            approachCityObject(d, name, reenter=True)
        d.test.assertEqual(link["to"], currentArea(d), (name, "Actual portal arrival"))
        d.test.assertEqual(tuple(link["target"]), d.coords(), (name, "Actual source arrival coordinates"))
        d.test.assertEqual(link["to"], d.string("activeSimulationRegion"))
        properties = config[name]["properties"]
        source_id = properties.get("sourceRegion")
        if not source_id:
            for index, boundary in enumerate(documents()["source"]["worldMapLinks"], 1):
                if name == "city" + boundary["source"].title() + "Boundary" + str(index):
                    source_id = "WORLDMAP.WMP#cityLink" + str(index)
                    break
        d.test.assertTrue(source_id, ("Unidentified authored source connection", name))
        traversed.append(source_id)
    d.test.assertEqual(destination, currentArea(d))
    return traversed


def visit(d, actor, action="talk"):
    properties = documents()["config"][actor]["properties"]
    travel(d, properties["sourceArea"])
    d.navigateTo(actor)
    return d.choose(actor + "Dialog", action)


def cityTour(d):
    start(d)
    region_document = read(d, d.object("cityClock"), "regionDefinitions", {})
    candidate = next(
        (
            row
            for row in region_document.get("regions", [])
            if row["sourceArea"] == "AR0800"
            and not row.get("trapped")
            and tuple(row["position"]) in {tuple(cell) for cell in row["cells"]}
            and documents()["config"][row["object"]]["properties"]["regionEnabled"]
        ),
        None,
    )
    d.test.assertIsNotNone(candidate, "The city tour requires an actual enabled source information region anchor")
    before = read(d, d.game_map, "plugin_cityRegionVisits", {}).get(candidate["sourceId"], 0)
    d.navigateTo(candidate["object"])
    visits = read(d, d.game_map, "plugin_cityRegionVisits", {})
    d.check(
        "baldursGate.regions.entered",
        visits.get(candidate["sourceId"], 0) > before,
        sourceId=candidate["sourceId"],
        scope="native region-entry receipt; information text and source effects remain pending",
    )
    for area_id in WARDS:
        traversed = travel(d, area_id)
        d.check(
            "baldursGate.travel." + area_id,
            area_id in read(d, d.game_map, "plugin_cityVisitedAreas", []),
            sourceConnections=traversed,
        )
    for area_id in ("AR0705", "AR0706", "AR0002"):
        travel(d, area_id)
        d.check("baldursGate.interior." + area_id, currentArea(d) == area_id)
    visited = read(d, d.game_map, "plugin_cityVisitedAreas", [])
    regions = read(d, d.game_map, "plugin_cityRegionVisits", {})
    d.saveAndReload("city-nine-wards-and-interiors")
    d.test.assertEqual(visited, read(d, d.game_map, "plugin_cityVisitedAreas", []))
    d.test.assertEqual(regions, read(d, d.game_map, "plugin_cityRegionVisits", {}))
    travel(d, "AR0800")
    d.check(
        "baldursGate.travel.revisitAndReload", set(WARDS) <= set(read(d, d.game_map, "plugin_cityVisitedAreas", []))
    )


def history(d, outcome):
    start(d)
    d.navigateTo("cityStart")
    d.choose("cityStartDialog", "historyAldeth" + outcome)
    d.choose("cityStartDialog", "historyTenya" + outcome)
    expected = {"aldeth": outcome.lower(), "tenya": outcome.lower()}
    d.test.assertEqual(expected, read(d, d.game_map, "plugin_cityHistory", {}))
    other = "Killed" if outcome == "Helped" else "Helped"
    d.choose("cityStartDialog", "historyAldeth" + other)
    d.choose("cityStartDialog", "historyTenya" + other)
    d.test.assertEqual(expected, read(d, d.game_map, "plugin_cityHistory", {}))
    d.choose("cityStartDialog", "finishHistoryChoices")
    d.choose("cityStartDialog", "historyEldothAbsent")
    d.test.assertTrue(d.flag("plugin_cityHistoryFrozen"))
    d.test.assertEqual(expected, read(d, d.game_map, "plugin_cityHistory", {}))
    d.test.assertEqual(expected, read(d, d.game_map, "plugin_cityStartingProfile", {})["history"])
    before = resources(d)
    d.choose("cityStartDialog", "returnFromInterlude")
    d.test.assertEqual(5, d.number("plugin_cityPhase"))
    d.test.assertEqual(before, resources(d))
    d.saveAndReload("city-history-" + outcome.lower())
    d.check("baldursGate.history." + outcome.lower(), expected == read(d, d.game_map, "plugin_cityHistory", {}))
    d.check("baldursGate.interlude.earlyReturnRefused", d.number("plugin_cityPhase") == 5)


def openContainer(d, name, *, forced=False):
    travel(d, documents()["config"][name]["properties"]["sourceArea"])
    d.navigateTo(name)
    owner, dialog = d.object(name), name + "Dialog"
    if d.call(owner, "getBoolProperty", "locked"):
        condition, action = ("canForce", "force") if forced else ("canUnlock", "unlock")
        d.test.assertTrue(d.condition(dialog, condition), (name, condition))
        d.choose(dialog, action)
        d.test.assertFalse(d.call(owner, "getBoolProperty", "locked"))
    if d.condition(dialog, "canDisarm"):
        d.choose(dialog, "disarm")
    before = resources(d)
    contents = read(d, owner, "contents", [])
    d.choose(dialog, "open")
    after = resources(d)
    expected_gold = sum(sourceQuantity(row) for row in contents if row["item"] == "MISC07")
    expected_items = Counter()
    for row in contents:
        if row["item"] != "MISC07":
            expected_items[row["item"]] += sourceQuantity(row)
    d.test.assertEqual(before[0] + expected_gold, after[0])
    d.test.assertEqual(before[2] + expected_items, after[2])
    d.test.assertTrue(d.call(owner, "getBoolProperty", "looted"))
    d.test.assertEqual([], read(d, owner, "contents", []))
    d.choose(dialog, "open")
    d.test.assertEqual(after, resources(d), "Repeated opening paid twice")
    return after


def ownership(d):
    start(d)
    openContainer(d, "cityAr0800Container1")
    openContainer(d, "cityAr0800Container2")
    before = resources(d)
    d.saveAndReload("city-source-loot")
    travel(d, "AR0700")
    travel(d, "AR0800")
    visit(d, "cityAr0800Container1", "open")
    visit(d, "cityAr0800Container2", "open")
    d.check(
        "baldursGate.ownership.exactLootAndReload",
        before == resources(d),
        sourceIds=("AR0800#container1", "AR0800#container2"),
    )


def locks(d, *, refused=False):
    start(d)
    name = "cityAr0706Container1" if refused else "cityAr0803Container2"
    if refused:
        travel(d, "AR0706")
        d.navigateTo(name)
        owner = d.object(name)
        before = resources(d)
        d.test.assertFalse(d.condition(name + "Dialog", "canUnlock"))
        d.test.assertFalse(d.condition(name + "Dialog", "canForce"))
        for action in ("unlock", "force", "open", "useKey"):
            d.choose(name + "Dialog", action)
        d.check(
            "baldursGate.locks.refused",
            d.call(owner, "getBoolProperty", "locked") and before == resources(d),
            sourceId="AR0706#container1",
        )
    else:
        openContainer(d, name, forced=d.class_id == "Warrior")
        owner = d.object(name)
        property_name = "plugin_cityForced" if d.class_id == "Warrior" else "plugin_cityPicked"
        d.test.assertTrue(d.call(owner, "getBoolProperty", property_name))
        before = resources(d)
        d.saveAndReload("city-opened-lock")
        d.check(
            "baldursGate.locks." + ("forced" if d.class_id == "Warrior" else "picked"),
            not d.call(d.object(name), "getBoolProperty", "locked") and before == resources(d),
            sourceId="AR0803#container2",
        )


def selectorMatches(properties, selector, name):
    return (
        (not selector.get("area") or properties.get("sourceArea") == selector["area"])
        and (not selector.get("creature") or properties.get("sourceCreature") == selector["creature"])
        and (
            not selector.get("label")
            or selector["label"].casefold() in (properties.get("label", "").strip().casefold(), name.casefold())
        )
    )


def nativeVictory(d, name):
    actor = d.object(name)
    d.assertNativeCombatOutcomes()
    before_seq = d._combat_trace_seq
    travel(d, currentArea(d, actor))
    if d.object(name, required=False):
        if d.call(actor, "isNpc"):
            d.navigateTo(name)
            d.choose(name + "Dialog", "attack")
            d.revisit(name)
        if d.object(name, required=False):
            if d.coords() == d.coords(d.object(name)):
                d.revisit(name)
            else:
                d.navigateTo(name)
    d.assertNativeCombatOutcomes()
    d.test.assertIsNone(d.object(name, required=False), "The opponent must actually leave the native map")
    d.test.assertFalse(d.call(actor, "isAlive"), "Removing a living actor is not a native combat victory")
    d.test.assertIsNotNone(
        d.playerVictoryAgainst(MAP, name, after_seq=before_seq), "Missing fresh native victory receipt"
    )
    d.combats += 1


class QuestRoute:
    """Finite dependency planner whose only mutations are normal movement and authored choices."""

    def __init__(self, driver):
        self.d = driver
        self.data = documents()
        self.quests = {row["id"]: row for row in self.data["quests"]}
        self.pending = set()
        self.pending_outcomes = set()
        self.actions = 0
        self.tamoko_refuse = False

    def bounded(self, goal):
        self.actions += 1
        self.d.test.assertLessEqual(self.actions, 240, ("City prerequisite budget exceeded", goal))

    def actorName(self, selectors):
        for selector in selectors:
            if selector.get("label") == "cityStart":
                return "cityStart"
            candidates = [
                name
                for name, entry in self.data["config"].items()
                if entry.get("class") in ACTOR_CLASSES
                and selectorMatches(
                    entry["properties"], {key: value for key, value in selector.items() if key != "area"}, name
                )
            ]
            for name in sorted(candidates):
                actor = self.d.object(name, required=False)
                if actor:
                    actual = {
                        key: self.d.call(actor, "getStringProperty", key)
                        for key in ("sourceArea", "sourceCreature", "label")
                    }
                    if self.d.call(actor, "getBoolProperty", "plugin_cityPetrified"):
                        actual["label"] = self.data["config"][name]["properties"].get("label", actual["label"])
                    if selectorMatches(actual, selector, name):
                        return name
        self.d.test.fail(("No living or currently placed factual actor matches any authored quest selector", selectors))

    def contact(self, name):
        actor = self.d.object(name, required=False)
        area_id = currentArea(self.d, actor) if actor else ""
        area_id = area_id or self.data["config"][name]["properties"].get("sourceArea", "AR0800")
        travel(self.d, area_id)
        contactCityObject(self.d, name)

    def ensurePhase(self, minimum):
        if self.d.number("plugin_cityPhase") >= minimum:
            return
        self.settle("eltanIronThrone", "complete")
        self.contact("cityStart")
        self.d.choose("cityStartDialog", "cityInterlude")
        self.d.choose("cityStartDialog", "returnFromInterlude")
        self.d.test.assertEqual(7, self.d.number("plugin_cityPhase"))

    def accept(self, key):
        if state(self.d, key) != "notStarted":
            return
        row = self.quests[key]
        self.ensurePhase(row.get("phase", 5))
        if key == "cythandriaDiary":
            self.tamokoMeetings()
            name = self.actorName([{"creature": "TAMOKO", "area": "AR1100"}])
            self.contact(name)
            self.d.choose(name + "Dialog", "acceptTamokoRequest")
            self.d.test.assertEqual("active", state(self.d, key))
            self.d.test.assertTrue(self.d.flag("plugin_cityFlag_tamokoMove2"))
            return
        self.conditions(row.get("acceptConditions", {}))
        name = self.actorName(row["givers"])
        self.contact(name)
        self.d.choose(name + "Dialog", "accept" + upperFirst(key))
        self.d.test.assertEqual("active", state(self.d, key), key)
        self.d.test.assertIn("city" + upperFirst(key) + "Quest", self.d.questNames())

    def tamokoMeetings(self):
        self.ensurePhase(7)
        if not self.d.flag("plugin_cityFlag_tamokoMove1"):
            name = self.actorName([{"creature": "TAMOKO", "area": "AR0800"}])
            self.contact(name)
            self.d.choose(name + "Dialog", "declineTamokoFirstMeeting" if self.tamoko_refuse else "hearTamokoWarning")
            self.d.test.assertEqual(
                "refuse" if self.tamoko_refuse else "listen", self.d.string("plugin_cityTamokoFirstChoice")
            )
        if not self.d.flag("plugin_cityFlag_tamokoDiscussed"):
            name = self.actorName([{"creature": "TAMOKO", "area": "AR1100"}])
            self.contact(name)
            self.d.choose(name + "Dialog", "discussTamokoRequest")
            self.d.test.assertTrue(self.d.flag("plugin_cityFlag_tamokoDiscussed"))

    def narlenLookout(self, *, warn):
        self.accept("narlenLookout")
        travel(self.d, "AR0300")
        self.d.waitTurns(1200, lambda: (8 + self.d.number("plugin_cityTicks") // 50) % 24 > 21)
        name = self.actorName([{"creature": "NARLEN", "area": "AR0300"}])
        self.contact(name)
        if not self.d.flag("plugin_cityFlag_narlenLookoutStarted"):
            self.d.test.assertTrue(self.d.condition(name + "Dialog", "canBeginNarlenLookout"))
            self.d.choose(name + "Dialog", "beginNarlenLookout")
            self.d.test.assertTrue(self.d.flag("plugin_cityFlag_narlenLookoutStarted"))
            self.d.test.assertEqual(self.d.number("plugin_cityTicks") + 20, self.d.number("plugin_cityNarlenOfficerAt"))
        self.d.waitTurns(21, lambda: self.d.flag("plugin_cityFlag_narlenOfficerDue"))
        officer = self.actorName([{"creature": "WATCHM", "area": "AR0300"}])
        self.d.test.assertTrue(self.d.call(self.d.object(officer), "isAlive"))
        self.d.test.assertIn(
            self.d.call(self.d.object(officer), "getStringProperty", "sourceSpawnFact"),
            ("AR0300.BCS#spawn5", "AR0300.BCS#spawn6", "AR0300.BCS#spawn7"),
        )
        if warn:
            self.contact(name)
            self.d.choose(name + "Dialog", "warnNarlen")
            self.d.test.assertTrue(self.d.flag("plugin_cityFlag_narlenWarning"))
        return officer

    def item(self, requirement):
        self.bounded(requirement)
        codes = requirement.get("anyOf", [requirement.get("item", "")])
        if sum(resources(self.d)[2][code] for code in codes) >= requirement.get("count", 1):
            return
        conversions = self.data["source"].get("editionItemConversions", {})
        codes = list(dict.fromkeys(conversions.get(code, {}).get("original", code) for code in codes))
        containers = []
        for name, entry in self.data["config"].items():
            properties = entry.get("properties", {})
            if entry.get("class") != "BaldursGateContainer" or "contents" not in properties:
                continue
            if any(row["item"] in codes for row in decodeCityData(properties["contents"])):
                containers.append((bool(properties.get("locked")), bool(properties.get("sourceOwner")), name))
        for _locked, _owned, name in sorted(containers):
            owner = self.d.object(name, required=False)
            if owner and not self.d.call(owner, "getBoolProperty", "looted"):
                openContainer(self.d, name, forced=self.d.class_id == "Warrior")
                if sum(resources(self.d)[2][code] for code in codes) >= requirement.get("count", 1):
                    return
        stores = read(self.d, self.d.object("cityClock"), "storeDefinitions", {})
        for store_id, store in sorted(stores.items()):
            owner = next(
                (
                    name
                    for name, entry in self.data["config"].items()
                    if entry.get("class") in ACTOR_CLASSES and entry["properties"].get("sourceStore") == store_id
                ),
                None,
            )
            if not owner:
                continue
            for index, stock in enumerate(store.get("stock", [])):
                if stock["item"] not in codes or stock["price"] > self.d.gold():
                    continue
                sold_key = "plugin_cityStockSold_" + store_id + "_" + str(index)
                for _ in range(requirement.get("count", 1)):
                    if not stock.get("infinite") and self.d.number(sold_key) >= stock.get("stock", 0):
                        break
                    self.contact(owner)
                    self.d.choose(owner + "Dialog", "buyStore" + upperFirst(store_id.lower()) + str(index))
                    if sum(resources(self.d)[2][code] for code in codes) >= requirement.get("count", 1):
                        return
        for excursion in decodeCityData(
            self.d.call(self.d.object("cityClock"), "getStringProperty", "questDefinitions")
        )["excursions"]:
            for choice in excursion["choices"]:
                if any(row["item"] in codes for row in choice.get("items", [])):
                    self.accept(excursion["quest"])
                    self.conditions(choice.get("conditions", {}))
                    name = self.actorName(excursion["at"])
                    self.contact(name)
                    self.d.choose(name + "Dialog", "excursion" + upperFirst(excursion["id"]) + upperFirst(choice["id"]))
                    if sum(resources(self.d)[2][code] for code in codes) >= requirement.get("count", 1):
                        return
        for key, row in self.quests.items():
            if any(item["item"] in codes for item in row.get("acceptEffects", {}).get("items", [])):
                self.accept(key)
            for outcome in row["outcomes"]:
                if key in self.pending and outcome.get("terminal", True):
                    continue
                if any(item["item"] in codes for item in outcome.get("effects", {}).get("items", [])):
                    self.settle(key, outcome["id"])
                    if sum(resources(self.d)[2][code] for code in codes) >= requirement.get("count", 1):
                        return
        for name, entry in sorted(self.data["config"].items()):
            properties = entry.get("properties", {})
            if entry.get("class") not in ACTOR_CLASSES or not any(
                row["item"] in codes for row in decodeCityData(properties.get("sourceInventory", "[]"))
            ):
                continue
            if not self.d.object(name, required=False):
                continue
            nativeVictory(self.d, name)
            if sum(resources(self.d)[2][code] for code in codes) >= requirement.get("count", 1):
                return
        self.d.test.fail(("No natural authored acquisition supplied the required source item", requirement))

    def conditions(self, condition):
        self.bounded(condition)
        for key, expected in condition.get("questStages", {}).items():
            if expected == "active":
                self.accept(key)
            else:
                self.d.test.assertEqual("completed", expected, "Unknown authored quest-stage prerequisite")
                self.settle(key)
        for flag in condition.get("flags", []):
            if self.d.flag("plugin_cityFlag_" + flag):
                continue
            found = next(
                (
                    (key, outcome["id"])
                    for key, row in self.quests.items()
                    for outcome in row["outcomes"]
                    if outcome.get("effects", {}).get("flags", {}).get(flag)
                    and (key not in self.pending or not outcome.get("terminal", True))
                ),
                None,
            )
            if found:
                self.settle(*found)
            elif flag in {"tamokoDiscussed", "tamokoMove1", "tamokoMove2"}:
                self.tamokoMeetings()
                if flag == "tamokoMove2":
                    if self.tamoko_refuse:
                        name = self.actorName([{"creature": "TAMOKO", "area": "AR1100"}])
                        self.contact(name)
                        self.d.choose(name + "Dialog", "refuseTamokoRequest")
                        self.d.test.assertEqual("refuse", self.d.string("plugin_cityTamokoSecondChoice"))
                        self.d.test.assertTrue(self.d.flag("plugin_cityFlag_tamokoMove2"))
                    else:
                        self.accept("cythandriaDiary")
            elif flag == "narlenWarning":
                self.narlenLookout(warn=True)
            else:
                document = decodeCityData(
                    self.d.call(self.d.object("cityClock"), "getStringProperty", "questDefinitions")
                )
                found_excursion = next(
                    (
                        (excursion, choice)
                        for excursion in document["excursions"]
                        for choice in excursion["choices"]
                        if choice.get("flags", {}).get(flag)
                    ),
                    None,
                )
                self.d.test.assertIsNotNone(found_excursion, ("No authored flag-producing choice", flag))
                excursion, choice = found_excursion
                self.accept(excursion["quest"])
                name = self.actorName(excursion["at"])
                self.contact(name)
                self.d.choose(name + "Dialog", "excursion" + upperFirst(excursion["id"]) + upperFirst(choice["id"]))
        for key, value in condition.get("history", {}).items():
            self.contact("cityStart")
            self.d.choose("cityStartDialog", "history" + upperFirst(key) + upperFirst(value))
        for selector in condition.get("talked", []):
            name = self.actorName([selector])
            self.contact(name)
            if self.d.call(self.d.object(name), "getBoolProperty", "plugin_cityPetrified"):
                self.item({"item": "SCRLPET"})
                self.contact(name)
                self.d.choose(name + "Dialog", "restoreStatue")
                self.d.test.assertFalse(self.d.call(self.d.object(name), "getBoolProperty", "plugin_cityPetrified"))
            self.d.choose(name + "Dialog", "talk")
        for requirement in condition.get("items", []):
            self.item(requirement)
        for area_id in condition.get("visitedAreas", []):
            travel(self.d, area_id)
        for selector in condition.get("kills", []):
            deaths = read(self.d, self.d.game_map, "plugin_cityDeaths", {})
            matches = sum(
                selectorMatches(
                    {
                        "sourceArea": row.get("area"),
                        "sourceCreature": row.get("creature"),
                        "label": row.get("label", ""),
                    },
                    selector,
                    "",
                )
                for row in deaths.values()
            )
            if selector.get("creature") == "WATCHM" and selector.get("area") == "AR0300" and not matches:
                self.narlenLookout(warn=False)
            for _ in range(max(0, selector.get("minimum", 1) - matches)):
                name = self.actorName([selector])
                nativeVictory(self.d, name)
        for area_id in condition.get("clearedAreas", []):
            travel(self.d, area_id)
            for name, entry in sorted(self.data["config"].items()):
                if entry.get("class") not in ACTOR_CLASSES or entry["properties"].get("sourceArea") != area_id:
                    continue
                actor = self.d.object(name, required=False)
                if actor and self.d.call(actor, "isAlive") and not self.d.call(actor, "isNpc"):
                    nativeVictory(self.d, name)
        for subcondition in condition.get("all", []):
            self.conditions(subcondition)
        if condition.get("any"):
            choices = condition["any"]
            ready = next(
                (
                    row
                    for row in choices
                    if row.get("flags") and all(self.d.flag("plugin_cityFlag_" + flag) for flag in row["flags"])
                ),
                None,
            )
            flag_choice = next((row for row in choices if row.get("flags")), None)
            self.conditions(ready or flag_choice or choices[0])
        for selector in condition.get("alive", []):
            self.d.test.assertTrue(self.d.call(self.d.object(self.actorName([selector])), "isAlive"))
        social = self.d.call(
            self.d.call(self.d.player, "getStats"), "getNumericProperty", "intelligence"
        ) + self.d.number("plugin_cityStanding")
        if social < condition.get("minSocial", -1000) and condition["minSocial"] <= 7:
            for key in ("quinnDagger", "ghorakSkull"):
                if key not in self.pending:
                    self.settle(key)
            social = self.d.call(
                self.d.call(self.d.player, "getStats"), "getNumericProperty", "intelligence"
            ) + self.d.number("plugin_cityStanding")
        if condition.get("guardKills") and not self.d.number("plugin_cityGuardKills"):
            nativeVictory(self.d, self.actorName([{"label": "Flaming Fist"}]))
        if condition.get("noGuardKills"):
            self.d.test.assertEqual(0, self.d.number("plugin_cityGuardKills"))
        if condition.get("thiefInParty"):
            party = [self.d.player] + [
                self.d.object(name) for name in read(self.d, self.d.object("cityClock"), "plugin_cityRoster", [])
            ]
            self.d.test.assertTrue(
                any(
                    self.d.call(self.d.call(actor, "getStats"), "getNumericProperty", "agility") >= 12
                    for actor in party
                )
            )
        self.d.test.assertGreaterEqual(
            self.d.call(self.d.player, "getNumericProperty", "level"), condition.get("minLevel", 0)
        )
        self.d.test.assertGreaterEqual(
            social, condition.get("minSocial", -1000), "Earned social standing is insufficient"
        )
        self.d.test.assertLessEqual(
            social, condition.get("maxSocial", 1000), "This route needs the ordinary reaction class"
        )
        self.d.test.assertGreaterEqual(self.d.number("plugin_cityReputation"), condition.get("minReputation", 1))
        self.d.test.assertLessEqual(self.d.number("plugin_cityReputation"), condition.get("maxReputation", 20))

    def settle(self, key, outcome_key=None):
        if state(self.d, key) == "completed":
            return
        self.bounded(key)
        goal = (key, outcome_key or "complete")
        self.d.test.assertNotIn(goal, self.pending_outcomes, ("Cyclic authored quest prerequisite", goal))
        already_pending = key in self.pending
        self.d.test.assertTrue(not already_pending or state(self.d, key) == "active", ("Cyclic quest acceptance", key))
        self.pending.add(key)
        self.pending_outcomes.add(goal)
        try:
            self.accept(key)
            row = self.quests[key]
            outcome = next(
                (entry for entry in row["outcomes"] if entry["id"] == (outcome_key or "complete")), row["outcomes"][0]
            )
            if outcome.get("conditions", {}).get("minTalks"):
                name = self.actorName(outcome.get("at", row["givers"]))
                self.contact(name)
                for _ in range(outcome["conditions"]["minTalks"]):
                    self.d.choose(name + "Dialog", "talk")
            self.conditions(outcome.get("conditions", {}))
            if (
                key == "cythandriaDiary"
                and self.d.flag("plugin_cityFlag_tamokoMove2")
                and not self.d.flag("plugin_cityFlag_palaceCleared")
            ):
                self.settle("ducalPalace", "complete")
            if outcome.get("effects", {}).get("finale"):
                self.d.test.assertEqual(
                    "completed", state(self.d, key), "The actual Sarevok death must complete the finale"
                )
                self.d.test.assertTrue(self.d.flag("plugin_cityFlag_cityCompleted"))
                return "cityStart", outcome
            name = self.actorName(outcome.get("at", row["givers"]))
            self.contact(name)
            before = resources(self.d)
            standing = self.d.number("plugin_cityStanding")
            action = "quest" + upperFirst(key) + upperFirst(outcome["id"])
            self.d.choose(name + "Dialog", action)
            effects = outcome.get("effects", {})
            self.d.test.assertEqual(before[0] + effects.get("gold", 0), self.d.gold())
            self.d.test.assertEqual(before[1] + effects.get("xp", 0), resources(self.d)[1])
            self.d.test.assertEqual(standing + effects.get("standing", 0), self.d.number("plugin_cityStanding"))
            expected_stage = "completed" if outcome.get("terminal", True) and not row.get("repeatable") else "active"
            self.d.test.assertEqual(expected_stage, state(self.d, key))
            self.d.test.assertIn(
                "city" + upperFirst(key) + "Quest", self.d.questNames(completed=expected_stage == "completed")
            )
            return name, outcome
        finally:
            self.pending_outcomes.remove(goal)
            if not already_pending:
                self.pending.remove(key)


def questRoute(d, key, outcome_key, *, item_first=False):
    start(d)
    planner = QuestRoute(d)
    planner.tamoko_refuse = key == "tamokoMercy" and outcome_key == "fight"
    row = planner.quests[key]
    outcome = next(entry for entry in row["outcomes"] if entry["id"] == outcome_key)
    if item_first:
        for requirement in outcome.get("conditions", {}).get("items", []):
            planner.item(requirement)
        d.test.assertEqual("notStarted", state(d, key))
    name, result = planner.settle(key, outcome_key)
    if key == "tamokoMercy" and outcome_key == "fight":
        nativeVictory(d, name)
    prefix = "baldursGate.quest." + key + "." + outcome_key
    before = resources(d)
    d.saveAndReload("city-quest-" + key + "-" + outcome_key)
    d.check(
        prefix,
        state(d, key) == ("completed" if result.get("terminal", True) and not row.get("repeatable") else "active"),
        sourceId="quest:" + key + ":" + outcome_key,
        itemBeforeAccept=item_first,
    )
    if not outcome.get("effects", {}).get("finale") and d.object(name, required=False):
        planner.contact(name)
    if not row.get("repeatable") and not outcome.get("effects", {}).get("finale") and d.object(name, required=False):
        d.test.assertFalse(d.condition(name + "Dialog", "canQuest" + upperFirst(key) + upperFirst(outcome_key)))
        d.choose(name + "Dialog", "talk")
        d.test.assertEqual(before, resources(d), "Returning after a quest reward paid twice")


def unknownPossessions(d):
    items = list(d.call(d.player, "getItems"))
    items.extend(item for item in d.call(d.player, "getEquipped").values() if item)
    return {d.call(item, "getName") for item in items if d.call(item, "getBoolProperty", "plugin_cityUnidentified")}


def prepareIdentification(d, planner):
    if unknownPossessions(d):
        return
    store_id = "STOCHEAP"
    config = documents()["config"]
    seller = next(
        name
        for name, entry in config.items()
        if entry.get("class") in ACTOR_CLASSES and entry.get("properties", {}).get("sourceStore") == store_id
    )
    store = read(d, d.object("cityClock"), "storeDefinitions", {})[store_id]
    index, row = next((index, row) for index, row in enumerate(store["stock"]) if row["item"] == "STAF25")
    d.test.assertTrue(store["flags"] & 1)
    d.test.assertFalse(row.get("flags", 0) & 1)
    d.test.assertFalse(row.get("infinite"))
    sold_key = "plugin_cityStockSold_" + store_id + "_" + str(index)
    sold = d.number(sold_key)
    d.test.assertLess(sold, row["stock"])
    planner.contact(seller)
    before = resources(d)
    d.test.assertGreaterEqual(before[0], row["price"])
    d.choose(seller + "Dialog", "buyStore" + upperFirst(store_id.lower()) + str(index))
    after = resources(d)
    expected = before[2].copy()
    expected[row["item"]] += max(1, row.get("quantity", 1))
    d.test.assertEqual((before[0] - row["price"], before[1], expected), after)
    d.test.assertEqual(sold + 1, d.number(sold_key))
    d.test.assertTrue(unknownPossessions(d), "The actual source purchase must supply an unknown possession")


def storeRequests(d, store_id, actor_name):
    """Choose every concrete row, distinguishing funded purchases from unchanged refusals."""
    from scripts.build_baldurs_gate_city_dialogs import storeDialogRows

    start(d)
    planner = QuestRoute(d)
    planner.contact(actor_name)
    store = read(d, d.object("cityClock"), "storeDefinitions", {})[store_id]
    rows = storeDialogRows(store_id, store)
    rows.sort(key=lambda row: not row["action"].startswith("identifyStore"))
    if any(row["action"].startswith("identifyStore") for row in rows):
        prepareIdentification(d, planner)
    for row in rows:
        planner.contact(actor_name)
        before = resources(d)
        before_intoxication = d.number("plugin_cityIntoxication")
        before_ticks = d.number("plugin_cityTicks")
        action = row["action"]
        before_unknown = unknownPossessions(d) if action.startswith("identifyStore") else set()
        before_identifications = d.number("plugin_cityIdentifications") if before_unknown else 0
        stock_index = (
            int(action.removeprefix("buyStore" + upperFirst(store_id.lower())))
            if action.startswith("buyStore")
            else None
        )
        before_sold = (
            d.number("plugin_cityStockSold_" + store_id + "_" + str(stock_index)) if stock_index is not None else 0
        )
        d.choose(actor_name + "Dialog", row["action"])
        after = resources(d)
        if action.startswith("buyStore"):
            index = stock_index
            stock = store["stock"][index]
            sold = d.number("plugin_cityStockSold_" + store_id + "_" + str(index))
            funded = before[0] >= stock["price"] and (stock.get("infinite") or before_sold < stock.get("stock", 0))
            expected = before[2].copy()
            if funded:
                expected[stock["item"]] += max(1, stock.get("quantity", 1))
            d.test.assertEqual(before[0] - (stock["price"] if funded else 0), after[0])
            d.test.assertEqual(expected, after[2])
            d.test.assertEqual(before_sold + int(bool(funded)), sold)
        elif action.startswith("identifyStore"):
            price = store.get("identify_price", 100)
            d.test.assertTrue(before_unknown)
            d.test.assertGreaterEqual(before[0], price)
            after_unknown = unknownPossessions(d)
            d.test.assertLess(after_unknown, before_unknown)
            d.test.assertEqual(1, len(before_unknown - after_unknown))
            d.test.assertEqual(before_identifications + 1, d.number("plugin_cityIdentifications"))
            d.test.assertEqual(before[0] - price, after[0])
            d.test.assertEqual(before[1:], after[1:])
        elif action.startswith("drinkStore"):
            index = int(action.removeprefix("drinkStore" + upperFirst(store_id.lower())))
            drink = store["drinks"][index]
            funded = before[0] >= drink["price"]
            d.test.assertEqual(before[0] - (drink["price"] if funded else 0), after[0])
            d.test.assertEqual(
                before_intoxication + (drink.get("strength", 0) if funded else 0), d.number("plugin_cityIntoxication")
            )
            d.test.assertEqual(before[2], after[2])
        elif action.startswith("restStore"):
            tier = int(action.removeprefix("restStore" + upperFirst(store_id.lower())))
            price = store["room_prices"][tier]
            funded = before[0] >= price
            d.test.assertEqual(before[0] - (price if funded else 0), after[0])
            d.test.assertEqual(before_ticks + (400 if funded else 0), d.number("plugin_cityTicks"))
            d.test.assertEqual(before[2], after[2])
        else:
            index = int(action.removeprefix("serviceStore" + upperFirst(store_id.lower())))
            price = store["cures"][index]["price"]
            d.test.assertIn(before[0] - after[0], [0, price], "A selected service charged an unauthored price")
            d.test.assertEqual(before[2], after[2])
        d.check(
            "baldursGate.store." + store_id + "." + action,
            True,
            action=action,
            goldBefore=before[0],
            goldAfter=after[0],
            selectedConcreteOption=True,
        )
    before = resources(d)
    d.saveAndReload("city-store-" + store_id)
    d.test.assertEqual(before, resources(d))


def generatedQuestCases():
    result = []
    for quest in documents()["quests"]:
        for outcome in quest["outcomes"]:
            condition = outcome.get("conditions", {})
            hero = "Sorcerer" if condition.get("minSocial", 0) >= 12 else "Warrior"
            prefix = "baldursGate.quest." + quest["id"] + "." + outcome["id"]
            result.append(
                RouteCase(
                    "baldurs-gate-quest-" + quest["id"] + "-" + outcome["id"],
                    MAP,
                    (MAP,),
                    (prefix,),
                    partial(questRoute, key=quest["id"], outcome_key=outcome["id"]),
                    classes=(hero,),
                    race=(
                        "highlanderRace" if hero == "Warrior" else "wandererRace" if hero == "Assasin" else "humanRace"
                    ),
                    sources=SOURCES,
                    duration_seconds=1200,
                )
            )
    return tuple(result)


def generatedStoreCases():
    from scripts.build_baldurs_gate_city_dialogs import storeDialogRows

    data = documents()
    stores = decodeCityData(data["config"]["cityClock"]["properties"]["storeDefinitions"])
    owners = {}
    for name, entry in data["config"].items():
        properties = entry.get("properties", {})
        if entry.get("class") in ACTOR_CLASSES and properties.get("sourceStore"):
            owners.setdefault(properties["sourceStore"], name)
    return tuple(
        RouteCase(
            "baldurs-gate-store-" + store_id,
            MAP,
            (MAP,),
            tuple(
                "baldursGate.store." + store_id + "." + row["action"]
                for row in storeDialogRows(store_id, stores[store_id])
            ),
            partial(storeRequests, store_id=store_id, actor_name=actor),
            classes=("Wayfarer",),
            sources=SOURCES,
            duration_seconds=1200,
        )
        for store_id, actor in sorted(owners.items())
        if storeDialogRows(store_id, stores[store_id])
    )


def companionState(d, names):
    result = {}
    for name in names:
        actor = d.object(name)
        backpack = sorted(d.call(item, "getName") for item in d.call(actor, "getItems"))
        equipped = {slot: d.call(item, "getName") for slot, item in d.call(actor, "getEquipped").items() if item}
        result[name] = (d.call(actor, "getHp"), backpack, equipped, d.call(actor, "getStringProperty", "affiliation"))
    return result


def companionsRoute(d):
    from tests.gameplay_branch_driver import readNewNativeTrace

    start(d)
    planner = QuestRoute(d)
    planner.contact("cityStart")
    d.choose("cityStartDialog", "historyEldothJoined")
    d.choose("cityStartDialog", "encounterQuayle")
    for name in ("cityCampaignNpc13", "cityCampaignNpc19"):
        planner.contact(name)
        d.choose(name + "Dialog", "recruit")
    planner.contact("cityStart")
    for _ in range(24):
        minute = (480 + d.number("plugin_cityTicks") * 6 // 5) % 1440
        if 1290 <= minute < 1440:
            break
        d.choose("cityStartDialog", "waitHour")
    else:
        d.test.fail("Authored waiting did not reach Alora's source night window")
    planner.contact("cityCampaignNpc1")
    for _ in range(3):
        d.choose("cityCampaignNpc1Dialog", "talk")
    d.choose("cityCampaignNpc1Dialog", "helpAloraLookout")
    d.choose("cityCampaignNpc1Dialog", "recruit")
    planner.contact("cityCampaignNpc15")
    d.choose("cityCampaignNpc15Dialog", "recruit")
    names = ("cityCampaignNpc16", "cityCampaignNpc13", "cityCampaignNpc19", "cityCampaignNpc1", "cityCampaignNpc15")
    roster = read(d, d.object("cityClock"), "plugin_cityRoster", [])
    d.test.assertEqual(set(names), set(roster))
    d.test.assertEqual(set(names), set(d.string("plugin_cityCompanionNames").split(",")))
    for name in names:
        actor = d.object(name)
        d.test.assertFalse(d.call(actor, "isPlayer"))
        d.test.assertFalse(d.call(actor, "isNpc"))
        d.test.assertTrue(d.call(actor, "getBoolProperty", "alwaysSimulate"))
    before = companionState(d, names)
    d.saveAndReload("city-five-actual-companions")
    d.test.assertEqual(before, companionState(d, names))
    travel(d, "AR0800")
    for name in names:
        d.test.assertEqual(d.coords()[2], d.coords(d.object(name))[2])
        d.test.assertEqual(
            d.string("activeSimulationRegion"), d.call(d.object(name), "getStringProperty", "simulationRegion")
        )
    d.check(
        "baldursGate.companions.fiveAndReload",
        True,
        sourceIds=tuple("BALDUR.GAM#npc" + name.removeprefix("cityCampaignNpc") for name in names),
    )
    planner.contact("cityCampaignNpc19")
    d.choose("cityCampaignNpc19Dialog", "dismiss")
    d.test.assertNotIn("cityCampaignNpc19", read(d, d.object("cityClock"), "plugin_cityRoster", []))
    d.choose("cityCampaignNpc19Dialog", "recruit")
    d.check(
        "baldursGate.companions.dismissAndReturn",
        "cityCampaignNpc19" in read(d, d.object("cityClock"), "plugin_cityRoster", []),
    )
    travel(d, "AR0224")
    target = next(
        (
            name
            for name, entry in sorted(documents()["config"].items())
            if entry.get("class") in ACTOR_CLASSES
            and entry["properties"].get("sourceArea") == "AR0224"
            and entry["properties"].get("affiliation") == "cityHostile"
            and d.object(name, required=False)
        ),
        None,
    )
    d.test.assertIsNotNone(target, "The native companion route requires an actual authored sewer foe")
    d.assertNativeCombatOutcomes()
    after_seq = d._combat_trace_seq
    nativeVictory(d, target)
    records = readNewNativeTrace(d.trace_path, {}, after_seq)
    actions = [
        record
        for record in records
        if record.get("event") == "combat_ally_acted" and record.get("actor", {}).get("name") in names
    ]
    d.check("baldursGate.companions.nativeCombat", bool(actions), allyActions=actions)


def skieRefusal(d):
    start(d)
    planner = QuestRoute(d)
    planner.contact("cityStart")
    d.choose("cityStartDialog", "historyEldothAbsent")
    planner.contact("cityCampaignNpc15")
    before_crimes = d.number("plugin_cityCrimes")
    d.choose("cityCampaignNpc15Dialog", "recruit")
    d.check(
        "baldursGate.companions.skieWithoutEldoth",
        d.call(d.object("cityCampaignNpc15"), "getBoolProperty", "plugin_cityLeftForever")
        and d.number("plugin_cityCrimes") == before_crimes + 1
        and "cityCampaignNpc15" not in read(d, d.object("cityClock"), "plugin_cityRoster", []),
    )


def excursionRoute(d, key, choice_key):
    start(d)
    planner = QuestRoute(d)
    document = read(d, d.object("cityClock"), "questDefinitions", {})
    excursion = next(entry for entry in document["excursions"] if entry["id"] == key)
    choice = next(entry for entry in excursion["choices"] if entry["id"] == choice_key)
    planner.accept(excursion["quest"])
    name = planner.actorName(excursion["at"])
    planner.contact(name)
    before, ticks = resources(d), d.number("plugin_cityTicks")
    agility = d.call(d.call(d.player, "getStats"), "getNumericProperty", "agility")
    d.test.assertGreaterEqual(agility, choice.get("conditions", {}).get("minAgility", 0))
    d.choose(name + "Dialog", "excursion" + upperFirst(key) + upperFirst(choice_key))
    if choice.get("pending"):
        d.test.assertEqual(before, resources(d))
        d.test.assertEqual(ticks, d.number("plugin_cityTicks"))
        d.test.assertFalse(d.flag("plugin_cityExcursion_" + key))
    else:
        d.test.assertEqual(ticks + excursion["hours"] * 50, d.number("plugin_cityTicks"))
        d.test.assertTrue(d.flag("plugin_cityExcursion_" + key))
        d.test.assertEqual(choice_key, d.string("plugin_cityExcursionChoice_" + key))
        for item in choice.get("items", []):
            d.test.assertEqual(before[2][item["item"]] + item.get("quantity", 1), resources(d)[2][item["item"]])
    d.test.assertEqual("active", state(d, excursion["quest"]), "An excursion must not auto-complete the city turn-in")
    before = resources(d)
    d.saveAndReload("city-explicit-excursion-" + key + "-" + choice_key)
    d.check(
        "baldursGate.excursion." + key + "." + choice_key,
        before == resources(d),
        scope="authored outside-city narrative choice; no outside native combat claim",
    )


def palaceAndTrap(d):
    start(d)
    planner = QuestRoute(d)
    for index in (1, 2):
        planner.contact("cityPalaceSwitch" + str(index))
        d.choose("cityPalaceSwitch" + str(index) + "Dialog", "pressPalaceSwitch" + ("One" if index == 1 else "Two"))
    d.test.assertTrue(d.flag("plugin_cityFlag_palaceCourtyardOpen"))
    travel(d, "AR0108")
    d.check("baldursGate.palace.twoSwitches", currentArea(d) == "AR0108")
    planner.contact("cityAr0200Door12")
    dialog = "cityAr0200Door12Dialog"
    if d.condition(dialog, "canUnlock"):
        d.choose(dialog, "unlock")
    d.choose(dialog, "open")
    d.test.assertTrue(d.call(d.object("cityAr0200Door12"), "getBoolProperty", "open"))
    d.choose(dialog, "close")
    d.check("baldursGate.doors.openAndClose", not d.call(d.object("cityAr0200Door12"), "getBoolProperty", "open"))
    planner.contact("cityAr0803Container1")
    d.test.assertTrue(d.condition("cityAr0803Container1Dialog", "canDisarm"))
    hp = d.call(d.player, "getHp")
    d.choose("cityAr0803Container1Dialog", "disarm")
    openContainer(d, "cityAr0803Container1")
    d.check(
        "baldursGate.traps.disarmed",
        d.call(d.player, "getHp") == hp
        and d.call(d.object("cityAr0803Container1"), "getBoolProperty", "plugin_cityDisarmed"),
    )


def refusedQuestAndReturn(d):
    start(d)
    planner = QuestRoute(d)
    name = planner.actorName(planner.quests["petrineRing"]["givers"])
    planner.contact(name)
    states = d._dialogStates(name + "Dialog")
    option = next(
        value["properties"]
        for value in states["ENTRY"]["options"]
        if not value["properties"].get("action") and value["properties"].get("nextStateId") == "EXIT"
    )
    before = resources(d)
    d.choose(name + "Dialog", "", option_number=option["number"], state_id="ENTRY")
    d.test.assertEqual("notStarted", state(d, "petrineRing"))
    d.test.assertEqual(before, resources(d))
    travel(d, "AR0800")
    planner.settle("petrineRing", "complete")
    d.check("baldursGate.quest.petrineRing.refusalAndReturn", state(d, "petrineRing") == "completed")


def templeUtilities(d):
    start(d)
    planner = QuestRoute(d)
    priestess = planner.actorName([{"creature": "PUMBERL", "area": "AR0609"}])
    planner.contact(priestess)
    before = d.gold()
    d.choose(priestess + "Dialog", "requestJalanthaAudience")
    d.test.assertEqual(before - 50, d.gold())
    d.test.assertTrue(d.flag("plugin_cityFlag_jalanthaSummoned"))
    jalantha = planner.actorName([{"label": "Jalantha Mistmyr", "area": "AR0609"}])
    d.test.assertIsNotNone(d.object(jalantha))
    d.choose(priestess + "Dialog", "requestJalanthaAudience")
    d.test.assertEqual(before - 50, d.gold(), "A repeated audience charged twice")
    d.check("baldursGate.temple.audience", True, actor=jalantha, goldPaid=50)
    owner = next(
        name
        for name, resource in documents()["config"].items()
        if resource.get("class") in ACTOR_CLASSES and resource["properties"].get("sourceStore") == "TEM0002"
    )
    planner.contact(owner)
    document = read(d, d.object("cityClock"), "questDefinitions", {})
    thresholds = document["donations"]["baseChurch"]
    funded = 0
    for _ in range(20):
        reputation, gold, standing = d.number("plugin_cityReputation"), d.gold(), d.number("plugin_cityStanding")
        cost = thresholds[reputation - 1] if 1 <= reputation <= len(thresholds) else 0
        d.choose(owner + "Dialog", "donate")
        if cost <= 0 or gold < cost:
            d.test.assertEqual(
                (gold, standing, reputation),
                (d.gold(), d.number("plugin_cityStanding"), d.number("plugin_cityReputation")),
            )
            break
        funded += 1
        d.test.assertEqual(gold - cost, d.gold())
        d.test.assertEqual(standing + 1, d.number("plugin_cityStanding"))
        d.test.assertEqual(min(20, reputation + 1), d.number("plugin_cityReputation"))
    else:
        d.test.fail("Donation route did not reach its finite source standing/funds limit")
    d.test.assertGreater(funded, 0)
    before = (resources(d), d.number("plugin_cityStanding"), d.number("plugin_cityReputation"))
    d.saveAndReload("city-temple-audience-and-donations")
    d.check(
        "baldursGate.temple.donation",
        before == (resources(d), d.number("plugin_cityStanding"), d.number("plugin_cityReputation")),
        paidDonations=funded,
    )


def itemInstances(d, owner):
    return {d.call(item, "getName"): item for item in d.call(owner, "getItems")}


def inventoryReaderLines(d, owner):
    owned = itemInstances(d, owner)
    owned.update((d.call(item, "getName"), item) for item in d.call(owner, "getEquipped").values() if item is not None)
    return [
        (d.call(item, "getStringProperty", "label") or d.call(item, "getStringProperty", "plugin_citySourceItem"))
        + " x"
        + str(max(1, d.call(item, "getNumericProperty", "plugin_cityQuantity")))
        for item in owned.values()
    ] or ["No carried belongings."]


def inventoryUi(d, *, failed=False):
    start(d)
    name = "cityAr0800Actor73"  # Niklos's authored backpack holds a Potion of Master Thievery.
    QuestRoute(d).contact(name)
    owner = d.object(name)
    before_items, before_owner = itemInstances(d, d.player), itemInstances(d, owner)
    candidates = [
        item
        for item in before_owner.values()
        if d.call(item, "getStringProperty", "plugin_citySourceItem") == "POTN36"
        and not d.call(item, "getBoolProperty", "plugin_cityUnstealable")
        and not d.call(item, "getBoolProperty", "plugin_cityUndroppable")
    ]
    d.test.assertEqual(1, len(candidates), "The route requires Niklos's actual source potion")
    selected = d.call(candidates[0], "getName")
    agility = d.call(d.call(d.player, "getStats"), "getNumericProperty", "agility")
    threshold = d.call(owner, "getNumericProperty", "plugin_cityTheftAgility") or 16
    if failed:
        d.test.assertLess(agility, threshold)
    else:
        d.test.assertGreaterEqual(agility, threshold)
        d.test.assertFalse(d.call(owner, "getBoolProperty", "plugin_cityUnavoidableDetection"))
    before, crimes, standing = resources(d), d.number("plugin_cityCrimes"), d.number("plugin_cityStanding")
    d.saveAndReload("city-before-native-theft")
    owner = d.object(name)
    reader = d.chooseUi(
        name + "Dialog",
        "showInventory",
        reader_title=d.call(owner, "getStringProperty", "label"),
        reader_lines=inventoryReaderLines(d, owner),
    )
    d.test.assertEqual(set(before_items), set(itemInstances(d, d.player)))
    d.test.assertEqual(set(before_owner), set(itemInstances(d, owner)))
    d.test.assertEqual(before, resources(d))
    d.check("baldursGate.inventory.nativeReader", True, nativePanel=reader, sourceActor="AR0800#actor73")
    witness = d.chooseUi(name + "Dialog", "pickPocket", selected_id=selected)
    after_items, after_owner = itemInstances(d, d.player), itemInstances(d, owner)
    if failed:
        d.test.assertEqual(set(before_items), set(after_items))
        d.test.assertEqual(set(before_owner), set(after_owner))
        d.test.assertEqual(before, resources(d))
        d.test.assertEqual(crimes + 1, d.number("plugin_cityCrimes"))
        d.test.assertEqual(standing - 2, d.number("plugin_cityStanding"))
        d.test.assertTrue(d.flag("plugin_cityFlag_guardsAlerted"))
        branch = "baldursGate.theft.nativeFailed"
    else:
        d.test.assertEqual(set(before_items) | {selected}, set(after_items))
        d.test.assertEqual(set(before_owner) - {selected}, set(after_owner))
        d.test.assertTrue(d.call(after_items[selected], "getBoolProperty", "plugin_cityStolen"))
        d.test.assertEqual(before[0:2], resources(d)[0:2])
        d.test.assertEqual(before[2] + Counter({"POTN36": 1}), resources(d)[2])
        d.test.assertEqual(crimes, d.number("plugin_cityCrimes"))
        d.test.assertEqual(standing, d.number("plugin_cityStanding"))
        branch = "baldursGate.theft.nativeSucceeded"
    after, crime_after = resources(d), d.number("plugin_cityCrimes")
    d.saveAndReload("city-after-native-theft")
    d.test.assertEqual(after, resources(d))
    d.test.assertEqual(set(after_items), set(itemInstances(d, d.player)))
    d.test.assertEqual(set(after_owner), set(itemInstances(d, d.object(name))))
    d.test.assertEqual(crime_after, d.number("plugin_cityCrimes"))
    d.check(branch, True, nativePanel=witness, item=selected, agility=agility, requiredAgility=threshold)


def tradeUi(d):
    start(d)
    name, store_id = "cityAr0153Actor5", "STOBLACK"
    QuestRoute(d).contact(name)
    owner = d.object(name)
    store = read(d, d.object("cityClock"), "storeDefinitions", {})[store_id]
    before_names = set(itemInstances(d, d.player))
    d.choose(name + "Dialog", "buyStoreStoblack1")
    purchased = itemInstances(d, d.player)
    added = set(purchased) - before_names
    d.test.assertEqual(1, len(added))
    selected = added.pop()
    item = purchased[selected]
    d.test.assertEqual("DART02", d.call(item, "getStringProperty", "plugin_citySourceItem"))
    d.test.assertEqual(5, d.call(item, "getNumericProperty", "plugin_cityQuantity"))
    base = d.call(item, "getNumericProperty", "plugin_cityValue") * 5
    sale_price, buy_price = base * store["buy_markup"] // 100, max(1, base * store["sell_markup"] // 100)
    d.test.assertEqual((20, 80), (sale_price, buy_price), "The source five-dart bundle must keep its exact price")
    before, before_owner = resources(d), set(itemInstances(d, owner))
    d.saveAndReload("city-before-native-sale")
    witness = d.chooseUi(name + "Dialog", "sell", selected_id=selected)
    owner = d.object(name)
    sold = itemInstances(d, owner)
    d.test.assertEqual(set(purchased) - {selected}, set(itemInstances(d, d.player)))
    d.test.assertEqual(before_owner | {selected}, set(sold))
    d.test.assertTrue(d.call(sold[selected], "getBoolProperty", "plugin_citySoldToStore"))
    d.test.assertEqual(before[0] + sale_price, d.gold())
    d.test.assertEqual(before[1], resources(d)[1])
    d.test.assertEqual(before[2] - Counter({"DART02": 5}), resources(d)[2])
    after_sale = resources(d)
    d.saveAndReload("city-after-native-sale")
    d.test.assertEqual(after_sale, resources(d))
    d.test.assertIn(selected, itemInstances(d, d.object(name)))
    d.check("baldursGate.trade.nativeSell", True, nativePanel=witness, item=selected, goldDelta=sale_price)
    witness = d.chooseUi(name + "Dialog", "buyBack", selected_id=selected)
    bought = itemInstances(d, d.player)
    d.test.assertEqual(set(purchased), set(bought))
    d.test.assertEqual(before_owner, set(itemInstances(d, d.object(name))))
    d.test.assertFalse(d.call(bought[selected], "getBoolProperty", "plugin_citySoldToStore"))
    d.test.assertEqual(after_sale[0] - buy_price, d.gold())
    d.test.assertEqual(before[1:], resources(d)[1:])
    after_buyback = resources(d)
    d.saveAndReload("city-after-native-buyback")
    d.test.assertEqual(after_buyback, resources(d))
    d.test.assertEqual(set(purchased), set(itemInstances(d, d.player)))
    d.test.assertNotIn(selected, itemInstances(d, d.object(name)))
    d.check("baldursGate.trade.nativeBuyBack", True, nativePanel=witness, item=selected, goldDelta=-buy_price)


def companionInventoryUi(d):
    start(d)
    planner = QuestRoute(d)
    planner.contact("cityStart")
    d.choose("cityStartDialog", "encounterQuayle")
    name = "cityCampaignNpc13"
    planner.contact(name)
    d.choose(name + "Dialog", "recruit")
    owner = d.object(name)
    d.test.assertIn(name, read(d, d.object("cityClock"), "plugin_cityRoster", []))
    before, before_items, before_owner = resources(d), itemInstances(d, d.player), itemInstances(d, owner)
    choices = [item for item in before_owner.values() if not d.call(item, "getBoolProperty", "plugin_cityUndroppable")]
    d.test.assertTrue(choices, "Quayle must retain an actual transferable source backpack item")
    item = min(choices, key=lambda item: d.call(item, "getName"))
    selected, code = d.call(item, "getName"), d.call(item, "getStringProperty", "plugin_citySourceItem")
    count = max(1, d.call(item, "getNumericProperty", "plugin_cityQuantity"))
    before_equipped = {slot: d.call(value, "getName") for slot, value in d.call(owner, "getEquipped").items() if value}
    d.saveAndReload("city-before-companion-inventory")
    owner = d.object(name)
    reader = d.chooseUi(
        name + "Dialog",
        "inspectCompanion",
        reader_title=d.call(owner, "getStringProperty", "label"),
        reader_lines=inventoryReaderLines(d, owner),
    )
    d.test.assertEqual(before, resources(d))
    d.test.assertEqual(set(before_owner), set(itemInstances(d, owner)))
    d.check("baldursGate.companions.nativeInventory", True, nativePanel=reader, companion=name)
    witness = d.chooseUi(name + "Dialog", "takeCompanionItem", selected_id=selected)
    d.test.assertEqual(set(before_items) | {selected}, set(itemInstances(d, d.player)))
    d.test.assertEqual(set(before_owner) - {selected}, set(itemInstances(d, owner)))
    d.test.assertEqual(before[0:2], resources(d)[0:2])
    d.test.assertEqual(before[2] + Counter({code: count}), resources(d)[2])
    after = resources(d)
    d.saveAndReload("city-after-companion-item-transfer")
    d.test.assertEqual(after, resources(d))
    d.test.assertIn(selected, itemInstances(d, d.player))
    d.test.assertNotIn(selected, itemInstances(d, d.object(name)))
    d.test.assertEqual(
        before_equipped,
        {slot: d.call(value, "getName") for slot, value in d.call(d.object(name), "getEquipped").items() if value},
    )
    d.test.assertIn(name, read(d, d.object("cityClock"), "plugin_cityRoster", []))
    d.check("baldursGate.companions.nativeItemTransfer", True, nativePanel=witness, companion=name, item=selected)


def custodyInventory(d, owner):
    bag = itemInstances(d, owner)
    d.test.assertEqual(len(bag), len(d.call(owner, "getItems")), "Custody ownership needs unique actual item names")
    equipped = {
        slot: d.call(item, "getName") for slot, item in d.call(owner, "getEquipped").items() if item is not None
    }
    identities = {
        name: (
            d.call(item, "getTypeId"),
            d.call(item, "getStringProperty", "plugin_citySourceItem"),
            d.call(item, "getNumericProperty", "plugin_cityQuantity"),
        )
        for name, item in bag.items()
    }
    return identities, equipped


def custodyUi(d):
    start(d)
    planner = QuestRoute(d)
    planner.ensurePhase(7)
    travel(d, "AR0800")
    d.call(d.game_map, "move")
    d.pump()
    patrol = "cityCustodyPatrolAr0800One"
    d.test.assertIsNotNone(d.object(patrol))
    planner.contact(patrol)
    before, inventory = resources(d), custodyInventory(d, d.player)
    surrender = d.chooseUi(patrol + "Dialog", "talk", dialogue_choices=["0", "5"])
    d.test.assertEqual("jailed", d.string("plugin_cityCustodyState"))
    d.test.assertEqual("AR0607", currentArea(d))
    custody_data = read(d, d.object("cityCustody"), "custodyDefinitions", {})
    d.test.assertEqual(tuple(custody_data["jail"]["partyPositions"][0]), d.coords())
    d.test.assertEqual(1, read(d, d.game_map, "plugin_cityCustodyGlobals", {})["GLOBAL:Captured"])
    d.test.assertEqual({26844, 26842, 26841}, set(read(d, d.game_map, "plugin_cityCustodyJournal", [])))
    d.test.assertEqual(before, resources(d), "Arrest must not grant rewards or confiscate possessions")
    d.test.assertEqual(inventory, custodyInventory(d, d.player))
    d.test.assertIn("cityCustodyQuest", d.questNames())
    jail_trace = read(d, d.game_map, "plugin_cityCustodyTrace", [])
    d.test.assertEqual(
        [("FFHUNT", 0), ("FFHUNT", 5), ("FLAMC7", 13), ("ANGELO", 5), ("ANGELO", 15)],
        [(row["dialogue"], row["edge"]) for row in jail_trace],
    )
    d.check("baldursGate.custody.surrender", True, nativePanel=surrender, nativeCustodyTrace=jail_trace)

    def retainedAngelo():
        owner = d.call(d.object("cityCustody"), "getObjectProperty", "plugin_cityActor_cityCustodyAngelo")
        d.test.assertIsNotNone(owner, "Plot cleanup must retain the actual custody actor")
        d.test.assertTrue(d.call(owner, "isAlive"), "The peaceful jail branch must not create an execution corpse")
        d.test.assertTrue(d.call(owner, "getBoolProperty", "plugin_cityDeparted"))
        d.test.assertIsNone(d.object("cityCustodyAngelo", required=False))
        return custodyInventory(d, owner)

    angelo_inventory = retainedAngelo()
    jail_journal = read(d, d.game_map, "plugin_cityCustodyJournal", [])
    jail_position = d.coords()
    d.saveAndReload("city-custody-jailed")
    d.test.assertEqual("jailed", d.string("plugin_cityCustodyState"))
    d.test.assertEqual(jail_position, d.coords())
    d.test.assertEqual(jail_trace, read(d, d.game_map, "plugin_cityCustodyTrace", []))
    d.test.assertEqual(jail_journal, read(d, d.game_map, "plugin_cityCustodyJournal", []))
    d.test.assertEqual(angelo_inventory, retainedAngelo())
    d.test.assertEqual(before, resources(d))
    d.test.assertEqual(inventory, custodyInventory(d, d.player))

    neb = "cityAr0607Actor2"
    planner.contact(neb)
    d.chooseUi(neb + "Dialog", "talk", dialogue_choices=["2", "5"])
    d.test.assertIn(26846, read(d, d.game_map, "plugin_cityCustodyJournal", []))
    for expected_talks in (2, 3):
        d.chooseUi(neb + "Dialog", "talk", dialogue_choices=[])
        d.test.assertEqual(expected_talks, d.call(d.object(neb), "getNumericProperty", "plugin_cityTalkCount"))
    escape = d.chooseUi(neb + "Dialog", "talk", dialogue_choices=["9", "15"])
    d.test.assertEqual("escaped", d.string("plugin_cityCustodyState"))
    d.test.assertEqual("AR1100", currentArea(d))
    d.test.assertEqual(tuple(custody_data["escape"]["partyPositions"][0]), d.coords())
    d.test.assertEqual([27317], read(d, d.game_map, "plugin_cityCustodyJournal", []))
    d.test.assertIsNone(d.object(neb, required=False))
    retired_neb = d.call(d.object("cityCustody"), "getObjectProperty", "plugin_cityActor_" + neb)
    d.test.assertIsNotNone(retired_neb)
    d.test.assertTrue(d.call(retired_neb, "isAlive"))
    d.test.assertTrue(d.call(retired_neb, "getBoolProperty", "plugin_cityDeparted"))
    d.test.assertEqual(before, resources(d), "Neb's escape must grant exactly zero gold, XP or source items")
    d.test.assertEqual(inventory, custodyInventory(d, d.player), "Neb's spoken key must not create an item")
    d.test.assertIn("cityCustodyQuest", d.questNames(completed=True))
    d.test.assertNotIn("cityCustodyQuest", d.questNames())
    trace = read(d, d.game_map, "plugin_cityCustodyTrace", [])
    d.test.assertEqual([2, 5, 6, 7, 8, 9, 15, 19], [row["edge"] for row in trace if row["dialogue"] == "NEB"])
    d.check(
        "baldursGate.custody.escapeNoReward",
        True,
        nativePanel=escape,
        nativeCustodyTrace=trace,
        goldDelta=resources(d)[0] - before[0],
        experienceDelta=resources(d)[1] - before[1],
    )
    escaped_position = d.coords()
    d.saveAndReload("city-custody-escaped")
    d.test.assertEqual("escaped", d.string("plugin_cityCustodyState"))
    d.test.assertEqual(escaped_position, d.coords())
    d.test.assertEqual(trace, read(d, d.game_map, "plugin_cityCustodyTrace", []))
    d.test.assertEqual([27317], read(d, d.game_map, "plugin_cityCustodyJournal", []))
    d.test.assertEqual(before, resources(d))
    d.test.assertEqual(inventory, custodyInventory(d, d.player))
    d.test.assertEqual(angelo_inventory, retainedAngelo())
    d.test.assertIsNone(d.object(neb, required=False))
    d.test.assertIn("cityCustodyQuest", d.questNames(completed=True))
    d.check("baldursGate.custody.saveReload", True, completedQuest="cityCustodyQuest", checkpoints=2)


CASES = (
    (
        RouteCase(
            "baldurs-gate-tour",
            MAP,
            (MAP,),
            tuple("baldursGate.travel." + area for area in WARDS)
            + tuple("baldursGate.interior." + area for area in ("AR0705", "AR0706", "AR0002"))
            + ("baldursGate.travel.revisitAndReload", "baldursGate.regions.entered"),
            cityTour,
            sources=SOURCES,
            duration_seconds=900,
        ),
        RouteCase(
            "baldurs-gate-history-helped",
            MAP,
            (MAP,),
            ("baldursGate.history.helped", "baldursGate.interlude.earlyReturnRefused"),
            partial(history, outcome="Helped"),
            classes=("Wayfarer",),
            sources=SOURCES,
            duration_seconds=90,
        ),
        RouteCase(
            "baldurs-gate-history-killed",
            MAP,
            (MAP,),
            ("baldursGate.history.killed", "baldursGate.interlude.earlyReturnRefused"),
            partial(history, outcome="Killed"),
            classes=("Inquisitor",),
            sources=SOURCES,
            duration_seconds=90,
        ),
        RouteCase(
            "baldurs-gate-ownership",
            MAP,
            (MAP,),
            ("baldursGate.ownership.exactLootAndReload",),
            ownership,
            classes=("Wayfarer",),
            sources=SOURCES,
            duration_seconds=180,
        ),
        RouteCase(
            "baldurs-gate-forced-lock",
            MAP,
            (MAP,),
            ("baldursGate.locks.forced",),
            locks,
            classes=("Warrior",),
            race="highlanderRace",
            sources=SOURCES,
            duration_seconds=180,
        ),
        RouteCase(
            "baldurs-gate-picked-lock",
            MAP,
            (MAP,),
            ("baldursGate.locks.picked",),
            locks,
            classes=("Assasin",),
            race="wandererRace",
            sources=SOURCES,
            duration_seconds=180,
        ),
        RouteCase(
            "baldurs-gate-lock-refusals",
            MAP,
            (MAP,),
            ("baldursGate.locks.refused",),
            partial(locks, refused=True),
            classes=("Sorcerer",),
            sources=SOURCES,
            duration_seconds=180,
        ),
    )
    + generatedQuestCases()
    + generatedStoreCases()
    + (
        RouteCase(
            "baldurs-gate-five-companions",
            MAP,
            (MAP,),
            (
                "baldursGate.companions.fiveAndReload",
                "baldursGate.companions.dismissAndReturn",
                "baldursGate.companions.nativeCombat",
            ),
            companionsRoute,
            classes=("Sorcerer",),
            sources=SOURCES,
            duration_seconds=1200,
        ),
        RouteCase(
            "baldurs-gate-skie-refusal",
            MAP,
            (MAP,),
            ("baldursGate.companions.skieWithoutEldoth",),
            skieRefusal,
            classes=("Sorcerer",),
            sources=SOURCES,
            duration_seconds=300,
        ),
        RouteCase(
            "baldurs-gate-palace-trap",
            MAP,
            (MAP,),
            ("baldursGate.palace.twoSwitches", "baldursGate.doors.openAndClose", "baldursGate.traps.disarmed"),
            palaceAndTrap,
            classes=("Assasin",),
            race="wandererRace",
            sources=SOURCES,
            duration_seconds=900,
        ),
        RouteCase(
            "baldurs-gate-refuse-return",
            MAP,
            (MAP,),
            ("baldursGate.quest.petrineRing.refusalAndReturn",),
            refusedQuestAndReturn,
            classes=("Inquisitor",),
            sources=SOURCES,
            duration_seconds=600,
        ),
        RouteCase(
            "baldurs-gate-item-before-accept",
            MAP,
            (MAP,),
            ("baldursGate.quest.petrineRing.complete",),
            partial(questRoute, key="petrineRing", outcome_key="complete", item_first=True),
            classes=("Wayfarer",),
            sources=SOURCES,
            duration_seconds=600,
        ),
    )
    + tuple(
        RouteCase(
            "baldurs-gate-excursion-" + excursion["id"] + "-" + choice["id"],
            MAP,
            (MAP,),
            ("baldursGate.excursion." + excursion["id"] + "." + choice["id"],),
            partial(excursionRoute, key=excursion["id"], choice_key=choice["id"]),
            classes=("Assasin",) if excursion["id"] == "algernon" else ("Wayfarer",),
            race="wandererRace" if excursion["id"] == "algernon" else "humanRace",
            sources=SOURCES,
            duration_seconds=900,
        )
        for excursion in json.loads(
            (ROOT / "tests/fixtures/baldurs_gate_city_quests.json").read_text(encoding="utf-8")
        )["excursions"]
        for choice in excursion["choices"]
    )
)

CASES += (
    RouteCase(
        "baldurs-gate-temple-utilities",
        MAP,
        (MAP,),
        ("baldursGate.temple.audience", "baldursGate.temple.donation"),
        templeUtilities,
        classes=("Inquisitor",),
        sources=SOURCES,
        duration_seconds=600,
    ),
)

CASES += (
    RouteCase(
        "baldurs-gate-native-inventory",
        MAP,
        (MAP,),
        ("baldursGate.inventory.nativeReader", "baldursGate.theft.nativeSucceeded"),
        inventoryUi,
        classes=("Assasin",),
        race="wandererRace",
        sources=SOURCES,
        duration_seconds=300,
        isolated_gui=True,
    ),
    RouteCase(
        "baldurs-gate-native-failed-theft",
        MAP,
        (MAP,),
        ("baldursGate.inventory.nativeReader", "baldursGate.theft.nativeFailed"),
        partial(inventoryUi, failed=True),
        classes=("Warrior",),
        sources=SOURCES,
        duration_seconds=300,
        isolated_gui=True,
    ),
    RouteCase(
        "baldurs-gate-native-trading",
        MAP,
        (MAP,),
        ("baldursGate.trade.nativeSell", "baldursGate.trade.nativeBuyBack"),
        tradeUi,
        classes=("Wayfarer",),
        sources=SOURCES,
        duration_seconds=600,
        isolated_gui=True,
    ),
    RouteCase(
        "baldurs-gate-native-companion-inventory",
        MAP,
        (MAP,),
        ("baldursGate.companions.nativeInventory", "baldursGate.companions.nativeItemTransfer"),
        companionInventoryUi,
        classes=("Sorcerer",),
        sources=SOURCES,
        duration_seconds=300,
        isolated_gui=True,
    ),
)

CASES += (
    RouteCase(
        "baldurs-gate-native-custody",
        MAP,
        (MAP,),
        ("baldursGate.custody.surrender", "baldursGate.custody.escapeNoReward", "baldursGate.custody.saveReload"),
        custodyUi,
        classes=("Warrior",),
        race="highlanderRace",
        sources=SOURCES + ("tests/fixtures/baldurs_gate_city_prison_source.json",),
        duration_seconds=1200,
        isolated_gui=True,
    ),
)

SOURCE_BRANCHES = {
    "res/maps/baldursGate/script.py:BaldursGateCustodyQuest.isCompleted": ("baldursGate.custody.escapeNoReward",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.showInventory": ("baldursGate.inventory.nativeReader",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.pickPocket": (
        "baldursGate.theft.nativeSucceeded",
        "baldursGate.theft.nativeFailed",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.sell": ("baldursGate.trade.nativeSell",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.buyBack": ("baldursGate.trade.nativeBuyBack",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.inspectCompanion": ("baldursGate.companions.nativeInventory",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.takeCompanionItem": (
        "baldursGate.companions.nativeItemTransfer",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.declineTamokoFirstMeeting": (
        "baldursGate.quest.tamokoMercy.fight",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.refuseTamokoRequest": ("baldursGate.quest.tamokoMercy.fight",),
    "res/maps/baldursGate/script.py:BaldursGateRegion.onEnter": ("baldursGate.regions.entered",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.finishHistoryChoices": ("baldursGate.history.helped",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.canFinishHistoryChoices": ("baldursGate.history.helped",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.canTamokoFirstMeeting": (
        "baldursGate.quest.cythandriaDiary.complete",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.hearTamokoWarning": (
        "baldursGate.quest.cythandriaDiary.complete",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.canTamokoSecondMeeting": (
        "baldursGate.quest.cythandriaDiary.complete",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.discussTamokoRequest": (
        "baldursGate.quest.cythandriaDiary.complete",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.canFinishTamokoSecondMeeting": (
        "baldursGate.quest.cythandriaDiary.complete",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.acceptTamokoRequest": (
        "baldursGate.quest.cythandriaDiary.complete",
    ),
    "res/maps/baldursGate/script.py:BaldursGateDialog.restoreStatue": ("baldursGate.quest.balduranCloak.complete",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.canRestoreStatue": ("baldursGate.quest.balduranCloak.complete",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.requestJalanthaAudience": ("baldursGate.temple.audience",),
    "res/maps/baldursGate/script.py:BaldursGateDialog.donate": ("baldursGate.temple.donation",),
    "res/maps/baldursGate/script.py:BaldursGateStart.onEnter": ("baldursGate.travel.AR0800",),
    "res/maps/baldursGate/script.py:BaldursGateClock.onTurn": ("baldursGate.travel.AR0700",),
    "res/maps/baldursGate/script.py:BaldursGatePortal.onCreate": ("baldursGate.travel.AR0700",),
    "res/maps/baldursGate/script.py:BaldursGatePortal.onTurn": ("baldursGate.travel.AR0700",),
    "res/maps/baldursGate/script.py:BaldursGatePortal.onEnter": ("baldursGate.travel.AR0700",),
    "res/maps/baldursGate/script.py:BaldursGateContainer.onEnter": ("baldursGate.ownership.exactLootAndReload",),
    **{
        "res/maps/baldursGate/script.py:BaldursGateDialog." + callback: (branch,)
        for callback, branch in (
            ("historyAldethHelped", "baldursGate.history.helped"),
            ("historyAldethKilled", "baldursGate.history.killed"),
            ("historyTenyaHelped", "baldursGate.history.helped"),
            ("historyTenyaKilled", "baldursGate.history.killed"),
            ("returnFromInterlude", "baldursGate.interlude.earlyReturnRefused"),
            ("unlock", "baldursGate.locks.picked"),
            ("force", "baldursGate.locks.forced"),
            ("open", "baldursGate.ownership.exactLootAndReload"),
            ("useKey", "baldursGate.locks.refused"),
        )
    },
}

for _quest in documents()["quests"]:
    _key = upperFirst(_quest["id"])
    _branches = tuple("baldursGate.quest." + _quest["id"] + "." + outcome["id"] for outcome in _quest["outcomes"])
    for _method in ("accept" + _key, "canAccept" + _key):
        SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog." + _method] = _branches
    for _outcome, _branch in zip(_quest["outcomes"], _branches):
        _action = "quest" + _key + upperFirst(_outcome["id"])
        for _method in (_action, "can" + upperFirst(_action)):
            SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog." + _method] = (_branch,)

for _case in generatedStoreCases():
    _store_id = _case.id.removeprefix("baldurs-gate-store-")
    _token = upperFirst(_store_id.lower())
    SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog.canUseStore" + _token] = _case.branches
    for _branch in _case.branches:
        SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog." + _branch.rsplit(".", 1)[1]] = (_branch,)

SOURCE_BRANCHES.update(
    {
        "res/maps/baldursGate/script.py:BaldursGateQuest.isCompleted": ("baldursGate.quest.petrineRing.complete",),
        "res/maps/baldursGate/script.py:BaldursGateQuest.onComplete": ("baldursGate.quest.petrineRing.complete",),
        "res/maps/baldursGate/script.py:BaldursGateDeathTrigger.trigger": ("baldursGate.quest.bherenCat.complete",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.talk": ("baldursGate.quest.petrineRing.complete",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.attack": ("baldursGate.quest.bherenCat.complete",),
    }
)
for _excursion in json.loads((ROOT / "tests/fixtures/baldurs_gate_city_quests.json").read_text(encoding="utf-8"))[
    "excursions"
]:
    _branches = tuple(
        "baldursGate.excursion." + _excursion["id"] + "." + choice["id"] for choice in _excursion["choices"]
    )
    SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog.canExcursion" + upperFirst(_excursion["id"])] = (
        _branches
    )
    for _choice, _branch in zip(_excursion["choices"], _branches):
        SOURCE_BRANCHES[
            "res/maps/baldursGate/script.py:BaldursGateDialog.excursion"
            + upperFirst(_excursion["id"])
            + upperFirst(_choice["id"])
        ] = (_branch,)
SOURCE_BRANCHES.update(
    {
        "res/maps/baldursGate/script.py:BaldursGateDialog.pressPalaceSwitchOne": ("baldursGate.palace.twoSwitches",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.pressPalaceSwitchTwo": ("baldursGate.palace.twoSwitches",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.close": ("baldursGate.doors.openAndClose",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.disarm": ("baldursGate.traps.disarmed",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.cityInterlude": (
            "baldursGate.quest.cythandriaDiary.complete",
        ),
        "res/maps/baldursGate/script.py:BaldursGateDialog.warnNarlen": ("baldursGate.quest.narlenLookout.complete",),
        "res/maps/baldursGate/script.py:BaldursGateDialog.beginNarlenLookout": (
            "baldursGate.quest.narlenLookout.complete",
            "baldursGate.quest.narlenLookout.officerKilled",
        ),
        "res/maps/baldursGate/script.py:BaldursGateDialog.canBeginNarlenLookout": (
            "baldursGate.quest.narlenLookout.complete",
            "baldursGate.quest.narlenLookout.officerKilled",
        ),
        "res/maps/baldursGate/script.py:BaldursGatePersonTrigger.trigger": (
            "baldursGate.quest.petrineRing.refusalAndReturn",
        ),
    }
)
SOURCE_BRANCHES.update(
    {
        "res/maps/baldursGate/script.py:BaldursGateDialog." + method: (branch,)
        for method, branch in (
            ("recruit", "baldursGate.companions.fiveAndReload"),
            ("dismiss", "baldursGate.companions.dismissAndReturn"),
            ("helpAloraLookout", "baldursGate.companions.fiveAndReload"),
            ("canHelpAlora", "baldursGate.companions.fiveAndReload"),
            ("historyEldothJoined", "baldursGate.companions.fiveAndReload"),
            ("historyEldothAbsent", "baldursGate.companions.skieWithoutEldoth"),
            ("encounterQuayle", "baldursGate.companions.fiveAndReload"),
            ("waitHour", "baldursGate.companions.fiveAndReload"),
        )
    }
)


# The complete source ledger remains pending even when a representative adaptation route exists.
# Registration cannot turn a missing classic source branch into a passing native witness.
DEFENSIVE_SOURCE_BRANCHES = {
    "res/maps/baldursGate/script.py:BaldursGatePortal.onDestroy": "Connector teardown unregisters its owned edge; the named source/model regression gives no native gameplay credit.",
}

PENDING_GAMEPLAY_OBLIGATIONS = {
    "baldursGate.source."
    + entry["id"]: {
        "map": MAP,
        "sourceId": entry["id"],
        "ledger": "tests/fixtures/baldurs_gate_city_ledger.json",
        "implementationStatus": entry["implementation"]["status"],
        "reason": "Original-city parity and native source-outcome evidence remain pending; " + "; ".join(entry["gaps"]),
    }
    for entry in json.loads((ROOT / "tests/fixtures/baldurs_gate_city_ledger.json").read_text(encoding="utf-8"))[
        "entries"
    ]
    if entry["implementation"]["status"] != "excluded"
}
