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
#include "CGameCampaignPanel.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

bool CGameCampaignPanel::awaitDismissal() {
    vstd::wait_until([this]() { return dismissed != nullptr || !getGui(); });
    return dismissed ? *dismissed : false;
}

bool CGameCampaignPanel::isDismissed() { return dismissed != nullptr && *dismissed; }

std::string CGameCampaignPanel::getTitle() { return title; }

void CGameCampaignPanel::setTitle(std::string value) { title = value; }

std::string CGameCampaignPanel::getBody() { return body; }

void CGameCampaignPanel::setBody(std::string value) { body = value; }

std::string CGameCampaignPanel::getActionLabel() { return actionLabel; }

void CGameCampaignPanel::setActionLabel(std::string value) { actionLabel = value; }

void CGameCampaignPanel::renderTitle(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    gui->getTextManager()->drawTextCentered(title, rect);
}

void CGameCampaignPanel::renderBody(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    gui->getTextManager()->drawText(body, rect);
}

void CGameCampaignPanel::clickAction(std::shared_ptr<CGui> gui) {
    dismissed = std::make_shared<bool>(true);
    close();
}

bool CGameCampaignPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN) {
        // Enter, keypad Enter, or Space dismiss the screen exactly like the
        // action button. Escape (and any other key) is ignored on purpose:
        // campaign progression cannot be cancelled from a presentation screen.
        if (key == SDLK_RETURN || key == SDLK_KP_ENTER || key == SDLK_SPACE) {
            clickAction(gui);
        }
    }
    return true;
}
