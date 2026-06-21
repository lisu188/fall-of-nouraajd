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

#include "gui/object/CProxyTargetGraphicsObject.h"

class CProxyGraphicsObject;

class CScript;

class CListView : public CProxyTargetGraphicsObject {
    V_META(CListView, CProxyTargetGraphicsObject,
           V_PROPERTY(CListView, std::string, collection, getCollection, setCollection),
           V_PROPERTY(CListView, std::string, select, getSelect, setSelect),
           V_PROPERTY(CListView, std::string, callback, getCallback, setCallback),
           V_PROPERTY(CListView, std::string, rightClickCallback, getRightClickCallback, setRightClickCallback),
           V_PROPERTY(CListView, std::string, dragStart, getDragStart, setDragStart),
           V_PROPERTY(CListView, std::string, dragValidate, getDragValidate, setDragValidate),
           V_PROPERTY(CListView, std::string, drop, getDrop, setDrop),
           V_PROPERTY(CListView, std::string, dragCancel, getDragCancel, setDragCancel),
           V_PROPERTY(CListView, std::shared_ptr<CScript>, refreshObject, getRefreshObject, setRefreshObject),
           V_PROPERTY(CListView, std::string, refreshEvent, getRefreshEvent, setRefreshEvent),
           V_PROPERTY(CListView, bool, refreshOnPropertyChanged, getRefreshOnPropertyChanged,
                      setRefreshOnPropertyChanged),
           V_PROPERTY(CListView, std::set<std::string>, refreshProperties, getRefreshProperties, setRefreshProperties),
           V_PROPERTY(CListView, int, xPrefferedSize, getXPrefferedSize, setXPrefferedSize),
           V_PROPERTY(CListView, int, yPrefferedSize, getYPrefferedSize, setYPrefferedSize),
           V_PROPERTY(CListView, int, tileSize, getTileSize, setTileSize),
           V_PROPERTY(CListView, bool, allowOversize, getAllowOversize, setAllowOversize),
           V_PROPERTY(CListView, bool, showEmpty, getShowEmpty, setShowEmpty),
           V_PROPERTY(CListView, bool, grouping, getGrouping, setGrouping), V_METHOD(CListView, initialize),
           V_METHOD(CListView, refreshFromRefreshEvent),
           V_METHOD(CListView, refreshFromPropertyChanged, void, std::string),
           V_METHOD(CListView, refreshFromPropertiesChanged, void, std::set<std::string>),
           V_METHOD(CListView, refreshFromPropertySpecificChanged))

    std::string collection;

    std::string callback;

    std::string rightClickCallback;

    std::string select;

    std::string dragStart;

    std::string dragValidate;

    std::string drop;

    std::string dragCancel;

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

    bool getRefreshOnPropertyChanged();

    void setRefreshOnPropertyChanged(bool refreshOnPropertyChanged);

    std::set<std::string> getRefreshProperties();

    void setRefreshProperties(std::set<std::string> refreshProperties);

    void initialize();

    void refreshFromRefreshEvent();

    void refreshFromPropertyChanged(std::string propertyName);

    void refreshFromPropertiesChanged(std::set<std::string> propertyNames);

    void refreshFromPropertySpecificChanged();

  private:
    std::string refreshEvent;

    bool refreshOnPropertyChanged = false;

    std::set<std::string> refreshProperties;

    std::weak_ptr<CGameObject> refreshSubscriptionTarget;

    std::string subscribedRefreshEvent;

    bool subscribedRefreshOnPropertyChanged = false;

    std::set<std::string> subscribedRefreshProperties;

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

