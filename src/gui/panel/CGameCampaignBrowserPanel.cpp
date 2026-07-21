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
#include "CGameCampaignBrowserPanel.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

std::string CGameCampaignBrowserPanel::awaitChoice() {
    vstd::wait_until([this]() { return choice != nullptr || !getGui(); });
    return choice ? *choice : "";
}

bool CGameCampaignBrowserPanel::hasChoice() { return choice != nullptr; }

std::string CGameCampaignBrowserPanel::getSelectedId() { return selectedId; }

void CGameCampaignBrowserPanel::setSelectedId(std::string value) { selectedId = value; }

std::string CGameCampaignBrowserPanel::getDetailText() { return detailText; }

void CGameCampaignBrowserPanel::setDetailText(std::string value) { detailText = value; }

void CGameCampaignBrowserPanel::renderDetail(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect,
                                             int frameTime) {
    gui->getTextManager()->drawText(detailText, rect);
}

void CGameCampaignBrowserPanel::clickSelect(std::shared_ptr<CGui> gui) {
    // Selection begins only after SELECT confirms a highlighted campaign; the
    // button is inert until one is picked from the title column.
    if (selectedId.empty()) {
        return;
    }
    choice = std::make_shared<std::string>(selectedId);
    close();
}

void CGameCampaignBrowserPanel::clickCancel(std::shared_ptr<CGui> gui) {
    choice = std::make_shared<std::string>("");
    close();
}

bool CGameCampaignBrowserPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN && key == SDLK_ESCAPE) {
        // Escape is a cancel path: it resolves the browser to an empty stable id.
        clickCancel(gui);
    }
    return true;
}
