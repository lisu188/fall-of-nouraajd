/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

class CGameQuestionPanel : public CGamePanel {
  V_META(CGameQuestionPanel, CGamePanel,
         V_PROPERTY(CGameQuestionPanel, std::string, question, getQuestion,
                    setQuestion),
         V_METHOD(CGameQuestionPanel, renderQuestion, void,
                  std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
         V_METHOD(CGameQuestionPanel, clickNo, void, std::shared_ptr<CGui>),
         V_METHOD(CGameQuestionPanel, clickYes, void, std::shared_ptr<CGui>))

public:
  bool awaitAnswer();

  std::string getQuestion();

  void setQuestion(std::string question);

  void renderQuestion(std::shared_ptr<CGui> gui,
                      std::shared_ptr<SDL_Rect> pRect, int i);

  void clickYes(std::shared_ptr<CGui> gui);

  void clickNo(std::shared_ptr<CGui> gui);

private:
  std::string question;

  std::shared_ptr<bool> selection;
};
