//
// Created by andrz on 07.02.17.
//

#include <core/CProvider.h>
#include "CAnimation.h"
#include "gui/CGui.h"

CStaticAnimation::CStaticAnimation(std::string path) {
    raw_path = path + ".png";
}

void CStaticAnimation::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime,
                              std::string data) {
    if (texture == nullptr) {
        texture = IMG_LoadTexture(gui->getRenderer(), raw_path.c_str());
    }
    SDL_RenderCopy(gui->getRenderer(), texture, nullptr, pos);
}

CStaticAnimation::~CStaticAnimation() {
    SDL_DestroyTexture(texture);
}

CDynamicAnimation::CDynamicAnimation(std::string path) {
    auto time = CConfigurationProvider::getConfig(path + "/" + "time.json");
    this->size = time->size();
    for (int i = 0; i < size; i++) {
        paths.push_back(path + "/" + std::to_string(i) + ".png");
        if (i == 0) {
            times.push_back((*time)[std::to_string(i)].asInt());
        } else {
            times.push_back(times[i - 1] + (*time)[std::to_string(i)].asInt());
        }
        totalAnimTime += (*time)[std::to_string(i)].asInt();
        textures.push_back(nullptr);
    }
}

void CDynamicAnimation::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime,
                               std::string object) {
    int currFrame = getCurrentAnimFrame(frameTime + (totalAnimTime * (getFrameOffset(object, frameTime) / 100.0)));
    if (!textures[currFrame]) {
        textures[currFrame] = IMG_LoadTexture(gui->getRenderer(), paths[currFrame].c_str());
    }
    SDL_RenderCopy(gui->getRenderer(), textures[currFrame], nullptr, pos);
}

int CDynamicAnimation::getCurrentAnimFrame(int frameTime) {
    int animTime = (frameTime) % totalAnimTime;
    for (int i = 0; i < size; i++) {
        if (animTime < times[i]) {
            return i;
        }
    }
    vstd::logger::fatal("Cannot determine anim frame!");
}

CDynamicAnimation::~CDynamicAnimation() {
    for (auto texture:textures) {
        SDL_DestroyTexture(texture);
    }
}

int CDynamicAnimation::get_next() {
    return vstd::rand(0, 100);
}

double CDynamicAnimation::getFrameOffset(std::string object, int frameTime) {
    return _offsets.get(object, frameTime);
}

int CDynamicAnimation::get_ttl() {
    return vstd::rand(5000, 30000);
}
