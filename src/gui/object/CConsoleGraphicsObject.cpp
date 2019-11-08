/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "CConsoleGraphicsObject.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

void CConsoleGraphicsObject::renderObject(std::shared_ptr<CGui> gui, int frameTime) {
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
