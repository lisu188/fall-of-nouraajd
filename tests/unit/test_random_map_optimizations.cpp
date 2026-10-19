/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CGame.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CRuntimeBridge.h"
#include "core/CSerialization.h"
#include "handler/CObjectHandler.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "veventloop.h"

#include <pybind11/embed.h>
#include <rdg.h>

#include <algorithm>
#include <array>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

struct CRandomMapGeneratorTestAccess {
    static void generateTiles(std::shared_ptr<CMap> &map, const rdg::Dungeon &dungeon) {
        CRandomMapGenerator::generateTiles(map, dungeon);
    }
};

namespace {

class TileInstallationProbe : public CGameObject {
    V_META(TileInstallationProbe, CGameObject, V_METHOD(TileInstallationProbe, onPropertyChanged, void, std::string),
           V_METHOD(TileInstallationProbe, onTileChanged, void, Coords))

  public:
    void onPropertyChanged(std::string name) {
        tileChanges += name == "tiles";
        revisionChanges += name == "navigationRevision";
    }
    void onTileChanged(Coords) { ++cellSignals; }
    std::size_t tileChanges = 0;
    std::size_t revisionChanges = 0;
    std::size_t cellSignals = 0;
};

std::shared_ptr<CTile> positionedTile(Coords coords, bool walkable = true, int cost = 3) {
    auto tile = std::make_shared<CTile>();
    tile->setPosx(coords.x);
    tile->setPosy(coords.y);
    tile->setPosz(coords.z);
    tile->setCanStep(walkable);
    tile->setMovementCost(cost);
    return tile;
}

void testFreshTileInstallationNormalizesAndKeepsFirst() {
    auto map = std::make_shared<CMap>();
    map->setXBounds({{0, 4}, {1, 2}});
    map->setYBounds({{0, 3}, {1, 2}});
    map->setWrapX({{0, 1}});
    map->setWrapY({{0, 1}});
    auto probe = std::make_shared<TileInstallationProbe>();
    map->connect("propertyChanged", probe, "onPropertyChanged");
    map->connect("tileChanged", probe, "onTileChanged");
    auto service = map->getNavigationService();
    auto previous_snapshot = service->snapshot(map);
    const auto revision = map->getNavigationRevision();
    const auto epoch = map->getRoutingEpoch();
    const std::array<std::shared_ptr<CTile>, 2> empty_tiles{nullptr, nullptr};
    expect_true(map->installTiles(empty_tiles) == 0 && map->installTiles({}) == 0 &&
                    map->getNavigationRevision() == revision && map->getRoutingEpoch() == epoch,
                "empty and null-only tile batches leave the map and navigation counters unchanged");

    auto first = positionedTile(Coords(-1, 4, 0));
    auto duplicate = positionedTile(Coords(4, 0, 0), false);
    auto upper = positionedTile(Coords(1, 1, 1), false, 7);
    const std::array tiles{first, std::shared_ptr<CTile>{}, duplicate, upper, first};
    expect_true(map->installTiles(tiles) == 2 && map->getTiles().size() == 2,
                "tile installation skips nulls and retains the first tile at duplicate normalized coordinates");
    expect_true(first->getCoords() == Coords(4, 0, 0) && map->getTile(-1, 4, 0) == first &&
                    upper->getCoords() == Coords(1, 1, 1) && map->getTile(1, 1, 1) == upper,
                "installed coordinates and lookup indexes share wrapping and preserve separate levels");
    expect_true(first->getMap() == map && upper->getMap() == map && !duplicate->getMap() &&
                    duplicate->getCoords() == Coords(4, 0, 0),
                "only accepted tiles acquire ownership; rejected duplicates remain untouched");
    expect_true(map->getNavigationRevision() == revision + 1 && map->getRoutingEpoch() == epoch + 1 &&
                    !previous_snapshot->isCurrent(),
                "one tile batch advances structural and routing revisions once and invalidates prior snapshots");
    auto snapshot = service->snapshot(map);
    expect_true(snapshot->isFinite() && snapshot->canStep(Coords(4, 0, 0)) && !snapshot->canStep(Coords(1, 1, 1)) &&
                    snapshot->movementCost(Coords(1, 1, 1)) == 7,
                "installed terrain contributes the same bounded domain and navigation values as individual tiles");
    vstd::event_loop<>::instance()->runUntilIdle();
    expect_true(probe->tileChanges == 1 && probe->revisionChanges == 1 && probe->cellSignals == 0,
                "fresh installation emits one tiles notification and no per-cell refresh work");

    const auto before_mutation = map->getRoutingEpoch();
    first->setMovementCost(9);
    expect_true(map->getRoutingEpoch() == before_mutation + 1 && !snapshot->isCurrent() &&
                    service->snapshot(map)->movementCost(Coords(4, 0, 0)) == 9,
                "installed ownership preserves later tile cost invalidation");
    first->setCanStep(false);
    expect_true(map->getRoutingEpoch() == before_mutation + 2 && !map->canStep(Coords(4, 0, 0)),
                "installed ownership preserves later walkability invalidation");
    first->setPosx(3);
    expect_true(map->getTile(3, 0, 0) == first && !map->contains(4, 0, 0),
                "installed tiles retain ordinary coordinate setters and map indexing");
    map->removeTile(3, 0, 0);
    expect_true(!first->getMap(), "removing an installed tile clears its map ownership");
    vstd::event_loop<>::instance()->runUntilIdle();
}

void testTileInstallationRejectsNonemptyMapsBeforeMutation() {
    auto map = std::make_shared<CMap>();
    auto existing = positionedTile(Coords(2, 3, 0));
    map->addTile(existing, 2, 3, 0);
    const auto revision = map->getNavigationRevision();
    const auto epoch = map->getRoutingEpoch();
    auto incoming = positionedTile(Coords(-3, -4, 0));
    for (const auto &batch : {std::vector<std::shared_ptr<CTile>>{incoming}, std::vector<std::shared_ptr<CTile>>{}}) {
        bool rejected = false;
        try {
            map->installTiles(batch);
        } catch (const std::logic_error &) {
            rejected = true;
        }
        expect_true(rejected && map->getTiles().size() == 1 && map->getTile(2, 3, 0) == existing &&
                        map->getNavigationRevision() == revision && map->getRoutingEpoch() == epoch &&
                        incoming->getCoords() == Coords(-3, -4, 0) && !incoming->getMap(),
                    "nonempty-map rejection preserves existing tiles, incoming ownership and navigation state");
    }

    auto outside_map = std::make_shared<CMap>();
    outside_map->setXBounds({{0, 2}});
    outside_map->setYBounds({{0, 2}});
    auto outside = positionedTile(Coords(4, 0, 0));
    outside_map->installTiles(std::array{outside});
    expect_true(!outside_map->getNavigationService()->snapshot(outside_map)->isFinite(),
                "bulk installation includes outlying tile extents in navigation domain safety checks");
}

class RestoreDungeonRng {
  public:
    ~RestoreDungeonRng() { vstd::rng() = previous; }

