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

#include "gui/CTextureCache.h"

template<typename Collection>
class CListView : public std::enable_shared_from_this<CListView<Collection>> {
    typedef typename Collection::value_type Item;

    std::function<Collection(std::shared_ptr<CGui>)> collection;

    std::function<int(Item, int)> index;

    std::function<void(std::shared_ptr<CGui>, int, Item)> callback;

    std::function<void(std::shared_ptr<CGui> gui, Item, std::shared_ptr<SDL_Rect> loc, int frameTime)> draw;

    std::function<bool(std::shared_ptr<CGui> gui, int, Item)> select;

    int xSize, ySize;

    int tileSize;

    bool allowOversize;

    int selectionThickness;

    int shift = 0;

public:

    CListView(int xSize,
              int ySize,
              int tileSize,
              bool allowOversize,
              int selectionThickness) : xSize(xSize),
                                        ySize(ySize),
                                        tileSize(tileSize),
                                        allowOversize(allowOversize),
                                        selectionThickness(selectionThickness) {
        index = &defaultIndex;
        draw = &defaultDraw;
    }


    void drawCollection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) {
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
                if (select(gui, itemIndex, indexedCollection[itemIndex])) {
                    drawSelection(gui, pos, selectionThickness);
                }
            }
        }
    }


    void onClicked(std::shared_ptr<CGui> gui, int x, int y) {
        int i = ((x) / tileSize + ((y / tileSize) * xSize));

        if (i == getLeftArrowIndex() && isOversized(gui)) {
            doShift(gui, -1);
        } else if (i == getRightArrowIndex() && isOversized(gui)) {
            doShift(gui, 1);
        } else {
            callback(gui, shiftIndex(gui, i), calculateIndices(gui)[shiftIndex(gui, i)]);
        }
    }



    //builder methods

    std::shared_ptr<CListView> withCollection(std::function<Collection(std::shared_ptr<CGui>)> collection) {
        this->collection = collection;
        return this->shared_from_this();
    }

    std::shared_ptr<CListView> withIndex(std::function<int(Item, int)> index) {
        this->index = index;
        return this->shared_from_this();
    }

    std::shared_ptr<CListView> withCallback(std::function<void(std::shared_ptr<CGui>, int, Item)> callback) {
        this->callback = callback;
        return this->shared_from_this();
    }

    std::shared_ptr<CListView>
    withDraw(std::function<void(std::shared_ptr<CGui> gui, Item, std::shared_ptr<SDL_Rect> loc, int frameTime)> draw) {
        this->draw = draw;
        return this->shared_from_this();
    }

    std::shared_ptr<CListView> withSelect(std::function<bool(std::shared_ptr<CGui> gui, int, Item)> select) {
        this->select = select;
        return this->shared_from_this();
    }

    static int defaultIndex(Item ob, int prevIndex) {
        return prevIndex + 1;
    };

    static void defaultDraw(std::shared_ptr<CGui> gui, Item item, std::shared_ptr<SDL_Rect> loc, int frameTime) {
        _defaultDraw(gui, item, loc, frameTime);
    };

private:
    void doShift(std::shared_ptr<CGui> gui, int val) {
        shift += val;
        if (shift < 0) {
            shift = 0;
        } else if (shift > (signed) collection(gui).size() - (xSize * ySize - 2/*arrows*/)) {
            shift = collection(gui).size() - (xSize * ySize - 2/*arrows*/);
        }
    }

    template<typename T=Item>
    static void _defaultDraw(std::shared_ptr<CGui> gui, T item, std::shared_ptr<SDL_Rect> loc, int frameTime,
                             typename vstd::enable_if<vstd::is_shared_ptr<T>::value>::type * = 0) {
        item->getAnimationObject()->render(gui, loc, frameTime);
    }

    template<typename T=Item>
    static void _defaultDraw(std::shared_ptr<CGui> gui, T item, std::shared_ptr<SDL_Rect> loc, int frameTime,
                             typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type * = 0) {

    }

    void drawSelection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> location, int thickness) {
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


    int shiftIndex(std::shared_ptr<CGui> gui, int arg) {
        if (!isOversized(gui)) {
            return arg;
        }
        return arg > getLeftArrowIndex() ? arg + shift - 1 : arg + shift;
    }

    int getRightArrowIndex() {
        return xSize * ySize - 1;
    }

    int getLeftArrowIndex() {
        return xSize * (ySize - 1);
    }

//TODO: do not generate whole map, instead add callback arguement and stop when met
    auto calculateIndices(std::shared_ptr<CGui> gui) {
        std::unordered_map<int, Item> indices;
        int i = -1;
        for (auto it:collection(gui)) {
            i = index(it, i);
            indices.insert(std::make_pair(i, it));
        }
        return indices;
    }

    std::shared_ptr<SDL_Rect>
    calculateIndexPosition(std::shared_ptr<SDL_Rect> loc, int index) {
        return RECT(
                tileSize * (index % xSize) + loc->x,
                tileSize * (index / xSize) + loc->y,
                tileSize,
                tileSize);
    }


    void drawItemBox(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc) {
        SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/item.png"), nullptr,
                       loc.get());
    }


    void drawArrowLeft(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc) {
        SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/arrows/left.png"), nullptr,
                       loc.get());
    }


    void drawArrowRight(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc) {
        SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/arrows/right.png"), nullptr,
                       loc.get());
    }

//TODO: cache method calls // note to self, seems like no performance impact, even in debug
    bool isOversized(std::shared_ptr<CGui> gui) {
        return allowOversize && collection(gui).size() > ((unsigned) xSize * (unsigned) ySize);
    }
};


