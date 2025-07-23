/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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


Uint32 getpixel(SDL_Surface *surface, int x, int y) {
    int bpp = surface->format->BytesPerPixel;
    /* Here p is the address to the pixel we want to retrieve */
    Uint8 *p = (Uint8 *) surface->pixels + y * surface->pitch + x * bpp;

    switch (bpp) {
        case 1:
            return *p;
            break;

        case 2:
            return *(Uint16 *) p;
            break;

        case 3:
            if (SDL_BYTEORDER == SDL_BIG_ENDIAN)
                return p[0] << 16 | p[1] << 8 | p[2];
            else
                return p[0] | p[1] << 8 | p[2] << 16;
            break;

        case 4:
            return *(Uint32 *) p;
            break;

        default:
            return 0;       /* shouldn't happen, but avoids warnings */
    }
}

void putpixel(SDL_Surface *surface, int x, int y, Uint32 pixel) {
    int bpp = surface->format->BytesPerPixel;
    /* Here p is the address to the pixel we want to set */
    Uint8 *p = (Uint8 *) surface->pixels + y * surface->pitch + x * bpp;

    switch (bpp) {
        case 1:
            *p = pixel;
            break;

        case 2:
            *(Uint16 *) p = pixel;
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
            *(Uint32 *) p = pixel;
            break;
    }
}

SDL_Texture *CTextureCache::getTexture(std::string path) {
    if (vstd::ends_with(path, ".png")) {
        auto anim = _textures.find(path);
        if (anim == _textures.end()) {
            _textures[path] = this->loadTexture(path);
            return getTexture(path);
        }
        return _textures[path];
    }
    return getTexture(path + ".png");
}

SDL_Texture *CTextureCache::loadTexture(std::string path) {
    if (path.empty()) {
        vstd::logger::error("CTextureCache::loadTexture: empty path");
        return nullptr;
    }

    auto gui = _gui.lock();
    if (!gui) {
        vstd::logger::error("CTextureCache::loadTexture: gui expired", path);
        return nullptr;
    }

    SDL_Surface *surface = IMG_Load(path.c_str());
    if (!surface) {
        vstd::logger::error("CTextureCache::loadTexture: cannot load", path);
        return nullptr;
    }
    return CTextureUtil::calculateAlpha(gui->getRenderer(), surface);
}

CTextureCache::CTextureCache(std::shared_ptr<CGui> _gui) : _gui(_gui) {}

CTextureCache::~CTextureCache() {
    for (auto texture:_textures) {
        SDL_DestroyTexture(texture.second);
    }
    _textures.clear();
}

CTextureCache::CTextureCache() {

}

auto CTextureUtil::getPixelColor(SDL_Surface *surface, int x, int y) {
    return getpixel(surface, x, y);
}

void CTextureUtil::setPixelColor(SDL_Surface *surface, int x, int y,
                                 std::tuple<Uint8, Uint8, Uint8, Uint8> color) {
    auto[r, g, b, a]=color;
    auto rgbaColor = SDL_MapRGBA(surface->format, r, g, b, a);
    putpixel(surface, x, y, rgbaColor);
}


auto CTextureUtil::getPixelRgba(SDL_Surface *surface, int x, int y) {
    Uint8 r, g, b, a;
    SDL_GetRGBA(getpixel(surface, x, y), surface->format, &r, &g, &b, &a);
    return std::make_tuple(r, g, b, a);
}

SDL_Texture *CTextureUtil::calculateAlpha(SDL_Renderer *renderer, SDL_Surface *surface) {
    if (!surface) {
        vstd::logger::error("CTextureUtil::calculateAlpha: null surface");
        return nullptr;
    }

    int w = surface->w;
    int h = surface->h;

    if (w <= 0 || h <= 0) {
        vstd::logger::error("CTextureUtil::calculateAlpha: invalid surface size", w, h);
        SDL_SAFE(SDL_FreeSurface(surface));
        return nullptr;
    }

    auto secondSurface = SDL_CreateRGBSurfaceWithFormat(surface->flags, surface->w, surface->h, 32,
                                                        SDL_PIXELFORMAT_RGBA32);
    if (!secondSurface) {
        vstd::logger::error("CTextureUtil::calculateAlpha: cannot create surface");
        SDL_SAFE(SDL_FreeSurface(surface));
        return nullptr;
    }

    auto maskPixel = getPixelRgba(surface, 0, 0);

    bool shouldAddMask = vstd::all_equals(getPixelColor(surface, 0, 0),
                                          getPixelColor(surface, 0, h - 1),
                                          getPixelColor(surface, w - 1, 0),
                                          getPixelColor(surface, w - 1, h - 1))
                         && std::get<3>(maskPixel) == 255;


    std::unordered_set<std::pair<int, int>> mask = shouldAddMask ? calculateMask(surface)
                                                                 : std::unordered_set<std::pair<int, int>>();

    for (auto verticalIndex = 0; verticalIndex < h; verticalIndex++) {
        for (auto horizontalIndex = 0; horizontalIndex < w; horizontalIndex++) {
            auto currentPixel = getPixelRgba(surface,
                                             horizontalIndex,
                                             verticalIndex);


            auto[r, g, b, a]=currentPixel;
            if (vstd::ctn(mask, std::make_pair(horizontalIndex, verticalIndex))) {
                setPixelColor(secondSurface, horizontalIndex, verticalIndex,
                              {r, g, b, 0});
            } else {
                setPixelColor(secondSurface, horizontalIndex, verticalIndex,
                              {r, g, b, a});
            }
        }
    }

    auto texture = SDL_SAFE(SDL_CreateTextureFromSurface(renderer, secondSurface));
    if (!texture) {
        vstd::logger::error("CTextureUtil::calculateAlpha: failed to create texture");
        SDL_SAFE(SDL_FreeSurface(surface));
        SDL_SAFE(SDL_FreeSurface(secondSurface));
        return nullptr;
    }

    SDL_SAFE(SDL_FreeSurface(surface));
    SDL_SAFE(SDL_FreeSurface(secondSurface));

    return texture;
}

std::unordered_set<std::pair<int, int>> CTextureUtil::calculateMask(SDL_Surface *pSurface) {
    std::unordered_set<std::pair<int, int>> checked;
    std::unordered_set<std::pair<int, int>> remaining;
    std::unordered_set<std::pair<int, int>> result;

    remaining.insert(std::make_pair(0, 0));
    remaining.insert(std::make_pair(0, pSurface->h - 1));
    remaining.insert(std::make_pair(pSurface->w - 1, 0));
    remaining.insert(std::make_pair(pSurface->w - 1, pSurface->h - 1));

    auto mask = getPixelRgba(pSurface, 0, 0);

    while (!remaining.empty()) {
        //TODO: make pop
        auto coords = vstd::any(remaining);
        remaining.erase(coords);

        if (getPixelRgba(pSurface, coords.first, coords.second) == mask) {
            result.insert(coords);
            for (int i = -1; i <= 1; i++) {
                for (int j = -1; j <= 1; j++) {
                    int x = coords.first + i;
                    int y = coords.second + j;
                    if (x >= 0 && x < pSurface->w && y >= 0 && y < pSurface->h) {
                        std::pair<int, int> value = std::make_pair(x, y);
                        if (!vstd::ctn(checked, value)) {
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

