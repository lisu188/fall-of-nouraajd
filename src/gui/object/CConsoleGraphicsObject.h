//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#pragma once

#include "CGameGraphicsObject.h"

class CConsoleGraphicsObject : public CGameGraphicsObject {
V_META(CConsoleGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CConsoleGraphicsObject, std::string, consoleState, getConsoleState, setConsoleState),
       V_PROPERTY(CConsoleGraphicsObject, std::list<std::string>, consoleHistory, getConsoleHistory, setConsoleHistory))
//TODO: make this properties
    int height = 30;
    int width = 1080;

public:
    CConsoleGraphicsObject();

    void render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) override;

    std::string getConsoleState();

    void setConsoleState(std::string consoleState);

    std::list<std::string> getConsoleHistory();

    void setConsoleHistory(std::list<std::string> consoleHistory);

private:
    bool inProgress = false;
    std::string consoleState = "";
    //TODO: persist order when saving
    std::vector<std::string> consoleHistory = {""};
    int historyIndex = 0;

    void stopInput();

    void startInput();

    void clearConsole();

    void decrementHistoryIndex();

    void incrementHistoryIndex();
};