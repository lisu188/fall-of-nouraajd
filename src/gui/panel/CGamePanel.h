#pragma once


#include <Python-ast.h>
#include "gui/object/CGameGraphicsObject.h"
#include "gui/CGui.h"

#define OVERSIZED() isOversized(gui, collection, xSize, ySize, allowOversize)

class CGamePanel : public CGameGraphicsObject {
V_META(CGamePanel, CGameGraphicsObject,
       V_PROPERTY(CGamePanel, int, xSize, getXSize, setXSize),
       V_PROPERTY(CGamePanel, int, ySize, getYSize, setYSize))
public:
    int getXSize();

    void setXSize(int _xSize);

    int getYSize();

    void setYSize(int _ySize);

    void render(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> pos, int frameTime) override final;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

    std::pair<int, int> translatePos(std::shared_ptr<CGui> gui, int x, int y);;

    std::shared_ptr<SDL_Rect> getPanelRect(std::shared_ptr<SDL_Rect> pos);;
protected:
    //TODO: refactor, maybe separate util or create view class to hold all the data
    template<typename Collection, typename Index, typename Draw, typename SelectionPredicate, typename DrawSelection>
    void drawCollection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, Collection collection, int xSize,
                        int ySize, int tileSize,
                        Index index, Draw draw, SelectionPredicate selPred, DrawSelection drawSelection,
                        int thickness, bool allowOversize = false) {


        auto indexedCollection = calculateIndices(collection(), index);


        for (int i = 0; i < xSize * ySize; i++) {
            auto pos = calculateIndexPosition(loc, i, xSize, ySize, tileSize);
            if (i == getLeftArowIndex(xSize, ySize) && OVERSIZED()) {
                drawArrowLeft(gui, pos);
            } else if (i == getRightArrowIndex(xSize, ySize) && OVERSIZED()) {
                drawArrowRight(gui, pos);
            } else {
                int itemIndex = !OVERSIZED() ? i : (i > getLeftArowIndex(xSize, ySize) ? i - 1 : i);
                drawItemBox(gui, pos);
                draw(indexedCollection[itemIndex], pos);
                if (selPred(indexedCollection[itemIndex])) {
                    drawSelection(gui, pos, thickness);
                }
            }
        }
    }

    int getRightArrowIndex(int xSize, int ySize) const { return xSize * ySize - 1; }

    int getLeftArowIndex(int xSize, int ySize) const { return (xSize - 1) * ySize + 1; }

    template<typename Collection, typename Index>
    auto calculateIndices(Collection collection, Index index) const {
        std::unordered_map<int, typename Collection::value_type> indices;
        int i = -1;
        for (auto it:collection) {
            i = index(it, i);
            indices.insert(std::make_pair(i, it));
        }
        return indices;
    }

    std::shared_ptr<SDL_Rect>
    calculateIndexPosition(std::shared_ptr<SDL_Rect> loc, int index, int xSize, int ySize, int tileSize) {
        auto location = std::make_shared<SDL_Rect>();
        location->x = tileSize * (index % xSize) + loc->x;
        location->y = tileSize * (index / xSize) + loc->y;
        location->w = tileSize;
        location->h = tileSize;
        return location;
    }

    void drawItemBox(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);

    void drawArrowLeft(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);

    void drawArrowRight(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc);

    template<typename Collection, typename Index, typename Callback>
    void
    onClicked(Collection collection, int x, int y, int xSize, int ySize, int tileSize, Index index, Callback callback) {
        int i = ((x) / tileSize + ((y / tileSize) * xSize));
        int prevIndex = -1;
        for (auto it:collection()) {
            prevIndex = index(it, prevIndex);
            //TODO: correct indexing
            //TODO: add shift index
            if (i == prevIndex) {
                callback(it);
                break;
            }
        }
    }


    void drawSelection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> location, int thickness);

    virtual void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i);

    virtual void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i);

    virtual void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y);

private:
    template<typename T>
    bool isOversized(std::shared_ptr<CGui> gui, T t, int xSize, int ySize, bool allowOversize) {
        return allowOversize && t().size() > ((unsigned) xSize * (unsigned) ySize);
    }

    int xSize = 800;
    int ySize = 600;
};

#undef OVERSIZED