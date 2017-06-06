
#include "CGamePanel.h"
#include "gui/CGui.h"

std::string CGameTextPanel::getText() {
    return text;
}

void CGameTextPanel::setText(std::string _text) {
    text = _text;
}

void CGameTextPanel::panelRender(std::shared_ptr<CGui> gui, SDL_Rect *pRect, int i, std::string basic_string) {
    if (texture == nullptr) {
        texture = loadTextTexture(gui);
    }
    SDL_Rect actual;
    actual.x = pRect->x;
    actual.y = pRect->y;
    SDL_QueryTexture(texture, NULL, NULL, &actual.w, &actual.h);
    SDL_RenderFillRect(gui->getRenderer(), pRect);
    SDL_RenderCopy(gui->getRenderer(), texture, NULL, &actual);
}

SDL_Texture *CGameTextPanel::loadTextTexture(std::shared_ptr<CGui> ptr) {
    TTF_Init();
    TTF_Font *font = TTF_OpenFont("fonts/ampersand.ttf", 24);
    SDL_Color textColor = {255, 255, 255, 0};
    SDL_Surface *surface = TTF_RenderText_Blended_Wrapped(font, text.c_str(), textColor, this->getXSize());
    auto _texture = SDL_CreateTextureFromSurface(ptr->getRenderer(), surface);
    SDL_FreeSurface(surface);
    return _texture;
}

void CGameTextPanel::panelEvent(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event->type == SDL_KEYDOWN && event->key.keysym.sym == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameTextPanel>());
    }
}


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

void CGamePanel::render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime, std::string object) {
    SDL_Rect recalc;
    recalc.x = pos->x + pos->w / 2 - this->xSize / 2;
    recalc.y = pos->y + pos->h / 2 - this->ySize / 2;
    recalc.w = xSize;
    recalc.h = ySize;
    this->panelRender(reneder, &recalc, frameTime, object);
}

void CGamePanel::panelRender(std::shared_ptr<CGui> shared_ptr, SDL_Rect *pRect, int i, std::string basic_string) {

}

bool CGamePanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    this->panelEvent(gui, event);
    return true;
}

void CGamePanel::panelEvent(std::shared_ptr<CGui> gui, SDL_Event *pEvent) {

}


