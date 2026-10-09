# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from hashlib import sha256
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter
import unittest
import uuid
from unittest.mock import patch

from tests import test_ui_mcp_dialogue as dialogue_mcp
from tests.castle_walkthrough import TransitRoutes, shortestRoute
from tests.narrative_walkthrough import authoredRegion


def readNativeLogTail(path, *, max_bytes=65536, max_lines=256):
    if max_bytes <= 0 or max_lines <= 0:
        raise ValueError("Native diagnostic tail limits must be positive")
    path = Path(path)
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        offset = max(0, size - max_bytes)
        stream.seek(offset)
        raw = stream.read(max_bytes)
    lines = raw.splitlines()
    if offset and lines:
        lines = lines[1:]
    omitted_lines = max(0, len(lines) - max_lines)
    selected = b"\n".join(lines[-max_lines:])
    # Replacement characters can expand malformed UTF-8; bound the printed text as well as the read.
    encoded = selected.decode("utf-8", errors="replace").encode("utf-8")
    text = encoded[-max_bytes:].decode("utf-8", errors="ignore")
    return {
        "path": str(path),
        "fileBytes": size,
        "startOffset": offset,
        "readBytes": len(raw),
        "printedBytes": len(text.encode("utf-8")),
        "byteLimit": max_bytes,
        "lineLimit": max_lines,
        "truncated": bool(offset or omitted_lines or len(encoded) > max_bytes),
        "text": text,
    }


def retainDecisionReplayStreams(stdout, stderr):
    evidence = {"paths": {}, "bytes": {}, "errors": []}

    def report():
        try:
            print("Saved hunt decision replay streams", evidence, file=sys.stderr, flush=True)
        except Exception as error:
            evidence["errors"].append({"stream": "report", "type": type(error).__name__, "message": str(error)[:512]})

    try:
        import test as harness

        output = Path(harness.TEST_OUTPUT_DIR)
        output.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="mcp-octobogz-decision-", dir=output))
    except Exception as error:
        evidence["errors"].append({"stream": "directory", "type": type(error).__name__, "message": str(error)[:512]})
        report()
        return evidence
    for name, value in (("stdout", stdout), ("stderr", stderr)):
        path = directory / (name + ".log")
        try:
            raw = value if isinstance(value, bytes) else (value or "").encode("utf-8")
            with path.open("xb") as stream:
                stream.write(raw)
            evidence["paths"][name] = str(path)
            evidence["bytes"][name] = len(raw)
        except Exception as error:
            evidence["errors"].append({"stream": name, "type": type(error).__name__, "message": str(error)[:512]})
    report()
    return evidence


def reportDecisionReplayFailure(stdout, returncode, evidence):
    try:
        marker = "NATIVE_HUNT_DECISION_RESULT "
        reports = [json.loads(line[len(marker) :]) for line in stdout.splitlines() if line.startswith(marker)]
        if len(reports) != 1 or not isinstance(reports[0], dict):
            return
        report = reports[0]
        decisions = report.get("decisions", [])
        if not isinstance(decisions, list):
            return
        columns = (
            "index",
            "round",
            "slot",
            "target",
            "phase",
            "action",
            "hpBefore",
            "hpAfter",
            "hpMax",
            "manaBefore",
            "manaAfter",
            "enemyHpBefore",
            "enemyHpAfter",
            "enemyManaBefore",
            "enemyManaAfter",
            "cost",
            "refund",
            "item.typeId",
            "item.name",
            "item.power",
            "consumedOnce",
            "healOnlyDisposable",
            "inventoryCountBefore",
            "inventoryCountAfter",
            "finishingHitConditional",
            "finishingHitMinimum",
        )
        truncated_fields = 0

        def scalar(value, byte_limit=64):
            nonlocal truncated_fields
            if value is None or isinstance(value, (bool, int, float)):
                return value
            if not isinstance(value, str):
                truncated_fields += 1
                return None
            raw = value.encode("utf-8", errors="replace")
            if len(raw) > byte_limit:
                truncated_fields += 1
                return raw[:byte_limit].decode("utf-8", errors="ignore")
            return value

        rows = []
        for index, decision in enumerate(decisions[:256]):
            row = [index]
            for key in columns[1:]:
                if key.startswith("item."):
                    item = decision.get("item") if isinstance(decision, dict) else None
                    value = item.get(key[5:]) if isinstance(item, dict) else None
                else:
                    value = decision.get(key) if isinstance(decision, dict) else None
                row.append(scalar(value))
            encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > 4096:
                truncated_fields += 1
                encoded = json.dumps([index] + [None] * (len(columns) - 1), separators=(",", ":"))
            rows.append(encoded)
        metadata = {
            key: scalar(report.get(key))
            for key in (
                "mode",
                "saveSlot",
                "seed",
                "success",
                "movements",
                "cardinalVerified",
                "paidBarriers",
                "playerAlive",
                "defeatReceiptUnchanged",
                "sourceUnchanged",
            )
        }
        metadata.update(returncode=returncode, error=scalar(report.get("error"), 256))
        before = report.get("playerBefore", {})
        metadata["playerBefore"] = (
            {
                key: scalar(before.get(key))
                for key in (
                    "name",
                    "typeId",
                    "classId",
                    "level",
                    "exp",
                    "hp",
                    "hpMax",
                    "mana",
                    "manaMax",
                    "gold",
                )
            }
            if isinstance(before, dict)
            else None
        )
        composed = report.get("playerComposedStatsBefore", {})
        properties = composed.get("properties", {}) if isinstance(composed, dict) else {}
        metadata["composedStatsBefore"] = (
            {
                key: scalar(properties.get(key))
                for key in (
                    "dmgMin",
                    "dmgMax",
                    "damage",
                    "hit",
                    "attack",
                    "armor",
                    "normalResist",
                    "shadowResist",
                    "crit",
                    "block",
                )
            }
            if isinstance(properties, dict)
            else None
        )
        metadata.update(
            totalDecisions=len(decisions),
            printedDecisions=len(rows),
            decisionsTruncated=len(decisions) > 256,
            truncatedFields=truncated_fields,
            rowByteLimit=4096,
            metadataByteLimit=8192,
        )
        metadata["artifactPaths"] = {key: scalar(value, 256) for key, value in evidence["paths"].items()}
        metadata["truncatedFields"] = truncated_fields
        encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 8192:
            encoded = json.dumps(
                {
                    "returncode": returncode,
                    "totalDecisions": len(decisions),
                    "printedDecisions": len(rows),
                    "decisionsTruncated": len(decisions) > 256,
                    "metadataTruncated": True,
                    "metadataByteLimit": 8192,
                    "rowByteLimit": 4096,
                },
                separators=(",", ":"),
            )
        print("HUNT_DECISION_FAILURE_META " + encoded, file=sys.stderr, flush=True)
        print("HUNT_DECISION_FAILURE_COLUMNS " + json.dumps(columns), file=sys.stderr, flush=True)
        for row in rows:
            print("HUNT_DECISION_FAILURE_ROW " + row, file=sys.stderr, flush=True)
    except Exception:
        pass


