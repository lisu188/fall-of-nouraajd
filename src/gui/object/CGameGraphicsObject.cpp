#include "CGameGraphicsObject.h"


void CGameGraphicsObject::render(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> pos, int frameTime) {

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
