# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
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
import csv
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "planning" / "generated-assets" / "mj_best_picks_manifest.csv"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def manifest_rows():
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as manifest:
        return list(csv.DictReader(manifest))


def selected_rows_by_target(rows):
    selected = {}
    for row in rows:
        if row["selected_variant"] == "MISSING" or not row["selected_file"]:
            continue
        target = row["target_png"]
        current = selected.get(target)
        if current is None or int(row["selected_variant"]) > int(current["selected_variant"]):
            selected[target] = row
    return selected


class MjBestPicksAssetsTest(unittest.TestCase):
    def test_selected_manifest_targets_are_committed_pngs(self):
        rows = manifest_rows()
        selected = selected_rows_by_target(rows)
        selected_ids = {row["object_id"] for row in selected.values()}
        missing_only_ids = sorted(
            {row["object_id"] for row in rows if row["selected_variant"] == "MISSING"} - selected_ids
        )

        self.assertEqual(50, len(selected))
        self.assertEqual(["ashCultist", "coldHorror", "marchRaider"], missing_only_ids)

        for target in sorted(selected):
            with self.subTest(target=target):
                path = REPO_ROOT / target
                self.assertTrue(path.is_file(), f"{target} is missing")
                self.assertEqual(PNG_SIGNATURE, path.read_bytes()[: len(PNG_SIGNATURE)])

    def test_map_config_entries_use_selected_animation_ids(self):
        selected = selected_rows_by_target(manifest_rows())
        animations = {row["object_id"]: row["target_animation_id"] for row in selected.values()}
        checked = set()

        for config_path in sorted((REPO_ROOT / "res" / "maps").glob("*/config.json")):
            config = json.loads(config_path.read_text(encoding="utf-8"))
            map_name = config_path.parent.name
            for object_id, animation in sorted(animations.items()):
                entry = config.get(object_id)
                if not isinstance(entry, dict):
                    continue
                checked.add((map_name, object_id))
                self.assertEqual(
                    animation,
                    entry.get("properties", {}).get("animation"),
                    f"{config_path.relative_to(REPO_ROOT)}:{object_id}",
                )

        self.assertIn(("nouraajd", "preciousAmulet"), checked)
        self.assertIn(("ninemarches", "theNinefoldKing"), checked)
        self.assertIn(("ritual", "ritualLeaderTemplate"), checked)

    def test_cmake_stages_selected_pngs(self):
        selected = selected_rows_by_target(manifest_rows())
        cmake = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        for target in sorted(selected):
            staged = target.removeprefix("res/")
            expected = f"configure_file({target} {staged} COPYONLY)"
            with self.subTest(target=target):
                self.assertIn(expected, cmake)
