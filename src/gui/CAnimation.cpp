//
// Created by andrz on 07.02.17.
//

#include "CAnimation.h"
#include "gui/CGui.h"

CStaticAnimation::CStaticAnimation(std::string path) {
    raw_path = path + ".png";
}

void CStaticAnimation::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    if (texture == nullptr) {
        texture = IMG_LoadTexture(gui->getRenderer(), raw_path.c_str());
    }
    SDL_RenderCopy(gui->getRenderer(), texture, nullptr, pos);
}

CStaticAnimation::~CStaticAnimation() {
    SDL_DestroyTexture(texture);
}

CDynamicAnimation::CDynamicAnimation(std::string path) {
    //TODO:
}
