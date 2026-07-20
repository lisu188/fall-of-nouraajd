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

#include "object/CGameObject.h"

#include <utility>

class CListString;

class CGamePanel;

class CDialog;

class CMarket;

class CCreature;

class CItem;

class CGuiHandler : public CGameObject {
    V_META(CGuiHandler, CGameObject, vstd::meta::empty())

  public:
    CGuiHandler();

    CGuiHandler(std::shared_ptr<CGame> game);

    void showMessage(std::string message);

    void showInfo(std::string message, bool centered = false);

    bool showQuestion(std::string message);

    void showTrade(std::shared_ptr<CMarket> market);

    void showDialog(std::shared_ptr<CDialog> dialog);

    void showLoot(std::shared_ptr<CCreature>, std::set<std::shared_ptr<CItem>> items);

    std::string showSelection(std::shared_ptr<CListString> list);

    // Blocking character-creation chooser: two columns of buttons (class options
    // and race options, each an already-formatted label string), returning the
    // picked {classLabel, raceLabel}. Returns {"",""} if either column is empty
    // or the panel is closed without a full pick. The caller (res/game.py) owns
    // building the labels and mapping them back to ids.
    std::pair<std::string, std::string> showCharacterCreation(std::shared_ptr<CListString> classes,
                                                              std::shared_ptr<CListString> races);

    // Full-window blocking campaign presentation screen (briefing / epilogue /
    // completion): title band, body text, and one action button whose label the
    // campaign driver supplies (BEGIN / CONTINUE / RETURN). Enter, Space, or the
    // action button dismiss it; closing/cancel input cannot cancel campaign
    // progression. Headless execution (no GUI) logs the title/body/action
    // content and returns immediately.
    void showCampaignScreen(std::string title, std::string body, std::string actionLabel);

    void showTooltip(std::string text, int x, int y);

    std::shared_ptr<CGamePanel> openPanel(std::string panel);

    void flipPanel(std::string panel, std::string hotkey);

  private:
    std::weak_ptr<CGame> _game;
};
