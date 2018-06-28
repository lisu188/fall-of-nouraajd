#include "CConsoleGraphicsObject.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

void CConsoleGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    gui->getTextManager()->drawText(consoleState, pos->x, pos->y + pos->h - height, width);
}


CConsoleGraphicsObject::CConsoleGraphicsObject() {
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_KEYDOWN;
    }, [this](std::shared_ptr<CGui> gui, SDL_Event *event) {
        if (inProgress) {
            if (event->key.keysym.sym == SDLK_TAB) {
                stopInput();

            } else if (event->key.keysym.sym == SDLK_RETURN && consoleState.length() > 0) {
                gui->getGame()->getScriptHandler()->call_created_function(consoleState, {"game"}, gui->getGame());
                stopInput();
            } else if (event->key.keysym.sym == SDLK_BACKSPACE) {
                consoleState = consoleState.substr(0, consoleState.length() - 1);
            }
            return true;
        } else {
            if (event->key.keysym.sym == SDLK_TAB) {
                startInput();
                return true;
            }
        }
        return false;
    });
    registerEventCallback([](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_TEXTINPUT;
    }, [this](std::shared_ptr<CGui> gui, SDL_Event *event) {
        consoleState += event->text.text;
        return true;
    });
}

void CConsoleGraphicsObject::startInput() {
    SDL_StartTextInput();
    inProgress = true;
}

void CConsoleGraphicsObject::stopInput() {
    SDL_StopTextInput();
    inProgress = false;
    consoleState = "";
}

std::string CConsoleGraphicsObject::getConsoleState() {
    return consoleState;
}

void CConsoleGraphicsObject::setConsoleState(std::string consoleState) {
    CConsoleGraphicsObject::consoleState = consoleState;
}
