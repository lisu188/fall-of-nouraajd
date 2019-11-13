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

class CListView : public CGameGraphicsObject {
    std::function<std::set<std::shared_ptr<CGameObject>>(std::shared_ptr<CGui>)> collection;

    std::function<int(std::shared_ptr<CGameObject>, int)> index;

    std::function<void(std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>)> callback;

    std::function<void(std::shared_ptr<CGui> gui, std::shared_ptr<CGameObject>, std::shared_ptr<SDL_Rect> loc,
                       int frameTime)> draw;

    std::function<bool(std::shared_ptr<CGui> gui, int, std::shared_ptr<CGameObject>)> select;

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
              int selectionThickness);


    void drawCollection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime);

    void onClicked(std::shared_ptr<CGui> gui, int x, int y);

    //builder methods
    std::shared_ptr<CListView>
    withCollection(std::function<std::set<std::shared_ptr<CGameObject>>(std::shared_ptr<CGui>)> collection);

    std::shared_ptr<CListView> withIndex(std::function<int(std::shared_ptr<CGameObject>, int)> index);

    std::shared_ptr<CListView>
    withCallback(std::function<void(std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>)> callback);

    std::shared_ptr<CListView>
    withDraw(std::function<void(std::shared_ptr<CGui> gui, std::shared_ptr<CGameObject>, std::shared_ptr<SDL_Rect> loc,
                                int frameTime)> draw);

    std::shared_ptr<CListView>
    withSelect(std::function<bool(std::shared_ptr<CGui> gui, int, std::shared_ptr<CGameObject>)> select);

    static int defaultIndex(std::shared_ptr<CGameObject> ob, int prevIndex);;

    static void defaultDraw(std::shared_ptr<CGui> gui, std::shared_ptr<CGameObject> item, std::shared_ptr<SDL_Rect> loc,
                            int frameTime);;

private:
    void doShift(std::shared_ptr<CGui> gui, int val);

    template<typename T=std::shared_ptr<CGameObject>>
    static void _defaultDraw(std::shared_ptr<CGui> gui, T item, std::shared_ptr<SDL_Rect> loc, int frameTime,
                             typename vstd::enable_if<vstd::is_shared_ptr<T>::value>::type * = 0) {
        item->getGraphicsObject()->renderObject(gui, loc, frameTime);
    }

    template<typename T=std::shared_ptr<CGameObject>>
    static void _defaultDraw(std::shared_ptr<CGui> gui, T item, std::shared_ptr<SDL_Rect> loc, int frameTime,
                             typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type * = 0) {

    }

    void drawSelection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> location, int thickness);

    int shiftIndex(std::shared_ptr<CGui> gui, int arg);

    int getRightArrowIndex();

    int getLeftArrowIndex();

//TODO: do not generate whole map, instead add callback arguement and stop when met
    std::unordered_map<int, std::shared_ptr<CGameObject>> calculateIndices(std::shared_ptr<CGui> gui);

    std::shared_ptr<SDL_Rect>
    calculateIndexPosition(std::shared_ptr<SDL_Rect> loc, int index);


    void drawItemBox(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);


    void drawArrowLeft(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);


    void drawArrowRight(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);

//TODO: cache method calls // note to self, seems like no performance impact, even in debug
    bool isOversized(std::shared_ptr<CGui> gui);
};


