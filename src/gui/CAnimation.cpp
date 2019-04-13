//
// Created by andrz on 07.02.17.
//

#include "core/CProvider.h"
#include "CAnimation.h"
#include "gui/CGui.h"
#include "gui/CTextureCache.h"

CStaticAnimation::CStaticAnimation(std::string path) {
    raw_path = path;
}

void CStaticAnimation::render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) {
    SDL_SAFE(SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture(raw_path), nullptr, pos.get()));
}


CStaticAnimation::CStaticAnimation() {

}

CDynamicAnimation::CDynamicAnimation(std::string path) {
    auto time = CConfigurationProvider::getConfig(path + "/" + "time.json");
    this->size = time->size();
    for (int i = 0; i < size; i++) {
        paths.push_back(path + "/" + std::to_string(i) + ".png");
        times.push_back((*time)[std::to_string(i)].asInt());
    }
}

void CDynamicAnimation::render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) {
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
    SDL_SAFE(SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture(paths[currFrame]), nullptr,
                            pos.get()));
}


int CDynamicAnimation::get_ttl() {
    return vstd::rand(5000, 30000);
}

CDynamicAnimation::CDynamicAnimation() {

}

int CDynamicAnimation::get_next() {
    return vstd::rand(0, 100);
}

