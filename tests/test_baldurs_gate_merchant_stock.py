# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite stock source/model checks; these do not establish native factory or item-ability parity."""

from copy import deepcopy
from contextlib import redirect_stdout
import io
from itertools import product
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from scripts import build_baldurs_gate_merchant_stock as stock

ROOT = Path(__file__).resolve().parents[1]


def terminalTree(document):
    """Enumerate the finite directed data tree independently of the compiled rolling loop."""
    leaves = {}

    def expand(family, prefix, trace):
        row = document["rows"][family]
        by_column = dict(zip(row["columns"], row["cells"]))
        for column in range(1, 21):
            token = by_column.get(column, "")
            path = (*prefix, column)
            steps = [*trace, {"family": family, "row": row["ordinal"], "column": column, "token": token}]
            if token in document["rows"]:
                expand(token, path, steps)
                continue
            outcome = {"kind": "none", "code": "", "quantity": 0, "gold": 0, "charges": [0, 0, 0]}
            if token.isdecimal():
                outcome.update(kind="gold", gold=int(token))
            elif token:
                code, _, suffix = token.partition("*")
                item = document["items"][code]
                quantity = int(suffix) if suffix and item["stackSize"] > 1 else 1
                outcome.update(kind="item", code=code, quantity=quantity, charges=list(item["charges"]))
            leaves[path] = {"rolls": steps, "outcome": outcome}

    expand("RNDTRE05", (), [])
    return leaves


class BaldursGateMerchantStockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / stock.FIXTURE_PATH).read_text(encoding="utf-8"))
        cls.leaves = terminalTree(cls.document)

    def testSixRowsAndNinetySevenConcreteItemsAreClosedWithoutAbilityOrClassicCredit(self):
        self.assertIs(self.document, stock.validateStock(self.document))
        self.assertEqual(6, len(self.document["rows"]))
        self.assertEqual(97, len(self.document["items"]))
        self.assertEqual(set(stock.FAMILIES), set(self.document["rows"]))
        terminal_codes = {leaf["outcome"]["code"] for leaf in self.leaves.values() if leaf["outcome"]["kind"] == "item"}
        self.assertEqual(set(self.document["items"]), terminal_codes)
        self.assertEqual({"none", "gold", "item"}, {leaf["outcome"]["kind"] for leaf in self.leaves.values()})
        self.assertFalse(self.document["originalParity"])
        self.assertFalse(self.document["itemAbilitiesEstablished"])
        self.assertFalse(self.document["sourceDiceRuleEstablished"])
        self.assertEqual("oneNativeD20PerSelectedRow", self.document["nativeDiceRule"])
        self.assertTrue(self.document["acceptanceGaps"])
        self.assertTrue(all(item["abilitiesPending"] for item in self.document["items"].values()))

    def testAllEightThousandRollTriplesUseExactlyOneCompiledValidationAndMatchTheDataTree(self):
        with patch.object(stock, "validateStock", wraps=stock.validateStock) as validate:
            resolve = stock.compileResolver(self.document)
            self.assertEqual(1, validate.call_count)
        outcomes, codes, lengths = set(), set(), set()
        with patch.object(stock, "validateStock", side_effect=AssertionError("Repeated closure validation")):
            for triple in product(range(1, 21), repeat=3):
                prefix = next(triple[:length] for length in (1, 2, 3) if triple[:length] in self.leaves)
                expected = self.leaves[prefix]
                actual = resolve(triple)
                self.assertEqual(expected, actual, triple)
                outcomes.add(actual["outcome"]["kind"])
                lengths.add(len(actual["rolls"]))
                if actual["outcome"]["kind"] == "item":
                    codes.add(actual["outcome"]["code"])
        self.assertEqual({"none", "gold", "item"}, outcomes)
        self.assertEqual({1, 2, 3}, lengths)
        self.assertEqual(set(self.document["items"]), codes)

    def testSelectedRowsConsumeOneNativeD20EachAndLeaveUnusedDrawsUntouched(self):
        resolve = stock.compileResolver(self.document)
        for draws, expected in (((1,), 1), ((11,), 1), ((2, 18), 2), ((2, 7, 4), 3), ((3, 7, 1), 3)):
            consumed = []

            def stream():
                for value in draws:
                    consumed.append(value)
                    yield value
                raise AssertionError("Unselected native random draw consumed")

            result = resolve(stream())
            self.assertEqual(expected, len(result["rolls"]))
            self.assertEqual(list(draws), consumed)
        self.assertEqual("gold", resolve((11, False, "unused"))["outcome"]["kind"])
        self.assertEqual("none", resolve((1, False))["outcome"]["kind"])

    def testInvalidSelectedD20ValuesAndMissingNestedRollsFailClosed(self):
        resolve = stock.compileResolver(self.document)
        for invalid in (0, 21, -1, True, False, 1.0, "1", None):
            for draws in ((invalid,), (2, invalid), (2, 7, invalid)):
                with self.subTest(draws=draws), self.assertRaises(ValueError):
                    resolve(draws)
        for draws in ((), (2,), (2, 7)):
            with self.subTest(draws=draws), self.assertRaisesRegex(ValueError, "Missing"):
                resolve(draws)

    def testCompiledSnapshotAndReturnedResultsDoNotRetainMutableInputOwnership(self):
        document = deepcopy(self.document)
        resolve = stock.compileResolver(document)
        expected = resolve((2, 18))
        document["rows"]["RNDTRE05"]["cells"][0] = "RNDTRE05"
        document["items"]["WAND03"]["charges"][0] = 999
        self.assertEqual(expected, resolve((2, 18)))
        result = resolve((2, 18))
        result["outcome"]["charges"][0] = 777
        result["rolls"][0]["token"] = "tampered"
        self.assertEqual(expected, resolve((2, 18)))
        self.assertEqual(expected, stock.resolveStock(self.document, (2, 18)))

    def testStacksAndWandSuffixesPreserveParsedChargesWithoutMultiplyingWands(self):
        resolve = stock.compileResolver(self.document)
        self.assertEqual(("BULL03", 3), tuple(resolve((3, 4))["outcome"][key] for key in ("code", "quantity")))
        self.assertEqual(("AROW02", 5), tuple(resolve((3, 17))["outcome"][key] for key in ("code", "quantity")))
        for column, code, charges in (
            (18, "WAND03", [100, 0, 0]),
            (19, "WAND05", [50, 50, 0]),
            (20, "WAND06", [100, 0, 0]),
        ):
            self.assertEqual(
                {"kind": "item", "code": code, "quantity": 1, "gold": 0, "charges": charges},
                resolve((2, column))["outcome"],
            )
        changed = deepcopy(self.document)
        changed["items"]["BULL03"]["stackSize"] = 2
        with self.assertRaisesRegex(ValueError, "capacity"):
            stock.compileResolver(changed)((3, 4))

    def testCyclicUnknownFamiliesAndChangedRowHeadersAreRejectedBeforeResolution(self):
        for family, field, value in (
            ("RNDTRE05", "table", "RNDMAGIC"),
            ("RNDSCR01", "ordinal", True),
            ("RNDTRE05", "ordinal", 6),
            ("RNDSCR01", "columns", list(range(2, 22))),
        ):
            changed = deepcopy(self.document)
            changed["rows"][family][field] = value
            with self.subTest(family=family, field=field), self.assertRaises(ValueError):
                stock.compileResolver(changed)
        for family, token in (("RNDTRE05", "RNDTRE05"), ("RNDMAG01", "RNDMAG02"), ("RNDTRE05", "RNDMAG99")):
            changed = deepcopy(self.document)
            changed["rows"][family]["cells"][0] = token
            with self.subTest(family=family, token=token), self.assertRaises(ValueError):
                stock.compileResolver(changed)

    def testBooleanOrFloatColumnsCannotBecomeInvalidNativeHeaderFields(self):
        for invalid in (True, 1.0):
            changed = deepcopy(self.document)
            changed["rows"]["RNDSCR01"]["columns"][0] = invalid
            with self.subTest(header=invalid), self.assertRaisesRegex(ValueError, "columns"):
                stock.stockHeader(changed)

    def testParsedChargeCountEffectMetadataAndHeaderIdentityStayBounded(self):
        for code, item in self.document["items"].items():
            self.assertEqual(item["abilityCount"], len(item["abilityEffectCounts"]), code)
            self.assertTrue(all(value == 0 for value in item["charges"][item["abilityCount"] :]), code)
            self.assertEqual(item["baseSha256"], item["headerEvidence"]["fingerprint"]["sha256"])
            self.assertEqual("ITM V1", item["headerEvidence"]["format"])
        for key, value in (
            ("abilityCount", True),
            ("abilityCount", 4),
            ("abilityEffectCounts", [4097]),
            ("equippedEffectCount", -1),
            ("charges", [100, 0, 1]),
        ):
            changed = deepcopy(self.document)
            changed["items"]["WAND03"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                stock.validateStock(changed)
        changed = deepcopy(self.document)
        changed["items"]["WAND03"]["headerEvidence"]["fingerprint"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "header identity"):
            stock.validateStock(changed)
        self.assertEqual(
            {"itemHeaders", "scrollFrontier", "priorClosure", "rootTable"}, set(self.document["inputFingerprints"])
        )
        self.assertTrue(
            all(
                len(value) == 64 and all(char in "0123456789abcdef" for char in value)
                for value in self.document["inputFingerprints"].values()
            )
        )

    def testDedicatedConfigClassesBodyWeaponAndNewConcreteItemsHaveNoGlobalS1Mutation(self):
        config = stock.stockDefinitions(self.document)
        self.assertEqual(99, len(config))
        self.assertNotIn("S1-12", config)
        actor = config[stock.ACTOR_ID]
        self.assertEqual("CCreature", actor["class"])
        body = actor["properties"]["baseStats"]["properties"]
        self.assertEqual((0, 0, 0, 0), tuple(body[key] for key in ("dmgMin", "dmgMax", "damage", "crit")))
        self.assertEqual((4, 75), (body["stamina"], body["hit"]))
        self.assertEqual(420, actor["properties"]["sourceKillXp"])
        weapon = config[stock.WEAPON_ID]
        self.assertEqual("CWeapon", weapon["class"])
        self.assertEqual({"dmgMin": 1, "dmgMax": 12, "hit": 0}, weapon["properties"]["bonus"]["properties"])
        for code in ("BOLT05", "SCRL1J", "SCRL2I"):
            self.assertEqual("CItem", config[stock.itemId(code)]["class"])
            self.assertEqual(code, config[stock.itemId(code)]["properties"]["plugin_citySourceItem"])
            self.assertNotIn(code, config[stock.itemId(code)]["properties"]["label"])

    def testSourceEnchantmentIsMetadataOnlyForWeaponAndAllNinetySevenItems(self):
        config = stock.stockDefinitions(self.document)
        self.assertEqual(1, self.document["weapon"]["enchantment"])
        self.assertEqual(1, config[stock.WEAPON_ID]["properties"]["plugin_citySourceEnchantment"])
        for code, item in self.document["items"].items():
            properties = config[stock.itemId(code)]["properties"]
            self.assertEqual(item["enchantment"], properties["plugin_citySourceEnchantment"])
            self.assertNotIn("bonus", properties)
            self.assertTrue(properties["plugin_cityAbilitiesPending"])
        self.assertEqual({"dmgMin", "dmgMax", "hit"}, set(config[stock.WEAPON_ID]["properties"]["bonus"]["properties"]))
        for invalid in (0, True, 1.0):
            changed = deepcopy(self.document)
            changed["weapon"]["enchantment"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                stock.validateStock(changed)

    def testGeneratedHeaderCheckRejectsStaleContentWithoutWritingFiles(self):
        expected = stock.stockHeader(self.document)
        self.assertIn("std::array<Item, 97>", expected)
        self.assertIn("std::array<Row, 6>", expected)
        self.assertIn('"WAND03"', expected)
        root = Path("virtual-finite-stock")

        def read(path, *args, **kwargs):
            return json.dumps(self.document) if path == root / stock.FIXTURE_PATH else header

        for header, succeeds in ((expected, True), (expected.replace('"WAND03"', '"CHANGED"', 1), False)):
            with patch.object(stock, "ROOT", root), patch.object(
                sys, "argv", ["stock-compiler", "--check"]
            ), patch.object(Path, "read_text", read), patch.object(Path, "is_file", return_value=True), patch.object(
                Path, "write_text", side_effect=AssertionError("Check mode attempted a write")
            ), redirect_stdout(
                io.StringIO()
            ):
                if succeeds:
                    stock.main()
                else:
                    with self.assertRaisesRegex(ValueError, "Stale"):
                        stock.main()


if __name__ == "__main__":
    unittest.main()
