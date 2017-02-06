#pragma once

#include "object/CGameObject.h"
#include "core/CGlobal.h"
#include "gui/CGameGraphicsObject.h"

class CGui : public CGameObject {
    SDL_Window *window = 0;
    SDL_Renderer *renderer = 0;

    //TODO: make linked hash set
    std::list<std::shared_ptr<CGameGraphicsObject>> gui_stack;
public:
    CGui();

    ~CGui();

    void addObject(std::shared_ptr<CGameGraphicsObject> object) {
        gui_stack.push_back(object);
    }

    void removeObject(std::shared_ptr<CGameGraphicsObject> object) {
        std::remove_if(gui_stack.begin(), gui_stack.end(), [object](std::shared_ptr<CGameGraphicsObject> ob) {
            return ob == object;
        });
    }

    void render() {
        for (std::shared_ptr<CGameGraphicsObject> object:gui_stack) {
            object->render(renderer);
        }
    }

    bool event(SDL_Event *event) {
        for (std::shared_ptr<CGameGraphicsObject> object:gui_stack | boost::adaptors::reversed) {
            if (object->event(event)) {
                return true;
            }
        }
        return false;
    }
};
