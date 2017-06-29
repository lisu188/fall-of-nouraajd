
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
    this->panelRender(reneder, getPanelRect(pos), frameTime);
}

void CGamePanel::panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) {

}

bool CGamePanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event->type == SDL_KEYDOWN) {
        this->panelKeyboardEvent(gui, event->key.keysym.sym);
    } else if (event->type == SDL_MOUSEBUTTONDOWN) {
        std::pair<int, int> translated = translatePos(gui, event->button.x, event->button.y);
        if (translated.first >= 0 && translated.first < xSize && translated.second >= 0 && translated.second < ySize) {
            this->panelMouseEvent(gui, translated.first, translated.second);
        }
    }
    return true;
}


std::shared_ptr<SDL_Rect> CGamePanel::getPanelRect(SDL_Rect *pos) {
    std::shared_ptr<SDL_Rect> recalc = std::make_shared<SDL_Rect>();
    recalc->x = pos->x + pos->w / 2 - this->xSize / 2;
    recalc->y = pos->y + pos->h / 2 - this->ySize / 2;
    recalc->w = xSize;
    recalc->h = ySize;
    return recalc;
}

std::pair<int, int> CGamePanel::translatePos(std::shared_ptr<CGui> gui, int x, int y) {
    SDL_Rect pos = {0, 0, gui->getWidth(), gui->getHeight()};
    std::shared_ptr<SDL_Rect> transPos = getPanelRect(&pos);
    return std::make_pair<int, int>(x - transPos->x, y - transPos->y);
}

void CGamePanel::panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) {

}

void CGamePanel::panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) {

}


CListView::CListView() {

}
