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
#pragma once

#include "gui/object/CGameGraphicsObject.h"

class CGui;

class CAnimation : public CGameGraphicsObject {
    V_META(CAnimation, CGameGraphicsObject, vstd::meta::empty())

  protected:
    std::shared_ptr<CGameObject> object; // TODO: try make weak

  public:
    CAnimation();

    std::shared_ptr<CGameObject> getObject();

    void setObject(std::shared_ptr<CGameObject> _object);

    bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) override;

    template <fn::AnimationCallback F> auto withCallback(F f) {
        callback = f;
        hasCallback = true;
        return this->ptr<CAnimation>();
    }

  private:
    bool hasCallback = false;

    std::function<bool(std::shared_ptr<CGui>, SDL_EventType, int, int, int)> callback =
        [](auto a, auto b, auto c, auto d, auto e) { return false; };
};

class CStaticAnimation : public CAnimation {
    V_META(CStaticAnimation, CAnimation, V_PROPERTY(CStaticAnimation, int, rotation, getRotation, setRotation))

  public:
    CStaticAnimation();

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

  private:
    int rotation = 0;
    bool useColorMod = false;
    Uint8 colorR = 255;
    Uint8 colorG = 255;
    Uint8 colorB = 255;
    Uint8 colorA = 255;

  public:
    int getRotation() const;

    void setRotation(int rotation);

    void setColorMod(Uint8 r, Uint8 g, Uint8 b, Uint8 a = 255);

    void clearColorMod();
};

class CDynamicAnimation : public CAnimation {
    V_META(CDynamicAnimation, CAnimation, V_METHOD(CDynamicAnimation, initialize))
  public:
    CDynamicAnimation();

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    void initialize();

  private:
    static int get_next();

    static int get_ttl();

    std::vector<std::string> paths;
    std::vector<int> times;

    vstd::cache<std::string, int, get_next, get_ttl> _offsets;
    vstd::cache2<std::string, std::vector<int>, get_ttl> _tables;

    int size = 0;
    bool initialized = false;
};

class CSelectionBox : public CAnimation {
    V_META(CSelectionBox, CAnimation, V_PROPERTY(CSelectionBox, int, thickness, getThickness, setThickness))

  public:
    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    int getThickness();

    void setThickness(int _thickness);

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;

  private:
    int thickness;
};
