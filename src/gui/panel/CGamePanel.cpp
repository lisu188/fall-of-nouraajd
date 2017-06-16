
#include "CGamePanel.h"
#include "gui/CGui.h"


int CGamePanel::getXSize() {
    return xSize;
}

void CGamePanel::setXSize(int _xSize) {
    xSize = _xSize;
}

int CGamePanel::getYSize() {
    return ySize;
}

void CGamePanel::setYSize(int _ySize) {
    ySize = _ySize;
}

void CGamePanel::render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime) {
    SDL_Rect recalc;
    recalc.x = pos->x + pos->w / 2 - this->xSize / 2;
    recalc.y = pos->y + pos->h / 2 - this->ySize / 2;
    recalc.w = xSize;
    recalc.h = ySize;
    this->panelRender(reneder, &recalc, frameTime);
}

void CGamePanel::panelRender(std::shared_ptr<CGui> shared_ptr, SDL_Rect *pRect, int i) {

}

bool CGamePanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    this->panelEvent(gui, event);
    return true;
}

void CGamePanel::panelEvent(std::shared_ptr<CGui> gui, SDL_Event *pEvent) {

}


