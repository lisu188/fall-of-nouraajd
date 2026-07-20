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

// Stable-ID campaign browser: campaign titles down the left column (built by
// CGuiHandler::showCampaignSelection), the highlighted campaign's description
// and chapter count on the right, and SELECT / CANCEL actions. Selection only
// begins after SELECT confirms a highlighted campaign; CANCEL, Escape, or the
// panel being torn down resolve to an empty campaign id.
class CGameCampaignBrowserPanel : public CGamePanel {
    V_META(CGameCampaignBrowserPanel, CGamePanel,
           V_PROPERTY(CGameCampaignBrowserPanel, std::string, selectedId, getSelectedId, setSelectedId),
           V_PROPERTY(CGameCampaignBrowserPanel, std::string, detailText, getDetailText, setDetailText),
           V_METHOD(CGameCampaignBrowserPanel, renderDetail, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>,
                    int),
           V_METHOD(CGameCampaignBrowserPanel, clickSelect, void, std::shared_ptr<CGui>),
           V_METHOD(CGameCampaignBrowserPanel, clickCancel, void, std::shared_ptr<CGui>))

  public:
    // Blocks until SELECT confirms a campaign, CANCEL/Escape aborts, or the
    // panel is torn down. Returns the confirmed stable campaign id, or "" for
    // every cancel path.
    std::string awaitChoice();

    bool hasChoice();

    std::string getSelectedId();

    void setSelectedId(std::string value);

    std::string getDetailText();

    void setDetailText(std::string value);

    void renderDetail(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void clickSelect(std::shared_ptr<CGui> gui);

    void clickCancel(std::shared_ptr<CGui> gui);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) override;

  private:
    std::string selectedId;
    std::string detailText;
    std::shared_ptr<std::string> choice;
};
