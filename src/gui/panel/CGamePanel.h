#pragma once

#include "gui/object/CGameGraphicsObject.h"

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
    template<typename Collection, typename Index, typename Draw>
    void drawCollection(std::shared_ptr<SDL_Rect> loc, Collection collection, int xSize, int ySize, int tileSize,
                        Index index, Draw draw) {
        int i = -1;
        for (auto it:collection()) {
            i = index(it, i);
            SDL_Rect location;
            location.x = tileSize * (i % xSize) + loc->x;
            location.y = tileSize * (i / xSize) + loc->y;
            location.w = tileSize;
            location.h = tileSize;
            draw(it, &location);
        }
    }

    virtual void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i);

    virtual void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i);

    virtual void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y);

private:
    int xSize = 800;
    int ySize = 600;
};

