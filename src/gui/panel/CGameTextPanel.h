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

// TODO: unify with CTextWidget
class CGameTextPanel : public CGamePanel {
    V_META(CGameTextPanel, CGamePanel, V_PROPERTY(CGameTextPanel, std::string, text, getText, setText))

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    bool mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX, int wheelY) override;

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;

    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

  private:
    std::string text;
    bool centered = false;
    bool continuePressed = false;
    int scrollOffset = 0;
    int scrollMaximum = 0;
    int measuredWidth = 0;
    double measuredScale = 0;
    double measuredTextScale = 0;
    std::shared_ptr<SDL_Rect> bodyRect;
    std::shared_ptr<SDL_Rect> continueRect;
    struct Paragraph {
        std::string text;
        int y;
        int height;
    };
    std::vector<Paragraph> paragraphs;

    void measureContent(const std::shared_ptr<CGui> &gui, int width, int height);

  public:
#ifdef GAME_UNIT_TESTS
    std::shared_ptr<SDL_Rect> getBodyRectForTest() const { return bodyRect; }
    std::shared_ptr<SDL_Rect> getContinueRectForTest() const { return continueRect; }
#endif
    ~CGameTextPanel();

    std::string getText();

    void setText(std::string ext);

    bool getCentered();

    void setCentered(bool ext);
};
