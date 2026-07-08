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
    V_META(CGameQuestPanel, CGamePanel, V_METHOD(CGameQuestPanel, refreshFromQuestsChanged))

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

  public:
    std::string getText(std::shared_ptr<CGui> ptr);

    // Reactive slot (same signal channel CListView refresh subscriptions use): the
    // subscribed player's quest data changed, so the cached journal text is stale and
    // must be rebuilt on the next read. Repeated notifications within one event-loop
    // turn coalesce naturally into a single rebuild through the dirty flag.
    void refreshFromQuestsChanged();

  protected:
    // Resolves the player whose quest journal this panel renders. Virtual so tests can
    // inject a player without booting a full map (mirrors CListView::resolveRefreshTarget).
    virtual std::shared_ptr<CPlayer> resolveQuestSource(const std::shared_ptr<CGui> &gui);

    // Builds the journal text from the player's active/completed quests. Virtual so
    // tests can observe how often the text is actually rebuilt.
    virtual std::string buildText(const std::shared_ptr<CPlayer> &player);

  private:
    // Keeps the quest-change subscription bound to the currently resolved player,
    // reconnecting when the player changes (new game, map transition) and marking the
    // cached text stale on any target change — the same follow-the-target contract
    // CListView::refreshSubscriptions() implements.
    void refreshQuestSubscription(const std::shared_ptr<CPlayer> &player);

    std::weak_ptr<CGameObject> subscribedQuestSource;

    std::string cachedQuestText;

    bool questTextDirty = true;
};
