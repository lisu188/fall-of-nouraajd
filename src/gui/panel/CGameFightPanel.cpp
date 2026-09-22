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
#include "CGameFightPanel.h"
#include "CManagementActions.h"
#include "CCreatureView.h"
#include "gui/CLayout.h"
#include <algorithm>
#include <string>
#include <unordered_set>

#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "gui/CAnimation.h"
#include "gui/CTextManager.h"
#include "gui/CDetailViewport.h"
#include "gui/CTextureCache.h"
#include "gui/object/CProxyTargetGraphicsObject.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "handler/CTooltipHandler.h"
#include "handler/CFightHandler.h"
#include "gui/panel/CGameTextPanel.h"

namespace {
void refresh_proxy_children(const std::shared_ptr<CGameGraphicsObject> &object) {
    if (!object) {
        return;
    }
    if (auto proxy = vstd::cast<CProxyTargetGraphicsObject>(object)) {
        proxy->refreshAll();
    }
    for (const auto &child : object->getChildren()) {
        refresh_proxy_children(child);
    }
}

std::shared_ptr<CMap> combat_status_map(const std::shared_ptr<CGui> &gui,
                                        const std::vector<std::shared_ptr<CCreature>> &enemies,
                                        const std::shared_ptr<CCreature> &enemy) {
    if (gui && gui->getGame() && gui->getGame()->getMap()) {
        return gui->getGame()->getMap();
    }
    if (enemy && enemy->getMap()) {
        return enemy->getMap();
    }
    for (const auto &candidate : enemies) {
        if (candidate && candidate->getMap()) {
            return candidate->getMap();
        }
    }
    return nullptr;
}

bool is_stale_combat_status(const std::string &status) {
    return status.starts_with("Combat round ") || status.find("survives the encounter") != std::string::npos ||
           status.find(" is defeated.") != std::string::npos || status.find("cancelled") != std::string::npos;
}

std::shared_ptr<CPlayer> active_player(const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap()) {
        return nullptr;
    }
    return gui->getGame()->getMap()->getPlayer();
}

CListView::collection_pointer empty_collection() { return std::make_shared<CListView::collection_type>(); }

void clear_combat_status(const std::shared_ptr<CGui> &gui, const std::vector<std::shared_ptr<CCreature>> &enemies,
                         const std::shared_ptr<CCreature> &enemy) {
    if (auto map = combat_status_map(gui, enemies, enemy)) {
        map->setStringProperty("combatStatus", "");
    }
}

void clear_stale_combat_status(const std::shared_ptr<CGui> &gui, const std::vector<std::shared_ptr<CCreature>> &enemies,
                               const std::shared_ptr<CCreature> &enemy) {
    if (auto map = combat_status_map(gui, enemies, enemy)) {
        if (is_stale_combat_status(map->getStringProperty("combatStatus"))) {
            map->setStringProperty("combatStatus", "");
        }
    }
}
} // namespace

CListView::collection_pointer CGameFightPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    if (!player) {
        return empty_collection();
    }
    return std::make_shared<CListView::collection_type>(
        vstd::cast<CListView::collection_type>(player->getEffectiveInteractions()));
}

void CGameFightPanel::interactionsCallback(std::shared_ptr<CGui> gui, int index,
                                           std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CInteraction>(_newSelection);
    auto player = active_player(gui);
    selected = player ? newSelection : nullptr;
    selectedItem.reset();
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
    refreshEncounterViews();
}

bool CGameFightPanel::interactionsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return selected.lock() && CGameObject::sameInstance(selected.lock(), object);
}

CListView::collection_pointer CGameFightPanel::itemsCollection(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    if (!player) {
        return empty_collection();
    }
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(player->getItems()));
}

void CGameFightPanel::itemsCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CItem>(_newSelection);
    auto player = active_player(gui);
    if (!player) {
        selectedItem.reset();
        refreshEncounterViews();
        return;
    }
    selectedItem = newSelection;
    selected.reset();
    actionMessage.clear();
    detailsOffset = 0;
    updateActionAvailability(gui);
    refreshEncounterViews();
}

