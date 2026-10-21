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
#include "CTextureCache.h"
#include "core/CProvider.h"
#include "core/CUtil.h"

#include <algorithm>
#include <cstdint>

namespace {
constexpr int MAX_ALPHA_MASK_PIXELS = 4'000'000;
constexpr int MAX_TILE_TEXTURE_EXTENT = 512;

bool containsRect(const SDL_Rect &bounds, const SDL_Rect &target) {
    return target.x >= bounds.x && target.y >= bounds.y &&
           static_cast<std::int64_t>(target.x) + target.w <= static_cast<std::int64_t>(bounds.x) + bounds.w &&
           static_cast<std::int64_t>(target.y) + target.h <= static_cast<std::int64_t>(bounds.y) + bounds.h;
}

bool canPrescaleTile(SDL_Renderer *renderer, const SDL_Rect &target) {
    if (target.w <= 0 || target.h <= 0 || target.w > MAX_TILE_TEXTURE_EXTENT || target.h > MAX_TILE_TEXTURE_EXTENT) {
        return false;
    }
    SDL_RendererInfo info{};
    if (SDL_GetRendererInfo(renderer, &info) != 0 || (info.flags & SDL_RENDERER_SOFTWARE) == 0) {
        return false;
    }
    const auto quality = SDL_GetHint(SDL_HINT_RENDER_SCALE_QUALITY);
    if (quality && SDL_strcmp(quality, "0") != 0 && SDL_strcasecmp(quality, "nearest") != 0) {
        return false;
    }
    float scaleX = 0;
    float scaleY = 0;
    SDL_RenderGetScale(renderer, &scaleX, &scaleY);
    if (scaleX != 1.0f || scaleY != 1.0f) {
        return false;
    }
    SDL_Rect viewport{};
    SDL_RenderGetViewport(renderer, &viewport);
    // Software clipping rescales a cropped source; clipping a prescaled texture samples different pixels.
    if (viewport.x != 0 || viewport.y != 0) {
        return false;
    }
    int outputWidth = 0;
    int outputHeight = 0;
    if (SDL_GetRendererOutputSize(renderer, &outputWidth, &outputHeight) != 0) {
        return false;
    }
    viewport.w = std::min(viewport.w, outputWidth);
    viewport.h = std::min(viewport.h, outputHeight);
    if (!containsRect(viewport, target)) {
        return false;
    }
    if (SDL_RenderIsClipEnabled(renderer)) {
        SDL_Rect clip{};
        SDL_RenderGetClipRect(renderer, &clip);
        if (!containsRect(clip, target)) {
            return false;
        }
    }
    return true;
}
} // namespace

Uint32 getpixel(SDL_Surface *surface, int x, int y) {
    int bpp = surface->format->BytesPerPixel;
    /* Here p is the address to the pixel we want to retrieve */
    Uint8 *p = (Uint8 *)surface->pixels + y * surface->pitch + x * bpp;

    switch (bpp) {
    case 1:
        return *p;
        break;

    case 2:
        return *(Uint16 *)p;
        break;

    case 3:
        if (SDL_BYTEORDER == SDL_BIG_ENDIAN)
            return p[0] << 16 | p[1] << 8 | p[2];
        else
            return p[0] | p[1] << 8 | p[2] << 16;
        break;

    case 4:
        return *(Uint32 *)p;
        break;

    default:
        return 0; /* shouldn't happen, but avoids warnings */
    }
}

void putpixel(SDL_Surface *surface, int x, int y, Uint32 pixel) {
    int bpp = surface->format->BytesPerPixel;
    /* Here p is the address to the pixel we want to set */
    Uint8 *p = (Uint8 *)surface->pixels + y * surface->pitch + x * bpp;

    switch (bpp) {
    case 1:
        *p = pixel;
        break;

    case 2:
        *(Uint16 *)p = pixel;
        break;

    case 3:
        if (SDL_BYTEORDER == SDL_BIG_ENDIAN) {
            p[0] = (pixel >> 16) & 0xff;
            p[1] = (pixel >> 8) & 0xff;
            p[2] = pixel & 0xff;
        } else {
            p[0] = pixel & 0xff;
            p[1] = (pixel >> 8) & 0xff;
            p[2] = (pixel >> 16) & 0xff;
        }
        break;

    case 4:
        *(Uint32 *)p = pixel;
        break;
    }
}

SDL_Texture *CTextureCache::getTexture(std::string path) {
    auto gui = _gui.lock();
    if (!gui || !gui->getRenderer()) {
        _textures.clear();
        tileTextures.clear();
        return nullptr;
    }
    if (vstd::ends_with(path, ".png")) {
        auto anim = _textures.find(path);
        if (anim == _textures.end()) {
            auto texture = loadTexture(path);
            auto [inserted, _] =
                _textures.emplace(path, fn::sdl::GuiTexturePtr(texture.release(), fn::sdl::GuiTextureDeleter{_gui}));
            return inserted->second.get();
        }
        return anim->second.get();
    }
    return getTexture(path + ".png");
}

