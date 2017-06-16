//
// Created by andrz on 07.02.17.
//

#include <core/CProvider.h>
#include "CAnimation.h"
#include "gui/CGui.h"

CStaticAnimation::CStaticAnimation(std::string path) {
    raw_path = path + ".png";
}

void CStaticAnimation::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture(raw_path), nullptr, pos);
}


CStaticAnimation::CStaticAnimation() {

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
    }
}

void CDynamicAnimation::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    int currFrame = getCurrentAnimFrame(
            frameTime + (totalAnimTime * (_offsets.get("main", frameTime % totalAnimTime) / 100.0)));
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture(paths[currFrame]), nullptr, pos);
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


int CDynamicAnimation::get_ttl() {
    return vstd::rand(5000, 30000);
}

CDynamicAnimation::CDynamicAnimation() {

}

int CDynamicAnimation::get_next() {
    return vstd::rand(0, 100);
}

std::shared_ptr<CAnimation> CAnimation::buildAnimation(std::string path) {
    if (boost::filesystem::is_directory(path)) {
        return std::make_shared<CDynamicAnimation>(path);
    } else if (boost::filesystem::is_regular_file(path + ".png")) {
        return std::make_shared<CStaticAnimation>(path);
    } else {
        vstd::logger::warning("Loading empty animation");
        return std::make_shared<CAnimation>();
    }
}