bool CGameFightPanel::itemsRightClickCallback(std::shared_ptr<CGui> gui, int index,
                                              std::shared_ptr<CGameObject> _newSelection) {
    itemsCallback(gui, index, _newSelection);
    return false;
}

bool CGameFightPanel::itemsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && selectedItem.lock() && CGameObject::sameInstance(selectedItem.lock(), object);
}

CGameFightPanel::CGameFightPanel() {}

void CGameFightPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    updateActionAvailability(gui);
    for (const auto &card : getChildren()) {
        for (const auto &child : card->getChildren()) {
            if (auto portrait = vstd::cast<CCreatureView>(child)) {
                CCreatureView::layoutCombatantCard(gui, card, portrait->getCreature());
                break;
            }
        }
    }
    CGamePanel::renderObject(gui, rect, frameTime);
}

void CGameFightPanel::updateActionAvailability(const std::shared_ptr<CGui> &gui) {
    auto player = active_player(gui);
    auto action = selected.lock();
    auto target = enemy.lock();
    bool available = false;
    if (!cancelled && player && action && target && target->isAlive() && action->getManaCost() <= player->getMana()) {
        const auto actions = player->getEffectiveInteractions();
        available = std::any_of(actions.begin(), actions.end(), [action](const auto &candidate) {
            return CGameObject::sameInstance(candidate, action);
        });
    }
    ManagementActions::updateButtons(
        this->ptr<CGameGraphicsObject>(),
        {{"executeSelectedAction", available},
         {"useSelectedItem", !cancelled && ManagementActions::itemUseReason(player, selectedItem.lock()).empty()}});
}

bool CGameFightPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    return CGamePanel::mouseEvent(gui, type, button, x, y);
}

void CGameFightPanel::refreshEncounterViews() {
    refreshViews();
    refresh_proxy_children(this->ptr<CGameFightPanel>());
}

std::shared_ptr<CInteraction> CGameFightPanel::selectInteraction() {
    auto self = this->ptr<CGameFightPanel>();
    auto gui = self->getGui();
    auto game = gui ? gui->getGame() : nullptr;
    auto context = game ? game->getContext() : nullptr;
    std::weak_ptr<CMap> weakExpectedMap;
    if (game) {
        weakExpectedMap = game->getMap();
    }
    const bool hadExpectedMap = game && game->getMap() != nullptr;
    const auto expectedGeneration =
        context ? context->captureTransitionGeneration() : CGameContext::TransitionGeneration{0};
    vstd::call_later_block([self, weakExpectedMap, hadExpectedMap, context, expectedGeneration]() {
        while (self->finalSelected.lock() == nullptr) {
            if (self->isCancelled()) {
                return;
            }
            auto gui = self->getGui();
            auto game = gui ? gui->getGame() : nullptr;
            auto expectedMap = weakExpectedMap.lock();
            if ((context && !context->isTransitionGenerationCurrent(expectedGeneration)) ||
                (hadExpectedMap && (!game || !expectedMap || game->getMap() != expectedMap))) {
                self->cancel();
                return;
            }
            if (!gui || gui->findChild(self) == nullptr) {
                self->cancel();
                return;
            }
            if (SDL_HasEvent(SDL_QUIT)) {
                self->cancel();
                return;
            }
            if (!vstd::event_loop<>::instance()->run()) {
                self->cancel();
                SDL_Event quit_event;
                SDL_zero(quit_event);
                quit_event.type = SDL_QUIT;
                SDL_PushEvent(&quit_event);
                return;
            }
        }
    });
    auto ret = self->finalSelected.lock();
    self->finalSelected.reset();
    self->selected.reset();
    self->refreshEncounterViews();
    return ret;
}

bool CGameFightPanel::isCancelled() const { return cancelled; }

void CGameFightPanel::cancel() {
    cancelled = true;
    finalSelected.reset();
    selected.reset();
    selectedItem.reset();
}

void CGameFightPanel::resetCancellation() { cancelled = false; }

