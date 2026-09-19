/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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

#include <vector>

class CGameQuestionPanel : public CGamePanel {
    V_META(CGameQuestionPanel, CGamePanel,
           V_PROPERTY(CGameQuestionPanel, std::string, question, getQuestion, setQuestion),
           V_PROPERTY(CGameQuestionPanel, std::string, confirmLabel, getConfirmLabel, setConfirmLabel),
           V_PROPERTY(CGameQuestionPanel, std::string, cancelLabel, getCancelLabel, setCancelLabel),
           V_METHOD(CGameQuestionPanel, renderQuestion, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
           V_METHOD(CGameQuestionPanel, clickNo, void, std::shared_ptr<CGui>),
           V_METHOD(CGameQuestionPanel, clickYes, void, std::shared_ptr<CGui>))

  public:
    bool awaitAnswer();

    std::string getQuestion();

    void setQuestion(std::string question);

    void renderQuestion(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i);

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    void clickYes(std::shared_ptr<CGui> gui);

    void clickNo(std::shared_ptr<CGui> gui);

    std::string getConfirmLabel() const;

    void setConfirmLabel(std::string value);

    std::string getCancelLabel() const;

    void setCancelLabel(std::string value);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) override;

    bool mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX, int wheelY) override;

#ifdef GAME_UNIT_TESTS
    int getQuestionScrollForTest() const { return bodyScroll; }
    int getQuestionScrollMaximumForTest() const { return bodyMaximum; }
    std::shared_ptr<SDL_Rect> getBodyRectForTest() const { return questionRect; }
    std::shared_ptr<SDL_Rect> getFooterRectForTest() const { return footerRect; }
#endif

  protected:
    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

  private:
    std::string question;
    std::string confirmLabel = "Confirm";
    std::string cancelLabel = "Cancel";
    bool focusedAnswer = false;
    struct Paragraph {
        std::string text;
        int y;
        int height;
    };
    std::vector<Paragraph> paragraphs;
    int measuredWidth = 0;
    double measuredScale = 0;
    double measuredTextScale = 0;
    int contentHeight = 0;
    int bodyHeight = 0;
    int bodyScroll = 0;
    int bodyMaximum = 0;
    std::shared_ptr<SDL_Rect> questionRect;
    std::shared_ptr<SDL_Rect> footerRect;

    void refreshButtons();

    std::shared_ptr<bool> selection;
};
