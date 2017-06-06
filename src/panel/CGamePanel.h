#pragma once

#include "gui/CGameGraphicsObject.h"

class CGamePanel : public CGameGraphicsObject {
V_META(CGamePanel, CGameGraphicsObject,
       V_PROPERTY(CGamePanel, int, xSize, getXSize, setXSize),
       V_PROPERTY(CGamePanel, int, ySize, getYSize, setYSize))
public:
    int getXSize();

    void setXSize(int _xSize);

    int getYSize();

    void setYSize(int _ySize);

    void render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime, std::string object) override final;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

private:
    int xSize = 800;
    int ySize = 600;

    virtual void panelRender(std::shared_ptr<CGui> shared_ptr, SDL_Rect *pRect, int i, std::string basic_string);

    virtual void panelEvent(std::shared_ptr<CGui> gui, SDL_Event *pEvent);
};

