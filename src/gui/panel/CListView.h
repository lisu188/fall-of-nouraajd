#pragma once

#include "gui/CTextureCache.h"

//TODO: implement locking scrolling on edges and make in on/off
template<typename Collection>
class CListView {
    std::function<Collection(std::shared_ptr<CGui>)> collection;

    std::function<int(typename Collection::value_type, int)> index;

    std::function<void(std::shared_ptr<CGui>, typename Collection::value_type)> callback;

    int xSize, ySize;

    bool allowOversize;

    int tileSize;

    int shift = 0;

public:

    CListView(int xSize, int ySize,
              std::function<Collection(std::shared_ptr<CGui>)> collection,
              std::function<int(typename Collection::value_type, int)> index,
              std::function<void(std::shared_ptr<CGui>, typename Collection::value_type)> callback,
              int tileSize,
              bool allowOversize) : xSize(xSize),
                                    ySize(ySize),
                                    collection(collection),
                                    index(index),
                                    callback(callback),
                                    tileSize(tileSize),
                                    allowOversize(allowOversize) {

    }


    template<typename Draw, typename SelectionPredicate>
    void drawCollection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc,
                        Draw draw, SelectionPredicate selPred,
                        int thickness) {
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
                draw(indexedCollection[itemIndex], pos);
                if (selPred(indexedCollection[itemIndex])) {
                    drawSelection(gui, pos, thickness);
                }
            }
        }
    }


    void onClicked(std::shared_ptr<CGui> gui, int x, int y) {
        int i = ((x) / tileSize + ((y / tileSize) * xSize));

        if (i == getLeftArrowIndex() && isOversized(gui)) {
            shift += -1;
        } else if (i == getRightArrowIndex() && isOversized(gui)) {
            shift -= 1;
        } else {
            callback(gui, calculateIndices(gui)[shiftIndex(gui, i)]);
        }
    }

    //TODO: consider making private
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

private:
    int shiftIndex(std::shared_ptr<CGui> gui, int arg) {
        int i = arg + shift;
        return !isOversized(gui) ? i : (i > getLeftArrowIndex() ? i - 1 : i);
    }

    int getRightArrowIndex() {
        return xSize * ySize - 1;
    }

    int getLeftArrowIndex() {
        return (xSize - 1) * ySize + 1;
    }

    //TODO: do not generate whole map, instead add callback arguement and stop when met
    auto calculateIndices(std::shared_ptr<CGui> gui) {
        std::unordered_map<int, typename Collection::value_type> indices;
        int i = -1;
        for (auto it:collection(gui)) {
            i = index(it, i);
            indices.insert(std::make_pair(i, it));
        }
        return indices;
    }

    std::shared_ptr<SDL_Rect>
    calculateIndexPosition(std::shared_ptr<SDL_Rect> loc, int index) {
        auto location = std::make_shared<SDL_Rect>();
        location->x = tileSize * (index % xSize) + loc->x;
        location->y = tileSize * (index / xSize) + loc->y;
        location->w = tileSize;
        location->h = tileSize;
        return location;
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

    //TODO: cache method calls
    bool isOversized(std::shared_ptr<CGui> gui) {
        return allowOversize && collection(gui).size() > ((unsigned) xSize * (unsigned) ySize);
    }
};