    std::list<std::shared_ptr<CGameGraphicsObject>> getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) override;

    int getSizeX(std::shared_ptr<CGui> gui) override;

    int getSizeY(std::shared_ptr<CGui> gui) override;

    std::string getCollection();

    void setCollection(std::string collection);

    std::string getCallback();

    void setCallback(std::string callback);

    std::string getRightClickCallback();

    void setRightClickCallback(std::string rightClickCallback);

    std::string getSelect();

    void setSelect(std::string select);

    std::string getDragStart();

    void setDragStart(std::string dragStart);

    std::string getDragValidate();

    void setDragValidate(std::string dragValidate);

    std::string getDrop();

    void setDrop(std::string drop);

    std::string getDragCancel();

    void setDragCancel(std::string dragCancel);

    int getXPrefferedSize() const;

    void setXPrefferedSize(int xPrefferedSize);

    int getYPrefferedSize() const;

    void setYPrefferedSize(int yPrefferedSize);

  private:
    CListView::collection_pointer invokeCollection(std::shared_ptr<CGui> gui);

    void invokeCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool invokeRightClickCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool invokeSelect(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool invokeDragStart(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool invokeDragValidate(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    void invokeDrop(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    void invokeDragCancel(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object);

    bool canInvokeParentCallback(const std::shared_ptr<CGui> &gui, const std::shared_ptr<CGameGraphicsObject> &parent);

    bool tryGetClickedObject(std::shared_ptr<CGui> gui, int x, int y, int &index, std::shared_ptr<CGameObject> &object,
                             bool allowEmptyCell = false);

    bool hasSourceDragCallbacks() const;

    bool hasTargetDragCallbacks() const;

    bool runDropCallbacks(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object,
                          const std::shared_ptr<CListView> &sourceList, int sourceIndex,
                          std::shared_ptr<CGameObject> sourceObject);

    void notifySourceDragCancel(std::shared_ptr<CGui> gui, int sourceIndex, std::shared_ptr<CGameObject> sourceObject);

    std::unordered_map<std::pair<int, int>, std::shared_ptr<CProxyGraphicsObject>> proxyObjects;

    void doShift(const std::shared_ptr<CGui> &gui, int val);

    int shiftIndex(const std::shared_ptr<CGui> &gui, int arg);

    int getRightArrowIndex(const std::shared_ptr<CGui> &gui);

    int getLeftArrowIndex(const std::shared_ptr<CGui> &gui);

    int getCellCount(const std::shared_ptr<CGui> &gui);

    int getVisibleItemSlots(const std::shared_ptr<CGui> &gui, int itemTypeCount);

    int getMaxShift(const std::shared_ptr<CGui> &gui, int itemTypeCount);

    bool isOversizedForCount(const std::shared_ptr<CGui> &gui, int itemTypeCount);

    void clampShift(const std::shared_ptr<CGui> &gui, int itemTypeCount);

    // TODO: do not generate whole map, instead add callback arguement and stop
    // when met
    std::unordered_multimap<int, std::shared_ptr<CGameObject>> calculateIndices(const std::shared_ptr<CGui> &gui);

    std::shared_ptr<SDL_Rect> calculateIndexPosition(const std::shared_ptr<CGui> &gui,
                                                     const std::shared_ptr<SDL_Rect> &loc, int index);

    // TODO: cache method calls // note to self, seems like no performance impact,
    // even in debug
    bool isOversized(const std::shared_ptr<CGui> &gui);

    auto getArrowCallback(bool left);

    void addItemBox(const std::shared_ptr<CGui> &gui,
                    std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    void addItem(const std::shared_ptr<CGui> &gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                 std::unordered_multimap<int, std::shared_ptr<CGameObject>> indexedCollection, int itemIndex) const;

    void addSelectionBox(const std::shared_ptr<CGui> &gui,
                         std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    void addCountBox(const std::shared_ptr<CGui> &gui, int count,
                     std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    int getItemTypesCount(const std::shared_ptr<CGui> &gui);

  protected:
    virtual std::shared_ptr<CGameObject> resolveRefreshTarget();

  private:
    void refreshSubscriptions();

    void disconnectRefreshSubscriptions();

    void connectRefreshSubscriptions(const std::shared_ptr<CGameObject> &refreshTarget);

    void refreshFromSubscription();

    bool shouldRefreshForProperty(const std::string &propertyName) const;
};
