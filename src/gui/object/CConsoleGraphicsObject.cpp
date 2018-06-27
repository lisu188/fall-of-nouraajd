#include "CConsoleGraphicsObject.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

void CConsoleGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    gui->getTextManager()->drawTextCentered(consoleState, pos->x, pos->y + pos->h - height, width, height);
}


CConsoleGraphicsObject::CConsoleGraphicsObject() {
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN;
    }, [this](std::shared_ptr<CGui> gui, SDL_Event *event) {
        if (event->key.keysym.sym == SDLK_TAB) {
            if (inProgress) {
                inProgress = false;
                SDL_StopTextInput();
            } else {
                SDL_StartTextInput();
                inProgress = true;
            }
        } else {
            return inProgress;
        }
        return true;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_TEXTINPUT;
    }, [this](std::shared_ptr<CGui> gui, SDL_Event *event) {
        consoleState += event->text.text;
        return true;
    });
}

std::string CConsoleGraphicsObject::getConsoleState() {
    return consoleState;
}

void CConsoleGraphicsObject::setConsoleState(std::string consoleState) {
    CConsoleGraphicsObject::consoleState = consoleState;
}
