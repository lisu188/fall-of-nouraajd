

#include "core/CJsonUtil.h"
#include "CGameCharacterPanel.h"


void CGameCharacterPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    if (texture == nullptr) {
        texture = loadTextTexture(gui);
    }
    SDL_Rect actual;
    actual.x = pRect->x;
    actual.y = pRect->y;
    SDL_QueryTexture(texture, NULL, NULL, &actual.w, &actual.h);
    SDL_RenderCopy(gui->getRenderer(), texture, NULL, &actual);
}

struct SDL_Texture *CGameCharacterPanel::loadTextTexture(std::shared_ptr<CGui> ptr) {
    TTF_Init();
    struct _TTF_Font *font = TTF_OpenFont("fonts/ampersand.ttf", 24);
    SDL_Color textColor = {255, 255, 255, 0};
    std::string text = JSONIFY_STYLED(ptr->getGame()->getMap()->getPlayer());
    SDL_Surface *surface = TTF_RenderText_Blended_Wrapped(font, text.c_str(), textColor, this->getXSize());
    auto _texture = SDL_CreateTextureFromSurface(ptr->getRenderer(), surface);
    SDL_FreeSurface(surface);
    TTF_CloseFont(font);
    return _texture;
}

void CGameCharacterPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameCharacterPanel>());
    }
}

CGameCharacterPanel::~CGameCharacterPanel() {
    SDL_DestroyTexture(texture);
}