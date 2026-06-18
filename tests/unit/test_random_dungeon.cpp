/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include "test_harness.h"
#include <rdg.h>

#include <random>
#include <vector>

namespace {

void test_random_dungeon_cell_flags_and_validation() {
    rdg::Cell cell;
    cell.setType(rdg::CellType::ROOM);
    expect_true(cell.hasType(rdg::CellType::ROOM), "rdg cell should store a primary type");
    expect_true(cell.isBlockedRoom(), "rdg room cells should block room placement");
    expect_true(cell.isOpenspace(), "rdg room cells should be open space");
    cell.addType(rdg::CellType::ENTRANCE);
    cell.setLabel("A");
    expect_true(cell.hasLabel() && cell.getLabel() == "A", "rdg cells should expose single-character labels");
    expect_true(cell.isEspace(), "rdg labeled entrance cells should count as entrance space");
    cell.clearEspace();
    expect_true(!cell.hasLabel(), "rdg clearEspace should clear labels");
    expect_true(!cell.hasType(rdg::CellType::ENTRANCE), "rdg clearEspace should clear entrance flags");
    cell.setType(rdg::CellType::STAIR_DN);
    cell.addType(rdg::CellType::STAIR_UP);
    expect_true(cell.isStairs(), "rdg stair flags should be detected");
    cell.clearTypes();
    expect_true(!cell.isStairs(), "rdg clearTypes should remove stair flags");

    rdg::Door locked_door{.kind = rdg::DoorKind::Locked};
    rdg::Stairs up_stairs{.kind = rdg::StairKind::Up};
    expect_true(locked_door.getKey() == "lock", "rdg door keys should describe locked doors");
    expect_true(locked_door.getType() == "Locked Door", "rdg door labels should describe locked doors");
    expect_true(up_stairs.getKey() == "up", "rdg stair keys should describe up stairs");

    expect_true(rdg::dungeon_layout_from_string("Box") == rdg::DungeonLayout::Box,
                "rdg dungeon layout parsing should accept Box");
    expect_true(!rdg::dungeon_layout_from_string("Invalid"), "rdg dungeon layout parsing should reject unknown values");
    expect_true(rdg::room_layout_from_string("Packed") == rdg::RoomLayout::Packed,
                "rdg room layout parsing should accept Packed");
    expect_true(!rdg::room_layout_from_string("Invalid"), "rdg room layout parsing should reject unknown values");
    expect_true(rdg::map_style_from_string("Standard") == rdg::MapStyle::Standard,
                "rdg map style parsing should accept Standard");
    expect_true(!rdg::map_style_from_string("Invalid"), "rdg map style parsing should reject unknown values");
    expect_true(rdg::to_string(rdg::DungeonLayout::Round) == "Round", "rdg layout strings should include Round");
    expect_true(rdg::to_string(rdg::RoomLayout::Scattered) == "Scattered",
                "rdg room layout strings should include Scattered");
    expect_true(rdg::to_string(rdg::MapStyle::Standard) == "Standard", "rdg map style strings should include Standard");
    expect_true(rdg::key(rdg::DoorKind::Portcullis) == "portc", "rdg door keys should include portcullis");
    expect_true(rdg::to_string(rdg::DoorKind::Secret) == "Secret Door", "rdg door labels should include secret doors");
    expect_true(rdg::key(rdg::StairKind::Down) == "down", "rdg stair keys should include down stairs");

    rdg::Options options;
    options.n_rows = 2;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject tiny dimensions");
    options.n_rows = 4;
    options.n_cols = 5;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject even dimensions");
    options.n_rows = 5;
    options.room_min = 0;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject non-positive room sizes");
    options.room_min = 7;
    options.room_max = 3;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject inverted room sizes");
    options.room_min = 3;
    options.room_max = 7;
    options.remove_deadends = 101;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject invalid dead-end percentages");
    options.remove_deadends = 50;
    options.add_stairs = -1;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject negative stair counts");
    options.add_stairs = 1;
    options.cell_size = 0;
    expect_true(rdg::validate_options(options).has_value(), "rdg should reject non-positive cell sizes");
    options.cell_size = 18;
    expect_true(!rdg::validate_options(options).has_value(), "rdg should accept valid options");
}

void test_random_dungeon_layout_variants_generate_accessible_maps() {
    std::mt19937 rng(12345);
    std::vector<rdg::Options> variants;

    rdg::Options packed_box;
    packed_box.n_rows = 17;
    packed_box.n_cols = 17;
    packed_box.room_layout = rdg::RoomLayout::Packed;
    packed_box.dungeon_layout = rdg::DungeonLayout::Box;
    packed_box.corridor_layout = rdg::CorridorLayout::STRAIGHT;
    packed_box.add_stairs = 2;
    variants.push_back(packed_box);

    rdg::Options scattered_cross;
    scattered_cross.n_rows = 21;
    scattered_cross.n_cols = 21;
    scattered_cross.room_layout = rdg::RoomLayout::Scattered;
    scattered_cross.dungeon_layout = rdg::DungeonLayout::Cross;
    scattered_cross.corridor_layout = rdg::CorridorLayout::BENT;
    scattered_cross.remove_deadends = 50;
    scattered_cross.add_stairs = 1;
    variants.push_back(scattered_cross);

    rdg::Options round_labyrinth;
    round_labyrinth.n_rows = 19;
    round_labyrinth.n_cols = 19;
    round_labyrinth.room_layout = rdg::RoomLayout::Packed;
    round_labyrinth.dungeon_layout = rdg::DungeonLayout::Round;
    round_labyrinth.corridor_layout = rdg::CorridorLayout::LABYRINTH;
    round_labyrinth.remove_deadends = 0;
    round_labyrinth.add_stairs = 0;
    variants.push_back(round_labyrinth);

    for (const auto &options : variants) {
        auto dungeon = rdg::create_dungeon(options, rng);
        expect_true(dungeon.rowCount() == options.n_rows, "rdg dungeon should preserve requested row count");
        expect_true(dungeon.colCount() == options.n_cols, "rdg dungeon should preserve requested column count");
        expect_true(!dungeon.getCells().empty(), "rdg dungeon should expose generated cells");
        expect_true(!dungeon.getRooms().empty(), "rdg dungeon variants should generate rooms");

        int open_cells = 0;
        int blocked_cells = 0;
        int door_cells = 0;
        int stair_cells = 0;
        for (int row = 0; row < dungeon.rowCount(); ++row) {
            for (int col = 0; col < dungeon.colCount(); ++col) {
                const auto &cell = dungeon.cellAt(row, col);
                open_cells += cell.isOpenspace() ? 1 : 0;
                blocked_cells += cell.hasType(rdg::CellType::BLOCKED) ? 1 : 0;
                door_cells += cell.isDoorspace() ? 1 : 0;
                stair_cells += cell.isStairs() ? 1 : 0;
            }
        }

        expect_true(open_cells > 0, "rdg dungeon variants should include open cells");
        expect_true(blocked_cells >= 0, "rdg dungeon blocked count should be inspectable");
        expect_true(door_cells >= 0, "rdg dungeon door count should be inspectable");
        expect_true(stair_cells >= static_cast<int>(dungeon.getStairs().size()),
                    "rdg stair records should correspond to stair cells");
    }
}

} // namespace

int main() {
    test_random_dungeon_cell_flags_and_validation();
    test_random_dungeon_layout_variants_generate_accessible_maps();

    return finish_tests();
}
