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
#include "gui/object/CWidget.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "CListView.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include "gui/CLayout.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "handler/CEventHandler.h"
#include "core/CScript.h"

void CListView::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) {

}

bool CListView::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {//TODO: separate to objects
        int xIndex = x / tileSize;
        int yIndex = y / tileSize;
        if (xIndex < getSizeX(gui) && yIndex < getSizeY(gui)) {
            int i = (xIndex + (yIndex * getSizeX(gui)));
            invokeCallback(gui, shiftIndex(gui, i), calculateIndices(gui).find(shiftIndex(gui, i))->second);
        }
    }
    return true;
}

CListView::CListView() {

}

void CListView::doShift(std::shared_ptr<CGui> gui, int val) {
    shift += val;
    if (shift < 0) {
        shift = 0;
    } else if (shift > (signed) (*invokeCollection(gui)).size() - (getSizeX(gui) * getSizeY(gui) - 2/*arrows*/)) {
        shift = (*invokeCollection(gui)).size() - (getSizeX(gui) * getSizeY(gui) - 2/*arrows*/);
    }
    refreshAll();
}

int CListView::shiftIndex(std::shared_ptr<CGui> gui, int arg) {
    if (!isOversized(gui)) {
        return arg;
    }
    return arg > getLeftArrowIndex(gui) ? arg + shift - 1 : arg + shift;
}

int CListView::getRightArrowIndex(std::shared_ptr<CGui> gui) {
    return getSizeX(gui) * getSizeY(gui) - 1;
}

int CListView::getLeftArrowIndex(std::shared_ptr<CGui> gui) {
    return getSizeX(gui) * (getSizeY(gui) - 1);
}

//TODO: maybe return collection pointer to avoid copying
std::unordered_multimap<int, std::shared_ptr<CGameObject>> CListView::calculateIndices(std::shared_ptr<CGui> gui) {
    if (grouping) {
        collection_pointer collection = invokeCollection(gui);
        vstd::list<std::shared_ptr<CGameObject>> &container = *collection;
        auto reduced =
                vstd::functional::map_reduce<std::string>(container,
                                                          [](auto ob) { return ob->getTypeId(); });

        std::unordered_multimap<int, std::shared_ptr<CGameObject>> indices;

        int i = -1;

        for (auto it:(reduced)) {
            i++;
            for (auto it2:it.second) {
                indices.insert(std::make_pair(i, it2));
            }
        }
        return indices;
    } else {
        std::unordered_multimap<int, std::shared_ptr<CGameObject>> indices;
        int i = -1;
        collection_pointer sharedPtr = invokeCollection(gui);
        for (auto it:(*sharedPtr)) {
            indices.insert(std::make_pair(++i, it));
        }
        return indices;
    }
}

std::shared_ptr<SDL_Rect>
CListView::calculateIndexPosition(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int index) {
    return RECT(
            tileSize * (index % getSizeX(gui)) + loc->x,
            tileSize * (index / getSizeX(gui)) + loc->y,
            tileSize,
            tileSize);
}

bool CListView::isOversized(std::shared_ptr<CGui> gui) {
    return allowOversize && (calculateIndices(gui)).size() > ((unsigned) getSizeX(gui) * (unsigned) getSizeY(gui));
}

//TODO: sizes should be calculated dynamically based on preferences
int CListView::getSizeX(std::shared_ptr<CGui> gui) {
    return xPrefferedSize != -1 ? xPrefferedSize : getLayout()->getRect(this->ptr<CListView>())->w / tileSize;
}

//TODO: sizes should be calculated dynamically based on preferences
int CListView::getSizeY(std::shared_ptr<CGui> gui) {
    return yPrefferedSize != -1 ? yPrefferedSize : getLayout()->getRect(this->ptr<CListView>())->h / tileSize;
}

CListView::collection_pointer CListView::invokeCollection(std::shared_ptr<CGui> gui) {
    return getParent()->meta()->invoke_method<CListView::collection_pointer, CGameGraphicsObject,
            std::shared_ptr<CGui>>(collection,
                                   vstd::cast<CGameGraphicsObject>(getParent()), gui);
}

void CListView::invokeCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    getParent()->meta()->invoke_method<void, CGameGraphicsObject,
            std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(callback,
                                                                      vstd::cast<CGameGraphicsObject>(getParent()),
                                                                      gui, i, object);
}

auto CListView::getArrowCallback(bool left) {
    return [=](std::shared_ptr<CGui> gui, SDL_EventType type,
               int button,
               int,
               int) {
        if (type == SDL_MOUSEBUTTONDOWN &&
            button == SDL_BUTTON_LEFT) {
            doShift(gui, left ? -1 : 1);
        }
        return true;
    };
}

bool CListView::invokeSelect(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    return getParent()->meta()->invoke_method<bool, CGameGraphicsObject,
            std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(select,
                                                                      vstd::cast<CGameGraphicsObject>(getParent()),
                                                                      gui, i, object);
}

