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

#include "CGamePanel.h"

class CPlayer;

class CGameQuestPanel : public CGamePanel {
    V_META(CGameQuestPanel, CGamePanel, V_METHOD(CGameQuestPanel, refreshFromQuestsChanged),
           V_METHOD(CGameQuestPanel, refreshFromMapPropertyChanged, void, std::string),
           V_METHOD(CGameQuestPanel, refreshFromMapObjectChanged, void, Coords))

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

  public:
    std::string getText(std::shared_ptr<CGui> ptr);

    // Reactive slots (same signal channels CListView refresh subscriptions use): a
    // subscribed source changed, so the cached journal text is stale and must be
    // rebuilt on the next read. Repeated notifications within one event-loop turn
    // coalesce naturally into a single rebuild through the dirty flag.
    //
    // refreshFromQuestsChanged serves the player's questsChanged/completedQuestsChanged
    // membership signals and the map's no-argument turnPassed signal. The map slots
    // exist because quest getObjective/getReward/getHint are arbitrary map scripts whose
    // text derives from quest-state properties (QuestStateStore.set_state writes
    // "quest_state_*" string properties on the map) and from map object state — the
    // journal can change without any quest being added or completed, so quest-set
    // membership signals alone are not a sufficient invalidation source.
    void refreshFromQuestsChanged();

    void refreshFromMapPropertyChanged(std::string propertyName);

    void refreshFromMapObjectChanged(Coords coords);

  protected:
    // Resolves the player whose quest journal this panel renders. Virtual so tests can
    // inject a player without booting a full map (mirrors CListView::resolveRefreshTarget).
    virtual std::shared_ptr<CPlayer> resolveQuestSource(const std::shared_ptr<CGui> &gui);

    // Resolves the object carrying the quest-state signals the journal text derives
    // from — the current map (propertyChanged / turnPassed / objectChanged). Virtual
    // for tests, like resolveQuestSource.
    virtual std::shared_ptr<CGameObject> resolveQuestStateSource(const std::shared_ptr<CGui> &gui);

    // Builds the journal text from the player's active/completed quests. Virtual so
    // tests can observe how often the text is actually rebuilt.
    virtual std::string buildText(const std::shared_ptr<CPlayer> &player);

  private:
    // Keeps the change subscriptions bound to the currently resolved player and map,
    // reconnecting when either changes (new game, map transition) and marking the
    // cached text stale on any target change — the same follow-the-target contract
    // CListView::refreshSubscriptions() implements.
    void refreshQuestSubscriptions(const std::shared_ptr<CPlayer> &player,
                                   const std::shared_ptr<CGameObject> &questState);

    std::weak_ptr<CGameObject> subscribedQuestSource;

    std::weak_ptr<CGameObject> subscribedQuestStateSource;

    std::string cachedQuestText;

    bool questTextDirty = true;
};
