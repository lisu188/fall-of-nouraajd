
#include "CTextManager.h"
#include "core/CUtil.h"

SDL_Texture *CTextManager::getTexture(std::string text, int width) {
    auto anim = _textures.find(std::make_pair(text, width));
    if (anim == _textures.end()) {
        _textures[std::make_pair(text, width)] = this->loadTexture(text, width);
        return getTexture(text, width);
    }
    return _textures[std::make_pair(text, width)];
}

SDL_Texture *CTextManager::loadTexture(std::string text, int width) {
    SDL_Color textColor = {255, 255, 255, 0};
    SDL_Surface *surface = SDL_SAFE(TTF_RenderText_Blended_Wrapped(font, text.c_str(), textColor, width));
    auto _texture = SDL_SAFE(SDL_CreateTextureFromSurface(_gui.lock()->getRenderer(), surface));
    SDL_SAFE(SDL_FreeSurface(surface));
    return _texture;
}

CTextManager::CTextManager(std::shared_ptr<CGui> _gui) {
    SDL_SAFE(TTF_Init());
    font = SDL_SAFE(TTF_OpenFont("fonts/ampersand.ttf", 24));
    this->_gui = _gui;
}

CTextManager::~CTextManager() {
    for (auto texture:_textures) {
        SDL_SAFE(SDL_DestroyTexture(texture.second));
    }
    _textures.clear();
    SDL_SAFE(TTF_CloseFont(font));
}


void CTextManager::drawText(std::string text, int x, int y, int w) {
    if (text.length() != 0) {
        SDL_Rect actual;
        actual.x = x;
        actual.y = y;
        SDL_Texture *pTexture = getTexture(text, w);
        SDL_SAFE(SDL_QueryTexture(pTexture, NULL, NULL, &actual.w, &actual.h));
        SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, NULL, &actual));
    }
}

void CTextManager::drawTextCentered(std::string text, int x, int y, int w, int h) {
    if (text.length() != 0) {
        SDL_Rect actual;
        SDL_Texture *pTexture = getTexture(text);
        SDL_SAFE(SDL_QueryTexture(pTexture, NULL, NULL, &actual.w, &actual.h));
        actual = CUtil::boxInBox(SDL_Rect{x, y, w, h}, &actual);
        SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, NULL, &actual));
    }
}