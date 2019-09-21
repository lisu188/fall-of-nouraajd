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
#pragma once

#include "CGamePanel.h"


class CGameDialogPanel : public CGamePanel {
V_META(CGameDialogPanel, CGamePanel,
       V_PROPERTY(CGameDialogPanel, std::string, question, getQuestion, setQuestion),
       V_METHOD(CGameDialogPanel, renderQuestion, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
       V_METHOD(CGameDialogPanel, renderYes, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
       V_METHOD(CGameDialogPanel, renderNo, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
       V_METHOD(CGameDialogPanel, clickNo, void, std::shared_ptr<CGui>),
       V_METHOD(CGameDialogPanel, clickYes, void, std::shared_ptr<CGui>))


public:
    bool awaitAnswer();

    std::string getQuestion();

    void setQuestion(std::string question);

    void renderQuestion(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i);

    void renderYes(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i);

    void renderNo(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i);

    void clickYes(std::shared_ptr<CGui> gui);

    void clickNo(std::shared_ptr<CGui> gui);

private:

    std::string question;

    std::shared_ptr<bool> selection;

};

