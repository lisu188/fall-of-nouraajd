/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "core/CProvider.h"
#include "CAnimation.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include "CLayout.h"


void CAnimation::setObject(std::shared_ptr<CGameObject> _object) {
    object = _object;
}

std::shared_ptr<CGameObject> CAnimation::getObject() {
    return object.lock();
}

void CStaticAnimation::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    SDL_SAFE(
            SDL_RenderCopy(gui->getRenderer(),
                           gui->getTextureCache()->getTexture(object.lock()->getAnimation()),
                           nullptr,
                           rect.get()));
}


CStaticAnimation::CStaticAnimation() {

}

CDynamicAnimation::CDynamicAnimation() {

}

void CDynamicAnimation::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    initialize();
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

    int animTime = int(frameTime + (_offsets.get("main", frameTime) / 100.0 * tab[size - 1])) % tab[size - 1];

    int currFrame = -1;
    for (int i = 0; i < size; i++) {
        if (animTime < tab[i]) {
            currFrame = i;
            break;
        }
    }
    SDL_SAFE(SDL_RenderCopy(gui->getRenderer(),
                            gui->getTextureCache()->getTexture(paths[currFrame]),
                            nullptr,
                            rect.get()));
}

void CDynamicAnimation::initialize() {
    if (!initialized) {
        std::string path = object.lock()->getAnimation();
        auto time = CConfigurationProvider::getConfig(path + "/" + "time.json");
        size = time->size();
        for (int i = 0; i < size; i++) {
            paths.push_back(path + "/" + std::to_string(i) + ".png");
            times.push_back((*time)[std::to_string(i)].get<int>());
        }
    }
}


int CDynamicAnimation::get_ttl() {
    return vstd::rand(5000, 30000);
}

CDynamicAnimation::CDynamicAnimation() {

}

int CDynamicAnimation::get_next() {
    return vstd::rand(0, 100);
}

CAnimation::CAnimation() {
    setLayout(std::make_shared<CParentLayout>());
}
