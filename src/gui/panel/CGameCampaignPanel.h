/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

// Full-window blocking campaign presentation screen: a title band, a body text
// area, and one action button (BEGIN / CONTINUE / RETURN). Enter, Space, or the
// action button dismiss it. Campaign progression must not be cancellable from
// this screen, so Escape and window-close style input are deliberately ignored:
// the only way forward is the action itself.
class CGameCampaignPanel : public CGamePanel {
    V_META(CGameCampaignPanel, CGamePanel,
           V_PROPERTY(CGameCampaignPanel, std::string, title, getTitle, setTitle),
           V_PROPERTY(CGameCampaignPanel, std::string, body, getBody, setBody),
           V_PROPERTY(CGameCampaignPanel, std::string, actionLabel, getActionLabel, setActionLabel),
           V_METHOD(CGameCampaignPanel, renderTitle, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
           V_METHOD(CGameCampaignPanel, renderBody, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
           V_METHOD(CGameCampaignPanel, clickAction, void, std::shared_ptr<CGui>))

  public:
    // Blocks until the screen is dismissed via the action (or the panel is torn
    // down with the GUI). Returns true when the action dismissed it.
    bool awaitDismissal();

    bool isDismissed();

    std::string getTitle();

    void setTitle(std::string value);

    std::string getBody();

    void setBody(std::string value);

    std::string getActionLabel();

    void setActionLabel(std::string value);

    void renderTitle(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void renderBody(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void clickAction(std::shared_ptr<CGui> gui);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) override;

  private:
    std::string title;
    std::string body;
    std::string actionLabel;
    std::shared_ptr<bool> dismissed;
};