SDL_Texture *CTextureCache::getTileTexture(std::string path, const SDL_Rect &target) {
    auto gui = _gui.lock();
    if (!gui || !gui->getRenderer()) {
        _textures.clear();
        tileTextures.clear();
        return nullptr;
    }
    if (!vstd::ends_with(path, ".png")) {
        path += ".png";
    }
    if (!canPrescaleTile(gui->getRenderer(), target)) {
        return getTexture(std::move(path));
    }
    auto original = _textures.find(path);
    if (original != _textures.end() && original->second) {
        SDL_ScaleMode mode{};
        SDL_BlendMode blend{};
        Uint8 red = 0, green = 0, blue = 0, alpha = 0;
        if (SDL_GetTextureScaleMode(original->second.get(), &mode) != 0 || mode != SDL_ScaleModeNearest ||
            SDL_GetTextureColorMod(original->second.get(), &red, &green, &blue) != 0 || red != 255 || green != 255 ||
            blue != 255 || SDL_GetTextureAlphaMod(original->second.get(), &alpha) != 0 || alpha != 255 ||
            SDL_GetTextureBlendMode(original->second.get(), &blend) != 0 || blend != SDL_BLENDMODE_BLEND) {
            return original->second.get();
        }
    }
    auto found = tileTextures.find(path);
    if (found != tileTextures.end()) {
        if (!found->second.scaleSafe) {
            return getTexture(std::move(path));
        }
        if (found->second.width == target.w && found->second.height == target.h) {
            return found->second.texture.get();
        }
    }

    bool scaleSafe = false;
    auto texture = loadTexture(path, target.w, target.h, &scaleSafe);
    auto &entry = tileTextures[path];
    entry.width = target.w;
    entry.height = target.h;
    entry.scaleSafe = scaleSafe && texture != nullptr;
    if (!entry.scaleSafe) {
        entry.texture.reset();
        if (!texture) {
            return getTexture(std::move(path));
        }
        auto [original, inserted] = _textures.try_emplace(path, nullptr, fn::sdl::GuiTextureDeleter{_gui});
        if (inserted) {
            original->second.reset(texture.release());
        }
        return original->second.get();
    }
    entry.texture = fn::sdl::GuiTexturePtr(texture.release(), fn::sdl::GuiTextureDeleter{_gui});
    ++tileTextureBuildCount;
    return entry.texture.get();
}

fn::sdl::TexturePtr CTextureCache::loadTexture(std::string path, int targetWidth, int targetHeight, bool *scaleSafe) {
    auto gui = _gui.lock();
    // Resolve through the owning game's per-session resources provider; fall back to the process
    // singleton only when the cache is detached from a live GUI/game (compatibility path).
    auto game = gui ? gui->getGame() : nullptr;
    auto resourcesProvider = game ? game->getResourcesProvider() : CResourcesProvider::getInstance();
    const auto resolvedPath = resourcesProvider->getPath(path);
    if (resolvedPath.empty()) {
        vstd::logger::error("CTextureCache::loadTexture: cannot resolve", path, "resolved:", resolvedPath);
        return nullptr;
    }
    ++textureLoadCount;
    auto surface = fn::sdl::SurfacePtr(IMG_Load(resolvedPath.c_str()));
    if (!surface) {
        vstd::logger::error("CTextureCache::loadTexture: cannot load", path, "resolved:", resolvedPath);
        return nullptr;
    }
    return gui ? CTextureUtil::calculateAlpha(gui->getRenderer(), std::move(surface), targetWidth, targetHeight,
                                              scaleSafe)
               : nullptr;
}

CTextureCache::CTextureCache(std::shared_ptr<CGui> _gui) : _gui(_gui) {}

CTextureCache::~CTextureCache() { _textures.clear(); }

CTextureCache::CTextureCache() {}

auto CTextureUtil::getPixelColor(SDL_Surface *surface, int x, int y) { return getpixel(surface, x, y); }

void CTextureUtil::setPixelColor(SDL_Surface *surface, int x, int y, std::tuple<Uint8, Uint8, Uint8, Uint8> color) {
    auto [r, g, b, a] = color;
    auto rgbaColor = SDL_MapRGBA(surface->format, r, g, b, a);
    putpixel(surface, x, y, rgbaColor);
}

auto CTextureUtil::getPixelRgba(SDL_Surface *surface, int x, int y) {
    Uint8 r, g, b, a;
    SDL_GetRGBA(getpixel(surface, x, y), surface->format, &r, &g, &b, &a);
    return std::make_tuple(r, g, b, a);
}