std::list<std::shared_ptr<CGameGraphicsObject>>
CListView::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    std::list<std::shared_ptr<CGameGraphicsObject>> return_val;
    int i = getSizeX(gui) * y + x;
    if (i == getLeftArrowIndex(gui) && isOversized(gui)) {
        return_val.push_back(CAnimationProvider::getAnimation(gui->getGame(),
                                                              "images/arrows/left")->withCallback(
                getArrowCallback(true)));//TODO: cache
    } else if (i == getRightArrowIndex(gui) && isOversized(gui)) {
        return_val.push_back(CAnimationProvider::getAnimation(gui->getGame(),
                                                              "images/arrows/right")->withCallback(
                getArrowCallback(false)));//TODO: cache
    } else {
        auto indexedCollection = calculateIndices(gui);
        int itemIndex = shiftIndex(gui, i);

        bool isItemPresent = vstd::ctn(indexedCollection, itemIndex) && indexedCollection.find(itemIndex)->second;

        if (isItemPresent || showEmpty) {
            addItemBox(gui, return_val);
        }
        if (isItemPresent) {
            addItem(return_val, indexedCollection, itemIndex);
        }
        if (invokeSelect(gui, itemIndex,
                         isItemPresent ? indexedCollection.find(itemIndex)->second : nullptr)) {
            addSelectionBox(gui, return_val);
        }
        if (indexedCollection.count(itemIndex) > 1) {
            addCountBox(gui, indexedCollection.count(itemIndex), return_val);
        }
    }
    return return_val;
}

void CListView::addCountBox(std::shared_ptr<CGui> gui, int count,
                            std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    auto countBox = gui->getGame()->getObjectHandler()->createObject<CTextWidget>(gui->getGame());
    countBox->setText(vstd::str(count));
    auto layout = gui->getGame()->getObjectHandler()->createObject<CLayout>(gui->getGame());
    layout->setHorizontal("RIGHT");
    layout->setVertical("DOWN");
    layout->setW("10%");
    layout->setH("10%");
    countBox->setLayout(layout);
    countBox->setPriority(4);
    return_val.push_back(countBox);//TODO: cache
}

void CListView::addSelectionBox(std::shared_ptr<CGui> gui,
                                std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    auto selectionBox = gui->getGame()->getObjectHandler()->createObject<CSelectionBox>(gui->getGame());
    selectionBox->setThickness(5);
    selectionBox->setPriority(3);
    return_val.push_back(selectionBox);//TODO: cache
}

void CListView::addItem(std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                        std::unordered_multimap<int, std::shared_ptr<CGameObject>, std::hash<int>, std::equal_to<int>, std::allocator<std::pair<const int, std::shared_ptr<CGameObject>>>> indexedCollection,
                        int itemIndex) const {
    std::shared_ptr<CGameGraphicsObject> objectGraphic = indexedCollection.find(itemIndex)->second->getGraphicsObject();
    objectGraphic->setPriority(2);
    return_val.push_back(objectGraphic);
}

void
CListView::addItemBox(std::shared_ptr<CGui> gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    std::shared_ptr<CAnimation> itemBox = CAnimationProvider::getAnimation(gui->getGame(), "images/item");
    itemBox->setPriority(1);
    return_val.push_back(itemBox);//TODO: cache

}

std::string CListView::getCollection() {
    return collection;
}

void CListView::setCollection(std::string collection) {
    CListView::collection = collection;
}

std::string CListView::getCallback() {
    return callback;
}

void CListView::setCallback(std::string callback) {
    CListView::callback = callback;
}

std::string CListView::getSelect() {
    return select;
}

void CListView::setSelect(std::string select) {
    CListView::select = select;
}

std::shared_ptr<CScript> CListView::getRefreshObject() {
    return refreshObject;
}

void CListView::setRefreshObject(std::shared_ptr<CScript> refreshObject) {
    CListView::refreshObject = refreshObject;
}

std::string CListView::getRefreshEvent() {
    return refreshEvent;
}

void CListView::setRefreshEvent(std::string refreshEvent) {
    CListView::refreshEvent = refreshEvent;
}

void CListView::initialize() {
    auto self = this->ptr<CListView>();
    vstd::call_when([self]() {
                        return self->getGui() != nullptr
                               && self->getGui()->getGame() != nullptr
                               && self->getGui()->getGame()->getMap() != nullptr;
                    }, [self]() {
                        self->refreshObject->invoke(
                                self->getGui()->getGame(),
                                self)->connect(self->refreshEvent,
                                               self,
                                               "refresh");
                        self->refreshObject->invoke(
                                self->getGui()->getGame(),
                                self)->connect(self->refreshEvent,
                                               self,
                                               "refreshAll");
                        self->refresh();
                    }
    );

}

int CListView::getXPrefferedSize() const {
    return xPrefferedSize;
}

void CListView::setXPrefferedSize(int xPrefferedSize) {
    CListView::xPrefferedSize = xPrefferedSize;
}

int CListView::getYPrefferedSize() const {
    return yPrefferedSize;
}

void CListView::setYPrefferedSize(int yPrefferedSize) {
    CListView::yPrefferedSize = yPrefferedSize;
}

int CListView::getTileSize() {
    return tileSize;
}

void CListView::setTileSize(int _tileSize) {
    tileSize = _tileSize;
}

bool CListView::getAllowOversize() {
    return allowOversize;
}

void CListView::setAllowOversize(bool _allowOversize) {
    allowOversize = _allowOversize;
}


bool CListView::getShowEmpty() {
    return showEmpty;
}

void CListView::setShowEmpty(bool _showEmpty) {
    showEmpty = _showEmpty;
}

bool CListView::getGrouping() {
    return grouping;
}

void CListView::setGrouping(bool _grouping) {
    grouping = _grouping;
}


