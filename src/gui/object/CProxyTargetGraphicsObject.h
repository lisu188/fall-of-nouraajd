/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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

class CProxyGraphicsObject;

class CProxyTargetGraphicsObject : public CGameGraphicsObject {
V_META(CProxyTargetGraphicsObject, CGameGraphicsObject,
       V_METHOD(CProxyTargetGraphicsObject, refresh),
       V_METHOD(CProxyTargetGraphicsObject, refreshAll),
       V_PROPERTY(CProxyTargetGraphicsObject, std::string, proxyLayout, getProxyLayout, setProxyLayout))
public:
    void render(std::shared_ptr<CGui> reneder, int frameTime) override;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

    virtual std::list<std::shared_ptr<CGameGraphicsObject>>
    getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y);

    virtual int getSizeX(std::shared_ptr<CGui> gui);

    virtual int getSizeY(std::shared_ptr<CGui> gui);

    CProxyTargetGraphicsObject() = default;

private:
    std::map<int, std::map<int, std::shared_ptr<CProxyGraphicsObject>>> proxyObjects;
    std::string proxyLayout = "CProxyGraphicsLayout";


public:
    std::string getProxyLayout();

    void setProxyLayout(std::string _layout);

    void refresh();

    void refreshObject(int x, int y);

    void refreshAll();
};