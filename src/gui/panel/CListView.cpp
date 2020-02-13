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
#include "gui/object/CProxyGraphicsObject.h"
#include "CListView.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include "gui/CLayout.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "handler/CEventHandler.h"

void CListView::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) {

}

bool CListView::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {//TODO: separate to objects
        int i = ((x) / gui->getTileSize() + ((y / gui->getTileSize()) * getSizeX(gui)));

        if (i == getLeftArrowIndex(gui) && isOversized(gui)) {
            doShift(gui, -1);
        } else if (i == getRightArrowIndex(gui) && isOversized(gui)) {
            doShift(gui, 1);
        } else {
            invokeCallback(gui, shiftIndex(gui, i), calculateIndices(gui)[shiftIndex(gui, i)]);
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
}

void CListView::drawSelection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> location, int thickness) {
    SDL_SetRenderDrawColor(gui->getRenderer(), YELLOW);
    SDL_Rect tmp = {location->x, location->y, thickness, location->h};
    SDL_Rect tmp2 = {location->x, location->y, location->w, thickness};
    SDL_Rect tmp3 = {location->x, location->y + location->h - thickness, location->w,
                     thickness};
    SDL_Rect tmp4 = {location->x + location->w - thickness, location->y, thickness,
                     location->h};
    SDL_RenderFillRect(gui->getRenderer(), &tmp);
    SDL_RenderFillRect(gui->getRenderer(), &tmp2);
    SDL_RenderFillRect(gui->getRenderer(), &tmp3);
    SDL_RenderFillRect(gui->getRenderer(), &tmp4);
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

std::unordered_map<int, std::shared_ptr<CGameObject>> CListView::calculateIndices(std::shared_ptr<CGui> gui) {
    std::unordered_map<int, std::shared_ptr<CGameObject>> indices;
    int i = -1;
    for (auto it:(*invokeCollection(gui))) {
        indices.insert(std::make_pair(++i, it));
    }
    return indices;
}

std::shared_ptr<SDL_Rect>
CListView::calculateIndexPosition(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int index) {
    return RECT(
            gui->getTileSize() * (index % getSizeX(gui)) + loc->x,
            gui->getTileSize() * (index / getSizeX(gui)) + loc->y,
            gui->getTileSize(),
            gui->getTileSize());
}

bool CListView::isOversized(std::shared_ptr<CGui> gui) {
    return allowOversize && (*invokeCollection(gui)).size() > ((unsigned) getSizeX(gui) * (unsigned) getSizeY(gui));
}

int CListView::getSizeX(std::shared_ptr<CGui> gui) {
    return getLayout()->getRect(this->ptr<CListView>())->w / gui->getTileSize();
}

int CListView::getSizeY(std::shared_ptr<CGui> gui) {
    return getLayout()->getRect(this->ptr<CListView>())->h / gui->getTileSize();
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

bool CListView::invokeSelect(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    return getParent()->meta()->invoke_method<bool, CGameGraphicsObject,
            std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(select,
                                                                      vstd::cast<CGameGraphicsObject>(getParent()),
                                                                      gui, i, object);
}

std::set<std::shared_ptr<CGameGraphicsObject>>
CListView::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    std::set<std::shared_ptr<CGameGraphicsObject>> return_val;
    int i = getSizeX(gui) * y + x;
    if (i == getLeftArrowIndex(gui) && isOversized(gui)) {
        return_val.insert(CAnimationProvider::getAnimation(gui->getGame(), "images/arrows/left"));//TODO: cache
    } else if (i == getRightArrowIndex(gui) && isOversized(gui)) {
        return_val.insert(CAnimationProvider::getAnimation(gui->getGame(), "images/arrows/right"));//TODO: cache
    } else {
        auto indexedCollection = calculateIndices(gui);
        int itemIndex = shiftIndex(gui, i);
        return_val.insert(CAnimationProvider::getAnimation(gui->getGame(), "images/item"));//TODO: cache
        if (vstd::ctn(indexedCollection, itemIndex) && indexedCollection[itemIndex]) {
            return_val.insert(indexedCollection[itemIndex]->getGraphicsObject());
        }
        if (invokeSelect(gui, itemIndex, indexedCollection[itemIndex])) {
            //TODO:  drawSelection(gui, rect, selectionThickness);
        }
    }
    return return_val;
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

std::string CListView::getRefreshObject() {
    return refreshObject;
}

void CListView::setRefreshObject(std::string refreshObject) {
    CListView::refreshObject = refreshObject;
}

std::string CListView::getRefreshEvent() {
    return refreshEvent;
}

void CListView::setRefreshEvent(std::string refreshEvent) {
    CListView::refreshEvent = refreshEvent;
}

void CListView::initialize() {
    vstd::cast<CGui>(getTopParent())->getGame()->getMap()->getObjectByName(refreshObject)->connect(refreshEvent,
                                                                                                   this->ptr<CListView>(),
                                                                                                   "refresh");
}