void CGameFightPanel::close() {
    if (auto reader = combatLogReader.lock())
        reader->close();
    combatLogReader.reset();
    clear_combat_status(getGui(), enemies, enemy.lock());
    cancel();
    CGamePanel::close();
}

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() { return enemy.lock(); }

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) {
    const auto enemyIt = std::find_if(enemies.begin(), enemies.end(),
                                      [en](const auto &enemy) { return CGameObject::sameInstance(enemy, en); });
    if (en && en->isAlive() && enemyIt == enemies.end()) {
        enemies.push_back(en);
    }
    enemy = en && en->isAlive() ? en : nullptr;
    clear_stale_combat_status(getGui(), enemies, enemy.lock());
    if (enemy.lock()) {
        refreshEncounterViews();
    } else {
        refreshViews();
    }
}

void CGameFightPanel::setEnemies(const std::vector<std::shared_ptr<CCreature>> &value) {
    enemies.clear();
    std::unordered_set<std::string> names;
    for (const auto &candidate : value) {
        if (candidate && candidate->isAlive() && names.insert(candidate->getName()).second) {
            enemies.push_back(candidate);
        }
    }

    auto current = enemy.lock();
    auto current_it = std::find_if(enemies.begin(), enemies.end(), [current](const auto &candidate) {
        return CGameObject::sameInstance(candidate, current);
    });
    enemy =
        current_it != enemies.end() ? *current_it : (enemies.empty() ? std::shared_ptr<CCreature>() : enemies.front());
    clear_stale_combat_status(getGui(), enemies, enemy.lock());
    if (enemy.lock()) {
        refreshEncounterViews();
    } else {
        refreshViews();
    }
}

CListView::collection_pointer CGameFightPanel::enemiesCollection(std::shared_ptr<CGui> gui) {
    auto collection = std::make_shared<CListView::collection_type>();
    for (const auto &candidate : enemies) {
        collection->push_back(candidate);
    }
    return collection;
}

void CGameFightPanel::enemiesCallback(std::shared_ptr<CGui> gui, int index,
                                      std::shared_ptr<CGameObject> _newSelection) {
    auto newSelection = vstd::cast<CCreature>(_newSelection);
    if (newSelection && newSelection->isAlive()) {
        enemy = newSelection;
        refreshEncounterViews();
    }
}

bool CGameFightPanel::enemiesSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
    return object && enemy.lock() && CGameObject::sameInstance(enemy.lock(), object);
}

std::string CGameFightPanel::getCombatStatus(std::shared_ptr<CGui> gui) {
    if (!gui || !gui->getGame() || !gui->getGame()->getMap()) {
        return "";
    }
    const auto map = gui->getGame()->getMap();
    auto status = map->getStringProperty("combatStatus");
    const auto round = map->getNumericProperty("combatRound");
    const std::string roundLabel = round > 0 ? "Round " + std::to_string(round) + "\n" : "";
    if (!status.empty()) {
        return roundLabel + status;
    }
    if (enemy.lock()) {
        return roundLabel + "Choose an action.\nEnemy: " + enemy.lock()->getLabel();
    }
    return roundLabel + "Choose an action.";
}

std::string CGameFightPanel::getCombatLog(std::shared_ptr<CGui> gui) {
    const auto history = CFightHandler::getCombatHistory(combat_status_map(gui, enemies, enemy.lock()));
    if (history.empty())
        return "No combat events yet. Events will appear here as the encounter progresses.";
    std::string text = "Recent combat events - oldest to newest\n";
    for (const auto &entry : history)
        text += "\n" + entry + "\n";
    return text;
}

void CGameFightPanel::showCombatLog(std::shared_ptr<CGui> gui) {
    if (!gui || !gui->getGame() || cancelled || !isAttachedToGui(gui))
        return;
    if (auto reader = combatLogReader.lock(); reader && reader->isAttachedToGui(gui))
        return;
    auto reader = gui->getGame()->createObject<CGameTextPanel>("infoPanel");
    reader->setTitle("Combat log");
    reader->setText(getCombatLog(gui));
    reader->setCentered(false);
    combatLogReader = reader;
    gui->pushChild(reader);
}

