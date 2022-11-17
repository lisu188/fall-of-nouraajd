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

#include "gui/object/CProxyTargetGraphicsObject.h"

class CProxyGraphicsObject;

class CScript;

class CListView : public CProxyTargetGraphicsObject {
V_META(CListView, CProxyTargetGraphicsObject,
       V_PROPERTY(CListView, std::string, collection, getCollection, setCollection),
       V_PROPERTY(CListView, std::string, select, getSelect, setSelect),
       V_PROPERTY(CListView, std::string, callback, getCallback, setCallback),
       V_PROPERTY(CListView, std::shared_ptr<CScript>, refreshObject, getRefreshObject, setRefreshObject),
       V_PROPERTY(CListView, std::string, refreshEvent, getRefreshEvent, setRefreshEvent),
       V_PROPERTY(CListView, int, xPrefferedSize, getXPrefferedSize, setXPrefferedSize),
       V_PROPERTY(CListView, int, yPrefferedSize, getYPrefferedSize, setYPrefferedSize),
       V_PROPERTY(CListView, int, tileSize, getTileSize, setTileSize),
       V_PROPERTY(CListView, bool, allowOversize, getAllowOversize, setAllowOversize),
       V_PROPERTY(CListView, bool, showEmpty, getShowEmpty, setShowEmpty),
       V_PROPERTY(CListView, bool, grouping, getGrouping, setGrouping),
       V_METHOD(CListView, initialize))

    std::string collection;

    std::string callback;

    std::string select;

    std::shared_ptr<CScript> refreshObject;
public:
    typedef vstd::list<std::shared_ptr<CGameObject>> collection_type;
    typedef std::shared_ptr<collection_type> collection_pointer;

    typedef std::set<std::shared_ptr<CGameGraphicsObject>> children_type;
    typedef std::shared_ptr<children_type> children_pointer;

    std::shared_ptr<CScript> getRefreshObject();

    void setRefreshObject(std::shared_ptr<CScript> refreshObject);

    std::string getRefreshEvent();

    void setRefreshEvent(std::string refreshEvent);

    void initialize();

private:

    std::string refreshEvent;

    bool allowOversize = true;

    bool showEmpty = true;

    bool grouping = false;

    int selectionThickness = 5;

    int shift = 0;

    int xPrefferedSize = -1;

    int yPrefferedSize = -1;

    int tileSize = 50;
public:
    CListView() = default;

    bool getAllowOversize();

    void setAllowOversize(bool _allowOversize);

    bool getGrouping();

    void setGrouping(bool _grouping);

    bool getShowEmpty();

    void setShowEmpty(bool _showEmpty);

    int getTileSize();

    void setTileSize(int _tileSize);

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) override;

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;

    std::list<std::shared_ptr<CGameGraphicsObject>>
    getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) override;

    int getSizeX(std::shared_ptr<CGui> gui) override;

    int getSizeY(std::shared_ptr<CGui> gui) override;

    std::string getCollection();

    void setCollection(std::string collection);

    std::string getCallback();

    void setCallback(std::string callback);

    std::string getSelect();

    void setSelect(std::string select);

    int getXPrefferedSize() const;

    void setXPrefferedSize(int xPrefferedSize);

    int getYPrefferedSize() const;

    void setYPrefferedSize(int yPrefferedSize);

private:
    CListView::collection_pointer invokeCollection(std::shared_ptr<CGui> gui);

    void
    invokeCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool
    invokeSelect(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    std::unordered_map<std::pair<int, int>, std::shared_ptr<CProxyGraphicsObject>> proxyObjects;

    void doShift(const std::shared_ptr<CGui> &gui, int val);

    int shiftIndex(const std::shared_ptr<CGui> &gui, int arg);

    int getRightArrowIndex(const std::shared_ptr<CGui> &gui);

    int getLeftArrowIndex(const std::shared_ptr<CGui> &gui);

//TODO: do not generate whole map, instead add callback arguement and stop when met
    std::unordered_multimap<int, std::shared_ptr<CGameObject>> calculateIndices(const std::shared_ptr<CGui> &gui);

    std::shared_ptr<SDL_Rect>
    calculateIndexPosition(const std::shared_ptr<CGui> &gui, const std::shared_ptr<SDL_Rect> &loc, int index);

//TODO: cache method calls // note to self, seems like no performance impact, even in debug
    bool isOversized(const std::shared_ptr<CGui> &gui);

    auto getArrowCallback(bool left);

    void
    addItemBox(const std::shared_ptr<CGui> &gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    void addItem(std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                 std::unordered_multimap<int, std::shared_ptr<CGameObject>> indexedCollection,
                 int itemIndex) const;

    void addSelectionBox(const std::shared_ptr<CGui> &gui,
                         std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    void
    addCountBox(const std::shared_ptr<CGui> &gui, int count,
                std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    int getItemTypesCount(const std::shared_ptr<CGui> &gui);
};


