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
#pragma once

#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CSdlResources.h"
#include "object/CGameObject.h"

class CTextManager : public CGameObject {
    V_META(CTextManager, CGameObject, vstd::meta::empty())
    std::unordered_map<std::pair<std::string, int>, fn::sdl::TexturePtr> _textures;

  public:
    explicit CTextManager(const std::shared_ptr<CGui> &_gui = nullptr);

    ~CTextManager() override;

    std::pair<int, int> getTextureSize(std::string text);

    void drawText(const std::string &text, int x, int y, int w);

    void drawText(const std::string &text, const std::shared_ptr<SDL_Rect> &rect);

    void drawTextCentered(const std::string &text, int x, int y, int w, int h);

    void drawTextCentered(const std::string &text, const std::shared_ptr<SDL_Rect> &rect);

    int countLines(const std::string &text, int w);

  private:
    SDL_Texture *getTexture(const std::string &text, int width = 0);

    fn::sdl::TexturePtr loadTexture(std::string text, int width = 0);

    std::weak_ptr<CGui> _gui;

    fn::sdl::FontPtr font;
};
