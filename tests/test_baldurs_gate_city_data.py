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


if __name__ == "__main__":
    unittest.main()
