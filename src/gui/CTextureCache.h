//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#pragma once

#include "object/CGameObject.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"

//TODO: generify all cache classes

class CTextureCache : public CGameObject {
V_META(CTextureCache, CGameObject, vstd::meta::empty())
    std::unordered_map<std::string, SDL_Texture *> _textures;
public:
    CTextureCache(std::shared_ptr<CGui> _gui);

    CTextureCache();

    ~CTextureCache();


    SDL_Texture *getTexture(std::string path);

private:
    SDL_Texture *loadTexture(std::string path);

    std::weak_ptr<CGui> _gui;
};
