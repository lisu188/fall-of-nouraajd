# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""City text metadata contracts; the coercion double is not native execution evidence."""

import inspect
import json
from pathlib import Path
import unittest

from scripts import build_baldurs_gate_city as builder
from tests.test_baldurs_gate_city_content import CityModel

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "city-json:"


class NativeMetadataSlot:
    """Model only the source-verified untyped JSON-string coercion and strict string getter."""

    def __init__(self, encoded):
        try:
            self.value = json.loads(encoded)
        except (ValueError, TypeError):
            self.value = encoded

    def getStringProperty(self, _key):
        if not isinstance(self.value, str):
            raise RuntimeError("bad any_cast")
        return self.value


class BaldursGateCityDataTest(unittest.TestCase):
    def helpers(self, model):
        return inspect.getclosurevars(type(model.clock).spawnActors).nonlocals

    def testDefinitionsProtectOnlyStructuredJsonTextAndKeepNativeValuesTyped(self):
        values = {
            "sourceInventory": '[{"item":"SCRL2K"}]',
            "sourceItemSlots": "[0,65535]",
            "questDefinitions": '{"quests":[]}',
            "typedItems": [{"ref": "cityItemScrl2k"}],
            "typedStats": {"class": "CStats", "properties": {"strength": 12}},
            "number": 12,
            "enabled": True,
            "label": "Marek",
            "numericText": "123",
            "booleanText": "true",
            "malformedText": "{unclosed",
        }
        props = builder.definition("CCreature", **values)["properties"]
        for key in ("sourceInventory", "sourceItemSlots", "questDefinitions"):
            self.assertEqual(PREFIX + values[key], props[key], key)
            self.assertEqual(props[key], NativeMetadataSlot(props[key]).getStringProperty(key))
        for key in values.keys() - {"sourceInventory", "sourceItemSlots", "questDefinitions"}:
            self.assertEqual(values[key], props[key], key)
        self.assertEqual(props, builder.definition("CCreature", **props)["properties"])

    def testFinalNormalizationPreservesReferencesExtraKeysAndTypedProperties(self):
        document = {
            "alias": {"ref": "nativeAlias", "extra": "kept", "properties": {"payload": "[]", "value": 12}},
            "actor": {
                "class": "CCreature",
                "properties": {
                    "inventory": [{"ref": "item"}],
                    "dialog": {"class": "CDialog", "properties": {"metadata": "{}"}},
                },
            },
        }
        result = builder.protectCityDefinitions(document)
        self.assertIs(document, result)
        self.assertEqual("nativeAlias", result["alias"]["ref"])
        self.assertEqual("kept", result["alias"]["extra"])
        self.assertNotIn("class", result["alias"])
        self.assertEqual({"payload": PREFIX + "[]", "value": 12}, result["alias"]["properties"])
        self.assertEqual([{"ref": "item"}], result["actor"]["properties"]["inventory"])
        self.assertEqual(PREFIX + "{}", result["actor"]["properties"]["dialog"]["properties"]["metadata"])
        before = json.dumps(result)
        self.assertEqual(before, json.dumps(builder.protectCityDefinitions(result)))

    def testRuntimeReadAcceptsLegacyAndProtectedMetadata(self):
        model = CityModel()
        read = self.helpers(model)["read"]
        for value in ([], {}, [{"item": "SCRL2K"}], {"quests": ["ducalPalace"]}):
            encoded = json.dumps(value)
            model.clock.setStringProperty("dataProbe", encoded)
            self.assertEqual(value, read(model.clock, "dataProbe", None))
            model.clock.setStringProperty("dataProbe", PREFIX + encoded)
            self.assertEqual(value, read(model.clock, "dataProbe", None))
            self.assertEqual(value, builder.decodeCityData(PREFIX + encoded))
            self.assertEqual(value, model.namespace["decodeData"](PREFIX + encoded))
        self.assertEqual([], read(model.clock, "missingProbe", []))

    def testRuntimeWriteSurvivesSerializedStringAndUntypedReload(self):
        model = CityModel()
        helpers = self.helpers(model)
        value = {"stage": "evidence", "actors": ["BELT", "LIIA"], "counts": [1, 2]}
        helpers["write"](model.clock, "dataProbe", value)
        encoded = model.clock.getStringProperty("dataProbe")
        self.assertTrue(encoded.startswith(PREFIX))
        saved = json.loads(json.dumps({"class": "CBuilding", "properties": {"dataProbe": encoded}}))
        restored = NativeMetadataSlot(saved["properties"]["dataProbe"])
        self.assertEqual(value, helpers["read"](restored, "dataProbe", {}))
        self.assertEqual(encoded, restored.getStringProperty("dataProbe"))

    def testProtectedRegionCacheInputsDecodeWithoutLosingState(self):
        model = CityModel()
        model.clock.setStringProperty("regionDefinitions", PREFIX + '{"regions":[]}')
        model.clock.observeRegions()
        self.assertEqual(1, model.clock.getNumericProperty("plugin_cityRegionIndexBuilds"))
        model.clock.observeRegions()
        self.assertEqual(1, model.clock.getNumericProperty("plugin_cityRegionIndexBuilds"))
        self.assertEqual([], builder.decodeCityData(model.game_map.getStringProperty("plugin_cityRegionOccupancy")))
        self.assertEqual({}, builder.decodeCityData(model.game_map.getStringProperty("plugin_cityRegionVisits")))

    def testActualSourceAndClockMetadataRemainTextAfterUntypedCoercion(self):
        config = json.loads((ROOT / "res/maps/baldursGate/config.json").read_text(encoding="utf-8"))
        cases = (
            ("cityAr0300Actor29", "sourceInventory", list),
            ("cityAr0300Actor29", "sourceItemSlots", list),
            ("cityClock", "questDefinitions", dict),
            ("cityClock", "areaAtlas", dict),
            ("cityClock", "actorDefinitions", list),
            ("cityClock", "regionDefinitions", dict),
        )
        for resource, key, expected_type in cases:
            with self.subTest(resource=resource, key=key):
                encoded = config[resource]["properties"][key]
                self.assertTrue(encoded.startswith(PREFIX))
                retained = NativeMetadataSlot(encoded).getStringProperty(key)
                self.assertIsInstance(builder.decodeCityData(retained), expected_type)

    def sourceFlagScenario(self, item_flags=32, instance_flags=0, known=True):
        model = CityModel()
        facts = {"flags": item_flags, "item_type": 0, "stack_size": 1, "ability_count": 1}
        if not known:
            del facts["flags"]
        model.resources["cityItemCarrio1"] = builder.nativeItem("CARRIO1", facts)
        initialize = inspect.getclosurevars(type(model.clock).initializeActor).nonlocals["initializeInventory"]
        make_item = inspect.getclosurevars(initialize).nonlocals["makeSourceItem"]
        row = {"item": "CARRIO1", "flags": instance_flags, "charges": [0, 0, 0], "expiration": 0}
        item = make_item(model.clock, row)
        model.resources["flagOwner"] = {"class": "CCreature", "properties": {"label": "Flag owner"}}
        owner = model.createObject("flagOwner")
        owner.addItem(item)
        model.game_map.addObject(owner)
        return model, owner, item, row

    def testSourceNaturalWeaponRetainsHeaderRestrictionAndActualOwner(self):
        source = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf8"))
        facts = source["items"]["CARRIO1"]
        row = source["creatures"]["CARRIO"]["items"][0]
        self.assertEqual(32, facts["flags"])
        self.assertEqual(0, row["flags"])
        self.assertEqual(420, source["creatures"]["CARRIO"]["kill_xp"])
        props = builder.nativeItem("CARRIO1", facts)["properties"]
        self.assertEqual(32, props.get("plugin_cityItemFlags"))
        self.assertTrue(props.get("plugin_cityItemImmovable"))
        self.assertTrue(props.get("plugin_cityUndroppable"))
        self.assertFalse(props["plugin_cityTradeable"])
        model, owner, item, original = self.sourceFlagScenario()
        self.assertTrue(item.getBoolProperty("plugin_cityUndroppable"))
        self.assertIs(item, owner.getItems()[0])
        self.assertEqual(1, len(owner.getItems()))
        self.assertEqual([0, 0, 0], builder.decodeCityData(item.getStringProperty("plugin_cityCharges")))
        self.assertEqual(0, item.getNumericProperty("plugin_citySourceFlags"))
        self.assertEqual(32, item.getNumericProperty("plugin_cityItemFlags"))
        self.assertEqual({"item": "CARRIO1", "flags": 0, "charges": [0, 0, 0], "expiration": 0}, original)
        self.assertFalse(model.dialog(owner).canPickpocket())

    def testSourceItemAndInstanceFlagsComposeWithoutReplacingEither(self):
        for header, instance, undroppable, unstealable in (
            (32, 0, True, False),
            (36, 0, False, False),
            (36, 2, False, True),
            (36, 8, True, False),
            (36, 10, True, True),
            (32, 4, True, False),
        ):
            with self.subTest(header=header, instance=instance):
                model, owner, item, row = self.sourceFlagScenario(header, instance)
                self.assertEqual(undroppable, item.getBoolProperty("plugin_cityUndroppable"))
                self.assertEqual(unstealable, item.getBoolProperty("plugin_cityUnstealable"))
                self.assertEqual(header, item.getNumericProperty("plugin_cityItemFlags"))
                self.assertEqual(instance, item.getNumericProperty("plugin_citySourceFlags"))
                self.assertEqual(instance, row["flags"])
                self.assertEqual(bool(instance & 4), item.getBoolProperty("plugin_cityStolen"))
                self.assertEqual(not bool(instance & 1), item.getBoolProperty("plugin_cityUnidentified"))
                self.assertIs(item, owner.getItems()[0])

    def testSourceItemMovementPermissionControlsExistingTheftEligibility(self):
        for flags, expected in ((32, False), (36, True), (40, False), (44, True)):
            with self.subTest(flags=flags):
                model, owner, item, _ = self.sourceFlagScenario(flags)
                self.assertTrue(model.dialog(owner).canInteract())
                self.assertEqual(expected, model.dialog(owner).canPickpocket())
                self.assertIs(item, owner.getItems()[0])

    def testClassicCriticalAndUnsellableFlagsRemainEditionSpecific(self):
        for flags, tradeable, undroppable in (
            (5, True, False),
            (2052, False, False),
            (32, False, True),
            (36, True, False),
        ):
            with self.subTest(flags=flags):
                props = builder.nativeItem("TEST", {"flags": flags})["properties"]
                self.assertEqual(tradeable, props["plugin_cityTradeable"])
                self.assertEqual(undroppable, props.get("plugin_cityUndroppable", False))

    def testUnknownItemHeaderDoesNotInventAnImmovabilityRestriction(self):
        props = builder.nativeItem("UNKNOWN", {})["properties"]
        self.assertNotIn("plugin_cityItemFlags", props)
        self.assertNotIn("plugin_cityItemImmovable", props)
        self.assertTrue(props["plugin_cityTradeable"])
        model, owner, item, _ = self.sourceFlagScenario(known=False)
        self.assertFalse(item.getBoolProperty("plugin_cityUndroppable"))
        self.assertTrue(model.dialog(owner).canPickpocket())
        self.assertIs(item, owner.getItems()[0])
        _, _, restricted, _ = self.sourceFlagScenario(instance_flags=8, known=False)
        self.assertTrue(restricted.getBoolProperty("plugin_cityUndroppable"))

    def testSerializedItemProjectionKeepsTheExistingUndroppableFilterInput(self):
        _, owner, item, _ = self.sourceFlagScenario()
        restored = json.loads(json.dumps(item.properties))
        self.assertTrue(restored["plugin_cityUndroppable"])
        self.assertEqual(32, restored["plugin_cityItemFlags"])
        self.assertEqual(0, restored["plugin_citySourceFlags"])
        self.assertIs(item, owner.getItems()[0])

    def testAuthoredNaturalWeaponTemplateCarriesEffectiveRestriction(self):
        config = json.loads((ROOT / "res/maps/baldursGate/config.json").read_text(encoding="utf8"))
        props = config["cityItemCarrio1"]["properties"]
        self.assertEqual(32, props.get("plugin_cityItemFlags"))
        self.assertTrue(props.get("plugin_cityUndroppable"))
        self.assertFalse(props["plugin_cityTradeable"])
        actor = config["cityAr0226Actor8"]["properties"]
        self.assertEqual(420, actor["sourceKillXp"])
        rows = builder.decodeCityData(actor["sourceInventory"])
        self.assertEqual(["CARRIO1"], [row["item"] for row in rows])
        self.assertEqual(0, rows[0]["flags"])


if __name__ == "__main__":
    unittest.main()
