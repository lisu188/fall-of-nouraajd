
#include "CGamePanel.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"

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

void CGamePanel::drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location, int thickness) {
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

void CGamePanel::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    std::shared_ptr < SDL_Rect > rect = getPanelRect(pos);
    SDL_RenderFillRect(gui->getRenderer(), rect.get());
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/panel.png"), nullptr, rect.get());
    this->panelRender(gui, rect, frameTime);
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

void CGamePanel::drawItemBox(std::shared_ptr<CGui> gui, SDL_Rect *location)  {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/item.png"), nullptr,
                   location);
}

void CGamePanel::drawArrowLeft(std::shared_ptr<CGui> gui, SDL_Rect *location) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/arrows/left.png"), nullptr,
                   location);
}


void CGamePanel::drawArrowRight(std::shared_ptr<CGui> gui, SDL_Rect *location) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/arrows/right.png"), nullptr,
                   location);
}