class OctobogzMcpWalkthroughTest(unittest.TestCase):
    def setUp(self):
        import test as harness
        from types import SimpleNamespace

        self.native_log_path = harness.TEST_OUTPUT_DIR / f"mcp-octobogz-native-{uuid.uuid4().hex}.log"
        startup = harness.McpServerTest._start_stdio_mcp_process

        def startWithNativeLog(instance, *args, **kwargs):
            kwargs.setdefault("map_name", "nouraajd")
            kwargs.setdefault("trace_name", "octobogz-" + uuid.uuid4().hex)
            with patch.dict(os.environ, GAME_PLAYTEST_TRACE_RETAIN_RECENT="1"):
                return startup(instance, *args, native_log_file=self.native_log_path, **kwargs)

        with patch.object(harness.McpServerTest, "_start_stdio_mcp_process", startWithNativeLog):
            dialogue_mcp.DialogueMcpWalkthroughTest.setUp(self)
        self._native_combat_validator = SimpleNamespace(
            test=self,
            trace_path=self.process._playtest_trace_path,
            _combat_trace_positions={},
            _combat_trace_seq=0,
            _combat_failure=None,
            player=None,
        )
        self.assertIsNotNone(self._native_combat_validator.trace_path)
        print("MCP hunt native log", str(self.native_log_path), flush=True)
        print("MCP hunt native trace", str(self._native_combat_validator.trace_path), flush=True)

    def pump(self):
        from tests.gameplay_branch_driver import GameplayBranchDriver

        validator = getattr(self, "_native_combat_validator", None)
        if validator is not None:
            GameplayBranchDriver.assertNativeCombatOutcomes(validator)
        loop = self.engine("event_loop.instance")
        for _ in range(3):
            self.call(loop, "run")
            if validator is not None:
                GameplayBranchDriver.assertNativeCombatOutcomes(validator)

    object = dialogue_mcp.DialogueMcpWalkthroughTest.object
    dialog = dialogue_mcp.DialogueMcpWalkthroughTest.dialog
    action = dialogue_mcp.DialogueMcpWalkthroughTest.action
    questNames = dialogue_mcp.DialogueMcpWalkthroughTest.questNames

    def resetMcpProfile(self, player_class):
        self.mcp_profile_class = player_class
        self.mcp_profile_started = perf_counter()
        self.mcp_method_profile = {}

    def profiledMcpCall(self, key, callback, *args):
        started = perf_counter()
        failed = False
        try:
            return callback(self, *args)
        except BaseException:
            failed = True
            raise
        finally:
            elapsed = perf_counter() - started
            if not hasattr(self, "mcp_method_profile"):
                self.mcp_method_profile = {}
                self.mcp_profile_started = started
            entry = self.mcp_method_profile.setdefault(key, {"count": 0, "seconds": 0.0, "max": 0.0, "failures": 0})
            entry["count"] += 1
            entry["seconds"] += elapsed
            entry["max"] = max(entry["max"], elapsed)
            entry["failures"] += int(failed)

    def engine(self, name, *args):
        return self.profiledMcpCall("export:" + name, dialogue_mcp.DialogueMcpWalkthroughTest.engine, name, *args)

    def call(self, handle, method, *args):
        return self.profiledMcpCall(
            "handle:" + method, dialogue_mcp.DialogueMcpWalkthroughTest.call, handle, method, *args
        )

    def reportMcpProfile(self, stage):
        profile = getattr(self, "mcp_method_profile", {})
        now = perf_counter()
        methods = [
            {
                "method": name,
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in values.items()},
            }
            for name, values in sorted(profile.items(), key=lambda entry: (-entry[1]["seconds"], entry[0]))[:64]
        ]
        print(
            "MCP hunt method profile",
            {
                "class": getattr(self, "mcp_profile_class", "unassigned"),
                "stage": stage,
                "steps": getattr(self, "movement_steps", 0),
                "elapsed": round(now - getattr(self, "mcp_profile_started", now), 6),
                "calls": sum(entry["count"] for entry in profile.values()),
                "rpcSeconds": round(sum(entry["seconds"] for entry in profile.values()), 6),
                "methods": methods,
                "omittedMethods": max(0, len(profile) - len(methods)),
            },
            flush=True,
        )

    def probeCoordinateReadCosts(self):
        expected = self.fullJsonCoords()
        turn_before = self.call(self.game_map, "getTurn")
        state_before = self.state()
        resources_before = (self.call(self.player, "getHp"), self.call(self.player, "getMana"))
        full_samples, scalar_samples = [], []
        for index in range(21):
            started = perf_counter()
            full_coords = self.fullJsonCoords()
            full_elapsed = perf_counter() - started
            started = perf_counter()
            scalar_coords = tuple(self.call(self.player, "getNumericProperty", "pos" + axis) for axis in "xyz")
            scalar_elapsed = perf_counter() - started
            self.assertEqual(expected, full_coords)
            self.assertEqual(full_coords, scalar_coords)
            self.assertEqual(turn_before, self.call(self.game_map, "getTurn"))
            self.assertEqual(state_before, self.state())
            if index:
                full_samples.append(full_elapsed)
                scalar_samples.append(scalar_elapsed)
        self.assertEqual(resources_before, (self.call(self.player, "getHp"), self.call(self.player, "getMana")))
        print(
            "MCP hunt paired coordinate read probe",
            {
                "class": getattr(self, "mcp_profile_class", "unassigned"),
                "samples": 20,
                "warmup": 1,
                "coords": expected,
                "turn": turn_before,
                "fullJsonRpcPerSample": 1,
                "scalarRpcPerSample": 3,
                "fullJsonMedianSeconds": round(median(full_samples), 6),
                "scalarMedianSeconds": round(median(scalar_samples), 6),
                "fullJsonTotalSeconds": round(sum(full_samples), 6),
                "scalarTotalSeconds": round(sum(scalar_samples), 6),
            },
            flush=True,
        )

    def state(self):
        return json.loads(
            self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry").removeprefix("octobogzHunt.v1:")
        )

    def refresh(self):
        self.game_map = self.call(self.game, "getMap")
        self.player = self.call(self.game_map, "getPlayer")
        registered = self.call(self.game_map, "getObjectByName", self.call(self.player, "getName"))
        self.assertEqual(self.player["__handle__"], registered["__handle__"])

    def fullJsonCoords(self, handle=None):
        data = json.loads(self.engine("jsonify", handle or self.player))["properties"]
        return tuple(data["pos" + axis] for axis in "xyz")

    def coords(self, handle=None):
        actor = handle or self.player
        return tuple(self.call(actor, "getNumericProperty", "pos" + axis) for axis in "xyz")

    def snapshot(self, stage):
        data = json.loads(self.engine("jsonify", self.player))["properties"]
        coords = self.coords()
        self.assertEqual(
            tuple(data["pos" + axis] for axis in "xyz"), coords, "Scalar coordinates must match the native snapshot"
        )
        result = {
            "stage": stage,
            "coords": coords,
            "level": self.call(self.player, "getLevel"),
            "exp": self.call(self.player, "getNumericProperty", "exp"),
            "hp": data.get("hp"),
            "mana": self.call(self.player, "getMana"),
            "gold": self.call(self.player, "getGold"),
            "items": [item["properties"].get("typeId") for item in data.get("items") or []],
            "turn": self.call(self.game_map, "getTurn"),
            "defeat": self.call(self.player, "getStringProperty", "uiDefeatReceipt"),
        }
        print("MCP hunt journey", result, flush=True)
        self.reportMcpProfile(stage)
        return result

    def step(self, destination):
        origin = self.coords()
        defeat_before = self.call(self.player, "getStringProperty", "uiDefeatReceipt")
        self.assertEqual(1, sum(abs(a - b) for a, b in zip(origin, destination)))
        tile = self.call(self.game_map, "getTile", *destination)
        self.assertIsNotNone(tile, destination)
        self.assertTrue(self.call(tile, "getBoolProperty", "canStep"), destination)
        capture = getattr(self, "capture_before_move", None)
        if capture:
            capture(origin, destination)
        # Native adjacent moveTo checks CMap.canStep before committing, including object footprints.
        self.call(self.player, "moveTo", *destination)
        self.pump()
        if capture:
            capture(origin, destination)
        if not self.call(self.player, "isAlive"):
            self.fail(self.snapshot("defeated during movement"))
        if self.call(self.player, "getStringProperty", "uiDefeatReceipt") != defeat_before:
            self.fail(self.snapshot("lost authored combat and respawned"))
        recover = getattr(self, "recover_before_map_turn", None)
        if recover:
            recover()
        turn = self.call(self.game_map, "getTurn")
        self.call(self.game_map, "move")
        self.pump()
        self.assertEqual(turn + 1, self.call(self.game_map, "getTurn"))
        if not self.call(self.player, "isAlive"):
            self.fail(self.snapshot("defeated during movement"))
        if self.call(self.player, "getStringProperty", "uiDefeatReceipt") != defeat_before:
            self.fail(self.snapshot("lost authored combat and respawned"))
        arrival = self.coords()
        if sum(abs(a - b) for a, b in zip(origin, arrival)) > 1:
            self.fail(
                ("Unexpected movement without an authored transit", origin, destination, self.snapshot("arrival"))
            )
        self.movement_steps += 1
        if self.movement_steps % 128 == 0:
            self.reportMcpProfile("adjacent movement checkpoint")
        return arrival

    def walkTo(self, name, *, allow_removed=False):
        return self.walkRoute(name, allow_removed=allow_removed)

    def walkCoords(self, coords):
        return self.walkRoute(tuple(coords))

    def walkRoute(self, target, *, allow_removed=False):
        route = []
        planned_target = None
        blockers = None
        for _ in range(512):
            actor = self.call(self.game_map, "getObjectByName", target) if isinstance(target, str) else None
            if isinstance(target, str):
                if actor is None and allow_removed:
                    return
                self.assertIsNotNone(actor, target)
                destination = self.coords(actor)
            else:
                destination = target
            current = self.coords()
            if current == destination:
                return actor
            if planned_target != destination or not route:
                route = shortestRoute(self.walkable, TransitRoutes(), current, destination)
                planned_target = destination
            step, expected = route.pop(0)
            tile = self.call(self.game_map, "getTile", *step)
            self.assertIsNotNone(tile, step)
            if not self.call(tile, "getBoolProperty", "canStep"):
                self.walkable.discard(step)
                route = []
                continue
            if self.step(step) != expected:
                # Player victories restore the origin, including repeated fights in a cave cell.
                if blockers is None:
                    blockers = [
                        candidate
                        for candidate in self.call(self.game_map, "getObjects")
                        if not self.call(candidate, "getBoolProperty", "canStep")
                    ]
                for blocker in blockers:
                    if self.coords(blocker) == step and not self.call(
                        self.game_map, "canStep", self.call(blocker, "getCoords")
                    ):
                        self.walkable.discard(step)
                route = []
        self.fail(("Bounded adjacent hunt route did not reach its target", target, self.snapshot("route blocked")))

    def roadDepartureState(self):
        properties = json.loads(self.engine("jsonify", self.player))["properties"]
        controller = self.call(self.player, "getFightController")
        movement_controller = self.call(self.player, "getController")
        return {
            "player": {key: value for key, value in properties.items() if key not in ("hp", "items")},
            "hpMax": self.call(self.player, "getHpMax"),
            "mana": self.call(self.player, "getMana"),
            "manaMax": self.call(self.player, "getManaMax"),
            "controller": controller["__handle__"] if controller else None,
            "movementController": movement_controller["__handle__"] if movement_controller else None,
            "coords": self.coords(),
            "turn": self.call(self.game_map, "getTurn"),
            "registry": self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry"),
            "quests": self.questNames(),
            "completed": self.questNames("getCompletedQuests"),
        }

    def recoverBeforeRoadDeparture(self, *, target_percent=75):
        self.assertIn(target_percent, (75, 100))
        self.assertTrue(self.call(self.player, "isAlive"), "Road recovery cannot revive a defeated player")
        self.assertEqual("", self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
        hp_max = self.call(self.player, "getHpMax")
        self.assertGreater(hp_max, 0)
        hp = self.call(self.player, "getHp")
        self.assertGreater(hp, 0)
        if hp * 100 >= hp_max * target_percent:
            return
        configured = json.loads(
            (Path(__file__).resolve().parents[1] / "res/config/potions.json").read_text(encoding="utf-8")
        )
        life_ids = {
            type_id
            for type_id, definition in configured.items()
            if definition.get("class") == "LifePotion" and definition.get("properties", {}).get("singleUse") is True
        }
        candidates = []
        for item in self.call(self.player, "getItems"):
            type_id = self.call(item, "getTypeId")
            if type_id not in life_ids or self.call(item, "getType") != "LifePotion":
                continue
            if not self.call(item, "getBoolProperty", "singleUse"):
                continue
            if (
                not self.call(item, "hasTag", "heal")
                or self.call(item, "hasTag", "mana")
                or self.call(item, "hasTag", "quest")
            ):
                continue
            power = self.call(item, "getNumericProperty", "power")
            if power > 0:
                candidates.append((power, type_id, self.call(item, "getName"), item))
        self.assertLessEqual(len(candidates), 128)
        for power, type_id, name, item in sorted(candidates, key=lambda candidate: candidate[:3]):
            self.assertTrue(self.call(self.player, "isAlive"))
            self.assertEqual("", self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
            hp_before = self.call(self.player, "getHp")
            self.assertGreater(hp_before, 0)
            if hp_before * 100 >= hp_max * target_percent:
                break
            owned = self.call(self.player, "getItems")
            identities = {candidate["__handle__"] for candidate in owned}
            identity = item["__handle__"]
            self.assertIn(identity, identities)
            before = self.roadDepartureState()
            self.call(self.player, "useItem", item)
            self.assertTrue(self.call(self.player, "isAlive"))
            self.assertEqual("", self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
            hp_after = self.call(self.player, "getHp")
            self.assertEqual(min(hp_max, hp_before + max(1, int(power * 20 / 100.0 * hp_max))), hp_after)
            self.assertGreater(hp_after, hp_before)
            after_items = self.call(self.player, "getItems")
            self.assertEqual(identities - {identity}, {candidate["__handle__"] for candidate in after_items})
            self.assertEqual(len(owned) - 1, len(after_items))
            self.assertEqual(before, self.roadDepartureState())
            print(
                "MCP hunt owned departure recovery",
                {"typeId": type_id, "name": name, "hpBefore": hp_before, "hpAfter": hp_after},
                flush=True,
            )

    def recoverOnAuthoredRoad(self):
        actors = getattr(self, "hunt_actors", {})
        try:
            actors = self.livingActors()
            self.recoverBeforeRoadDeparture()
            self.recoverOnRoadPair((118, 21, 0), (118, 20, 0), "hunt road recovery", actors)
        except Exception:
            try:
                self.reportCombatFailure("hunt road recovery", getattr(self, "hunt_actors", actors))
            except Exception:
                pass
            raise

    def equipEarnedBroodWeapon(self):
        inventory = self.call(self.player, "getItems")
        swords = [item for item in inventory if self.call(item, "getTypeId") == "LongSword"]
        if not swords:
            return None
        current = self.call(self.player, "getItemAtSlot", "0")
        if current is None or self.call(current, "getTypeId") != "Staff":
            return None
        self.assertLessEqual(len(swords), 128)
        sword = min(swords, key=lambda item: self.call(item, "getName"))
        self.assertEqual("CWeapon", self.call(sword, "getType"))
        old_bonus = json.loads(self.engine("jsonify", current))["properties"]["bonus"]["properties"]
        new_bonus = json.loads(self.engine("jsonify", sword))["properties"]["bonus"]["properties"]
        delta = {
            key: new_bonus.get(key, 0) - old_bonus.get(key, 0)
            for key in ("dmgMin", "dmgMax", "stamina", "intelligence")
        }
        self.assertGreater(delta["dmgMin"], 0)
        self.assertGreater(delta["dmgMax"], 0)
        self.assertEqual(0, delta["stamina"], "Earned weapon preparation must preserve the native HP maximum")

        def nativeContext():
            data = json.loads(self.engine("jsonify", self.player))["properties"]
            return (
                {key: value for key, value in data.items() if key not in ("items", "equipped", "hp", "mana")},
                self.coords(),
                self.call(self.game_map, "getTurn"),
                self.state(),
                self.questNames(),
                self.questNames("getCompletedQuests"),
            )

        context = nativeContext()
        equipped_before = self.call(self.player, "getEquipped")
        owned_before = {item["__handle__"] for item in inventory}
        hp_before, mana_before = self.call(self.player, "getHp"), self.call(self.player, "getMana")
        hp_max, mana_max = self.call(self.player, "getHpMax"), self.call(self.player, "getManaMax")
        self.call(self.player, "equipItem", "0", sword)
        self.assertEqual({**equipped_before, "0": sword}, self.call(self.player, "getEquipped"))
        self.assertEqual(
            (owned_before - {sword["__handle__"]}) | {current["__handle__"]},
            {item["__handle__"] for item in self.call(self.player, "getItems")},
        )
        self.assertEqual(context, nativeContext(), "An owned equipment swap cannot change progression or other gear")
        self.assertEqual(hp_max, self.call(self.player, "getHpMax"))
        self.assertEqual(mana_max + delta["intelligence"] * 7, self.call(self.player, "getManaMax"))
        self.assertEqual(hp_before, self.call(self.player, "getHp"))
        self.assertEqual(min(mana_before, self.call(self.player, "getManaMax")), self.call(self.player, "getMana"))
        receipt = {
            "weapon": self.call(sword, "getName"),
            "ownedHandle": sword["__handle__"],
            "weaponBonusDelta": delta,
            "hpMaxBefore": hp_max,
            "hpMaxAfter": self.call(self.player, "getHpMax"),
            "manaMaxBefore": mana_max,
            "manaMaxAfter": self.call(self.player, "getManaMax"),
            "manaBefore": mana_before,
            "manaAfter": self.call(self.player, "getMana"),
        }
        print("MCP hunt actual earned weapon preparation", receipt, flush=True)
        return receipt

    def recoverBeforeRemainingBrood(self, player_class):
        if self.state()["slots"]["brood"]["status"] == "dead":
            self.assertSlotDefeated("brood")
            return
        self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "cave2"))
        self.assertFalse(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
        self.recoverOnAuthoredRoad()
        if self.state()["slots"]["brood"]["status"] == "dead":
            self.assertSlotDefeated("brood")
            return
        if player_class == "Sorcerer":
            self.prepareHealingStockAtAuthoredMarket(initial=False)
            self.equipEarnedBroodWeapon()
            self.recoverOnAuthoredRoad()

    def collectAuthoredRetreatScroll(self):
        before = self.call(self.player, "countItems", "TownPortalScroll")
        self.walkTo("townPortalScroll", allow_removed=True)
        self.assertIsNone(self.call(self.game_map, "getObjectByName", "townPortalScroll"))
        self.assertEqual(before + 1, self.call(self.player, "countItems", "TownPortalScroll"))
        self.snapshot("collected authored retreat scroll")

    def retreatWithOwnedAuthoredScroll(self):
        scrolls = [
            item for item in self.call(self.player, "getItems") if self.call(item, "getTypeId") == "TownPortalScroll"
        ]
        self.assertEqual(1, len(scrolls), "Retreat must use the actual collected, owned source scroll")
        before = self.snapshot("before owned town portal retreat")
        hunt_before = self.state()
        count_before = self.call(self.player, "countItems", "TownPortalScroll")
        self.call(self.player, "useItem", scrolls[0])
        self.pump()
        self.assertEqual(self.game_map, self.call(self.game, "getMap"))
        self.assertEqual(self.player, self.call(self.game_map, "getPlayer"))
        entry = tuple(self.call(self.game_map, method) for method in ("getEntryX", "getEntryY", "getEntryZ"))
        self.assertEqual((110, 111, 0), entry)
        self.assertEqual(entry, self.coords())
        self.assertEqual(before["defeat"], self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
        self.assertEqual(hunt_before, self.state())
        self.assertEqual(count_before - 1, self.call(self.player, "countItems", "TownPortalScroll"))
        self.assertGreater(self.call(self.player, "getHp"), 0)
        self.snapshot("owned town portal retreat complete")
        self.recoverOnRoadPair((110, 111, 0), (109, 111, 0), "town portal road recovery")

    def recoverOnRoadPair(self, first, second, stage, actors=None):
        self.assertEqual(1, sum(abs(a - b) for a, b in zip(first, second)))
        for destination in (first, second):
            tile = self.call(self.game_map, "getTile", *destination)
            self.assertEqual("RoadTile", self.call(tile, "getTypeId"))
        self.walkCoords(first)
        self.snapshot(stage + " arrival")
        if actors:
            self.observeActors(stage + " arrival", actors)
        for index in range(128):
            destination = second if index % 2 == 0 else first
            tile = self.call(self.game_map, "getTile", *destination)
            self.assertEqual("RoadTile", self.call(tile, "getTypeId"))
            self.step(destination)
            if self.call(self.player, "getHp") == self.call(self.player, "getHpMax") and self.call(
                self.player, "getMana"
            ) == self.call(self.player, "getManaMax"):
                self.snapshot(stage + " complete")
                return
        self.fail(
            ("Authored road steps did not restore the ordinary player", self.snapshot("road recovery incomplete"))
        )

    def nearbyAuthoredPritz(self, anchor):
        current = self.coords()
        candidates = []
        for actor in self.call(self.game_map, "getObjects"):
            if self.call(actor, "getTypeId") != "Pritz" or not self.call(actor, "isAlive"):
                continue
            if self.call(actor, "getStringProperty", "affiliation") != "gooby":
                continue
            coords = self.coords(actor)
            if coords[2] == anchor[2] and abs(coords[0] - anchor[0]) + abs(coords[1] - anchor[1]) <= 55:
                candidates.append((sum(abs(a - b) for a, b in zip(current, coords)), self.call(actor, "getName")))
        return sorted(candidates)

    def nearbyRolfEnemies(self):
        return self.nearbyAuthoredPritz((19, 10, 0))

    def marketTransactionState(self):
        player = json.loads(self.engine("jsonify", self.player))["properties"]
        return {
            "player": {key: value for key, value in player.items() if key not in ("items", "gold")},
            "turn": self.call(self.game_map, "getTurn"),
            "registry": self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry"),
            "quests": self.questNames(),
            "completed": self.questNames("getCompletedQuests"),
        }

    def sellWeakHealingStockAtAuthoredMarket(self, preserve_ingredients=False):
        self.walkTo("market1")
        market_actor = self.object("market1")
        self.assertEqual((106, 111, 0), self.coords(market_actor))
        self.assertEqual(self.coords(market_actor), self.coords())
        market = self.call(market_actor, "getObjectProperty", "market")
        self.assertIsNotNone(market)
        inventory = self.call(self.player, "getItems")
        strong = [
            item
            for item in inventory
            if self.call(item, "hasTag", "heal") and self.call(item, "getNumericProperty", "power") > 1
        ]
        if not preserve_ingredients:
            self.assertTrue(strong, "Ordinary preparation must retain genuinely earned stronger healing stock")
        weak = [
            item
            for item in inventory
            if self.call(item, "hasTag", "heal")
            and not self.call(item, "hasTag", "mana")
            and self.call(item, "getNumericProperty", "power") == 1
            and self.call(item, "getBoolProperty", "singleUse")
            and (not preserve_ingredients or self.call(item, "getTypeId") != "LesserLifePotion")
        ]
        weak.sort(key=lambda item: (self.call(item, "getTypeId"), self.call(item, "getName")))
        self.assertLessEqual(len(weak), 128)
        before = self.marketTransactionState()
        sold = []
        for item in weak:
            identity = item["__handle__"]
            self.assertIn(identity, [owned["__handle__"] for owned in self.call(self.player, "getItems")])
            gold_before = self.call(self.player, "getGold")
            price = self.call(market, "getBuyCost", item)
            self.assertGreater(price, 0)
            self.call(market, "buyItem", self.player, item)
            self.assertEqual(gold_before + price, self.call(self.player, "getGold"))
            self.assertNotIn(identity, [owned["__handle__"] for owned in self.call(self.player, "getItems")])
            self.assertIn(identity, [stocked["__handle__"] for stocked in self.call(market, "getItems")])
            self.assertEqual(before, self.marketTransactionState())
            sold.append({"name": self.call(item, "getName"), "typeId": self.call(item, "getTypeId"), "price": price})
        for item in strong:
            self.assertIn(item["__handle__"], [owned["__handle__"] for owned in self.call(self.player, "getItems")])
        print("MCP hunt ordinary authored market preparation", {"sold": sold, "strongStock": len(strong)}, flush=True)

    def basicLesserIngredients(self, items):
        return sorted(
            [item for item in items if self.call(item, "getTypeId") == "LesserLifePotion"],
            key=lambda item: self.call(item, "getName"),
        )

    def brewOwnedBasicLifePotions(self):
        self.walkTo("alchemyTable1")
        station = self.object("alchemyTable1")
        self.assertEqual((105, 110, 0), self.coords(station))
        self.assertEqual(self.coords(station), self.coords())
        self.assertEqual("CraftingStation", self.call(station, "getType"))
        self.assertEqual("alchemyTable1", self.call(station, "getTypeId"))
        self.assertEqual("alchemyTable", self.call(station, "getStringProperty", "craftingStationId"))
        self.assertTrue(self.call(station, "getBoolProperty", "enabled"))
        crafted = 0
        while len(self.basicLesserIngredients(self.call(self.player, "getItems"))) >= 2:
            gold_before = self.call(self.player, "getGold")
            if gold_before < 20:
                break
            self.assertLess(crafted, 64, "Basic brewing must consume bounded existing ingredients")
            before = self.marketTransactionState()
            inventory = self.call(self.player, "getItems")
            identities = {item["__handle__"]: item for item in inventory}
            lesser = {item["__handle__"] for item in self.basicLesserIngredients(inventory)}
            result = self.engine("craftRecipe", self.game, station, "brew_life_potion")
            self.pump()
            self.assertEqual({"ok": True, "reason": ""}, result)
            self.assertEqual(gold_before - 20, self.call(self.player, "getGold"))
            after_items = {item["__handle__"]: item for item in self.call(self.player, "getItems")}
            removed = set(identities) - set(after_items)
            added = set(after_items) - set(identities)
            self.assertEqual(2, len(removed))
            self.assertTrue(removed <= lesser, "The ordinary recipe must consume only actual Lesser Life ingredients")
            self.assertEqual(1, len(added))
            output = after_items[added.pop()]
            self.assertEqual("LifePotion", self.call(output, "getTypeId"))
            self.assertEqual(2, self.call(output, "getNumericProperty", "power"))
            self.assertEqual(before, self.marketTransactionState())
            crafted += 1
        print(
            "MCP hunt ordinary basic brewing",
            {"crafted": crafted, "gold": self.call(self.player, "getGold")},
            flush=True,
        )
        return crafted

    def fundBasicIngredientsWithOwnedMana(self, market, required_gold):
        self.assertEqual((106, 111, 0), self.coords())
        self.assertEqual(market, self.call(self.object("market1"), "getObjectProperty", "market"))
        shortfall = required_gold - self.call(self.player, "getGold")
        if shortfall <= 0 or self.call(self.player, "getMana") != self.call(self.player, "getManaMax"):
            return 0
        potions = json.loads(
            (Path(__file__).resolve().parents[1] / "res/config/potions.json").read_text(encoding="utf-8")
        )
        disposable_mana_ids = {
            type_id
            for type_id, config in potions.items()
            if config.get("class") == "ManaPotion" and config.get("properties", {}).get("singleUse") is True
        }
        inventory = self.call(self.player, "getItems")
        candidates = [
            item
            for item in inventory
            if self.call(item, "getTypeId") in disposable_mana_ids
            and self.call(item, "hasTag", "mana")
            and not self.call(item, "hasTag", "heal")
            and not self.call(item, "hasTag", "quest")
            and self.call(item, "getBoolProperty", "singleUse")
        ]
        self.assertLessEqual(len(candidates), 128)
        quoted = [
            (self.call(market, "getBuyCost", item), self.call(item, "getTypeId"), self.call(item, "getName"), item)
            for item in candidates
        ]
        quoted = sorted((quote for quote in quoted if quote[0] > 0), key=lambda quote: quote[:3])
        selected, proceeds = [], 0
        for quote in quoted:
            selected.append(quote)
            proceeds += quote[0]
            if proceeds >= shortfall:
                break
        if proceeds < shortfall:
            return 0
        before = self.marketTransactionState()
        owned = {item["__handle__"] for item in inventory}
        stocked = {item["__handle__"] for item in self.call(market, "getItems")}
        sold = []
        for price, type_id, name, item in selected:
            identity = item["__handle__"]
            self.assertIn(identity, owned)
            self.assertNotIn(identity, stocked)
            self.assertIn(identity, [entry["__handle__"] for entry in self.call(self.player, "getItems")])
            gold_before = self.call(self.player, "getGold")
            self.call(market, "buyItem", self.player, item)
            self.assertEqual(gold_before + price, self.call(self.player, "getGold"))
            owned.remove(identity)
            stocked.add(identity)
            self.assertEqual(owned, {entry["__handle__"] for entry in self.call(self.player, "getItems")})
            self.assertEqual(stocked, {entry["__handle__"] for entry in self.call(market, "getItems")})
            self.assertEqual(before, self.marketTransactionState())
            sold.append({"name": name, "typeId": type_id, "price": price})
        self.assertGreaterEqual(self.call(self.player, "getGold"), required_gold)
        print(
            "MCP hunt owned mana funding",
            {"sold": sold, "requiredGold": required_gold, "gold": self.call(self.player, "getGold")},
            flush=True,
        )
        return len(sold)

    def buyFiniteBasicIngredientsAtAuthoredMarket(self, initial):
        self.walkTo("market1")
        market_actor = self.object("market1")
        self.assertEqual((106, 111, 0), self.coords(market_actor))
        self.assertEqual(self.coords(market_actor), self.coords())
        market = self.call(market_actor, "getObjectProperty", "market")
        candidates = self.basicLesserIngredients(self.call(market, "getItems"))
        if initial and not hasattr(self, "original_lesser_shop_names"):
            self.original_lesser_shop_names = tuple(self.call(item, "getName") for item in candidates)
            self.purchased_lesser_shop_names = set()
            self.retained_lesser_shop_name = self.call(candidates[-1], "getName") if candidates else None
        original_names = getattr(self, "original_lesser_shop_names", ())
        purchased_names = getattr(self, "purchased_lesser_shop_names", set())
        candidates = [
            item
            for item in candidates
            if self.call(item, "getName") in original_names and self.call(item, "getName") not in purchased_names
        ]
        if initial:
            candidates = [item for item in candidates if self.call(item, "getName") != self.retained_lesser_shop_name]
        needed = 1 if len(self.basicLesserIngredients(self.call(self.player, "getItems"))) % 2 else 2
        receipt = {
            "initial": initial,
            "originalNames": list(original_names),
            "purchasedNames": sorted(purchased_names),
            "availableOriginalNames": [self.call(item, "getName") for item in candidates],
            "needed": needed,
            "gold": self.call(self.player, "getGold"),
        }
        candidates = candidates[:needed]
        if len(candidates) < needed:
            print("MCP hunt finite original stock", {**receipt, "skip": "incomplete original pair"}, flush=True)
            return 0
        quotes = [self.call(market, "getSellCost", item) for item in candidates]
        self.assertTrue(all(price > 0 for price in quotes))
        required_gold = sum(quotes) + 20
        if required_gold > self.call(self.player, "getGold"):
            self.fundBasicIngredientsWithOwnedMana(market, required_gold)
            receipt["gold"] = self.call(self.player, "getGold")
        if required_gold > self.call(self.player, "getGold"):
            print("MCP hunt finite original stock", {**receipt, "quotes": quotes, "skip": "unaffordable"}, flush=True)
            return 0
        print("MCP hunt finite original stock", {**receipt, "quotes": quotes, "skip": ""}, flush=True)
        before = self.marketTransactionState()
        purchases = []
        for item, price in zip(candidates, quotes):
            identity = item["__handle__"]
            self.assertIn(identity, [stocked["__handle__"] for stocked in self.call(market, "getItems")])
            self.assertNotIn(identity, [owned["__handle__"] for owned in self.call(self.player, "getItems")])
            gold_before = self.call(self.player, "getGold")
            self.assertTrue(self.call(market, "sellItem", self.player, item))
            self.assertEqual(gold_before - price, self.call(self.player, "getGold"))
            self.assertNotIn(identity, [stocked["__handle__"] for stocked in self.call(market, "getItems")])
            self.assertIn(identity, [owned["__handle__"] for owned in self.call(self.player, "getItems")])
            self.assertEqual(before, self.marketTransactionState())
            name = self.call(item, "getName")
            self.purchased_lesser_shop_names.add(name)
            purchases.append({"name": name, "price": price})
        print("MCP hunt finite authored ingredient purchase", {"initial": initial, "items": purchases}, flush=True)
        return len(purchases)

    def prepareHealingStockAtAuthoredMarket(self, initial=True):
        try:
            self.brewOwnedBasicLifePotions()
            self.sellWeakHealingStockAtAuthoredMarket(preserve_ingredients=True)
            self.brewOwnedBasicLifePotions()
            self.buyFiniteBasicIngredientsAtAuthoredMarket(initial)
            self.brewOwnedBasicLifePotions()
            self.sellWeakHealingStockAtAuthoredMarket()
            self.snapshot("initial basic healing preparation" if initial else "new loot healing preparation")
        except Exception:
            try:
                self.reportCombatFailure("healing preparation", getattr(self, "hunt_actors", {}))
            except Exception:
                pass
            raise

    def earnSorcererWardScroll(self):
        self.assertEqual(self.coords(self.object("nouraajdChapel")), self.coords())
        dialog = self.dialog("berenDialog")
        self.assertTrue(self.call(dialog, "invokeCondition", "can_decode_stained_glass_ward"))
        before = {item["__handle__"] for item in self.call(self.player, "getItems")}
        self.action(dialog, "decode_stained_glass_ward")
        inventory = self.call(self.player, "getItems")
        after = {item["__handle__"] for item in inventory}
        self.assertTrue(before <= after, "The actual class deed must preserve existing owned items")
        awarded = [item for item in inventory if item["__handle__"] not in before]
        self.assertEqual(1, len(awarded), "The actual class deed must award exactly one new parchment")
        self.assertEqual("Scroll", self.call(awarded[0], "getTypeId"))
        self.earned_ward_scroll_name = self.call(awarded[0], "getName")
        self.assertTrue(self.earned_ward_scroll_name)
        self.assertEqual(1, sum(self.call(item, "getName") == self.earned_ward_scroll_name for item in inventory))

    def purchaseVictorLifePotionWithEarnedWard(self):
        self.assertEqual("good_end", self.call(self.game_map, "getStringProperty", "quest_state_victor"))
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "VICTOR_REWARD_GRANTED"))
        handler = self.call(self.game, "getGuiHandler")
        market = self.call(handler, "getRequestedTradeMarket")
        self.assertIsNotNone(market, "The real rescue must expose its actual one-time merchant")
        self.assertEqual("victorMarket", self.call(market, "getTypeId"))
        stock = self.call(market, "getItems")
        self.assertEqual(["LifePotion", "ManaPotion"], sorted(self.call(item, "getTypeId") for item in stock))
        life = next(item for item in stock if self.call(item, "getTypeId") == "LifePotion")
        inventory = self.call(self.player, "getItems")
        self.assertTrue(getattr(self, "earned_ward_scroll_name", None), "The actual class-deed reward must be tracked")
        scrolls = [
            item
            for item in inventory
            if self.call(item, "getTypeId") == "Scroll" and self.call(item, "getName") == self.earned_ward_scroll_name
        ]
        self.assertEqual(1, len(scrolls), "Only the actual class-deed parchment may fund this purchase")
        parchment = scrolls[0]
        equipped = self.call(self.player, "getEquipped")
        self.assertNotIn(parchment, equipped.values())
        self.assertFalse(self.call(parchment, "hasTag", "quest"))
        self.assertTrue(self.call(self.player, "getBoolProperty", "decoded_stained_glass_ward"))
        before = self.marketTransactionState()
        owned = {item["__handle__"] for item in inventory}
        portals = {item["__handle__"] for item in inventory if self.call(item, "getTypeId") == "TownPortalScroll"}
        self.assertEqual(1, len(portals), "The later actual retreat still needs its collected scroll")
        self.assertEqual(700, self.call(self.player, "getGold"), "Only Gooby's 200 and Victor's 500 fund this step")
        self.assertEqual(160, self.call(market, "getBuyCost", parchment))
        self.call(market, "buyItem", self.player, parchment)
        self.assertEqual(860, self.call(self.player, "getGold"))
        self.assertEqual(
            owned - {parchment["__handle__"]}, {item["__handle__"] for item in self.call(self.player, "getItems")}
        )
        self.assertEqual(
            {item["__handle__"] for item in stock} | {parchment["__handle__"]},
            {item["__handle__"] for item in self.call(market, "getItems")},
        )
        self.assertEqual(800, self.call(market, "getSellCost", life))
        self.assertTrue(self.call(market, "sellItem", self.player, life))
        self.assertEqual(60, self.call(self.player, "getGold"))
        self.assertEqual(
            (owned - {parchment["__handle__"]}) | {life["__handle__"]},
            {item["__handle__"] for item in self.call(self.player, "getItems")},
        )
        self.assertTrue(portals <= {item["__handle__"] for item in self.call(self.player, "getItems")})
        self.assertEqual(equipped, self.call(self.player, "getEquipped"))
        self.assertEqual(before, self.marketTransactionState())
        remaining = {item["__handle__"] for item in self.call(market, "getItems")}
        self.assertEqual(
            ({item["__handle__"] for item in stock} - {life["__handle__"]}) | {parchment["__handle__"]}, remaining
        )
        self.assertEqual(market, self.call(handler, "getRequestedTradeMarket"))
        self.assertFalse(self.call(market, "sellItem", self.player, life))
        self.assertEqual(60, self.call(self.player, "getGold"))
        self.assertEqual(remaining, {item["__handle__"] for item in self.call(market, "getItems")})
        print(
            "MCP hunt actual Victor merchant preparation",
            {"life": life, "soldEarnedWard": parchment, "gold": 60},
            flush=True,
        )
        return life

    def prepareVictorHealingStock(self):
        from tests.gameplay_branch_driver import GameplayBranchDriver

        self.finishOriginalMainQuest()
        self.assertEqual(200, self.call(self.player, "getGold"))
        walkthrough = self

        class PreparationDialogue:
            test = walkthrough
            map_name = "nouraajd"
            game = walkthrough.game
            _dialog_positions = {}
            call = staticmethod(walkthrough.call)
            pump = staticmethod(walkthrough.pump)
            _dialogStates = GameplayBranchDriver._dialogStates
            choose = GameplayBranchDriver.choose
            select = GameplayBranchDriver.select

            def record(self, choice, **kwargs):
                print("MCP hunt Victor preparation dialogue", choice, flush=True)

        dialogue = PreparationDialogue()

        def select(dialog_id, state_id, number):
            actor = "nouraajdTownHall" if dialog_id == "townHallDialog" else "nouraajdTavern"
            self.assertEqual(self.coords(self.object(actor)), self.coords(), "Quest choices require actual arrival")
            return dialogue.select(dialog_id, state_id, number)

        defeat_before = self.call(self.player, "getStringProperty", "uiDefeatReceipt")

        def nativeTurn():
            before = self.call(self.game_map, "getTurn")
            self.call(self.game_map, "move")
            self.pump()
            self.assertEqual(before + 1, self.call(self.game_map, "getTurn"))
            if not self.call(self.player, "isAlive"):
                self.fail(self.snapshot("Victor preparation survival"))
            self.assertEqual(defeat_before, self.call(self.player, "getStringProperty", "uiDefeatReceipt"))

        self.walkTo("nouraajdTavern")
        tavern = self.object("nouraajdTavern")
        self.assertEqual(1, self.call(tavern, "getNumericProperty", "visited"))
        select("tavernDialog1", "INKEEPER_ABOUT_CULTISTS", 1)
        select("tavernDialog1", "INKEEPER_ABOUT_GIRL", 2)
        opened = self.call(tavern, "getNumericProperty", "time_visited")
        for _ in range(51):
            if self.call(self.game_map, "getTurn") - opened > 50:
                break
            nativeTurn()
        self.assertGreater(self.call(self.game_map, "getTurn") - opened, 50)
        position = self.coords(tavern)
        neighbors = [(position[0] + dx, position[1] + dy, position[2]) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        departure = next((value for value in neighbors if value in self.walkable), None)
        self.assertIsNotNone(departure, "The authored tavern must have a cardinal exit")
        self.step(departure)
        self.walkTo("nouraajdTavern")
        self.assertEqual(2, self.call(tavern, "getNumericProperty", "visited"))
        select("tavernDialog2", "INKEEPER_RANT", 1)
        select("tavernDialog2", "YELLED_AT_VICTOR", 0)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "TALKED_TO_VICTOR"))
        select("tavernDialog2", "VICTOR_SPEECH", 1)
        select("tavernDialog2", "SUGGEST_TOWN_HALL", 0)
        self.walkTo("nouraajdTownHall")
        self.assertTrue(self.call(self.dialog("townHallDialog"), "invokeCondition", "can_discuss_victor_records"))
        dialogue.choose("townHallDialog", "spawn_cultists", condition=None)
        self.assertEqual("encounter_active", self.call(self.game_map, "getStringProperty", "quest_state_victor"))
        leader = self.object("cultLeaderQuest")
        self.assertTrue(self.call(leader, "isAlive"))
        spawned = self.call(self.game_map, "getNumericProperty", "VICTOR_COURTYARD_TURN")
        experience = self.call(self.player, "getNumericProperty", "exp")
        # Actual targeting opponents approach the town hall; chasing the moving leader can oscillate beside a wall.
        for _ in range(75):
            if self.call(self.game_map, "getStringProperty", "quest_state_victor") != "encounter_active":
                break
            self.assertLess(self.call(self.game_map, "getTurn") - spawned, 75)
            nativeTurn()
        self.assertEqual("good_end", self.call(self.game_map, "getStringProperty", "quest_state_victor"))
        self.assertFalse(self.call(leader, "isAlive"), "Only an actual leader defeat can complete the rescue")
        self.assertIsNone(self.call(self.game_map, "getObjectByName", "cultLeaderQuest"))
        self.assertGreater(self.call(self.player, "getNumericProperty", "exp"), experience)
        history = json.loads(self.call(self.game_map, "getStringProperty", "combatHistory"))
        self.assertTrue(history, "The real rescue must retain its native combat witness")
        self.call(self.player, "checkQuests")
        self.assertIn("victorQuest", self.questNames("getCompletedQuests"))
        print(
            "MCP hunt actual Victor rescue",
            {"turns": self.call(self.game_map, "getTurn") - spawned, "combat": history[-8:]},
            flush=True,
        )
        self.purchaseVictorLifePotionWithEarnedWard()

    def prepareSorcererForHunt(self):
        self.prepareVictorHealingStock()
        self.prepareHealingStockAtAuthoredMarket()

    def prepareThroughRolf(self):
        self.recoverOnRoadPair((44, 106, 0), (44, 107, 0), "opened gate road recovery")
        self.snapshot("before original Rolf cave")
        self.walkTo("cave1", allow_removed=True)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "completed_rolf"))
        self.assertGreater(self.call(self.player, "countItems", "skullOfRolf"), 0)
        self.snapshot("after original Rolf cave")
        for _ in range(32):
            if self.call(self.player, "getLevel") >= 4:
                break
            candidates = self.nearbyRolfEnemies()
            if not candidates:
                break
            if self.call(self.player, "getHpRatio") < 75:
                self.recoverOnRoadPair((9, 36, 0), (9, 37, 0), "Rolf road recovery")
                candidates = self.nearbyRolfEnemies()
                if not candidates:
                    break
            name = candidates[0][1]
            before = self.snapshot("before authored Pritz " + name)
            self.walkTo(name, allow_removed=True)
            after = self.snapshot("after authored Pritz " + name)
            self.assertIsNone(self.call(self.game_map, "getObjectByName", name))
            self.assertGreater(after["exp"], before["exp"], "Preparation must earn experience through real combat")
        self.assertGreaterEqual(self.call(self.player, "getLevel"), 3, self.snapshot("Rolf preparation complete"))
        self.recoverOnRoadPair((9, 36, 0), (9, 37, 0), "before hunt Rolf road recovery")

    def prepareThroughCatacombs(self):
        if self.call(self.player, "getLevel") < 4:
            # Follow authored roads; the grass shortcut crosses the occupied cave before recovery.
            for waypoint in ((9, 39, 0), (8, 39, 0), (8, 49, 0), (9, 49, 0), (9, 81, 0), (30, 81, 0), (30, 115, 0)):
                self.walkCoords(waypoint)
            self.recoverOnRoadPair((57, 115, 0), (58, 115, 0), "before original catacombs road recovery")
            self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "catacombs"))
            relics_before = self.call(self.player, "countItems", "holyRelic")
            self.snapshot("before original catacombs")
            self.walkTo("catacombs", allow_removed=True)
            self.assertIsNone(self.call(self.game_map, "getObjectByName", "catacombs"))
            self.assertEqual(relics_before + 1, self.call(self.player, "countItems", "holyRelic"))
            self.snapshot("after original catacombs arrival")
            for _ in range(18):
                if self.call(self.player, "getLevel") >= 4:
                    break
                candidates = self.nearbyAuthoredPritz((57, 103, 0))
                if not candidates:
                    break
                if self.call(self.player, "getHpRatio") < 75:
                    self.recoverOnRoadPair((57, 115, 0), (58, 115, 0), "catacombs road recovery")
                    candidates = self.nearbyAuthoredPritz((57, 103, 0))
                    if not candidates:
                        break
                name = candidates[0][1]
                before = self.snapshot("before authored catacombs Pritz " + name)
                self.walkTo(name, allow_removed=True)
                after = self.snapshot("after authored catacombs Pritz " + name)
                self.assertIsNone(self.call(self.game_map, "getObjectByName", name))
                self.assertGreater(
                    after["exp"], before["exp"], "Catacombs preparation must earn real combat experience"
                )
            self.recoverOnRoadPair((57, 115, 0), (58, 115, 0), "after catacombs road recovery")
        self.assertGreaterEqual(self.call(self.player, "getLevel"), 4, self.snapshot("earned hunt preparation"))
        self.assertGreaterEqual(self.call(self.player, "getNumericProperty", "exp"), 6000)

    def advanceQuestEvaluationTurn(self):
        self.assertTrue(self.call(self.player, "isAlive"))
        defeat_before = self.call(self.player, "getStringProperty", "uiDefeatReceipt")
        turn = self.call(self.game_map, "getTurn")
        self.call(self.game_map, "move")
        self.pump()
        self.assertEqual(turn + 1, self.call(self.game_map, "getTurn"))
        self.assertTrue(self.call(self.player, "isAlive"))
        self.assertEqual(defeat_before, self.call(self.player, "getStringProperty", "uiDefeatReceipt"))

    def finishOriginalMainQuest(self):
        self.snapshot("before original Gooby approach after hunt")
        self.recoverOnRoadPair((109, 100, 0), (109, 101, 0), "Gooby road recovery")
        self.walkTo("gooby1", allow_removed=True)
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "completed_gooby"))
        if "mainQuest" not in self.questNames("getCompletedQuests"):
            gold = self.call(self.player, "getGold")
            self.advanceQuestEvaluationTurn()
            self.assertEqual(gold + 200, self.call(self.player, "getGold"))
        self.assertIn("mainQuest", self.questNames("getCompletedQuests"))
        self.snapshot("original MainQuest complete after hunt")

    def useOrdinaryCombatController(self, player_class):
        # Attachment and save restoration install the interactive controller.
        template = self.call(self.game, "createObject", player_class)
        self.call(self.player, "setFightController", self.call(template, "getFightController"))

    def livingActors(self):
        return {
            slot: self.call(self.game_map, "getObjectByName", record["name"])
            for slot, record in self.state()["slots"].items()
            if record["status"] == "living"
        }

    def trackLivingHuntActors(self):
        for slot, actor in self.livingActors().items():
            self.assertIsNotNone(actor, slot)
            self.assertTrue(self.call(actor, "isAlive"), slot)
            if self.hunt_actors.get(slot) != actor:
                self.hunt_actors[slot] = actor
                resources = {
                    "slot": slot,
                    "name": self.call(actor, "getName"),
                    "hp": self.call(actor, "getHp"),
                    "mana": self.call(actor, "getMana"),
                }
                self.assertGreater(resources["hp"], 0, resources)
                print("MCP hunt tracked living actor", resources, flush=True)

    def captureHuntActors(self, origin, destination):
        distance = min(
            sum(abs(a - b) for a, b in zip(coords, self.hunt_lair_coords)) for coords in (origin, destination)
        )
        if distance <= 12:
            self.trackLivingHuntActors()

    def assertSlotDefeated(self, slot):
        record = self.state()["slots"][slot]
        actor = self.hunt_actors.get(slot)
        self.assertIsNotNone(actor, "The actual living actor must be captured before its fight: " + slot)
        self.assertEqual(record["name"], self.call(actor, "getName"))
        self.assertFalse(self.call(actor, "isAlive"), slot)
        self.assertIsNone(self.call(self.game_map, "getObjectByName", record["name"]), slot)
        self.assertEqual("dead", record["status"])
        if slot not in self.confirmed_dead:
            self.observeActors("confirmed actual " + slot + " defeat", {slot: actor})
            self.confirmed_dead.add(slot)

    def enterHunt(self):
        lair = self.object("cave2")
        self.hunt_lair_coords = self.coords(lair)
        self.capture_before_move = self.captureHuntActors
        before = self.snapshot("before entering the hunt lair")
        healing_stock = [
            {"type": self.call(item, "getTypeId"), "power": self.call(item, "getNumericProperty", "power")}
            for item in self.call(self.player, "getItems")
            if self.call(item, "hasTag", "heal")
        ]
        print("MCP hunt actual earned healing stock", healing_stock, flush=True)
        self.walkTo("cave2")
        self.assertIn(self.state()["stage"], ("scout", "brood"))
        if self.state()["slots"]["scout"]["status"] == "dead":
            self.assertSlotDefeated("scout")
            self.assertGreater(self.call(self.player, "getNumericProperty", "exp"), before["exp"])
        else:
            self.defeat("scout")
        self.assertEqual("brood", self.state()["stage"])
        self.assertFalse(self.call(self.game_map, "getBoolProperty", "octobogzHuntCleared"))
        self.trackLivingHuntActors()
        if getattr(self, "mcp_profile_class", None) == "Sorcerer":
            self.equipEarnedBroodWeapon()

    def observeActors(self, stage, actors):
        for slot, actor in actors.items():
            self.assertIsNotNone(actor, slot)
            properties = json.loads(self.engine("jsonify", actor))["properties"]
            packet = (
                self.call(actor, "getObjectProperty", "enemyRoleDamagePacket")
                if properties.get("enemyRoleDamagePacket") is not None
                else None
            )
            observation = {
                "stage": stage,
                "slot": slot,
                "phase": self.call(actor, "getStringProperty", "octobogzCombatPhase"),
                "pulse": self.call(actor, "getBoolProperty", "octobogzPulseUsed"),
                "effect": self.call(actor, "getBoolProperty", "octobogzPulseEffectApplied"),
                "damage_roll": self.call(actor, "getNumericProperty", "enemyRoleAttackBudget"),
                "normal": self.call(packet, "getNumericProperty", "normal") if packet else 0,
                "shadow": self.call(packet, "getNumericProperty", "shadow") if packet else 0,
                "alive": self.call(actor, "isAlive"),
                "hp": self.call(actor, "getHp"),
                "mana": self.call(actor, "getMana"),
            }
            print("MCP hunt actor combat", observation, flush=True)
            self.phase_observations.append(observation)

    def reportCombatFailure(self, stage, actors):
        tail = None
        tail_error = None
        try:
            tail = readNativeLogTail(self.native_log_path)
        except Exception as exc:
            tail_error = (type(exc).__name__, str(exc))
        evidence = {"stage": stage, "class": getattr(self, "mcp_profile_class", "unassigned")}
        try:
            if self.process.poll() is not None:
                raise RuntimeError("MCP process exited before the failure snapshot")
            for key, method, args in (
                ("combatHistory", "getStringProperty", ["combatHistory"]),
                ("combatStatus", "getStringProperty", ["combatStatus"]),
                ("combatRound", "getNumericProperty", ["combatRound"]),
                ("turn", "getTurn", []),
            ):
                evidence[key] = self.harness._mcp_handle_call(self.session, self.game_map, method, args, timeout=5)
            for key, actor in [("player", self.player), *sorted(actors.items())]:
                evidence[key] = json.loads(self.harness._mcp_engine_call(self.session, "jsonify", [actor], timeout=5))
                evidence.setdefault("actorLimits", {})[key] = {
                    "hpMax": self.harness._mcp_handle_call(self.session, actor, "getHpMax", [], timeout=5),
                    "manaMax": self.harness._mcp_handle_call(self.session, actor, "getManaMax", [], timeout=5),
                }
        except Exception as exc:
            evidence["diagnosticError"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            try:
                path = self.native_log_path.with_suffix(".failure.jsonl")
                serialized = json.dumps(evidence, ensure_ascii=False)
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(serialized + "\n")
                encoded = serialized.encode("utf-8")
                print(
                    "MCP hunt combat failure snapshot",
                    {"path": str(path), "bytes": len(encoded), "byteLimit": 65536, "truncated": len(encoded) > 65536},
                    flush=True,
                )
                print(encoded[:65536].decode("utf-8", errors="ignore"), flush=True)
            except Exception as exc:
                print("MCP hunt failure snapshot unavailable", type(exc).__name__, str(exc), flush=True)
            try:
                if tail is not None:
                    text = tail.pop("text")
                    print("MCP hunt native failure tail", tail, flush=True)
                    print(text, flush=True)
                else:
                    print("MCP hunt native failure tail unavailable", tail_error, flush=True)
            except Exception as exc:
                print("MCP hunt native failure tail unavailable", type(exc).__name__, str(exc), flush=True)

    def recoverAfterAlphaVictoryBeforeMapTurn(self, alpha):
        if self.call(alpha, "isAlive"):
            return
        self.assertEqual(alpha, self.hunt_actors.get("alpha"))
        self.assertSlotDefeated("alpha")
        self.recover_before_map_turn = None
        record = self.state()["slots"]["brood"]
        if record["status"] != "living":
            return
        brood = self.hunt_actors.get("brood")
        self.assertIsNotNone(brood, "The living Brood must retain its captured native identity")
        self.assertEqual(record["name"], self.call(brood, "getName"))
        self.assertEqual(brood, self.call(self.game_map, "getObjectByName", record["name"]))
        self.assertTrue(self.call(brood, "isAlive"))
        before = self.snapshot("actual Alpha victory before the next native map turn")
        self.recoverBeforeRoadDeparture(target_percent=100)
        print(
            "MCP hunt post-Alpha owned recovery",
            {"before": before, "hpAfter": self.call(self.player, "getHp")},
            flush=True,
        )

    def defeat(self, slot):
        record = self.state()["slots"][slot]
        if record["status"] == "dead":
            self.assertSlotDefeated(slot)
            return
        self.assertEqual("living", record["status"])
        self.trackLivingHuntActors()
        actors = self.livingActors()
        self.snapshot("before " + slot)
        previous_recovery = getattr(self, "recover_before_map_turn", None)
        if slot == "alpha":
            alpha = self.hunt_actors.get("alpha")
            self.assertIsNotNone(alpha)
            self.assertTrue(self.call(alpha, "isAlive"))
            self.recover_before_map_turn = lambda: self.recoverAfterAlphaVictoryBeforeMapTurn(alpha)
        try:
            self.walkTo(record["name"], allow_removed=True)
            self.snapshot("after " + slot)
            self.observeActors("after " + slot, actors)
            self.assertGreater(
                self.call(self.player, "getNumericProperty", "hp"), 0, "Ordinary player loadout failed against " + slot
            )
            self.assertSlotDefeated(slot)
        except Exception:
            try:
                self.reportCombatFailure("defeat " + slot, actors)
            except Exception:
                pass
            raise
        finally:
            self.recover_before_map_turn = previous_recovery

    @staticmethod
    def itemIdentity(item):
        if item is None:
            return None
        properties = item["properties"]
        return {key: properties.get(key, 0 if key == "power" else "") for key in ("name", "typeId", "power")}

    def captureDecisionReplayState(self, slot):
        data = json.loads(self.engine("jsonify", self.player))["properties"]
        player = {
            "name": self.call(self.player, "getName"),
            "classId": self.mcp_profile_class,
            "typeId": self.call(self.player, "getTypeId"),
            "level": self.call(self.player, "getLevel"),
            "exp": data["exp"],
            "hp": data["hp"],
            "mana": data["mana"],
            "gold": self.call(self.player, "getGold"),
            "hpMax": self.call(self.player, "getHpMax"),
            "manaMax": self.call(self.player, "getManaMax"),
            "effects": data["effects"],
            "coords": {axis: data["pos" + axis] for axis in "xyz"},
            "raceId": data.get("raceId", ""),
            "archetypeRaceId": self.call(self.player, "getArchetypeRaceId"),
            "archetypeClassId": self.call(self.player, "getArchetypeClassId"),
            "baseStats": data["baseStats"],
            "levelStats": data["levelStats"],
            "equipment": {slot: self.itemIdentity(item) for slot, item in (data.get("equipped") or {}).items()},
            "inventory": sorted(
                (self.itemIdentity(item) for item in data.get("items") or []),
                key=lambda item: (item["name"], item["typeId"], item["power"]),
            ),
        }
        actors = []
        for actor_slot, actor in sorted(self.livingActors().items()):
            actors.append(
                {
                    "slot": actor_slot,
                    "name": self.call(actor, "getName"),
                    "typeId": self.call(actor, "getTypeId"),
                    "level": self.call(actor, "getLevel"),
                    "hp": self.call(actor, "getHp"),
                    "mana": self.call(actor, "getMana"),
                    "phase": self.call(actor, "getStringProperty", "octobogzCombatPhase"),
                    "role": self.call(actor, "getStringProperty", "octobogzCombatRole"),
                }
            )
        return {
            "saveSlot": slot,
            "playerBefore": player,
            "actorsBefore": actors,
            "registryBefore": self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry"),
        }

    def validateDecisionReplay(self, result, expected):
        self.assertTrue(result["success"])
        self.assertEqual("deterministic-manual-earned-save", result["mode"])
        self.assertEqual(expected["saveSlot"], result["saveSlot"])
        self.assertIsInstance(result["playerComposedStatsBefore"], dict)
        self.assertIsInstance(result["playerComposedStatsBefore"]["properties"], dict)
        self.assertEqual(100, result["seed"])
        for field in ("playerBefore", "actorsBefore", "registryBefore"):
            self.assertEqual(expected[field], result[field], field)
        self.assertTrue(result["cardinalVerified"])
        self.assertGreater(result["movements"], 0)
        self.assertLessEqual(result["movements"], 512)
        self.assertTrue(result["playerAlive"])
        self.assertTrue(result["defeatReceiptUnchanged"])
        self.assertTrue(result["sourceUnchanged"])
        barriers = [decision for decision in result["decisions"] if decision["action"] == "Barrier"]
        self.assertEqual(len(barriers), result["paidBarriers"])
        self.assertGreater(result["paidBarriers"], 0)
        for decision in barriers:
            self.assertEqual(17, decision["cost"], "The learned Barrier must retain its authored cost")
            self.assertGreaterEqual(decision["refund"], 0)
            self.assertLessEqual(decision["refund"], decision["cost"])
            self.assertEqual(decision["cost"] - decision["refund"], decision["manaBefore"] - decision["manaAfter"])
        self.assertTrue(any(decision["refund"] < decision["cost"] for decision in barriers))
        consumed_names = set()
        for decision in (entry for entry in result["decisions"] if entry["action"] == "UseItem"):
            self.assertTrue(decision["consumedOnce"])
            self.assertTrue(decision["healOnlyDisposable"])
            self.assertIn(decision["item"], expected["playerBefore"]["inventory"])
            self.assertNotIn(decision["item"]["name"], consumed_names)
            consumed_names.add(decision["item"]["name"])
            self.assertEqual(0, decision["cost"])
            self.assertEqual(0, decision["refund"])
            self.assertEqual(decision["manaBefore"], decision["manaAfter"])
            self.assertEqual(decision["enemyHpBefore"], decision["enemyHpAfter"])
            self.assertEqual(decision["enemyManaBefore"], decision["enemyManaAfter"])
            self.assertEqual(decision["inventoryCountBefore"] - 1, decision["inventoryCountAfter"])
            self.assertGreater(decision["hpAfter"], decision["hpBefore"])
            self.assertEqual(
                min(decision["hpMax"], decision["hpBefore"] + decision["item"]["power"] * decision["hpMax"] // 5),
                decision["hpAfter"],
            )
        self.assertTrue(result["positivePackets"], "A real paid defensive turn must expose a positive pulse")
        for packet in result["positivePackets"]:
            self.assertIn(packet["slot"], ("brood", "alpha"))
            self.assertTrue(packet["pulse"])
            self.assertTrue(packet["effect"])
            self.assertGreater(packet["damage_roll"], 0)
            self.assertEqual(1, packet["shadow"])
            self.assertEqual(packet["damage_roll"] - 1, packet["normal"])
            self.assertEqual(5, packet["enemyManaBefore"] - packet["enemyManaAfter"])
            effect = packet["linkedEffect"]
            self.assertEqual("octobogzShadowPulseEffect", effect["typeId"])
            actor = next(actor for actor in expected["actorsBefore"] if actor["slot"] == packet["slot"])
            self.assertEqual(actor["name"], effect["caster"])
            self.assertEqual(expected["playerBefore"]["name"], effect["victim"])
            self.assertEqual(1, effect["duration"])
            self.assertEqual(1, effect["timeTotal"])
            self.assertIn(effect["time"], (0, 1))
            bonus = effect["bonus"]["properties"]
            self.assertEqual(-1, bonus["shadowResist"])
            self.assertTrue(
                all(value == 0 for key, value in bonus.items() if key != "shadowResist" and isinstance(value, int))
            )
        return result["positivePackets"]

    def requireDecisionReplayExecutable(self):
        import test as harness

        executable_name = "monster_balance_unit_tests" + (".exe" if os.name == "nt" else "")
        candidates = [Path(directory) / executable_name for directory in (*harness.extension_dirs, self.build_dir)]
        executable = next((path for path in candidates if path.is_file()), None)
        if executable is None:
            if os.environ.get("CI"):
                self.fail("The required native saved-hero decision fixture is missing: " + str(candidates))
            self.skipTest("The current monster_balance_unit_tests binary is required for the saved-hero replay")
        return executable

    def replaySavedOrdinaryDefensiveDecisions(self, slot, save_path, expected):
        executable = getattr(self, "decision_executable", None) or self.requireDecisionReplayExecutable()
        environment = os.environ.copy()
        if os.name == "nt":
            cache = self.build_dir / "CMakeCache.txt"
            values = {}
            if cache.is_file():
                for line in cache.read_text(encoding="utf-8").splitlines():
                    if "=" in line and ":" in line.split("=", 1)[0]:
                        key, value = line.split("=", 1)
                        values[key.split(":", 1)[0]] = value
            python_path = Path(values.get("Python3_EXECUTABLE", sys.executable)).parent
            installed = values.get("_VCPKG_INSTALLED_DIR") or values.get("VCPKG_INSTALLED_DIR")
            triplet = values.get("VCPKG_TARGET_TRIPLET")
            runtime_paths = [executable.parent, self.build_dir, python_path]
            if installed and triplet:
                runtime_paths.append(Path(installed) / triplet / "bin")
            environment["PYTHONHOME"] = str(python_path)
            environment["PATH"] = os.pathsep.join(map(str, runtime_paths)) + os.pathsep + environment.get("PATH", "")
        before_hash = sha256(save_path.read_bytes()).hexdigest()
        live_before = (self.game, self.game_map, self.player, self.call(self.game_map, "getTurn"), self.state())
        resources_before = (self.call(self.player, "getHp"), self.call(self.player, "getMana"), self.coords())
        try:
            completed = subprocess.run(
                [str(executable), "--hunt-decision", slot],
                cwd=self.build_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            evidence = retainDecisionReplayStreams(completed.stdout, completed.stderr)
            if completed.returncode != 0:
                reportDecisionReplayFailure(completed.stdout, completed.returncode, evidence)
            self.assertEqual(0, completed.returncode, (completed.stdout[-8192:], completed.stderr[-8192:]))
            marker = "NATIVE_HUNT_DECISION_RESULT "
            results = [
                json.loads(line[len(marker) :]) for line in completed.stdout.splitlines() if line.startswith(marker)
            ]
            self.assertEqual(1, len(results), completed.stdout[-8192:])
            packets = self.validateDecisionReplay(results[0], expected)
            self.assertFalse(evidence["errors"], ("Unable to retain the complete replay evidence", evidence))
            print("MCP hunt deterministic ordinary defensive replay", results[0], flush=True)
            return packets
        except subprocess.TimeoutExpired as error:
            retainDecisionReplayStreams(error.stdout, error.stderr)
            for name in ("stdout", "stderr"):
                output = getattr(error, name) or ""
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                try:
                    print("Saved hunt decision replay timeout " + name, output[-8192:], file=sys.stderr, flush=True)
                except Exception:
                    pass
            raise
        finally:
            self.assertEqual(
                before_hash, sha256(save_path.read_bytes()).hexdigest(), "Replay must not rewrite the save"
            )
            self.assertEqual(
                live_before, (self.game, self.game_map, self.player, self.call(self.game_map, "getTurn"), self.state())
            )
            self.assertEqual(
                resources_before, (self.call(self.player, "getHp"), self.call(self.player, "getMana"), self.coords())
            )

    def assertMeaningfulPulseWitness(self):
        self.assertTrue(self.manual_phase_observations, "The ordinary saved-hero defensive replay remains mandatory")
        positive_packets = [
            observed
            for observed in self.phase_observations + self.manual_phase_observations
            if observed["pulse"] and observed["damage_roll"] > 0 and observed["shadow"] == 1
        ]
        self.assertTrue(positive_packets, "Real combat must exercise a positive shadow packet, not only a phase flag")
        for observed in positive_packets:
            self.assertEqual(
                observed["damage_roll"] - 1, observed["normal"], "The original damage budget must be preserved"
            )

    def testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce(self):
        self.decision_executable = self.requireDecisionReplayExecutable()
        self.phase_observations = []
        self.manual_phase_observations = []
        for player_class in ("Warrior", "Sorcerer"):
            with self.subTest(player_class=player_class):
                self.resetMcpProfile(player_class)
                self.hunt_actors, self.confirmed_dead = {}, set()
                self.capture_before_move = None
                self.game = self.engine("CGameLoader.loadGame")
                self.engine("CGameLoader.startGameWithPlayer", self.game, "nouraajd", player_class)
                self.refresh()
                self.pump()
                _, self.walkable = authoredRegion("nouraajd")
                self.movement_steps = 0
                self.assertIsNone(self.call(self.game, "getGui"), "The hunt must not create a desktop window")
                self.snapshot("entry")
                starting_blades = self.call(self.player, "countItems", "ShadowBlade")
                # The template's existing AI uses ordinary spells, equipment and carried potions.
                self.useOrdinaryCombatController(player_class)
                self.collectAuthoredRetreatScroll()
                # Earn the authored class discovery reward through its NPC action.
                if player_class == "Warrior":
                    self.walkTo("nouraajdDoor")
                    self.action(self.dialog("doorDialog"), "brace_gate")
                else:
                    self.walkTo("nouraajdDoor")
                    self.action(self.dialog("doorDialog"), "open_door")
                    _, self.walkable = authoredRegion("nouraajd")
                    self.walkTo("nouraajdChapel")
                    self.earnSorcererWardScroll()
                self.prepareThroughRolf()
                self.probeCoordinateReadCosts()
                self.prepareThroughCatacombs()
                if player_class == "Sorcerer":
                    self.prepareSorcererForHunt()
                self.walkTo("questGiver")
                if player_class == "Warrior":
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertIn("octoBogzQuest", self.questNames())
                self.walkTo("ambientOctobogzNet")
                self.recoverOnRoadPair((118, 21, 0), (118, 20, 0), "before hunt road recovery")
                self.enterHunt()

                slot = "mcp-octobogz-" + uuid.uuid4().hex
                save_path = self.build_dir / "save" / (slot + ".json")
                self.assertFalse(save_path.exists())
                try:
                    self.assertTrue(self.engine("CMapLoader.saveWithResult", self.game_map, slot))
                    self.assertTrue(save_path.is_file())
                    old_state = self.state()
                    self.game = self.engine("CGameLoader.loadGame")
                    self.engine("CGameLoader.loadSavedGame", self.game, slot)
                    self.refresh()
                    self.pump()
                    self.assertEqual(old_state, self.state())
                    self.useOrdinaryCombatController(player_class)
                    self.trackLivingHuntActors()
                    self.snapshot("partial reload")
                    decision_state = self.captureDecisionReplayState(slot) if player_class == "Warrior" else None
                    gold_before_final = self.call(self.player, "getGold")
                    self.retreatWithOwnedAuthoredScroll()
                    if player_class == "Sorcerer":
                        self.prepareHealingStockAtAuthoredMarket(initial=False)
                    self.recoverOnAuthoredRoad()
                    self.defeat("alpha")
                    self.recoverBeforeRemainingBrood(player_class)
                    self.defeat("brood")
                    self.assertEqual({"scout", "brood", "alpha"}, self.confirmed_dead)
                    self.assertEqual("cleared", self.state()["stage"])
                    self.assertTrue(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
                    self.assertIsNone(self.call(self.game_map, "getObjectByName", "cave2"))
                    self.walkTo("questGiver")
                    gold_before_claim = self.call(self.player, "getGold")
                    self.action(self.dialog("dialog"), "accept_quest")
                    gold_after_claim = self.call(self.player, "getGold")
                    if player_class == "Sorcerer":
                        self.assertEqual(gold_before_claim + 1000, gold_after_claim)
                    else:
                        self.assertGreaterEqual(gold_before_claim, gold_before_final + 1000)
                        self.assertEqual(gold_before_claim, gold_after_claim)
                    self.assertEqual(starting_blades + 1, self.call(self.player, "countItems", "ShadowBlade"))
                    self.assertIn("octoBogzQuest", self.questNames("getCompletedQuests"))
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertEqual(gold_after_claim, self.call(self.player, "getGold"))
                    self.assertEqual(starting_blades + 1, self.call(self.player, "countItems", "ShadowBlade"))
                    self.finishOriginalMainQuest()
                    self.assertGreater(self.movement_steps, 100)
                    self.snapshot("completed")
                    print(
                        "MCP OctoBogz real combat completed for",
                        player_class,
                        "adjacent steps",
                        self.movement_steps,
                        flush=True,
                    )
                    if decision_state is not None:
                        self.manual_phase_observations += self.replaySavedOrdinaryDefensiveDecisions(
                            slot, save_path, decision_state
                        )
                finally:
                    save_path.unlink(missing_ok=True)
                    save_path.with_suffix(".json.bak").unlink(missing_ok=True)
        self.assertMeaningfulPulseWitness()


class OctobogzDiagnosticTest(unittest.TestCase):
    def testLegacyStartupOptsIntoBoundedRecentTraceBeforeTheActualServerEnvironmentIsCopied(self):
        from types import SimpleNamespace

        import test as harness

        startups = []

        def start(command, **kwargs):
            startups.append((command, kwargs))
            return SimpleNamespace()

        def dialogueSetup(instance):
            native_harness = SimpleNamespace(assertTrue=self.assertTrue, _start_stdio_process=start)
            instance.process = harness.McpServerTest._start_stdio_mcp_process(native_harness)

        with tempfile.TemporaryDirectory() as temporary:
            fixture = OctobogzMcpWalkthroughTest("runTest")
            with (
                patch.dict(os.environ, GAME_PLAYTEST_TRACE_RETAIN_RECENT="0"),
                patch.object(harness, "TEST_OUTPUT_DIR", Path(temporary)),
                patch.object(dialogue_mcp.DialogueMcpWalkthroughTest, "setUp", dialogueSetup),
            ):
                fixture.setUp()
                self.assertEqual("0", os.environ["GAME_PLAYTEST_TRACE_RETAIN_RECENT"])
                self.assertEqual(1, len(startups))
                command, kwargs = startups[0]
                self.assertEqual("nouraajd", kwargs["map_name"])
                self.assertEqual("1", kwargs["env"]["GAME_PLAYTEST_TRACE"])
                self.assertEqual("1", kwargs["env"]["GAME_PLAYTEST_TRACE_RETAIN_RECENT"])
                self.assertEqual(str(fixture.process._playtest_trace_path), kwargs["env"]["GAME_PLAYTEST_TRACE_FILE"])
                self.assertEqual(Path(temporary), fixture.process._playtest_trace_path.parent)
                self.assertTrue(fixture.process._playtest_trace_path.name.startswith("mcp_walkthrough_octobogz-"))
                self.assertEqual(fixture.native_log_path, fixture.process._native_log_file)
                self.assertIn(str(fixture.native_log_path), command)
                # The shared harness retains its caller's opt-in/default behavior outside this route.
                native_harness = SimpleNamespace(assertTrue=self.assertTrue, _start_stdio_process=start)
                harness.McpServerTest._start_stdio_mcp_process(native_harness, "nouraajd", trace_name="ordinary")
                self.assertEqual("0", startups[1][1]["env"]["GAME_PLAYTEST_TRACE_RETAIN_RECENT"])

    def testLegacyPumpStopsAtTheFirstUnresolvedPlayerCombatAndCannotRetryIntoALaterVictory(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        for outcome in (0, 3, 4):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                trace = Path(directory) / "actual-native.trace.jsonl"
                validator = SimpleNamespace(
                    test=self,
                    trace_path=trace,
                    _combat_trace_positions={},
                    _combat_trace_seq=0,
                    _combat_failure=None,
                    player=None,
                )
                calls = []

                def append(seq, result):
                    with trace.open("a", encoding="utf-8") as output:
                        output.write(
                            json.dumps(
                                {
                                    "seq": seq,
                                    "event": "combat_finished",
                                    "attacker": {"isPlayer": True},
                                    "opponents": [{"isPlayer": False}],
                                    "outcome": result,
                                }
                            )
                            + "\n"
                        )

                def run(handle, method):
                    calls.append(method)
                    append(1, outcome)

                fixture = SimpleNamespace(
                    _native_combat_validator=validator, engine=Mock(return_value="loop"), call=run
                )
                with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
                    OctobogzMcpWalkthroughTest.pump(fixture)
                self.assertEqual(["run"], calls)
                append(2, 1)
                with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
                    OctobogzMcpWalkthroughTest.pump(fixture)
                self.assertEqual(
                    ["run"], calls, "A later victory cannot clear the first native failure or advance another turn"
                )
                fixture.engine.assert_called_once()

    def testSorcererWardTracksTheNewAuthoredRewardAmongExistingParchments(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        from tests.test_gameplay_route_dialogs import authoredFunction

        player = {"__handle__": "player"}
        dialog = {"__handle__": "beren"}
        chapel = {"__handle__": "chapel"}
        original = [{"__handle__": name} for name in ("loot-scroll", "portal", "starter")]
        awarded = {"__handle__": "ward"}
        owned = list(original)
        flags = {}
        native_player = SimpleNamespace(
            incProperty=Mock(),
            setBoolProperty=lambda key, value: flags.update({key: value}),
            addItem=lambda identity: owned.append(awarded) if identity == "Scroll" else self.fail(identity),
            addExp=Mock(),
        )
        native_game = SimpleNamespace(getMap=lambda: SimpleNamespace(getPlayer=lambda: native_player))
        ward = authoredFunction(
            "res/maps/nouraajd/script.py",
            "decode_stained_glass_ward",
            class_id="BerenDialog",
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
        )

        def action(selected, name):
            self.assertEqual((dialog, "decode_stained_glass_ward"), (selected, name))
            ward(SimpleNamespace(getGame=lambda: native_game, can_decode_stained_glass_ward=lambda: True))

        def call(handle, method, *args):
            if method == "getItems":
                self.assertEqual(player, handle)
                return list(owned)
            if method == "invokeCondition":
                self.assertEqual((dialog, "can_decode_stained_glass_ward"), (handle, args[0]))
                return not flags.get("decoded_stained_glass_ward", False)
            if method == "getTypeId":
                return (
                    "Scroll"
                    if handle in (original[0], awarded)
                    else "TownPortalScroll" if handle == original[1] else "Staff"
                )
            if method == "getName":
                return "native-" + handle["__handle__"]
            raise AssertionError((handle, method, args))

        fixture = SimpleNamespace(
            player=player,
            object=lambda name: chapel if name == "nouraajdChapel" else self.fail(name),
            coords=lambda handle=None: (43, 113, 0),
            dialog=lambda name: dialog if name == "berenDialog" else self.fail(name),
            call=call,
            action=action,
            assertEqual=self.assertEqual,
            assertTrue=self.assertTrue,
        )
        OctobogzMcpWalkthroughTest.earnSorcererWardScroll(fixture)
        self.assertEqual("native-ward", fixture.earned_ward_scroll_name)
        self.assertEqual([*original, awarded], owned)
        self.assertTrue(flags["decoded_stained_glass_ward"])

    def testVictorMerchantUsesTheTrackedWardAfterHandleRefreshAndRetainsOtherScrollLoot(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        from tests.test_gameplay_route_dialogs import authoredFunction

        state = {"gold": 0, "flags": {}, "victor": "encounter_active"}
        handles = {
            name: {"__handle__": name}
            for name in (
                "player",
                "world",
                "game",
                "handler",
                "market",
                "life",
                "mana",
                "ward",
                "loot-scroll",
                "portal",
                "starter",
                "quest",
            )
        }
        items = {
            "life": "LifePotion",
            "mana": "ManaPotion",
            "ward": "Scroll",
            "loot-scroll": "Scroll",
            "portal": "TownPortalScroll",
            "starter": "Staff",
            "quest": "letterFromRolf",
        }
        owned, stock = {"portal", "starter", "quest", "loot-scroll"}, {"life", "mana"}
        sold, purchases = [], []
        equipped = {"0": handles["starter"]}
        native_player = SimpleNamespace(
            addGold=lambda value: state.update(gold=state["gold"] + value),
            healProc=Mock(),
            addItem=lambda identity: owned.add("ward") if identity == "Scroll" else self.fail(identity),
            incProperty=Mock(),
            setBoolProperty=lambda key, value: state["flags"].update({key: value}),
            addExp=Mock(),
        )
        market_object = object()
        gui = SimpleNamespace(showTrade=Mock())
        native_game = SimpleNamespace(getGuiHandler=lambda: gui)
        world = SimpleNamespace(
            getGame=lambda: native_game,
            getPlayer=lambda: native_player,
            getBoolProperty=lambda key: state["flags"].get(key, False),
        )
        native_game.getMap = lambda: world
        native_game.createObject = lambda identity: (
            market_object if identity == "victorMarket" else SimpleNamespace(getStates=lambda: [])
        )

        def claim_once(world, flag):
            if state["flags"].get(flag):
                return False
            state["flags"][flag] = True
            return True

        source = "res/maps/nouraajd/script.py"
        ward = authoredFunction(
            source, "decode_stained_glass_ward", class_id="BerenDialog", rewardSnapshot=Mock(), showRewardReceipt=Mock()
        )
        ward(SimpleNamespace(getGame=lambda: native_game, can_decode_stained_glass_ward=lambda: True))
        gooby = authoredFunction(
            source,
            "onComplete",
            class_id="MainQuest",
            claim_once=claim_once,
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
            MAIN_QUEST_GOLD_REWARD=200,
        )
        gooby(SimpleNamespace(getGame=lambda: native_game))
        quest_system = SimpleNamespace(
            get_state=lambda quest: state["victor"], mark_victor_good_end=lambda: state.update(victor="good_end")
        )
        rescued = authoredFunction(
            source,
            "trigger",
            class_id="CultLeaderQuestTrigger",
            _quest_system_from=lambda obj: quest_system,
            claim_once=claim_once,
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
            narrative=SimpleNamespace(victorResponse=lambda game: ""),
            _clear_victor_encounter=Mock(),
        )
        rescued(SimpleNamespace(getGame=lambda: native_game), object(), object())
        gui.showTrade.assert_called_once_with(market_object)
        self.assertEqual(700, state["gold"])
        # Native names survive save/reload; MCP handles need not retain their original values.
        handles["ward"] = {"__handle__": "refreshed-ward"}

        def call(handle, method, *args):
            identity = next(name for name, current in handles.items() if current == handle)
            if method == "getStringProperty":
                return state["victor"]
            if method == "getBoolProperty":
                return state["flags"].get(args[0], False)
            if method == "getGuiHandler":
                return handles["handler"]
            if method == "getRequestedTradeMarket":
                return handles["market"]
            if method == "getTypeId":
                return "victorMarket" if identity == "market" else items[identity]
            if method == "getName":
                return "native-" + identity
            if method == "getItems":
                return [handles[key] for key in sorted(owned if identity == "player" else stock)]
            if method == "getEquipped":
                return dict(equipped)
            if method == "hasTag":
                return identity == "quest"
            if method == "getGold":
                return state["gold"]
            if method == "getBuyCost":
                self.assertEqual(handles["ward"], args[0])
                return 160
            if method == "getSellCost":
                self.assertEqual(handles["life"], args[0])
                return 800
            if method == "buyItem":
                self.assertEqual((handles["player"], handles["ward"]), args)
                owned.remove("ward")
                stock.add("ward")
                state["gold"] += 160
                sold.append("ward")
                return
            if method == "sellItem":
                self.assertEqual((handles["player"], handles["life"]), args)
                if "life" not in stock:
                    return False
                self.assertGreaterEqual(state["gold"], 800)
                stock.remove("life")
                owned.add("life")
                state["gold"] -= 800
                purchases.append("life")
                return True
            raise AssertionError((identity, method, args))

        fixture = SimpleNamespace(
            call=call,
            game=handles["game"],
            game_map=handles["world"],
            player=handles["player"],
            earned_ward_scroll_name="native-ward",
            marketTransactionState=lambda: {"context": "unchanged"},
        )
        for name in ("assertEqual", "assertTrue", "assertFalse", "assertNotIn", "assertIsNotNone"):
            setattr(fixture, name, getattr(self, name))
        self.assertEqual(handles["life"], OctobogzMcpWalkthroughTest.purchaseVictorLifePotionWithEarnedWard(fixture))
        self.assertEqual(60, state["gold"])
        self.assertEqual(["ward"], sold)
        self.assertEqual(["life"], purchases)
        self.assertEqual({"life", "portal", "starter", "quest", "loot-scroll"}, owned)
        self.assertEqual({"mana", "ward"}, stock)
        # Claim-first source callbacks cannot mint a second payout or replace the depleted market.
        gooby(SimpleNamespace(getGame=lambda: native_game))
        rescued(SimpleNamespace(getGame=lambda: native_game), object(), object())
        self.assertEqual(60, state["gold"])
        gui.showTrade.assert_called_once()

    def testSorcererEarnsVictorSuppliesBeforeInitialHuntPreparation(self):
        from types import SimpleNamespace

        calls = []
        fixture = SimpleNamespace(
            prepareVictorHealingStock=lambda: calls.append("actual-Victor-rescue-and-purchase"),
            prepareHealingStockAtAuthoredMarket=lambda: calls.append("finite-basic-preparation"),
        )
        OctobogzMcpWalkthroughTest.prepareSorcererForHunt(fixture)
        self.assertEqual(["actual-Victor-rescue-and-purchase", "finite-basic-preparation"], calls)

    def victorPreparationSequence(self, mode="success"):
        from types import SimpleNamespace
        from unittest.mock import Mock

        state = {
            "turn": 10,
            "coords": (58, 115, 0),
            "visited": 0,
            "opened": 0,
            "flags": {},
            "victor": "not_started",
            "alive": True,
            "leader_alive": True,
            "exp": 6000,
            "gold": 200,
            "receipt": "",
            "spawned": None,
        }
        positions = {"nouraajdTavern": (48, 99, 0), "nouraajdTownHall": (43, 101, 0)}
        actions, visits = [], []
        handles = {name: {"__handle__": name} for name in ("player", "world", "game", "cultLeaderQuest", *positions)}

        def turn():
            state["turn"] += 1
            if state["victor"] == "encounter_active":
                elapsed = state["turn"] - state["spawned"]
                if mode == "defeat":
                    state.update(alive=False, receipt="actual defeat")
                elif mode == "timeout" and elapsed == 75:
                    state["victor"] = "bad_end"
                elif mode == "success" and elapsed == 2:
                    state.update(victor="good_end", leader_alive=False, gold=700, exp=6250)

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if method == "createObject":
                return {"__handle__": args[0]}
            if method == "getTurn":
                return state["turn"]
            if method == "move":
                turn()
                return
            if method == "getGold":
                return state["gold"]
            if method == "getNumericProperty":
                if args[0] == "visited":
                    return state["visited"]
                if args[0] == "time_visited":
                    return state["opened"]
                if args[0] == "VICTOR_COURTYARD_TURN":
                    return state["spawned"]
                return state[args[0]]
            if method == "getStringProperty":
                if args[0] == "quest_state_victor":
                    return state["victor"]
                if args[0] == "combatHistory":
                    return json.dumps(["The cult leader is defeated."])
                return state["receipt"]
            if method == "getBoolProperty":
                return state["flags"].get(args[0], False)
            if method == "isAlive":
                return state["leader_alive"] if identity == "cultLeaderQuest" else state["alive"]
            if method == "getObjectByName":
                return None if args[0] == "cultLeaderQuest" and not state["leader_alive"] else handles[args[0]]
            if method == "checkQuests":
                self.assertEqual("good_end", state["victor"])
                return
            if method == "invokeCondition":
                return {
                    "asked_about_girl": state["flags"].get("ASKED_ABOUT_GIRL", False),
                    "can_discuss_victor_records": state["flags"].get("TALKED_TO_VICTOR", False)
                    and state["victor"] == "not_started",
                }.get(args[0], False)
            if method == "invokeAction":
                expected = "nouraajdTownHall" if identity == "townHallDialog" else "nouraajdTavern"
                self.assertEqual(positions[expected], state["coords"], "Actual dialogue actions cannot run remotely")
                actions.append(args[0])
                if args[0] == "asked_about_girl":
                    state["flags"]["ASKED_ABOUT_GIRL"] = True
                elif args[0] == "talked_to_victor":
                    self.assertEqual(2, state["visited"])
                    state["flags"]["TALKED_TO_VICTOR"] = True
                elif args[0] == "spawn_cultists":
                    self.assertTrue(state["flags"]["TALKED_TO_VICTOR"])
                    state.update(victor="encounter_active", spawned=state["turn"])
                else:
                    self.assertEqual("calmVictor", args[0])
                return
            raise AssertionError((identity, method, args))

        def walkTo(name):
            visits.append(name)
            state["coords"] = positions[name]
            if name == "nouraajdTavern":
                if state["visited"] == 0:
                    state.update(visited=1, opened=state["turn"])
                elif state["turn"] - state["opened"] > 50:
                    state["visited"] = 2

        def step(destination):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(destination, state["coords"])))
            state["coords"] = destination
            turn()

        fixture = SimpleNamespace(
            call=call,
            game=handles["game"],
            game_map=handles["world"],
            player=handles["player"],
            object=lambda name: handles[name],
            coords=lambda handle=None: state["coords"] if handle is None else positions[handle["__handle__"]],
            walkTo=walkTo,
            step=step,
            walkable={(49, 99, 0)},
            pump=Mock(),
            snapshot=lambda label: label,
            finishOriginalMainQuest=Mock(),
            dialog=lambda name: {"__handle__": name},
            questNames=lambda method: ["victorQuest"] if state["victor"] == "good_end" else [],
            purchaseVictorLifePotionWithEarnedWard=Mock(),
        )
        for name in (
            "assertEqual",
            "assertTrue",
            "assertFalse",
            "assertIsNotNone",
            "assertIsNone",
            "assertGreater",
            "assertLess",
            "assertIn",
            "fail",
        ):
            setattr(fixture, name, getattr(self, name))
        return fixture, state, actions, visits

    def testVictorPreparationUsesTheAuthoredDialogueGraphAfterActualVisitsAndNativeWaiting(self):
        fixture, state, actions, visits = self.victorPreparationSequence()
        OctobogzMcpWalkthroughTest.prepareVictorHealingStock(fixture)
        self.assertEqual(["nouraajdTavern", "nouraajdTavern", "nouraajdTownHall"], visits)
        self.assertEqual(["asked_about_girl", "calmVictor", "talked_to_victor", "spawn_cultists"], actions)
        self.assertEqual(2, state["turn"] - state["spawned"])
        self.assertEqual((43, 101, 0), state["coords"], "The actual targeting enemies approach the current town hall")
        fixture.purchaseVictorLifePotionWithEarnedWard.assert_called_once_with()

    def testVictorPreparationDoesNotBuyAfterDefeatOrTheRealDeadline(self):
        for mode in ("defeat", "timeout"):
            with self.subTest(mode=mode):
                fixture, state, _actions, _visits = self.victorPreparationSequence(mode)
                with self.assertRaises(AssertionError):
                    OctobogzMcpWalkthroughTest.prepareVictorHealingStock(fixture)
                self.assertLessEqual(state["turn"] - state["spawned"], 75)
                fixture.purchaseVictorLifePotionWithEarnedWard.assert_not_called()

    def testNativeLoggerIsOptInAndPassesTheExactFileArgument(self):
        import ast
        from types import SimpleNamespace

        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "test.py").read_text(encoding="utf-8"))
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "McpServerTest")
        method = next(
            node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "_start_stdio_mcp_process"
        )
        with tempfile.TemporaryDirectory() as temporary:
            namespace = {
                "REPO_ROOT": Path(dialogue_mcp.__file__).resolve().parents[1],
                "TEST_OUTPUT_DIR": Path(temporary),
                "build_dir": root / "cmake-build-release",
                "build_config": "Release",
                "Path": Path,
                "os": os,
                "sys": sys,
            }
            exec(compile(ast.Module(body=[method], type_ignores=[]), "<exact-mcp-startup>", "exec"), namespace)
            commands = []

            def start(command, **kwargs):
                commands.append((command, kwargs))
                return SimpleNamespace()

            fixture = SimpleNamespace(assertTrue=self.assertTrue, _start_stdio_process=start)
            default = namespace[method.name](fixture)
            path = Path(temporary) / "nested" / "native log.txt"
            enabled = namespace[method.name](fixture, native_log_file=path)
            self.assertIsNone(default._native_log_file)
            self.assertEqual(path, enabled._native_log_file)
            self.assertTrue(path.parent.is_dir())
            self.assertIn("disabled", commands[0][0])
            self.assertNotIn("--native-log-file", commands[0][0])
            sink_index = commands[1][0].index("--native-log-sink")
            self.assertEqual(
                ["--native-log-sink", "file", "--native-log-file", str(path)],
                commands[1][0][sink_index : sink_index + 4],
            )
            self.assertEqual(commands[0][1], commands[1][1])
            self.assertIsNone(default._playtest_trace_path)
            self.assertIsNone(enabled._playtest_trace_path)

    def testNativeTailBoundsBothReadsAndPrintedBytesAndLines(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "native.log"
            for raw in (b"early\n" * 100 + b"last1\nlast2\n", b"\xff" * 100 + b"\nlast\n"):
                with self.subTest(raw=raw[-16:]):
                    path.write_bytes(raw)
                    tail = readNativeLogTail(path, max_bytes=32, max_lines=2)
                    self.assertEqual(raw, path.read_bytes())
                    self.assertEqual(len(raw), tail["fileBytes"])
                    self.assertLessEqual(tail["readBytes"], 32)
                    self.assertLessEqual(len(tail["text"].encode("utf-8")), 32)
                    self.assertLessEqual(len(tail["text"].splitlines()), 2)
                    self.assertTrue(tail["truncated"])
                    self.assertTrue(tail["text"].endswith("last2" if raw.endswith(b"last2\n") else "last"))
            for limits in ({"max_bytes": 0}, {"max_lines": 0}):
                with self.subTest(limits=limits), self.assertRaises(ValueError):
                    readNativeLogTail(path, **limits)

    def testFailureCapturesReadOnlyCombatAndActualLinkedEffectJson(self):
        import contextlib
        import io
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "native.log"
            path.write_text("actual effect applied\n", encoding="utf-8")
            calls = []

            def handle(session, actor, method, args, *, timeout):
                calls.append((method, args, timeout))
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("snapshot getter noise\n" * 4096)
                return "recorded combat" if method == "getStringProperty" else 7

            def engine(session, name, args, *, timeout):
                calls.append((name, args, timeout))
                return json.dumps(
                    {"properties": {"name": args[0], "effects": [{"caster": "brood", "victim": "player"}]}}
                )

            fixture = SimpleNamespace(
                process=SimpleNamespace(poll=lambda: None),
                harness=SimpleNamespace(_mcp_handle_call=handle, _mcp_engine_call=engine),
                session={},
                game_map="map",
                player="player",
                native_log_path=path,
                mcp_profile_class="Sorcerer",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                OctobogzMcpWalkthroughTest.reportCombatFailure(fixture, "defeat brood", {"brood": "brood"})
            evidence = json.loads(path.with_suffix(".failure.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("recorded combat", evidence["combatHistory"])
            self.assertEqual(7, evidence["combatRound"])
            self.assertEqual({"caster": "brood", "victim": "player"}, evidence["player"]["properties"]["effects"][0])
            self.assertEqual("brood", evidence["brood"]["properties"]["name"])
            self.assertEqual({"hpMax": 7, "manaMax": 7}, evidence["actorLimits"]["player"])
            self.assertEqual({"hpMax": 7, "manaMax": 7}, evidence["actorLimits"]["brood"])
            self.assertEqual(
                [
                    "getStringProperty",
                    "getStringProperty",
                    "getNumericProperty",
                    "getTurn",
                    "jsonify",
                    "getHpMax",
                    "getManaMax",
                    "jsonify",
                    "getHpMax",
                    "getManaMax",
                ],
                [entry[0] for entry in calls],
            )
            self.assertTrue(all(entry[2] == 5 for entry in calls))
            self.assertIn("actual effect applied", output.getvalue())
            self.assertNotIn("snapshot getter noise", output.getvalue())

    def testNativeTailSurvivesFailedDiagnosticRpc(self):
        import contextlib
        import io
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "native.log"
            path.write_text("last actual combat action\n", encoding="utf-8")

            def broken(*args, **kwargs):
                raise OSError("stdio unavailable")

            fixture = SimpleNamespace(
                process=SimpleNamespace(poll=lambda: None),
                harness=SimpleNamespace(_mcp_handle_call=broken),
                session={},
                game_map="map",
                native_log_path=path,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                OctobogzMcpWalkthroughTest.reportCombatFailure(fixture, "defeat brood", {})
            evidence = json.loads(path.with_suffix(".failure.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("OSError", evidence["diagnosticError"]["type"])
            self.assertIn("last actual combat action", output.getvalue())

    def testMovementStopsAtTheFirstDefeatBeforeAnotherMapTurn(self):
        from types import SimpleNamespace

        for mode in ("move-defeat", "move-dead", "pump-defeat", "turn-defeat", "success", "acknowledged-success"):
            with self.subTest(mode=mode):
                calls = []
                prior_receipt = "earlier acknowledged defeat" if mode == "acknowledged-success" else ""
                state = {"coords": (0, 0, 0), "receipt": prior_receipt, "alive": True, "turn": 7}
                pumps = []

                def pump():
                    pumps.append(len(pumps) + 1)
                    if mode == "pump-defeat" and len(pumps) == 1:
                        state["receipt"] = "first defeat"
                        state["coords"] = (0, 0, 0)

                def call(actor, method, *args):
                    calls.append((actor, method))
                    if method == "getStringProperty":
                        self.assertEqual(("uiDefeatReceipt",), args)
                        return state["receipt"]
                    if method == "getTile":
                        return "tile"
                    if method == "getBoolProperty":
                        self.assertEqual(("canStep",), args)
                        return True
                    if method == "moveTo":
                        state["coords"] = args
                        if mode == "move-defeat":
                            state["receipt"] = "first defeat"
                            state["coords"] = (0, 0, 0)
                        elif mode == "move-dead":
                            state["alive"] = False
                        return None
                    if method == "getTurn":
                        return state["turn"]
                    if method == "move":
                        state["turn"] += 1
                        if mode == "turn-defeat":
                            state["receipt"] = "first defeat"
                            state["coords"] = (0, 0, 0)
                        elif mode == "move-defeat":
                            state["receipt"] = "overwritten defeat"
                        return None
                    if method == "isAlive":
                        return state["alive"]
                    self.fail("Unexpected movement RPC: " + method)

                fixture = SimpleNamespace(
                    coords=lambda: state["coords"],
                    call=call,
                    player="player",
                    game_map="map",
                    assertEqual=self.assertEqual,
                    assertIsNotNone=self.assertIsNotNone,
                    assertTrue=self.assertTrue,
                    fail=self.fail,
                    snapshot=lambda stage: stage,
                    pump=pump,
                    movement_steps=0,
                )
                if mode in ("success", "acknowledged-success"):
                    self.assertEqual((1, 0, 0), OctobogzMcpWalkthroughTest.step(fixture, (1, 0, 0)))
                    self.assertEqual(1, fixture.movement_steps)
                else:
                    with self.assertRaisesRegex(
                        AssertionError,
                        "defeated during movement" if mode == "move-dead" else "lost authored combat and respawned",
                    ):
                        OctobogzMcpWalkthroughTest.step(fixture, (1, 0, 0))
                    self.assertEqual(0, fixture.movement_steps)
                self.assertEqual(
                    0 if mode.startswith("move-") or mode == "pump-defeat" else 1,
                    calls.count(("map", "move")),
                    "A failed move must not issue a turn that can overwrite its first defeat receipt",
                )
                self.assertEqual("first defeat" if "defeat" in mode else prior_receipt, state["receipt"])
                self.assertEqual(1 if mode.startswith("move-") or mode == "pump-defeat" else 2, len(pumps))

    def testDiagnosticFailurePreservesTheOriginalCombatException(self):
        from types import SimpleNamespace

        failure = AssertionError("original authored combat failure")
        calls = []

        def walk(name, *, allow_removed):
            calls.append((name, allow_removed))
            raise failure

        def diagnostic(*args):
            raise OSError("diagnostic output failed")

        fixture = SimpleNamespace(
            state=lambda: {"slots": {"brood": {"status": "living", "name": "actualBrood"}}},
            assertEqual=self.assertEqual,
            trackLivingHuntActors=lambda: None,
            livingActors=lambda: {"brood": "actualBrood"},
            snapshot=lambda stage: None,
            walkTo=walk,
            reportCombatFailure=diagnostic,
        )
        with self.assertRaises(AssertionError) as raised:
            OctobogzMcpWalkthroughTest.defeat(fixture, "brood")
        self.assertIs(failure, raised.exception)
        self.assertEqual([("actualBrood", True)], calls)

    def testPreparationFailureRetainsNativeTailAndPreservesItsOriginalAssertion(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import Mock

        for diagnostic_failure in (None, "rpc", "read", "print"):
            with self.subTest(diagnostic_failure=diagnostic_failure), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "native.log"
                path.write_text("last actual Alpha combat action\n", encoding="utf-8")
                failure = AssertionError("original stronger healing stock assertion")
                actions, diagnostics = [], []

                def brew():
                    actions.append("brew")

                def sell(preserve_ingredients=False):
                    actions.append(("sell", preserve_ingredients))
                    if not preserve_ingredients:
                        raise failure

                def handle(*args, **kwargs):
                    if diagnostic_failure == "rpc":
                        raise OSError("diagnostic RPC failed")
                    return 7

                fixture = SimpleNamespace(
                    brewOwnedBasicLifePotions=brew,
                    sellWeakHealingStockAtAuthoredMarket=sell,
                    buyFiniteBasicIngredientsAtAuthoredMarket=lambda initial: actions.append(("buy", initial)),
                    snapshot=lambda stage: actions.append(("snapshot", stage)),
                    process=SimpleNamespace(poll=lambda: None),
                    harness=SimpleNamespace(
                        _mcp_handle_call=handle,
                        _mcp_engine_call=lambda *args, **kwargs: json.dumps({"properties": {"hp": 91}}),
                    ),
                    session={},
                    game_map="map",
                    player="player",
                    native_log_path=path,
                    mcp_profile_class="Sorcerer",
                    hunt_actors={"alpha": "actualAlpha", "brood": "actualBrood"},
                )

                def diagnostic(stage, actors):
                    diagnostics.append((stage, actors))
                    OctobogzMcpWalkthroughTest.reportCombatFailure(fixture, stage, actors)

                fixture.reportCombatFailure = diagnostic
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    stack.enter_context(contextlib.redirect_stdout(output))
                    if diagnostic_failure == "read":
                        stack.enter_context(patch(__name__ + ".readNativeLogTail", side_effect=OSError("read failed")))
                    if diagnostic_failure == "print":
                        stack.enter_context(patch("builtins.print", side_effect=OSError("report failed")))
                    with self.assertRaises(AssertionError) as raised:
                        OctobogzMcpWalkthroughTest.prepareHealingStockAtAuthoredMarket(fixture, initial=False)
                self.assertIs(failure, raised.exception)
                self.assertEqual(["brew", ("sell", True), "brew", ("buy", False), "brew", ("sell", False)], actions)
                self.assertEqual([("healing preparation", fixture.hunt_actors)], diagnostics)
                if diagnostic_failure in (None, "rpc"):
                    self.assertIn("last actual Alpha combat action", output.getvalue())
                self.assertEqual("last actual Alpha combat action\n", path.read_text(encoding="utf-8"))

        actions = []
        fixture.brewOwnedBasicLifePotions = lambda: actions.append("brew")
        fixture.sellWeakHealingStockAtAuthoredMarket = lambda **kwargs: actions.append(("sell", kwargs))
        fixture.buyFiniteBasicIngredientsAtAuthoredMarket = lambda initial: actions.append(("buy", initial))
        fixture.snapshot = lambda stage: actions.append(("snapshot", stage))
        fixture.reportCombatFailure = Mock(side_effect=AssertionError("successful preparation must not diagnose"))
        OctobogzMcpWalkthroughTest.prepareHealingStockAtAuthoredMarket(fixture, initial=False)
        fixture.reportCombatFailure.assert_not_called()
        self.assertEqual(7, len(actions))

    def testRoadRecoveryFailureRetainsNativeTailAndPreservesItsOriginalTravelException(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import Mock

        for diagnostic_failure in (None, "rpc", "read", "print"):
            with self.subTest(diagnostic_failure=diagnostic_failure), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "actual-road-native.log"
                path.write_text("actual native road combat sentinel\n", encoding="utf-8")
                failure = RuntimeError("original actual road travel failure")
                diagnostics = []

                def handle(*args, **kwargs):
                    if diagnostic_failure == "rpc":
                        raise OSError("diagnostic RPC failed")
                    return 7

                fixture = SimpleNamespace(
                    livingActors=lambda: {"brood": "actualBrood"},
                    recoverBeforeRoadDeparture=lambda: None,
                    recoverOnRoadPair=Mock(side_effect=failure),
                    process=SimpleNamespace(poll=lambda: None),
                    harness=SimpleNamespace(
                        _mcp_handle_call=handle,
                        _mcp_engine_call=lambda *args, **kwargs: json.dumps({"properties": {"hp": 91}}),
                    ),
                    session={},
                    game_map="map",
                    player="player",
                    native_log_path=path,
                    mcp_profile_class="Sorcerer",
                    hunt_actors={"alpha": "actualAlpha", "brood": "actualBrood"},
                )

                def diagnostic(stage, actors):
                    diagnostics.append((stage, actors))
                    OctobogzMcpWalkthroughTest.reportCombatFailure(fixture, stage, actors)

                fixture.reportCombatFailure = diagnostic
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    stack.enter_context(contextlib.redirect_stdout(output))
                    if diagnostic_failure == "read":
                        stack.enter_context(patch(__name__ + ".readNativeLogTail", side_effect=OSError("read failed")))
                    if diagnostic_failure == "print":
                        stack.enter_context(patch("builtins.print", side_effect=OSError("report failed")))
                    with self.assertRaises(RuntimeError) as raised:
                        OctobogzMcpWalkthroughTest.recoverOnAuthoredRoad(fixture)
                self.assertIs(failure, raised.exception)
                self.assertEqual([("hunt road recovery", fixture.hunt_actors)], diagnostics)
                if diagnostic_failure in (None, "rpc"):
                    self.assertIn("actual native road combat sentinel", output.getvalue())
                self.assertEqual("actual native road combat sentinel\n", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
