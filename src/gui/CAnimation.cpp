/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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

#include "CAnimation.h"
#include "CLayout.h"
#include "CTextManager.h"
#include "CTooltip.h"
#include "core/CProvider.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"

void CAnimation::setObject(std::shared_ptr<CGameObject> _object) { object = _object; }

void CAnimation::setOwnedObject(std::shared_ptr<CGameObject> _object) {
    ownedObject = _object;
    setObject(_object);
}

std::shared_ptr<CGameObject> CAnimation::getObject() { return object.lock(); }

void CStaticAnimation::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    auto currentObject = getObject();
    if (!currentObject) {
        return;
    }
    auto texture = gui->getTextureCache()->getTexture(currentObject->getAnimation());
    if (!texture) {
        vstd::logger::error("CStaticAnimation: missing texture", currentObject->getAnimation());
        return;
    }
    if (useColorMod) {
        SDL_SetTextureColorMod(texture, colorR, colorG, colorB);
        SDL_SetTextureAlphaMod(texture, colorA);
    }
    if (rotation == 0) {
        SDL_SAFE(SDL_RenderCopy(gui->getRenderer(), texture, nullptr, rect.get()));
    } else {
        SDL_SAFE(SDL_RenderCopyEx(gui->getRenderer(), texture, nullptr, rect.get(), rotation, nullptr, SDL_FLIP_NONE));
    }
    if (useColorMod) {
        SDL_SetTextureColorMod(texture, 255, 255, 255);
        SDL_SetTextureAlphaMod(texture, 255);
    }
}

CStaticAnimation::CStaticAnimation() {}

int CStaticAnimation::getRotation() const { return rotation; }

void CStaticAnimation::setRotation(int rotation) { CStaticAnimation::rotation = rotation; }

void CStaticAnimation::setColorMod(Uint8 r, Uint8 g, Uint8 b, Uint8 a) {
    useColorMod = true;
    colorR = r;
    colorG = g;
    colorB = b;
    colorA = a;
}

void CStaticAnimation::clearColorMod() {
    useColorMod = false;
    colorR = 255;
    colorG = 255;
    colorB = 255;
    colorA = 255;
}

CDynamicAnimation::CDynamicAnimation() {}

void CDynamicAnimation::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (initialized) {
        auto tableCalc = [this]() {
            std::vector<int> vec;
            for (int i = 0; i < size; i++) {
                if (times[i] < 0) {
                    if (i == 0) {
                        vec.push_back(vstd::rand(0, -times[i]));
                    } else {
                        vec.push_back(vec[i - 1] + vstd::rand(0, -times[i]));
                    }
                } else {
                    if (i == 0) {
                        vec.push_back(times[i]);
                    } else {
                        vec.push_back(vec[i - 1] + times[i]);
                    }
                }
            }
            return vec;
        };
        auto tab = _tables.get("table", frameTime, tableCalc);
        if (tab.empty() || tab[size - 1] <= 0) {
            return;
        }

        int animTime = int(frameTime + (_offsets.get("main", frameTime) / 100.0 * tab[size - 1])) % tab[size - 1];

        int currFrame = -1;
        for (int i = 0; i < size; i++) {
            if (animTime < tab[i]) {
                currFrame = i;
                break;
            }
        }
        auto texture = gui->getTextureCache()->getTexture(paths[currFrame]);
        if (!texture) {
            vstd::logger::error("CDynamicAnimation: missing frame", paths[currFrame]);
            return;
        }
        SDL_SAFE(SDL_RenderCopy(gui->getRenderer(), texture, nullptr, rect.get()));
    }
}

void CDynamicAnimation::initialize() {
    auto self = this->ptr<CDynamicAnimation>();
    vstd::call_when([self]() { return self->getObject() != nullptr; },
                    [self]() {
                        auto currentObject = self->getObject();
                        if (!currentObject) {
                            return;
                        }
                        std::string path = currentObject->getAnimation();
                        auto time = CConfigurationProvider::getConfig(path + "/" + "time.json");
                        if (!time || !time->is_object() || time->empty()) {
                            vstd::logger::warning("CDynamicAnimation: missing or malformed timing table", path);
                            return;
                        }
                        self->size = time->size();
                        for (int i = 0; i < self->size; i++) {
                            const auto key = std::to_string(i);
                            if (!time->contains(key) || !(*time)[key].is_number_integer()) {
                                vstd::logger::warning("CDynamicAnimation: invalid timing entry", key, "in", path);
                                self->paths.clear();
                                self->times.clear();
                                self->size = 0;
                                return;
                            }
                            const int frameTime = (*time)[key].get<int>();
                            if (frameTime == 0) {
                                vstd::logger::warning("CDynamicAnimation: zero timing entry", key, "in", path);
                                self->paths.clear();
                                self->times.clear();
                                self->size = 0;
                                return;
                            }
                            self->paths.push_back(path + "/" + key + ".png");
                            self->times.push_back(frameTime);
                        }
                        self->initialized = self->size > 0;
                    });
}

int CDynamicAnimation::get_ttl() { return vstd::rand(5000, 30000); }

int CDynamicAnimation::get_next() { return vstd::rand(0, 100); }

CAnimation::CAnimation() { setLayout(std::make_shared<CParentLayout>()); }

bool CAnimation::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    auto currentObject = getObject();
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_RIGHT) {
        if (hasCallback) {
            bool handled = callback(gui, type, button, x, y);
            if (handled) {
                return true;
            }
        }
        if (currentObject && (!currentObject->getLabel().empty() || !currentObject->getDescription().empty())) {
            std::shared_ptr<SDL_Rect> absPos = getLayout()->getRect(this->ptr<CAnimation>());
            gui->getGame()->getGuiHandler()->showTooltip(CTooltipHandler::buildTooltip(currentObject), absPos->x + x,
                                                         absPos->y + y);
        }
        return !hasCallback;
    }
    return callback(gui, type, button, x, y);
}

void CSelectionBox::setThickness(int _thickness) { this->thickness = _thickness; }

int CSelectionBox::getThickness() { return thickness; }

void CSelectionBox::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    CUtil::setRenderDrawColor(gui->getRenderer(), CColors::Yellow);
    SDL_Rect tmp = {rect->x, rect->y, thickness, rect->h};
    SDL_Rect tmp2 = {rect->x, rect->y, rect->w, thickness};
    SDL_Rect tmp3 = {rect->x, rect->y + rect->h - thickness, rect->w, thickness};
    SDL_Rect tmp4 = {rect->x + rect->w - thickness, rect->y, thickness, rect->h};
    SDL_RenderFillRect(gui->getRenderer(), &tmp);
    SDL_RenderFillRect(gui->getRenderer(), &tmp2);
    SDL_RenderFillRect(gui->getRenderer(), &tmp3);
    SDL_RenderFillRect(gui->getRenderer(), &tmp4);
}

bool CSelectionBox::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    return false;
}
