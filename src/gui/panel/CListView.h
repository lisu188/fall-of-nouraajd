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

#include "gui/object/CProxyTargetGraphicsObject.h"

class CProxyGraphicsObject;

class CListView : public CProxyTargetGraphicsObject {
V_META(CListView, CProxyTargetGraphicsObject,
       V_PROPERTY(CListView, std::string, collection, getCollection, setCollection),
       V_PROPERTY(CListView, std::string, select, getSelect, setSelect),
       V_PROPERTY(CListView, std::string, callback, getCallback, setCallback),
       V_PROPERTY(CListView, std::string, refreshObject, getRefreshObject, setRefreshObject),
       V_PROPERTY(CListView, std::string, refreshEvent, getRefreshEvent, setRefreshEvent),
       V_METHOD(CListView, initialize))

    std::string collection;

    std::string callback;

    std::string select;

    std::string refreshObject;
public:
    typedef vstd::list<std::shared_ptr<CGameObject>> collection_type;
    typedef std::shared_ptr<collection_type> collection_pointer;

    typedef  std::set<std::shared_ptr<CGameGraphicsObject>> children_type;
    typedef  std::shared_ptr<children_type> children_pointer;

    std::string getRefreshObject();

    void setRefreshObject(std::string refreshObject);

    std::string getRefreshEvent();

    void setRefreshEvent(std::string refreshEvent);

    void initialize();

private:

    std::string refreshEvent;

    bool allowOversize = true;

    int selectionThickness = 5;

    int shift = 0;

public:

    CListView();

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) override;

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;

    std::set<std::shared_ptr<CGameGraphicsObject>>
    getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) override;

    int getSizeX(std::shared_ptr<CGui> gui) override;

    int getSizeY(std::shared_ptr<CGui> gui) override;

    std::string getCollection();

    void setCollection(std::string collection);

    std::string getCallback();

    void setCallback(std::string callback);

    std::string getSelect();

    void setSelect(std::string select);

private:
    CListView::collection_pointer invokeCollection(std::shared_ptr<CGui> gui);

    void
    invokeCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool
    invokeSelect(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    std::unordered_map<std::pair<int, int>, std::shared_ptr<CProxyGraphicsObject>> proxyObjects;

    void doShift(std::shared_ptr<CGui> gui, int val);

    void drawSelection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> location, int thickness);

    int shiftIndex(std::shared_ptr<CGui> gui, int arg);

    int getRightArrowIndex(std::shared_ptr<CGui> gui);

    int getLeftArrowIndex(std::shared_ptr<CGui> gui);

//TODO: do not generate whole map, instead add callback arguement and stop when met
    std::unordered_map<int, std::shared_ptr<CGameObject>> calculateIndices(std::shared_ptr<CGui> gui);

    std::shared_ptr<SDL_Rect>
    calculateIndexPosition(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int index);

    void drawItemBox(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);


    void drawArrowLeft(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);


    void drawArrowRight(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);

//TODO: cache method calls // note to self, seems like no performance impact, even in debug
    bool isOversized(std::shared_ptr<CGui> gui);

    vstd::lazy<CListView::collection_type> _collection;

    void refresh();
};


