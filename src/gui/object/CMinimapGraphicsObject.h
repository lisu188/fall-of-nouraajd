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
#pragma once

#include "CGameGraphicsObject.h"
#include "gui/CSdlResources.h"

#include <cstddef>

class CMinimapGraphicsObject : public CGameGraphicsObject {
    V_META(CMinimapGraphicsObject, CGameGraphicsObject, vstd::meta::empty())

    fn::sdl::TexturePtr terrainTexture;
    SDL_Renderer *terrainRenderer = nullptr;
    std::size_t terrainSignature = 0;

  public:
    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;
};