  private:
    std::mt19937_64 previous = vstd::rng();
};

void testRandomDungeonTilesMatchIndividualCreation() {
    RestoreDungeonRng restore_rng;
    auto game = std::make_shared<CGame>();
    auto handler = game->getObjectHandler();
    handler->registerNativeType("CTile", [] { return std::make_shared<CTile>(); });
    for (const auto &[id, walkable] : {std::pair{"GroundTile", true}, std::pair{"MountainTile", false}}) {
        handler->registerConfig(
            id, std::make_shared<const json>(json{
                    {"class", "CTile"},
                    {"properties",
                     {{"canStep", walkable}, {"movementCost", walkable ? 3 : 7}, {"tileType", id}, {"label", id}}}}));
    }
    auto reference = std::make_shared<CMap>();
    auto actual = std::make_shared<CMap>();
    reference->setGame(game);
    actual->setGame(game);
    game->setMap(reference);
    rdg::Options options;
    options.n_rows = 17;
    options.n_cols = 19;
    std::mt19937 dungeon_rng{123};
    const auto dungeon = rdg::create_dungeon(options, dungeon_rng);
    const auto before_rng = vstd::rng();
    {
        CSerialization::NameFixtureScopeForTests names(901);
        for (int row = 0; row < dungeon.rowCount(); ++row) {
            for (int col = 0; col < dungeon.colCount(); ++col) {
                reference->addTile(
                    game->createObject<CTile>(dungeon.cellAt(row, col).isOpenspace() ? "GroundTile" : "MountainTile"),
                    row, col, 0);
            }
        }
    }
    const auto expected_rng = vstd::rng();
    vstd::rng() = before_rng;
    {
        CSerialization::NameFixtureScopeForTests names(901);
        CRandomMapGeneratorTestAccess::generateTiles(actual, dungeon);
    }
    expect_true(vstd::rng() == expected_rng, "batch terrain creation preserves the complete gameplay RNG state");
    expect_true(actual->getNavigationRevision() == 1 && reference->getNavigationRevision() == 17 * 19 &&
                    actual->getTiles().size() == 17 * 19,
                "real dungeon terrain construction installs all cells with one structural invalidation");
    for (int row = 0; row < dungeon.rowCount(); ++row) {
        for (int col = 0; col < dungeon.colCount(); ++col) {
            const auto expected = reference->getTile(row, col, 0);
            const auto tile = actual->getTile(row, col, 0);
            expect_true(
                tile && tile != expected && tile->getName() == expected->getName() &&
                    tile->getCoords() == expected->getCoords() && tile->canStep() == expected->canStep() &&
                    tile->getMovementCost() == expected->getMovementCost() &&
                    tile->getTypeId() == expected->getTypeId() && tile->getTileType() == expected->getTileType() &&
                    tile->getLabel() == expected->getLabel() && tile->getGame() == game && tile->getMap() == actual,
                "batch terrain preserves row-major names, types, values, coordinates and individual ownership");
        }
    }
    auto tile = actual->getTile(1, 1, 0);
    const auto actual_epoch = actual->getRoutingEpoch();
    const auto reference_epoch = reference->getRoutingEpoch();
    tile->setMovementCost(tile->getMovementCost() + 1);
    expect_true(actual->getRoutingEpoch() == actual_epoch + 1 && reference->getRoutingEpoch() == reference_epoch,
                "generated tiles invalidate their owning map even while another map is active in the game");
}

void testTileInstallationWorkBudget() {
    constexpr std::size_t tile_count = 1024;
    auto map = std::make_shared<CMap>();
    auto reference = std::make_shared<CMap>();
    std::vector<std::shared_ptr<CTile>> tiles;
    tiles.reserve(tile_count);
    for (std::size_t index = 0; index < tile_count; ++index) {
        auto coords = Coords(static_cast<int>(index % 32), static_cast<int>(index / 32), 0);
        tiles.push_back(positionedTile(coords));
        reference->addTile(positionedTile(coords), coords.x, coords.y, coords.z);
    }
    const auto revision = map->getNavigationRevision();
    const auto epoch = map->getRoutingEpoch();
    const auto installed = map->installTiles(tiles);
    const auto revision_delta = map->getNavigationRevision() - revision;
    const auto epoch_delta = map->getRoutingEpoch() - epoch;
    expect_true(installed == tile_count && revision_delta == 1 && epoch_delta == 1 &&
                    reference->getNavigationRevision() == tile_count && reference->getRoutingEpoch() == tile_count + 1,
                "a fixed terrain batch performs one invalidation instead of one invalidation per tile");
    expect_true(sizeof(rdg::Cell) == 8, "dungeon cells retain the compact eight-byte storage budget");
    rdg::Options options;
    options.n_rows = 101;
    options.n_cols = 101;
    options.room_max = 1;
    options.room_min = 1;
    std::mt19937 rng{123};
    auto dungeon = rdg::create_dungeon(options, rng);
    expect_true(dungeon.getRooms().capacity() == 999, "room reservation remains within the generator's room limit");
    std::cout << "random map installation guard: tiles=" << installed << " revision-delta=" << revision_delta
              << " routing-delta=" << epoch_delta << " individual-delta=" << reference->getNavigationRevision()
              << " batch-budget=1 cell-bytes=" << sizeof(rdg::Cell)
              << " room-capacity=" << dungeon.getRooms().capacity() << " room-budget=999\n";
}

} // namespace

void run_random_map_optimization_performance_tests() { testTileInstallationWorkBudget(); }

#ifdef GAME_RANDOM_MAP_OPTIMIZATION_MAIN
void run_tile_recipe_tests();
void run_generated_name_tests();
void run_generated_name_performance_tests();

int main() {
    pybind11::scoped_interpreter guard{};
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testFreshTileInstallationNormalizesAndKeepsFirst();
    testTileInstallationRejectsNonemptyMapsBeforeMutation();
    testRandomDungeonTilesMatchIndividualCreation();
    run_random_map_optimization_performance_tests();
    run_tile_recipe_tests();
    run_generated_name_tests();
    run_generated_name_performance_tests();
    return finish_tests();
}
#endif
