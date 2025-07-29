/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "CTextManager.h"
#include "core/CUtil.h"

SDL_Texture *CTextManager::getTexture(const std::string &text, int width) {
  auto anim = _textures.find(std::make_pair(text, width));
  if (anim == _textures.end()) {
    _textures[std::make_pair(text, width)] = this->loadTexture(text, width);
    return getTexture(text, width);
  }
  return _textures[std::make_pair(text, width)];
}

SDL_Texture *CTextManager::loadTexture(std::string text, int width) {
  SDL_Color textColor = {255, 255, 255, 0};
  // in some sdl versions blended wrapped automatically treats 0 as not wrapper,
  // other versions fail on width=0
  SDL_Surface *surface =
      SDL_SAFE(width ? TTF_RenderText_Blended_Wrapped(font, text.c_str(),
                                                      textColor, width)
                     : TTF_RenderText_Blended(font, text.c_str(), textColor));
  auto _texture = SDL_SAFE(
      SDL_CreateTextureFromSurface(_gui.lock()->getRenderer(), surface));
  SDL_SAFE(SDL_FreeSurface(surface));
  return _texture;
}

CTextManager::CTextManager(const std::shared_ptr<CGui> &_gui) {
  SDL_SAFE(TTF_Init());
  font = SDL_SAFE(TTF_OpenFont("fonts/ampersand.ttf", 24));
  this->_gui = _gui;
}

CTextManager::~CTextManager() {
  for (auto texture : _textures) {
    SDL_SAFE(SDL_DestroyTexture(texture.second));
  }
  _textures.clear();
  SDL_SAFE(TTF_CloseFont(font));
}

int CTextManager::countLines(const std::string &text, int w) {
  SDL_Rect wrapped;
  SDL_Texture *wrappedTexture = getTexture(text, w);
  SDL_SAFE(SDL_QueryTexture(wrappedTexture, nullptr, nullptr, &wrapped.w,
                            &wrapped.h));
  SDL_Rect notWrapped;
  SDL_Texture *notWrappedTexture = getTexture(text);
  SDL_SAFE(SDL_QueryTexture(notWrappedTexture, nullptr, nullptr, &notWrapped.w,
                            &notWrapped.h));
  return wrapped.h / notWrapped.h;
}

void CTextManager::drawText(const std::string &text, int x, int y, int w) {
  if (text.length() != 0) {
    SDL_Rect actual;
    actual.x = x;
    actual.y = y;
    SDL_Texture *pTexture = getTexture(text, w);
    SDL_SAFE(
        SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
    SDL_SAFE(
        SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, nullptr, &actual));
  }
}

void CTextManager::drawTextCentered(const std::string &text, int x, int y,
                                    int w, int h) {
  if (text.length() != 0) {
    SDL_Rect actual;
    SDL_Texture *pTexture = getTexture(text, w);
    SDL_SAFE(
        SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
    auto centered =
        CUtil::boxInBox(RECT(x, y, w, h), RECT(0, 0, actual.w, actual.h));
    SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, nullptr,
                            centered.get()));
  }
}

void CTextManager::drawTextCentered(const std::string &text,
                                    const std::shared_ptr<SDL_Rect> &rect) {
  drawTextCentered(text, rect->x, rect->y, rect->w, rect->h);
}

void CTextManager::drawText(const std::string &text,
                            const std::shared_ptr<SDL_Rect> &rect) {
  drawText(text, rect->x, rect->y, rect->w);
}

std::pair<int, int> CTextManager::getTextureSize(std::string text) {
  int w = 0, h = 0;
  if (vstd::ctn(text, '\n')) {
    for (const auto &line : vstd::split(text, '\n')) {
      auto lineSize = getTextureSize(line);
      if (lineSize.first > w) {
        w = lineSize.first;
      }
      h += lineSize.second;
    }
  } else {
    SDL_Texture *pTexture = getTexture(text);
    SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &w, &h));
  }
  return std::make_pair(w, h);
}
