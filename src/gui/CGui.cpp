#include "CGui.h"

CGui::CGui() {
    SDL_Init(SDL_INIT_VIDEO);
    SDL_CreateWindowAndRenderer(1920, 1080, SDL_WINDOW_FULLSCREEN | SDL_WINDOW_OPENGL, &window, &renderer);
    //TODO: check render flags
}

CGui::~CGui() {
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
}

void CGui::render() {
    for (std::shared_ptr<CGameGraphicsObject> object:gui_stack) {
        SDL_Rect physical;
        physical.x = 0;
        physical.y = 0;
        physical.h = Y_SIZE;
        physical.w = X_SIZE;
        object->render(this->ptr<CGui>(), &physical);
    }
}

bool CGui::event(SDL_Event *event) {
    for (std::shared_ptr<CGameGraphicsObject> object:gui_stack | boost::adaptors::reversed) {
        if (object->event(event)) {
            return true;
        }
    }
    return false;
}

void CGui::addObject(std::shared_ptr<CGameGraphicsObject> object) {
    gui_stack.push_back(object);
}

void CGui::removeObject(std::shared_ptr<CGameGraphicsObject> object) {
    std::remove_if(gui_stack.begin(), gui_stack.end(), [object](std::shared_ptr<CGameGraphicsObject> ob) {
        return ob == object;
    });
}

std::shared_ptr<CAnimationHandler> CGui::getAnimationHandler() {
    return _animationHandler;
}

SDL_Renderer *CGui::getRenderer() const {
    return renderer;
}
