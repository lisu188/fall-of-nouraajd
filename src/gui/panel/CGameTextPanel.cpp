

#include "CGameTextPanel.h"
#include "gui/CGui.h"

std::string CGameTextPanel::getText() {
    return text;
}

void CGameTextPanel::setText(std::string _text) {
    text = _text;
}

void CGameTextPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    if (texture == nullptr) {
        texture = loadTextTexture(gui);
    }
    SDL_Rect actual;
    actual.x = pRect->x;
    actual.y = pRect->y;
    SDL_QueryTexture(texture, NULL, NULL, &actual.w, &actual.h);
    SDL_RenderCopy(gui->getRenderer(), texture, NULL, &actual);
}

struct SDL_Texture *CGameTextPanel::loadTextTexture(std::shared_ptr<CGui> ptr) {
    TTF_Init();
    struct _TTF_Font *font = TTF_OpenFont("fonts/ampersand.ttf", 24);
    SDL_Color textColor = {255, 255, 255, 0};
    SDL_Surface *surface = TTF_RenderText_Blended_Wrapped(font, text.c_str(), textColor, this->getXSize());
    auto _texture = SDL_CreateTextureFromSurface(ptr->getRenderer(), surface);
    SDL_FreeSurface(surface);
    return _texture;
}

void CGameTextPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameTextPanel>());
    }
}