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
#pragma once


#include "gui/object/CGameGraphicsObject.h"

class CGui;

class CAnimation : public CGameGraphicsObject {
V_META(CAnimation, CGameGraphicsObject, vstd::meta::empty())

protected:
    std::weak_ptr<CGameObject> object;

public:
    CAnimation();

    std::shared_ptr<CGameObject> getObject();

    void setObject(std::shared_ptr<CGameObject> _object);
};


class CStaticAnimation : public CAnimation {
V_META(CStaticAnimation, CAnimation, vstd::meta::empty())

public:
    CStaticAnimation();

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;
};

class CDynamicAnimation : public CAnimation {
V_META(CDynamicAnimation, CAnimation, vstd::meta::empty())
public:
    CDynamicAnimation();

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

private:
    static int get_next();

    static int get_ttl();


    std::vector<std::string> paths;
    std::vector<int> times;

    vstd::cache<std::string, int, get_next, get_ttl> _offsets;
    vstd::cache2<std::string, std::vector<int>, get_ttl> _tables;

    int size = 0;
    bool initialized = false;

    void initialize();
};
