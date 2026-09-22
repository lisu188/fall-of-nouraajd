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
#include "CGameCharacterPanel.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"
#include "gui/CLayout.h"
#include "object/CPlayer.h"
#include "object/CInteraction.h"
#include "handler/CTooltipHandler.h"
#include "gui/panel/CGameTextPanel.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "object/CEffect.h"

#include <exception>
#include <algorithm>

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
                auto existing =
                    std::find_if(lines.begin(), lines.end(), [](const auto &line) { return line.first == "Race"; });
                if (existing == lines.end()) {
                    lines.emplace_back("Race", race);
                } else if (player->getRace()) {
                    existing->second = race;
                }
            }
        } catch (const std::exception &exception) {
            vstd::logger::warning("Ignoring character sheet race label failure:", exception.what());
        }
        try {
            std::string creatureClass = player->getArchetypeClassLabel();
            if (!creatureClass.empty()) {
                auto existing =
                    std::find_if(lines.begin(), lines.end(), [](const auto &line) { return line.first == "Class"; });
                if (existing == lines.end()) {
                    lines.emplace_back("Class", creatureClass);
                } else if (player->getCreatureClass()) {
                    existing->second = creatureClass;
                }
            }
        } catch (const std::exception &exception) {
            vstd::logger::warning("Ignoring character sheet class label failure:", exception.what());
        }
    }
    return lines;
}

std::string CGameCharacterPanel::buildModifierSources(const std::shared_ptr<CPlayer> &player) {
    if (!player) {
        return "No active hero.";
    }
    std::string text = "These are the current contributions to your attributes and combat statistics.";
    auto append = [&text](const std::string &name, const std::shared_ptr<CStats> &stats, int count = 1) {
        if (!stats || count <= 0) {
            return;
        }
        std::string values;
        stats->meta()->for_all_properties(stats, [&](auto property) {
            if (property->value_type() != std::type_index(typeid(int))) {
                return;
            }
            const auto value = static_cast<long long>(stats->getNumericProperty(property->name())) * count;
            if (value != 0) {
                static const std::map<std::string, std::string> labels = {{"dmgMin", "Minimum damage"},
                                                                          {"dmgMax", "Maximum damage"},
                                                                          {"crit", "Critical chance"},
                                                                          {"hit", "Hit chance"},
                                                                          {"fireResist", "Fire resistance"},
                                                                          {"frostResist", "Frost resistance"},
                                                                          {"normalResist", "Physical resistance"},
                                                                          {"thunderResist", "Thunder resistance"},
                                                                          {"shadowResist", "Shadow resistance"}};
                const auto label = labels.find(property->name());
                values += "\n" + (label == labels.end() ? vstd::camel(property->name()) : label->second) + ": " +
                          (value > 0 ? "+" : "") + std::to_string(value);
            }
        });
        if (!values.empty()) {
            text += "\n\n" + name + values;
        }
    };
    const auto race = player->getRace();
    const auto creatureClass = player->getCreatureClass();
    const auto tracks = player->getOrderedClassTracks();
    if (race) {
        append("Race: " + race->getLabel(), race->getBaseStats());
    }
    if (!tracks.empty()) {
        for (const auto &track : tracks) {
            if (const auto trackClass = track->getCreatureClass()) {
                append("Class: " + trackClass->getLabel(), trackClass->getBaseStats());
            }
        }
    } else if (creatureClass) {
        append("Class: " + creatureClass->getLabel(), creatureClass->getBaseStats());
    }
    append("Hero base", player->getBaseStats());
    if (race) {
        append("Race growth: " + race->getLabel() + " (" + std::to_string(player->getRacialLevel()) + " levels)",
               race->getRacialLevelStats(), player->getRacialLevel());
    }
    if (!tracks.empty()) {
        for (const auto &track : tracks) {
            if (const auto trackClass = track->getCreatureClass()) {
                append("Class growth: " + trackClass->getLabel() + " (" + std::to_string(track->getLevel()) +
                           " levels)",
                       trackClass->getLevelStats(), track->getLevel());
            }
        }
    } else if (creatureClass) {
        append("Class growth: " + creatureClass->getLabel() + " (" + std::to_string(player->getLevel()) + " levels)",
               creatureClass->getLevelStats(), player->getLevel());
    }
    append("Hero growth (" + std::to_string(player->getLevel()) + " levels)", player->getLevelStats(),
           player->getLevel());
    for (const auto &overlay : player->getOrderedTemplates()) {
        append("Trait: " + overlay->getLabel(), overlay->getStatAdjustments());
    }
    for (const auto &[slot, item] : player->getEquipped()) {
        if (item) {
            append("Equipment: " + item->getLabel(), item->getBonus());
        }
    }
    for (const auto &effect : player->getEffects()) {
        if (effect) {
            append("Effect: " + effect->getLabel() + " (" + std::to_string(effect->getTimeLeft()) + " turns remaining)",
                   effect->getBonus());
        }
    }
    append("Current totals", player->getStats());
    return text;
}

void CGameCharacterPanel::inspectModifiers(std::shared_ptr<CGui> gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap()) {
        return;
    }
    auto reader = gui->getGame()->createObject<CGameTextPanel>("textPanel");
    reader->setTitle("Stat modifiers");
    reader->setText(buildModifierSources(gui->getGame()->getMap()->getPlayer()));
    gui->pushChild(reader);
}

void CGameCharacterPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int i) {
    CGamePanel::renderObject(gui, rect, i);
}

CGameCharacterPanel::~CGameCharacterPanel() {}

std::shared_ptr<CMapStringString> CGameCharacterPanel::getCharSheet() { return charSheet; }

void CGameCharacterPanel::setCharSheet(std::shared_ptr<CMapStringString> charSheet) {
    CGameCharacterPanel::charSheet = charSheet;
}

CListView::collection_pointer CGameCharacterPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap() || !gui->getGame()->getMap()->getPlayer()) {
        return std::make_shared<CListView::collection_type>();
    }
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(gui->getGame()->getMap()->getPlayer()->getEffectiveInteractions()));
}

void CGameCharacterPanel::interactionsCallback(std::shared_ptr<CGui> gui, int index,
                                               std::shared_ptr<CGameObject> object) {
    selectedAbility = object;
    abilityOffset = 0;
    refreshViews();
}

bool CGameCharacterPanel::interactionsSelect(std::shared_ptr<CGui> gui, int index,
                                             std::shared_ptr<CGameObject> object) {
    return object && CGameObject::sameInstance(selectedAbility.lock(), object);
}

void CGameCharacterPanel::renderCharacterSheet(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect,
                                               int frameTime) {
    auto player = gui && gui->getGame() && gui->getGame()->getMap() ? gui->getGame()->getMap()->getPlayer() : nullptr;
    if (!player || !rect) {
        return;
    }
    const auto lines = buildCharacterSheetLines(player);
    auto value = [&lines](const std::string &key) {
        auto found = std::find_if(lines.begin(), lines.end(), [&key](const auto &line) { return line.first == key; });
        return found == lines.end() ? std::string("Unknown") : found->second;
    };
    auto stats = player->getStats();
    std::string text =
        "IDENTITY\n" + value("Race") + " / " + value("Class") + "\nLevel " + std::to_string(player->getLevel()) +
        "\nExperience: " + std::to_string(player->getExp()) + " / " + std::to_string(player->getExpForNextLevel()) +
        "\nGold: " + std::to_string(player->getGold()) + "\n\nRESOURCES\nHealth: " + std::to_string(player->getHp()) +
        " / " + std::to_string(player->getHpMax()) + "\nMana: " + std::to_string(player->getMana()) + " / " +
        std::to_string(player->getManaMax()) + "\nMana regeneration: " + std::to_string(player->getManaRegRate()) +
        " per turn\n\nATTRIBUTES\n";
    if (stats) {
        text += "Strength: " + std::to_string(stats->getStrength()) +
                "    Agility: " + std::to_string(stats->getAgility()) +
                "\nStamina: " + std::to_string(stats->getStamina()) +
                "    Intelligence: " + std::to_string(stats->getIntelligence()) +
                "\n\nCOMBAT\nAttack: " + std::to_string(stats->getAttack()) +
                "    Armor: " + std::to_string(stats->getArmor()) + "\nDamage: " + std::to_string(stats->getDmgMin()) +
                " - " + std::to_string(stats->getDmgMax());
    }
    sheetViewport = *rect;
    sheetMaximum =
        std::max(0, gui->getTextManager()->getWrappedTextureSize(text, std::max(1, rect->w)).second - rect->h);
    sheetOffset = std::clamp(sheetOffset, 0, sheetMaximum);
    gui->getTextManager()->drawTextScrolled(text, rect, -sheetOffset);
}

void CGameCharacterPanel::renderAbilityDetails(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect,
                                               int frameTime) {
    if (!gui || !rect) {
        return;
    }
    auto ability = selectedAbility.lock();
    std::string text =
        ability ? CTooltipHandler::buildTooltip(ability) : "Select an ability to read its effects and cost.";
    abilityViewport = *rect;
    abilityMaximum =
        std::max(0, gui->getTextManager()->getWrappedTextureSize(text, std::max(1, rect->w)).second - rect->h);
    abilityOffset = std::clamp(abilityOffset, 0, abilityMaximum);
    gui->getTextManager()->drawTextScrolled(text, rect, -abilityOffset);
}

bool CGameCharacterPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                          int wheelY) {
    auto origin = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : nullptr;
    SDL_Point point{x + (origin ? origin->x : 0), y + (origin ? origin->y : 0)};
    if (SDL_PointInRect(&point, &sheetViewport)) {
        sheetOffset =
            static_cast<int>(std::clamp(static_cast<long long>(sheetOffset) - static_cast<long long>(wheelY) * 72, 0LL,
                                        static_cast<long long>(sheetMaximum)));
        return true;
    }
    if (SDL_PointInRect(&point, &abilityViewport)) {
        abilityOffset =
            static_cast<int>(std::clamp(static_cast<long long>(abilityOffset) - static_cast<long long>(wheelY) * 72,
                                        0LL, static_cast<long long>(abilityMaximum)));
        return true;
    }
    return false;
}

bool CGameCharacterPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN && (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN)) {
        sheetOffset = std::clamp(sheetOffset + (key == SDLK_PAGEUP ? -1 : 1) * std::max(1, sheetViewport.h - 24), 0,
                                 sheetMaximum);
        abilityOffset = std::clamp(abilityOffset + (key == SDLK_PAGEUP ? -1 : 1) * std::max(1, abilityViewport.h - 24),
                                   0, abilityMaximum);
        return true;
    }
    return CGamePanel::keyboardEvent(gui, type, key);
}
