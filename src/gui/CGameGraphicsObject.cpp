//
// Created by andrz on 06.02.17.
//

#include "CGameGraphicsObject.h"


void CGameGraphicsObject::render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime,
                                 std::string object) {

}

bool CGameGraphicsObject::event(SDL_Event *event) {
    for (auto callback:eventCallbackList) {
        if (callback.first(event) && callback.second(event)) {
            return true;
        }
    }
    return false;
}

void
CGameGraphicsObject::registerEventCallback(std::function<bool(SDL_Event *)> pred,
                                           std::function<bool(SDL_Event *)> func) {
    eventCallbackList.push_back(std::make_pair(pred, func));
}
