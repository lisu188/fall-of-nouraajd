# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import struct
import unittest

from scripts.audit_baldurs_gate_city_chests import areaChests


class CityChestAreaAuditTest(unittest.TestCase):
    def setUp(self):
        start = 0x11C
        data = bytearray(start + 3 * 0xC0)
        data[:8] = b"AREAV1.0"
        struct.pack_into("<IH", data, 0x70, start, 3)
        containers = []
        for i, (name, kind) in enumerate((("Bag", 1), ("Chest", 2), ("Drawer", 3))):
            offset = start + i * 0xC0
            data[offset : offset + len(name)] = name.encode()
            struct.pack_into("<HHH", data, offset + 32, i, 10, kind)
            containers.append({"name": name, "position": [i, 10]})
        self.data = bytes(data)
        self.area = {"sha256": hashlib.sha256(data).hexdigest(), "containers": containers}

    def testOnlyChestFieldAssignsTheOneBasedSourceIndex(self):
        self.assertEqual(
            {"sha256": self.area["sha256"], "containerCount": 3, "chestIndices": [2]},
            areaChests(self.data, self.area),
        )

    def testAnEditedAreaAndMisalignedContainerTableAreRejected(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            areaChests(self.data + b"changed bytes", self.area)
        self.area["containers"][1]["position"][0] += 1
        with self.assertRaisesRegex(ValueError, "identity"):
            areaChests(self.data, self.area)
        self.area["containers"].pop()
        with self.assertRaisesRegex(ValueError, "count"):
            areaChests(self.data, self.area)
