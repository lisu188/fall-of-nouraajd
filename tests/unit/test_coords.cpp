/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "core/CUtil.h"

#include <iostream>

namespace {
int failures = 0;

void expect_true(bool condition, const char *message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << "\n";
        ++failures;
    }
}

void test_happy_path_add_and_distance() {
    Coords sum = Coords(2, 3, 0) + Coords(1, -1, 0);
    expect_true(sum == Coords(3, 2, 0), "Coords::operator+ should add each component");
    expect_true(Coords(0, 0, 0).getDist(Coords(3, 4, 0)) == 5.0,
                "Coords::getDist should compute Euclidean distance in XY plane");
}

void test_edge_case_adjacent_or_same() {
    Coords origin(7, 7, 0);
    expect_true(origin.adjacentOrSame(origin), "adjacentOrSame should accept identical coordinates");
    expect_true(origin.adjacent(Coords(8, 7, 0)), "adjacent should allow cardinal neighbors");
}

void test_direction_mapping() {
    expect_true(CUtil::getDirection(ZERO) == Coords::Direction::ZERO, "getDirection should detect ZERO direction");
    expect_true(CUtil::getDirection(EAST) == Coords::Direction::EAST, "getDirection should detect EAST direction");
    expect_true(CUtil::getDirection(WEST) == Coords::Direction::WEST, "getDirection should detect WEST direction");
    expect_true(CUtil::getDirection(NORTH) == Coords::Direction::NORTH, "getDirection should detect NORTH direction");
    expect_true(CUtil::getDirection(SOUTH) == Coords::Direction::SOUTH, "getDirection should detect SOUTH direction");
    expect_true(CUtil::getDirection(UP) == Coords::Direction::UP, "getDirection should detect UP direction");
    expect_true(CUtil::getDirection(DOWN) == Coords::Direction::DOWN, "getDirection should detect DOWN direction");
    expect_true(CUtil::getDirection(Coords(2, 1, 0)) == Coords::Direction::UNDEFINED,
                "getDirection should return UNDEFINED for unsupported vectors");
}

void test_rect_bounds_inclusion() {
    auto rect = CUtil::rect(10, 20, 30, 40);
    expect_true(CUtil::isIn(rect, 10, 20), "isIn should include lower bounds");
    expect_true(CUtil::isIn(rect, 40, 60), "isIn should include upper bounds");
    expect_true(!CUtil::isIn(rect, 9, 20), "isIn should reject x outside left bound");
    expect_true(!CUtil::isIn(rect, 41, 20), "isIn should reject x outside right bound");
    expect_true(!CUtil::isIn(rect, 10, 61), "isIn should reject y outside bottom bound");
}

void test_boundary_invalid_key_parsing() {
    expect_true(CUtil::parseKey(SDLK_9) == 9, "parseKey should parse a supported digit key");
    expect_true(CUtil::parseKey(SDLK_F1) == -1, "parseKey should reject unsupported keys");
}
} // namespace

int main() {
    test_happy_path_add_and_distance();
    test_edge_case_adjacent_or_same();
    test_boundary_invalid_key_parsing();
    test_direction_mapping();
    test_rect_bounds_inclusion();

    if (failures == 0) {
        std::cout << "All unit tests passed.\n";
        return 0;
    }

    std::cerr << failures << " unit test(s) failed.\n";
    return 1;
}