void CGameFightPanel::renderCombatStatus(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    (void)frameTime;
    gui->getTextManager()->drawText(getCombatStatus(gui), rect);
}

std::string CGameFightPanel::getSelectionDetails(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    std::string text = actionMessage.empty() ? "" : actionMessage + "\n\n";
    if (auto item = selectedItem.lock()) {
        text += CTooltipHandler::buildTooltip(item);
        const auto reason = ManagementActions::itemUseReason(player, item);
        text += "\n" + (reason.empty() ? "Choose Use item to use this item." : reason);
        return text;
    }
    auto action = selected.lock();
    if (!action || !player) {
        return text + "Select an action or item to inspect it.\nSelect an enemy to change your target.";
    }
    text += CTooltipHandler::buildTooltip(action);
    if (action->getManaCost() > player->getMana()) {
        text += "\nNeeds " + std::to_string(action->getManaCost() - player->getMana()) + " more mana.";
    }
    auto target = enemy.lock();
    const bool selfTarget = action->getSelfTarget() || action->effectRoutesToCaster(action->getEffect());
    text += "\nTarget: " + (selfTarget ? std::string("Yourself") : target ? target->getLabel() : "No target");
    text += "\nChoose Execute action to commit.";
    return text;
}

void CGameFightPanel::renderSelectionDetails(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (gui && rect) {
        const auto text = getSelectionDetails(gui);
        detailLayout.update(gui, text, rect->w);
        const int height = detailLayout.getContentHeight();
        const auto content = DetailViewport::contentRect(gui, rect, height);
        detailsViewport = *content;
        detailsMaximum = std::max(0, height - content->h);
        detailsOffset = std::clamp(detailsOffset, 0, detailsMaximum);
        detailLayout.draw(gui, content, detailsOffset);
        DetailViewport::drawScrollHint(gui, rect, content, detailsOffset, detailsMaximum);
    }
}

void CGameFightPanel::executeSelectedAction(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    auto action = selected.lock();
    auto target = enemy.lock();
    if (cancelled || !player || !action || !target || !target->isAlive()) {
        actionMessage = "Select an available action and a living target.";
        return;
    }
    auto available = player->getEffectiveInteractions();
    if (std::none_of(available.begin(), available.end(),
                     [action](const auto &candidate) { return CGameObject::sameInstance(candidate, action); })) {
        selected.reset();
        actionMessage = "This action is no longer available.";
        return;
    }
    if (action->getManaCost() > player->getMana()) {
        actionMessage = "Not enough mana.";
        return;
    }
    finalSelected = action;
    actionMessage.clear();
    detailsOffset = 0;
}

void CGameFightPanel::useSelectedItem(std::shared_ptr<CGui> gui) {
    auto player = active_player(gui);
    auto item = selectedItem.lock();
    actionMessage = cancelled ? "This encounter has ended." : ManagementActions::itemUseReason(player, item);
    if (!actionMessage.empty()) {
        return;
    }
    player->useItem(item);
    if (!player->hasInInventory(item)) {
        selectedItem.reset();
    }
    actionMessage.clear();
    detailsOffset = 0;
    refreshEncounterViews();
}

bool CGameFightPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                      int wheelY) {
    auto origin = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : nullptr;
    SDL_Point point{x + (origin ? origin->x : 0), y + (origin ? origin->y : 0)};
    if (!SDL_PointInRect(&point, &detailsViewport)) {
        return false;
    }
    detailsOffset =
        static_cast<int>(std::clamp(static_cast<long long>(detailsOffset) - static_cast<long long>(wheelY) * 72, 0LL,
                                    static_cast<long long>(detailsMaximum)));
    return true;
}

bool CGameFightPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN && key == SDLK_l) {
        showCombatLog(gui);
        return true;
    }
    if (type == SDL_KEYDOWN && (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN)) {
        detailsOffset = std::clamp(detailsOffset + (key == SDLK_PAGEUP ? -1 : 1) * std::max(1, detailsViewport.h - 24),
                                   0, detailsMaximum);
        return true;
    }
    return CGamePanel::keyboardEvent(gui, type, key);
}
