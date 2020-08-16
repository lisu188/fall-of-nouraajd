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
    return IMG_LoadTexture(_gui.lock()->getRenderer(), path.c_str());
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
