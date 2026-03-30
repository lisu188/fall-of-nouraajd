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
#include "core/CPathFinder.h"

#include <algorithm>
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
    Coords diff = Coords(4, 2, 1) - Coords(1, 5, -2);
    expect_true(sum == Coords(3, 2, 0), "Coords::operator+ should add each component");
    expect_true(diff == Coords(3, -3, 3), "Coords::operator- should subtract each component");
    expect_true((*Coords(6, 7, 8)) == Coords(6, 7, 8), "Coords::operator* should return same coordinates");
    expect_true(Coords(0, 0, 0).getDist(Coords(3, 4, 0)) == 5.0,
                "Coords::getDist should compute Euclidean distance in XY plane");
}

void test_edge_case_adjacent_or_same() {
    Coords origin(7, 7, 0);
    expect_true(origin.adjacentOrSame(origin), "adjacentOrSame should accept identical coordinates");
    expect_true(origin.same(origin), "same should return true for same coordinates");
    expect_true(origin.adjacent(Coords(8, 7, 0)), "adjacent should allow cardinal neighbors");
    expect_true(!origin.adjacent(Coords(8, 8, 0)), "adjacent should reject diagonal neighbors");
    expect_true(!origin.adjacent(Coords(7, 7, 1)), "adjacent should ignore Z-only movement");
}

void test_comparison_and_ordering() {
    expect_true(Coords(1, 2, 3) < Coords(1, 3, 0), "operator< should compare y when x is equal");
    expect_true(Coords(1, 2, 3) < Coords(1, 2, 4), "operator< should compare z when x and y are equal");
    expect_true(!(Coords(2, 0, 0) < Coords(1, 99, 99)), "operator< should reject larger x values");
    expect_true(Coords(2, 0, 0) > Coords(1, 99, 99), "operator> should invert operator< for non-equal values");
    expect_true(Coords(1, 2, 3) != Coords(1, 2, 4), "operator!= should detect different coordinates");
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
    auto bounds = CUtil::bounds(rect);
    auto centered = CUtil::boxInBox(CUtil::rect(0, 0, 10, 10), CUtil::rect(0, 0, 4, 6));
    auto centered_at = CUtil::centeredRect(50, 40, 10, 6);

    expect_true(bounds->x == 10 && bounds->y == 40 && bounds->w == 20 && bounds->h == 60,
                "bounds should return left, right, top and bottom values");
    expect_true(centered->x == 3 && centered->y == 2 && centered->w == 4 && centered->h == 6,
                "boxInBox should center the inner box");
    expect_true(centered_at->x == 45 && centered_at->y == 37 && centered_at->w == 10 && centered_at->h == 6,
                "centeredRect should position a rectangle around its center point");

    expect_true(CUtil::isIn(rect, 10, 20), "isIn should include lower bounds");
    expect_true(CUtil::isIn(rect, 40, 60), "isIn should include upper bounds");
    expect_true(!CUtil::isIn(rect, 9, 20), "isIn should reject x outside left bound");
    expect_true(!CUtil::isIn(rect, 41, 20), "isIn should reject x outside right bound");
    expect_true(!CUtil::isIn(rect, 10, 61), "isIn should reject y outside bottom bound");
}

void test_boundary_invalid_key_parsing() {
    expect_true(CUtil::parseKey(SDLK_0) == 0, "parseKey should parse zero");
    expect_true(CUtil::parseKey(SDLK_1) == 1, "parseKey should parse one");
    expect_true(CUtil::parseKey(SDLK_2) == 2, "parseKey should parse two");
    expect_true(CUtil::parseKey(SDLK_3) == 3, "parseKey should parse three");
    expect_true(CUtil::parseKey(SDLK_4) == 4, "parseKey should parse four");
    expect_true(CUtil::parseKey(SDLK_5) == 5, "parseKey should parse five");
    expect_true(CUtil::parseKey(SDLK_6) == 6, "parseKey should parse six");
    expect_true(CUtil::parseKey(SDLK_7) == 7, "parseKey should parse seven");
    expect_true(CUtil::parseKey(SDLK_8) == 8, "parseKey should parse eight");
    expect_true(CUtil::parseKey(SDLK_9) == 9, "parseKey should parse a supported digit key");
    expect_true(CUtil::parseKey(SDLK_F1) == -1, "parseKey should reject unsupported keys");
}

void test_near_coords_helpers() {
    auto neighbors = near_coords(Coords(4, 5, 0));
    expect_true(neighbors.size() == 4, "near_coords should return four cardinal neighbors");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(5, 5, 0)) != neighbors.end(),
                "near_coords should include east neighbor");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(3, 5, 0)) != neighbors.end(),
                "near_coords should include west neighbor");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(4, 6, 0)) != neighbors.end(),
                "near_coords should include south neighbor");
    expect_true(std::find(neighbors.begin(), neighbors.end(), Coords(4, 4, 0)) != neighbors.end(),
                "near_coords should include north neighbor");

    auto neighbors_with_self = near_coords_with(Coords(4, 5, 0));
    expect_true(neighbors_with_self.size() == 5, "near_coords_with should include origin and four neighbors");
    expect_true(std::find(neighbors_with_self.begin(), neighbors_with_self.end(), Coords(4, 5, 0)) !=
                    neighbors_with_self.end(),
                "near_coords_with should include origin");
}

