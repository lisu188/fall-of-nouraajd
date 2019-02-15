#pragma once


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

    void render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime) override final;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

    std::pair<int, int> translatePos(std::shared_ptr<CGui> gui, int x, int y);;

    std::shared_ptr<SDL_Rect> getPanelRect(SDL_Rect *pos);;
protected:
    template<typename Collection, typename Index, typename Draw, typename SelectionPredicate, typename DrawSelection>
    void drawCollection(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, Collection collection, int xSize,
                        int ySize, int tileSize,
                        Index index, Draw draw, SelectionPredicate selPred, DrawSelection drawSelection,
                        int thickness, bool allowOversize = false) {
        int i = -1;
        if (OVERSIZED()) {
            SDL_Rect location;
            location.x = loc->x;
            location.y = tileSize * (ySize - 1) + loc->y;
            location.w = tileSize;
            location.h = tileSize;
            drawArrowLeft(gui, &location);

            location.x = tileSize * (xSize - 1) + loc->x;
            location.y = tileSize * (ySize - 1) + loc->y;
            location.w = tileSize;
            location.h = tileSize;
            drawArrowRight(gui, &location);
        }
        for (auto it:collection()) {
            i = index(it, i);
            SDL_Rect location;
            location.x = tileSize * (i % xSize) + loc->x;
            location.y = tileSize * (i / xSize) + loc->y;
            location.w = tileSize;
            location.h = tileSize;
            drawItemBox(gui, &location);
            draw(it, &location);
            if (selPred(it)) {
                drawSelection(gui, &location, thickness);
            }
        }
    }

    void drawItemBox(std::shared_ptr<CGui> gui, SDL_Rect *location);

    void drawArrowLeft(std::shared_ptr<CGui> gui, SDL_Rect *location);

    void drawArrowRight(std::shared_ptr<CGui> gui, SDL_Rect *location);

    template<typename Collection, typename Index, typename Callback>
    void
    onClicked(Collection collection, int x, int y, int xSize, int ySize, int tileSize, Index index, Callback callback) {
        int i = ((x) / tileSize + ((y / tileSize) * xSize));
        int prevIndex = -1;
        for (auto it:collection()) {
            prevIndex = index(it, prevIndex);
            if (i == prevIndex) {
                callback(it);
                break;
            }
        }
    }


    void drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location, int thickness);

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