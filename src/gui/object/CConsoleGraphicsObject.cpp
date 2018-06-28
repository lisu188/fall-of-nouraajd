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
                gui->getGame()->getScriptHandler()->call_created_function(consoleState,
                                                                          {"game"},
                                                                          gui->getGame());
                stopInput();
            } else if (event->key.keysym.sym == SDLK_BACKSPACE) {
                consoleState = consoleState.substr(0, consoleState.length() - 1);
            } else if (event->key.keysym.sym == SDLK_UP) {
                decrementHistoryIndex();
                consoleState = consoleHistory[historyIndex];
            } else if (event->key.keysym.sym == SDLK_DOWN) {
                incrementHistoryIndex();
                consoleState = consoleHistory[historyIndex];
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
    registerEventCallback([this](std::shared_ptr<CGui> gui, SDL_Event *event) {
        return event->type == SDL_TEXTINPUT && inProgress;
    }, [this](std::shared_ptr<CGui> gui, SDL_Event *event) {
        consoleState += event->text.text;
        return true;
    });
}

void CConsoleGraphicsObject::incrementHistoryIndex() {
    historyIndex++;
    historyIndex = historyIndex % consoleHistory.size();
}

void CConsoleGraphicsObject::decrementHistoryIndex() {
    historyIndex--;
    if (historyIndex < 0) {
        historyIndex = consoleHistory.size() + historyIndex;
    }
}

void CConsoleGraphicsObject::startInput() {
    SDL_StartTextInput();
    inProgress = true;
}

void CConsoleGraphicsObject::stopInput() {
    SDL_StopTextInput();
    inProgress = false;
    clearConsole();
}

void CConsoleGraphicsObject::clearConsole() {
    consoleHistory.push_back(consoleState);
    consoleState = "";
}

std::string CConsoleGraphicsObject::getConsoleState() {
    return consoleState;
}

void CConsoleGraphicsObject::setConsoleState(std::string consoleState) {
    CConsoleGraphicsObject::consoleState = consoleState;
}

std::list<std::string> CConsoleGraphicsObject::getConsoleHistory() {
    return std::list<std::string>(consoleHistory.begin(), consoleHistory.end());
}

void CConsoleGraphicsObject::setConsoleHistory(std::list<std::string> consoleHistory) {
    this->consoleHistory = std::vector<std::string>(consoleHistory.begin(), consoleHistory.end());
}