void test_pathfinder_find_path_without_obstacles() {
    auto can_step = [](const Coords &coords) {
        return coords.x >= 0 && coords.x <= 2 && coords.y >= 0 && coords.y <= 2 && coords.z == 0;
    };
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(path.size() == 2, "findPath should include each next step until goal");
    expect_true(path.front() == Coords(1, 0, 0), "findPath should return first move toward goal");
    expect_true(path.back() == Coords(2, 0, 0), "findPath should end on goal");

    auto next_step = CPathFinder::findNextStep(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(next_step->get() == Coords(1, 0, 0), "findNextStep should return the first optimal neighbor");
}

void test_pathfinder_waypoint_and_blocked_goal() {
    auto can_step = [](const Coords &coords) { return coords == Coords(0, 0, 0); };
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(2, 0, 0), can_step, no_waypoint);
    expect_true(path.size() == 1, "findPath should return only start when goal is unreachable");
    expect_true(path.front() == Coords(0, 0, 0), "findPath should remain on start if no route exists");
}

void test_pathfinder_waypoint_override() {
    auto can_step = [](const Coords &coords) {
        return coords.y == 0 && coords.x >= 0 && coords.x <= 2 && coords.z == 0;
    };
    auto forced_waypoint = [](const Coords &coords) {
        if (coords == Coords(0, 0, 0)) {
            return std::pair<bool, Coords>(true, Coords(2, 0, 0));
        }
        return std::pair<bool, Coords>(false, ZERO);
    };
    auto next_step = CPathFinder::findNextStep(Coords(0, 0, 0), Coords(2, 0, 0), can_step, forced_waypoint);
    expect_true(next_step->get() == Coords(2, 0, 0), "findNextStep should allow waypoint override when available");
}

int wrap_axis(int value, int bound) {
    int size = bound + 1;
    int normalized = value % size;
    if (normalized < 0) {
        normalized += size;
    }
    return normalized;
}

Coords normalize_toroidal(Coords coords, int x_bound, int y_bound) {
    return Coords(wrap_axis(coords.x, x_bound), wrap_axis(coords.y, y_bound), coords.z);
}

std::vector<Coords> toroidal_neighbors(const Coords &coords, int x_bound, int y_bound) {
    std::set<Coords> unique;
    for (const auto &neighbor : near_coords(coords)) {
        unique.insert(normalize_toroidal(neighbor, x_bound, y_bound));
    }
    return {unique.begin(), unique.end()};
}

double toroidal_distance(const Coords &a, const Coords &b, int x_bound, int y_bound) {
    int width = x_bound + 1;
    int height = y_bound + 1;
    int dx = std::abs(a.x - b.x);
    int dy = std::abs(a.y - b.y);
    dx = std::min(dx, width - dx);
    dy = std::min(dy, height - dy);
    return std::sqrt(dx * dx + dy * dy);
}

void test_toroidal_pathfinder_prefers_wrapped_route() {
    constexpr int x_bound = 25;
    constexpr int y_bound = 25;
    auto can_step = [=](const Coords &coords) {
        Coords normalized = normalize_toroidal(coords, x_bound, y_bound);
        return normalized.z == 0 && normalized.y == 0;
    };
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };
    auto neighbors = [=](const Coords &coords) { return toroidal_neighbors(coords, x_bound, y_bound); };
    auto distance = [=](const Coords &a, const Coords &b) {
        return toroidal_distance(normalize_toroidal(a, x_bound, y_bound), normalize_toroidal(b, x_bound, y_bound),
                                 x_bound, y_bound);
    };

    auto path = CPathFinder::findPath(Coords(0, 0, 0), Coords(25, 0, 0), can_step, no_waypoint, neighbors, distance);
    expect_true(path.size() == 1, "Toroidal path should use the wrapped one-step route");
    expect_true(path.front() == Coords(25, 0, 0), "Toroidal path should wrap west-to-east in one move");

    auto next_step =
        CPathFinder::findNextStep(Coords(0, 0, 0), Coords(25, 0, 0), can_step, no_waypoint, neighbors, distance);
    expect_true(next_step->get() == Coords(25, 0, 0), "Toroidal next step should choose the wrapped edge tile");
}

void test_toroidal_pathfinder_wraps_on_both_axes() {
    constexpr int x_bound = 25;
    constexpr int y_bound = 25;
    auto can_step = [=](const Coords &coords) {
        Coords normalized = normalize_toroidal(coords, x_bound, y_bound);
        return normalized.z == 0;
    };
    auto no_waypoint = [](const Coords &) { return std::pair<bool, Coords>(false, ZERO); };
    auto neighbors = [=](const Coords &coords) { return toroidal_neighbors(coords, x_bound, y_bound); };
    auto distance = [=](const Coords &a, const Coords &b) {
        return toroidal_distance(normalize_toroidal(a, x_bound, y_bound), normalize_toroidal(b, x_bound, y_bound),
                                 x_bound, y_bound);
    };

    auto path =
        CPathFinder::findPath(Coords(0, 0, 0), Coords(25, 25, 0), can_step, no_waypoint, neighbors, distance);
    expect_true(path.size() == 2, "Toroidal path should wrap independently on both axes");
    expect_true(path.front() == Coords(0, 25, 0) || path.front() == Coords(25, 0, 0),
                "Toroidal path should take a wrapped step on one axis first");
    expect_true(path.back() == Coords(25, 25, 0), "Toroidal path should end at the wrapped goal coordinate");
}
} // namespace

int main() {
    test_happy_path_add_and_distance();
    test_edge_case_adjacent_or_same();
    test_comparison_and_ordering();
    test_boundary_invalid_key_parsing();
    test_near_coords_helpers();
    test_pathfinder_find_path_without_obstacles();
    test_pathfinder_waypoint_and_blocked_goal();
    test_pathfinder_waypoint_override();
    test_toroidal_pathfinder_prefers_wrapped_route();
    test_toroidal_pathfinder_wraps_on_both_axes();
    test_direction_mapping();
    test_rect_bounds_inclusion();

    if (failures == 0) {
        std::cout << "All unit tests passed.\n";
        return 0;
    }

    std::cerr << failures << " unit test(s) failed.\n";
    return 1;
}
