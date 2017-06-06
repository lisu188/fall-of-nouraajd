//
// Created by andrz on 06.02.17.
//

#include "CGameGraphicsObject.h"


void CGameGraphicsObject::render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime,
                                 std::string object) {

}

bool CGameGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    for (auto callback:eventCallbackList) {
        if (callback.first(gui, event) && callback.second(gui, event)) {
            return true;
        }
    }
    return false;
}

void
CGameGraphicsObject::registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                                           std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func) {
    eventCallbackList.push_back(std::make_pair(pred, func));
}
