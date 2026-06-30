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
#include "CMinimapGraphicsObject.h"
#include "core/CMap.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CSdlResources.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "object/CTile.h"

#include <algorithm>
#include <cstddef>
#include <cmath>
#include <functional>
#include <limits>
#include <map>
#include <optional>
#include <string>

namespace {
constexpr SDL_Color MINIMAP_BACKGROUND{7, 9, 10, 255};
constexpr SDL_Color MINIMAP_DEFAULT{39, 44, 41, 255};
constexpr SDL_Color MINIMAP_UNKNOWN{62, 63, 58, 255};
constexpr SDL_Color MINIMAP_GRASS{45, 111, 55, 255};
constexpr SDL_Color MINIMAP_GROUND{86, 72, 48, 255};
constexpr SDL_Color MINIMAP_ROAD{118, 103, 72, 255};
constexpr SDL_Color MINIMAP_WATER{29, 86, 148, 255};
constexpr SDL_Color MINIMAP_MOUNTAIN{83, 86, 91, 255};
constexpr SDL_Color MINIMAP_LAVA{190, 62, 38, 255};
constexpr SDL_Color MINIMAP_BEACH{176, 163, 108, 255};
constexpr SDL_Color MINIMAP_DESERT{177, 137, 64, 255};
constexpr SDL_Color MINIMAP_SNOW{188, 204, 209, 255};
constexpr SDL_Color MINIMAP_SWAMP{45, 84, 65, 255};
constexpr SDL_Color MINIMAP_WASTELAND{96, 79, 67, 255};
constexpr SDL_Color MINIMAP_PLAYER{255, 255, 0, 255};
constexpr SDL_Color MINIMAP_CREATURE{255, 0, 0, 255};
constexpr SDL_Color MINIMAP_OBJECT{255, 170, 0, 255};
constexpr SDL_Color MINIMAP_VIEWPORT{255, 255, 255, 255};
constexpr long long MAX_MINIMAP_DEFAULT_CELLS = 100'000;
// Maximum width/height (in map cells) the minimap will honour for a single level. Map metadata
// (xBound/yBound) and sparse object/tile coordinates are attacker-controllable and may be extreme or
// overflow-prone, so any level extent beyond this is rejected (fail closed -> bounded placeholder)
// before it can drive iteration, scaling, or pixel/texture dimension math. Matches the established
// MAX_TMX_LAYER_CELLS guard convention in CLoader.cpp.
constexpr long long MAX_MINIMAP_LEVEL_EXTENT = 100'000;

struct LevelBounds {
    int minX = 0;
    int minY = 0;
    int maxX = 0;
    int maxY = 0;
};

struct MinimapScale {
    std::shared_ptr<SDL_Rect> rect;
    LevelBounds bounds;
    double scaleX = 1.0;
    double scaleY = 1.0;
};

bool z_matches(Coords coords, int z) { return coords.z == z; }

void hash_combine(std::size_t &seed, std::size_t value) { seed ^= value + 0x9e3779b9 + (seed << 6) + (seed >> 2); }

SDL_Color tile_color(const std::string &tileType) {
    if (tileType == "GrassTile" || tileType == "grass") {
        return MINIMAP_GRASS;
    }
    if (tileType == "GroundTile" || tileType == "ground") {
        return MINIMAP_GROUND;
    }
    if (tileType == "RoadTile" || tileType == "road") {
        return MINIMAP_ROAD;
    }
    if (tileType == "WaterTile" || tileType == "water") {
        return MINIMAP_WATER;
    }
    if (tileType == "MountainTile" || tileType == "mountain") {
        return MINIMAP_MOUNTAIN;
    }
    if (tileType == "LavaTile" || tileType == "lava") {
        return MINIMAP_LAVA;
    }
    if (tileType == "BeachTile" || tileType == "beach") {
        return MINIMAP_BEACH;
    }
    if (tileType == "DesertTile" || tileType == "desert") {
        return MINIMAP_DESERT;
    }
    if (tileType == "SnowTile" || tileType == "snow") {
        return MINIMAP_SNOW;
    }
    if (tileType == "SwampTile" || tileType == "swamp") {
        return MINIMAP_SWAMP;
    }
    if (tileType == "WastelandTile" || tileType == "wasteland") {
        return MINIMAP_WASTELAND;
    }
    if (tileType.empty()) {
        return MINIMAP_DEFAULT;
    }
    return MINIMAP_UNKNOWN;
}

std::string tile_type(const std::shared_ptr<CTile> &tile) {
    const auto &tileType = tile->getTileType();
    return tileType.empty() ? tile->getTypeId() : tileType;
}

void include_coords(LevelBounds &bounds, bool &hasBounds, Coords coords) {
    if (!hasBounds) {
        bounds.minX = coords.x;
        bounds.maxX = coords.x;
        bounds.minY = coords.y;
        bounds.maxY = coords.y;
        hasBounds = true;
        return;
    }
    bounds.minX = std::min(bounds.minX, coords.x);
    bounds.maxX = std::max(bounds.maxX, coords.x);
    bounds.minY = std::min(bounds.minY, coords.y);
    bounds.maxY = std::max(bounds.maxY, coords.y);
}

// Rejects level extents whose width/height overflow or exceed MAX_MINIMAP_LEVEL_EXTENT. All arithmetic
// is performed in long long so attacker-extreme int bounds (e.g. INT_MAX maxX with a negative minX)
// cannot trigger signed-overflow UB before the bound check runs.
bool bounds_within_limits(const LevelBounds &bounds) {
    if (bounds.maxX < bounds.minX || bounds.maxY < bounds.minY) {
        return false;
    }
    const long long width = static_cast<long long>(bounds.maxX) - bounds.minX + 1;
    const long long height = static_cast<long long>(bounds.maxY) - bounds.minY + 1;
    return width > 0 && height > 0 && width <= MAX_MINIMAP_LEVEL_EXTENT && height <= MAX_MINIMAP_LEVEL_EXTENT;
}

std::optional<LevelBounds> get_level_bounds(const std::shared_ptr<CMap> &map, int z) {
    const auto xBounds = map->getXBounds();
    const auto yBounds = map->getYBounds();
    if (vstd::ctn(xBounds, z) && vstd::ctn(yBounds, z)) {
        const LevelBounds metadataBounds{0, 0, xBounds.at(z), yBounds.at(z)};
        if (!bounds_within_limits(metadataBounds)) {
            return std::nullopt;
        }
        return metadataBounds;
    }

    LevelBounds bounds;
    bool hasBounds = false;
    if (auto player = map->getPlayer()) {
        include_coords(bounds, hasBounds, player->getCoords());
    }
    for (const auto &tile : map->getTiles()) {
        if (tile && z_matches(tile->getCoords(), z)) {
            include_coords(bounds, hasBounds, tile->getCoords());
        }
    }
    for (const auto &object : map->getObjects()) {
        if (object && z_matches(object->getCoords(), z)) {
            include_coords(bounds, hasBounds, object->getCoords());
        }
    }
    if (!hasBounds) {
        return std::nullopt;
    }
    // Sparse player/object/tile coordinates may span an enormous (or overflow-prone) range; fail closed
    // rather than iterating/scaling over that empty space.
    if (!bounds_within_limits(bounds)) {
        return std::nullopt;
    }
    return bounds;
}

MinimapScale make_scale(std::shared_ptr<SDL_Rect> rect, LevelBounds bounds) {
    // Compute extents in long long to avoid signed-overflow UB, then clamp to MAX_MINIMAP_LEVEL_EXTENT.
    // get_level_bounds already rejects out-of-range extents, so this is defence in depth for direct callers.
    const long long rawWidth = static_cast<long long>(bounds.maxX) - bounds.minX + 1;
    const long long rawHeight = static_cast<long long>(bounds.maxY) - bounds.minY + 1;
    const int levelWidth = static_cast<int>(std::clamp<long long>(rawWidth, 1, MAX_MINIMAP_LEVEL_EXTENT));
    const int levelHeight = static_cast<int>(std::clamp<long long>(rawHeight, 1, MAX_MINIMAP_LEVEL_EXTENT));
    const double scale =
        std::min(rect->w / static_cast<double>(levelWidth), rect->h / static_cast<double>(levelHeight));
    const int drawW = std::max(1, static_cast<int>(std::floor(levelWidth * scale)));
    const int drawH = std::max(1, static_cast<int>(std::floor(levelHeight * scale)));
    auto drawRect = CUtil::rect(rect->x + (rect->w - drawW) / 2, rect->y + (rect->h - drawH) / 2, drawW, drawH);
    return MinimapScale{drawRect, bounds, scale, scale};
}

int cell_left(const MinimapScale &scale, int x) {
    return scale.rect->x + static_cast<int>(std::floor((x - scale.bounds.minX) * scale.scaleX));
}

int cell_top(const MinimapScale &scale, int y) {
    return scale.rect->y + static_cast<int>(std::floor((y - scale.bounds.minY) * scale.scaleY));
}

int cell_right(const MinimapScale &scale, int x) {
    return scale.rect->x + static_cast<int>(std::ceil((x - scale.bounds.minX + 1) * scale.scaleX));
}

int cell_bottom(const MinimapScale &scale, int y) {
    return scale.rect->y + static_cast<int>(std::ceil((y - scale.bounds.minY + 1) * scale.scaleY));
}

std::shared_ptr<SDL_Rect> cell_rect(const MinimapScale &scale, Coords coords) {
    const int x = std::clamp(cell_left(scale, coords.x), scale.rect->x, scale.rect->x + scale.rect->w - 1);
    const int y = std::clamp(cell_top(scale, coords.y), scale.rect->y, scale.rect->y + scale.rect->h - 1);
    const int right = std::clamp(cell_right(scale, coords.x), x + 1, scale.rect->x + scale.rect->w);
    const int bottom = std::clamp(cell_bottom(scale, coords.y), y + 1, scale.rect->y + scale.rect->h);
    return CUtil::rect(x, y, right - x, bottom - y);
}

void fill_rect(SDL_Renderer *renderer, const std::shared_ptr<SDL_Rect> &rect, SDL_Color color) {
    CUtil::setRenderDrawColor(renderer, color);
    SDL_SAFE(SDL_RenderFillRect(renderer, rect.get()));
}

void fill_rect(SDL_Surface *surface, const std::shared_ptr<SDL_Rect> &rect, SDL_Color color) {
    const auto mappedColor = SDL_MapRGBA(surface->format, color.r, color.g, color.b, color.a);
    SDL_SAFE(SDL_FillRect(surface, rect.get(), mappedColor));
}

template <typename T> void draw_cell(T *target, const MinimapScale &scale, Coords coords, SDL_Color color) {
    fill_rect(target, cell_rect(scale, coords), color);
}

template <typename T> void draw_default_terrain(T *target, const MinimapScale &scale, SDL_Color color) {
    const long long width = static_cast<long long>(scale.bounds.maxX) - scale.bounds.minX + 1;
    const long long height = static_cast<long long>(scale.bounds.maxY) - scale.bounds.minY + 1;
    if (width <= 0 || height <= 0 || width > MAX_MINIMAP_DEFAULT_CELLS / std::max(1LL, height)) {
        fill_rect(target, scale.rect, MINIMAP_BACKGROUND);
        return;
    }
    for (int y = scale.bounds.minY; y <= scale.bounds.maxY; ++y) {
        for (int x = scale.bounds.minX; x <= scale.bounds.maxX; ++x) {
            draw_cell(target, scale, Coords(x, y, 0), color);
        }
    }
}

std::string default_tile_type(const std::shared_ptr<CMap> &map, int z) {
    const auto defaultTiles = map->getDefaultTiles();
    if (vstd::ctn(defaultTiles, z)) {
        return defaultTiles.at(z);
    }
    return "";
}

SDL_Color default_tile_color(const std::shared_ptr<CMap> &map, int z) { return tile_color(default_tile_type(map, z)); }

template <typename T> void draw_terrain(T *target, const std::shared_ptr<CMap> &map, int z, const MinimapScale &scale) {
    draw_default_terrain(target, scale, default_tile_color(map, z));
    for (const auto &tile : map->getTiles()) {
        if (!tile || !z_matches(tile->getCoords(), z)) {
            continue;
        }
        draw_cell(target, scale, tile->getCoords(), tile_color(tile_type(tile)));
    }
}

std::size_t terrain_signature(const std::shared_ptr<CMap> &map, int z, const LevelBounds &bounds, int width,
                              int height) {
    std::size_t seed = 0;
    const std::hash<int> intHash;
    const std::hash<std::string> stringHash;
    hash_combine(seed, intHash(z));
    hash_combine(seed, intHash(bounds.minX));
    hash_combine(seed, intHash(bounds.minY));
    hash_combine(seed, intHash(bounds.maxX));
    hash_combine(seed, intHash(bounds.maxY));
    hash_combine(seed, intHash(width));
    hash_combine(seed, intHash(height));
    hash_combine(seed, stringHash(default_tile_type(map, z)));
    for (const auto &tile : map->getTiles()) {
        if (!tile || !z_matches(tile->getCoords(), z)) {
            continue;
        }
        const auto coords = tile->getCoords();
        hash_combine(seed, intHash(coords.x));
        hash_combine(seed, intHash(coords.y));
        hash_combine(seed, intHash(coords.z));
        hash_combine(seed, stringHash(tile_type(tile)));
    }
    return seed;
}

fn::sdl::TexturePtr build_terrain_texture(SDL_Renderer *renderer, const std::shared_ptr<CMap> &map, int z,
                                          const std::shared_ptr<SDL_Rect> &rect, LevelBounds bounds) {
    if (rect->w <= 0 || rect->h <= 0) {
        return nullptr;
    }
    fn::sdl::SurfacePtr surface(
        SDL_SAFE(SDL_CreateRGBSurfaceWithFormat(0, rect->w, rect->h, 32, SDL_PIXELFORMAT_RGBA32)));
    if (!surface) {
        return nullptr;
    }

    auto localRect = CUtil::rect(0, 0, rect->w, rect->h);
    fill_rect(surface.get(), localRect, MINIMAP_BACKGROUND);
    draw_terrain(surface.get(), map, z, make_scale(localRect, bounds));

    fn::sdl::TexturePtr texture(SDL_SAFE(SDL_CreateTextureFromSurface(renderer, surface.get())));
    if (texture) {
        SDL_SAFE(SDL_SetTextureBlendMode(texture.get(), SDL_BLENDMODE_NONE));
    }
    return texture;
}

bool in_bounds(const LevelBounds &bounds, Coords coords) {
    return coords.x >= bounds.minX && coords.x <= bounds.maxX && coords.y >= bounds.minY && coords.y <= bounds.maxY;
}

std::shared_ptr<SDL_Rect> marker_rect(const MinimapScale &scale, Coords coords, int size) {
    const auto terrainCell = cell_rect(scale, coords);
    const int markerWidth = std::min(size, scale.rect->w);
    const int markerHeight = std::min(size, scale.rect->h);
    const int centerX = terrainCell->x + terrainCell->w / 2;
    const int centerY = terrainCell->y + terrainCell->h / 2;
    auto marker = CUtil::centeredRect(centerX, centerY, markerWidth, markerHeight);
    marker->x = std::clamp(marker->x, scale.rect->x, scale.rect->x + scale.rect->w - marker->w);
    marker->y = std::clamp(marker->y, scale.rect->y, scale.rect->y + scale.rect->h - marker->h);
    return marker;
}

void draw_marker(SDL_Renderer *renderer, const MinimapScale &scale, Coords coords, int size, SDL_Color color) {
    if (in_bounds(scale.bounds, coords)) {
        fill_rect(renderer, marker_rect(scale, coords, size), color);
    }
}

void draw_viewport(SDL_Renderer *renderer, const std::shared_ptr<CGui> &gui, const MinimapScale &scale, Coords player) {
    const int tileCountX = gui->getTileCountX();
    const int tileCountY = gui->getTileCountY();
    const int minX = std::max(scale.bounds.minX, player.x - tileCountX / 2);
    const int minY = std::max(scale.bounds.minY, player.y - tileCountY / 2);
    const int maxX = std::min(scale.bounds.maxX, player.x - tileCountX / 2 + tileCountX - 1);
    const int maxY = std::min(scale.bounds.maxY, player.y - tileCountY / 2 + tileCountY - 1);
    if (minX > maxX || minY > maxY) {
        return;
    }

    const int x = std::clamp(cell_left(scale, minX), scale.rect->x, scale.rect->x + scale.rect->w - 1);
    const int y = std::clamp(cell_top(scale, minY), scale.rect->y, scale.rect->y + scale.rect->h - 1);
    const int right = std::clamp(cell_right(scale, maxX), x + 1, scale.rect->x + scale.rect->w);
    const int bottom = std::clamp(cell_bottom(scale, maxY), y + 1, scale.rect->y + scale.rect->h);
    auto viewport = CUtil::rect(x, y, right - x, bottom - y);

    CUtil::setRenderDrawColor(renderer, MINIMAP_VIEWPORT);
    SDL_SAFE(SDL_RenderDrawRect(renderer, viewport.get()));
}
} // namespace

void CMinimapGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) {
    auto game = gui->getGame();
    if (!game) {
        return;
    }
    auto map = game->getMap();
    if (!map) {
        return;
    }
    auto player = map->getPlayer();
    if (!player) {
        return;
    }

    auto renderer = gui->getRenderer();
    const Coords playerCoords = player->getCoords();
    const auto maybeBounds = get_level_bounds(map, playerCoords.z);
    if (!maybeBounds) {
        fill_rect(renderer, rect, MINIMAP_BACKGROUND);
        return;
    }
    const auto scale = make_scale(rect, *maybeBounds);
    const auto signature = terrain_signature(map, playerCoords.z, *maybeBounds, rect->w, rect->h);
    if (!terrainTexture || terrainRenderer != renderer || terrainSignature != signature) {
        terrainTexture = build_terrain_texture(renderer, map, playerCoords.z, rect, *maybeBounds);
        terrainRenderer = renderer;
        terrainSignature = signature;
    }
    if (terrainTexture) {
        gui->getRenderContext().copy(terrainTexture.get(), nullptr, rect.get());
    } else {
        fill_rect(renderer, rect, MINIMAP_BACKGROUND);
        draw_terrain(renderer, map, playerCoords.z, scale);
    }

    for (const auto &object : map->getObjects()) {
        if (!object || object == player || !z_matches(object->getCoords(), playerCoords.z)) {
            continue;
        }
        if (vstd::cast<CCreature>(object)) {
            draw_marker(renderer, scale, object->getCoords(), 3, MINIMAP_CREATURE);
        } else {
            draw_marker(renderer, scale, object->getCoords(), 3, MINIMAP_OBJECT);
        }
    }

    draw_marker(renderer, scale, playerCoords, 5, MINIMAP_PLAYER);
    draw_viewport(renderer, gui, scale, playerCoords);
}

bool CMinimapGraphicsObject::mouseEvent(std::shared_ptr<CGui>, SDL_EventType, int, int, int) {
    // Consume in-bounds pointer button events. CGameGraphicsObject::event() only calls this hook for a
    // visible minimap when the click is inside its rectangle (or it is modal), so returning true stops the
    // event from falling through to lower-priority siblings such as the map layer. Left/right (and any other)
    // button presses delivered inside the minimap are therefore swallowed and never move/interact with the
    // world.
    return true;
}

bool CMinimapGraphicsObject::mouseMotionEvent(std::shared_ptr<CGui>, SDL_EventType, int, int, int, int) {
    // Consume in-bounds motion the same way as button events so hovering/dragging over the minimap does not
    // reach the map underneath. Wheel events are deliberately NOT overridden: the base no-op leaves them
    // unconsumed so map zoom keeps working when the cursor is over the minimap.
    return true;
}
