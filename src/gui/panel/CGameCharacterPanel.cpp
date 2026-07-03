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
#include "CGameCharacterPanel.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"
#include "object/CPlayer.h"

#include <exception>

std::vector<std::pair<std::string, std::string>>
CGameCharacterPanel::buildCharacterSheetLines(const std::shared_ptr<CPlayer> &player) {
    std::vector<std::pair<std::string, std::string>> lines;
    if (!charSheet) {
        return lines;
    }
    for (auto [key, value] : charSheet->getValues()) {
        if (value.empty() || !player) {
            continue;
        }
        // Config-driven reflective accessor: fail closed so a missing / mistyped
        // char-sheet method name can never crash the render loop. Numeric accessors are
        // shown directly; string accessors (e.g. class / race identity) fall back to a
        // string invocation so they render as their text value rather than being skipped.
        try {
            lines.emplace_back(key, vstd::str(player->meta()->invoke_method<int>(value, player)));
        } catch (const std::exception &) {
            try {
                lines.emplace_back(key, player->meta()->invoke_method<std::string>(value, player));
            } catch (const std::exception &exception) {
                vstd::logger::warning("Ignoring character sheet value callback failure:", value, exception.what());
            }
        }
    }
    // Identity rows: the player's race and class rendered as human-readable
    // labels after the configured numeric / string rows. These come from the
    // archetype *Label accessors and fail closed exactly like the rows above -
    // an empty or throwing label is skipped so it can never escape the render
    // loop or emit a blank row.
    if (player) {
        try {
            std::string race = player->getArchetypeRaceLabel();
            if (!race.empty()) {
                lines.emplace_back("Race", race);
            }
        } catch (const std::exception &exception) {
            vstd::logger::warning("Ignoring character sheet race label failure:", exception.what());
        }
        try {
            std::string creatureClass = player->getArchetypeClassLabel();
            if (!creatureClass.empty()) {
                lines.emplace_back("Class", creatureClass);
            }
        } catch (const std::exception &exception) {
            vstd::logger::warning("Ignoring character sheet class label failure:", exception.what());
        }
    }
    return lines;
}

void CGameCharacterPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int i) {
    std::string text;
    std::shared_ptr<CPlayer> player = gui->getGame()->getMap()->getPlayer();
    for (const auto &[label, value] : buildCharacterSheetLines(player)) {
        text += label + ": " + value + "\n";
    }
    gui->getTextManager()->drawText(text, rect->x, rect->y, rect->w);
}

CGameCharacterPanel::~CGameCharacterPanel() {}

std::shared_ptr<CMapStringString> CGameCharacterPanel::getCharSheet() { return charSheet; }

void CGameCharacterPanel::setCharSheet(std::shared_ptr<CMapStringString> charSheet) {
    CGameCharacterPanel::charSheet = charSheet;
}

CListView::collection_pointer CGameCharacterPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getEffectiveInteractions()));
}