fn::sdl::TexturePtr CTextureUtil::calculateAlpha(SDL_Renderer *renderer, fn::sdl::SurfacePtr surface, int targetWidth,
                                                 int targetHeight, bool *scaleSafe) {
    if (scaleSafe) {
        *scaleSafe = false;
    }
    if (!surface) {
        vstd::logger::error("CTextureUtil::calculateAlpha: null surface");
        return nullptr;
    }

    int w = surface->w;
    int h = surface->h;

    if (w <= 0 || h <= 0 || w > MAX_ALPHA_MASK_PIXELS / std::max(1, h)) {
        vstd::logger::error("CTextureUtil::calculateAlpha: invalid surface size", w, h);
        return nullptr;
    }
    if (!renderer) {
        vstd::logger::error("CTextureUtil::calculateAlpha: null renderer");
        return nullptr;
    }

    auto secondSurface = fn::sdl::SurfacePtr(
        SDL_SAFE(SDL_CreateRGBSurfaceWithFormat(surface->flags, surface->w, surface->h, 32, SDL_PIXELFORMAT_RGBA32)));
    if (!secondSurface) {
        return nullptr;
    }

    auto maskPixel = getPixelRgba(surface.get(), 0, 0);

    bool shouldAddMask =
        vstd::all_equals(getPixelColor(surface.get(), 0, 0), getPixelColor(surface.get(), 0, h - 1),
                         getPixelColor(surface.get(), w - 1, 0), getPixelColor(surface.get(), w - 1, h - 1)) &&
        std::get<3>(maskPixel) == 255;

    std::unordered_set<std::pair<int, int>, vstd::pair_hash> mask =
        shouldAddMask ? calculateMask(surface.get()) : std::unordered_set<std::pair<int, int>, vstd::pair_hash>();

    bool binaryAlpha = true;
    for (auto verticalIndex = 0; verticalIndex < h; verticalIndex++) {
        for (auto horizontalIndex = 0; horizontalIndex < w; horizontalIndex++) {
            auto currentPixel = getPixelRgba(surface.get(), horizontalIndex, verticalIndex);

            auto [r, g, b, a] = currentPixel;
            if (vstd::ctn(mask, std::make_pair(horizontalIndex, verticalIndex))) {
                setPixelColor(secondSurface.get(), horizontalIndex, verticalIndex, {r, g, b, 0});
            } else {
                binaryAlpha = binaryAlpha && (a == 0 || a == 255);
                setPixelColor(secondSurface.get(), horizontalIndex, verticalIndex, {r, g, b, a});
            }
        }
    }

    // Partial alpha takes different scaled/unscaled SDL blend paths and can change channel rounding.
    if (binaryAlpha && targetWidth > 0 && targetHeight > 0 && targetWidth <= MAX_TILE_TEXTURE_EXTENT &&
        targetHeight <= MAX_TILE_TEXTURE_EXTENT) {
        auto scaled = fn::sdl::SurfacePtr(
            SDL_SAFE(SDL_CreateRGBSurfaceWithFormat(0, targetWidth, targetHeight, 32, SDL_PIXELFORMAT_RGBA32)));
        if (scaled && SDL_SetSurfaceBlendMode(secondSurface.get(), SDL_BLENDMODE_NONE) == 0 &&
            SDL_BlitScaled(secondSurface.get(), nullptr, scaled.get(), nullptr) == 0 &&
            SDL_SetSurfaceBlendMode(scaled.get(), SDL_BLENDMODE_BLEND) == 0) {
            secondSurface = std::move(scaled);
            if (scaleSafe) {
                *scaleSafe = true;
            }
        } else {
            SDL_SetSurfaceBlendMode(secondSurface.get(), SDL_BLENDMODE_BLEND);
        }
    }

    return fn::sdl::TexturePtr(SDL_SAFE(SDL_CreateTextureFromSurface(renderer, secondSurface.get())));
}

std::unordered_set<std::pair<int, int>, vstd::pair_hash> CTextureUtil::calculateMask(SDL_Surface *pSurface) {
    std::unordered_set<std::pair<int, int>, vstd::pair_hash> checked;
    std::unordered_set<std::pair<int, int>, vstd::pair_hash> remaining;
    std::unordered_set<std::pair<int, int>, vstd::pair_hash> result;

    if (!pSurface || pSurface->w <= 0 || pSurface->h <= 0 ||
        pSurface->w > MAX_ALPHA_MASK_PIXELS / std::max(1, pSurface->h)) {
        return result;
    }

    remaining.insert(std::make_pair(0, 0));
    remaining.insert(std::make_pair(0, pSurface->h - 1));
    remaining.insert(std::make_pair(pSurface->w - 1, 0));
    remaining.insert(std::make_pair(pSurface->w - 1, pSurface->h - 1));

    auto mask = getPixelRgba(pSurface, 0, 0);

    while (!remaining.empty()) {
        // TODO: make pop
        auto coordsIt = vstd::any(remaining);
        auto coords = *coordsIt;
        remaining.erase(coordsIt);

        if (getPixelRgba(pSurface, coords.first, coords.second) == mask) {
            result.insert(coords);
            for (int i = -1; i <= 1; i++) {
                for (int j = -1; j <= 1; j++) {
                    int x = coords.first + i;
                    int y = coords.second + j;
                    if (x >= 0 && x < pSurface->w && y >= 0 && y < pSurface->h) {
                        std::pair<int, int> value = std::make_pair(x, y);
                        if (!vstd::ctn(checked, value) && result.size() + remaining.size() < MAX_ALPHA_MASK_PIXELS) {
                            remaining.insert(value);
                        }
                    }
                }
            }
        }
        checked.insert(coords);
    }

    return result;
}
