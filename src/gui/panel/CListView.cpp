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

void CListView::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) {
    auto indexedCollection = calculateIndices(gui);
    for (int i = 0; i < xSize * ySize; i++) {
        auto pos = calculateIndexPosition(loc, i);
        if (i == getLeftArrowIndex() && isOversized(gui)) {
            drawArrowLeft(gui, pos);
        } else if (i == getRightArrowIndex() && isOversized(gui)) {
            drawArrowRight(gui, pos);
        } else {
            int itemIndex = shiftIndex(gui, i);
            drawItemBox(gui, pos);
            if (vstd::ctn(indexedCollection, itemIndex)) {
                draw(gui, indexedCollection[itemIndex], pos, frameTime);
            }
            if (invokeSelect(gui, itemIndex, indexedCollection[itemIndex])) {
                drawSelection(gui, pos, selectionThickness);
            }
        }
    }
}

bool CListView::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y) {
    int i = ((x) / tileSize + ((y / tileSize) * xSize));

    if (i == getLeftArrowIndex() && isOversized(gui)) {
        doShift(gui, -1);
    } else if (i == getRightArrowIndex() && isOversized(gui)) {
        doShift(gui, 1);
    } else {
        invokeCallback(gui, shiftIndex(gui, i), calculateIndices(gui)[shiftIndex(gui, i)]);
    }
    return true;
}

CListView::CListView(int xSize, int ySize, int tileSize, bool allowOversize, int selectionThickness) : xSize(xSize),
                                                                                                       ySize(ySize),
                                                                                                       tileSize(
                                                                                                               tileSize),
                                                                                                       allowOversize(
                                                                                                               allowOversize),
                                                                                                       selectionThickness(
                                                                                                               selectionThickness) {
    index = &defaultIndex;
    draw = &defaultDraw;
}

int CListView::defaultIndex(std::shared_ptr<CGameObject> ob, int prevIndex) {
    return prevIndex + 1;
}

void CListView::defaultDraw(std::shared_ptr<CGui> gui, std::shared_ptr<CGameObject> item, std::shared_ptr<SDL_Rect> loc,
                            int frameTime) {
    item->getGraphicsObject()->renderObject(gui, loc, frameTime);
}

void CListView::doShift(std::shared_ptr<CGui> gui, int val) {
    shift += val;
    if (shift < 0) {
        shift = 0;
    } else if (shift > (signed) invokeCollection(gui).size() - (xSize * ySize - 2/*arrows*/)) {
        shift = invokeCollection(gui).size() - (xSize * ySize - 2/*arrows*/);
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
    return arg > getLeftArrowIndex() ? arg + shift - 1 : arg + shift;
}

int CListView::getRightArrowIndex() {
    return xSize * ySize - 1;
}

int CListView::getLeftArrowIndex() {
    return xSize * (ySize - 1);
}

std::unordered_map<int, std::shared_ptr<CGameObject>> CListView::calculateIndices(std::shared_ptr<CGui> gui) {
    std::unordered_map<int, std::shared_ptr<CGameObject>> indices;
    int i = -1;
    for (auto it:invokeCollection(gui)) {
        i = index(it, i);
        indices.insert(std::make_pair(i, it));
    }
    return indices;
}

std::shared_ptr<SDL_Rect> CListView::calculateIndexPosition(std::shared_ptr<SDL_Rect> loc, int index) {
    return RECT(
            tileSize * (index % xSize) + loc->x,
            tileSize * (index / xSize) + loc->y,
            tileSize,
            tileSize);
}

void CListView::drawItemBox(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/item.png"), nullptr,
                   loc.get());
}

void CListView::drawArrowLeft(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/arrows/left.png"), nullptr,
                   loc.get());
}

void CListView::drawArrowRight(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/arrows/right.png"), nullptr,
                   loc.get());
}

bool CListView::isOversized(std::shared_ptr<CGui> gui) {
    return allowOversize && invokeCollection(gui).size() > ((unsigned) xSize * (unsigned) ySize);
}
