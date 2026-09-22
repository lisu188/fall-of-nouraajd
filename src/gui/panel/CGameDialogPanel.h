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

class CDialog;

class CDialogOption;

class CDialogState;

class CGameDialogPanel : public CGamePanel {
    V_META(CGameDialogPanel, CGamePanel,
           V_PROPERTY(CGameDialogPanel, std::shared_ptr<CDialog>, dialog, getDialog, setDialog))
  public:
    const std::shared_ptr<CDialog> &getDialog() const;

    void setDialog(const std::shared_ptr<CDialog> &_dialog);

    void reload();

    const std::string &getQuestContext() const { return questContext; }

#ifdef GAME_UNIT_TESTS
    std::shared_ptr<SDL_Rect> getBodyRectForTest() const { return bodyRect; }
    std::shared_ptr<SDL_Rect> getFooterRectForTest() const { return footerRect; }
#endif

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    bool mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX, int wheelY) override;

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;

#ifdef GAME_UNIT_TESTS
    std::map<int, std::shared_ptr<CDialogOption>> getCurrentOptionsForTest() { return getCurrentOptions(); }
#endif

  protected:
    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

  private:
    std::shared_ptr<CDialog> dialog;
    std::string currentStateId = "ENTRY";
    std::string recordedStateId;
    std::string bodyText;
    std::string questContext;
    std::vector<std::string> historyText;
    struct Paragraph {
        std::string text;
        int y;
        int height;
    };
    std::vector<Paragraph> paragraphs;
    std::shared_ptr<SDL_Rect> bodyRect;
    std::shared_ptr<SDL_Rect> questRect;
    std::shared_ptr<SDL_Rect> footerRect;
    int bodyScroll = 0;
    int bodyMaximum = 0;
    int choiceStart = 0;
    int choiceEnd = 0;
    int focusedChoice = -1;
    int measuredWidth = 0;
    int measuredHeight = 0;
    double measuredScale = 0;
    double measuredTextScale = 0;
    bool readingHistory = false;
    bool readingObjective = false;
    bool historyPressed = false;
    bool objectivePressed = false;

    void appendHistory(const std::string &speaker, const std::string &text, const std::string &kind);

    void loadHistory();

    std::string getFooterHint() const;

    void toggleHistory();

    std::shared_ptr<CDialogOption> getOption(int option);

    void selectOption(int option);

    void selectOption(const std::shared_ptr<CDialogOption> &option);

    std::map<int, std::shared_ptr<CDialogOption>> getCurrentOptions();
};
