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
#pragma once

#include "CGamePanel.h"
#include "gui/CDetailViewport.h"

#include <map>
#include <vector>

class CPlayer;
class CTextManager;

class CGameQuestPanel : public CGamePanel {
    V_META(CGameQuestPanel, CGamePanel, V_METHOD(CGameQuestPanel, refreshFromQuestsChanged),
           V_METHOD(CGameQuestPanel, refreshFromMapPropertyChanged, void, std::string),
           V_METHOD(CGameQuestPanel, refreshFromMapObjectChanged, void, Coords),
           V_METHOD(CGameQuestPanel, showActive, void, std::shared_ptr<CGui>),
           V_METHOD(CGameQuestPanel, showCompleted, void, std::shared_ptr<CGui>),
           V_METHOD(CGameQuestPanel, showHistory, void, std::shared_ptr<CGui>),
           V_METHOD(CGameQuestPanel, chooseTrackedQuest, void, std::shared_ptr<CGui>),
           V_METHOD(CGameQuestPanel, questCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
           V_METHOD(CGameQuestPanel, questCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
           V_METHOD(CGameQuestPanel, questSelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
           V_METHOD(CGameQuestPanel, renderSelectedQuest, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
           V_METHOD(CGameQuestPanel, trackSelectedQuest, void, std::shared_ptr<CGui>))

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

  public:
    std::string getText(std::shared_ptr<CGui> ptr);

    std::string getViewportText(const std::shared_ptr<CGui> &gui);

    int getScrollOffset() const;

    int getScrollMaximum() const;

    int getDetailsScrollOffset() const { return detailsOffset; }

    void showActive(std::shared_ptr<CGui> gui);

    void showCompleted(std::shared_ptr<CGui> gui);

    void showHistory(std::shared_ptr<CGui> gui);

    void chooseTrackedQuest(std::shared_ptr<CGui> gui);

    bool setTrackedQuest(std::shared_ptr<CGui> gui, const std::string &questId);

    CListView::collection_pointer questCollection(std::shared_ptr<CGui> gui);
    void questCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);
    bool questSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);
    std::string getSelectedQuestText(std::shared_ptr<CGui> gui);
    void renderSelectedQuest(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime);
    void trackSelectedQuest(std::shared_ptr<CGui> gui);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) override;

    bool mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX, int wheelY) override;

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

    virtual int measureParagraphHeight(const std::shared_ptr<CTextManager> &textManager, const std::string &text,
                                       int width);

  private:
    struct TabState {
        std::weak_ptr<CGameObject> selectedQuest;
        int scrollOffset = 0;
        int detailsOffset = 0;
        CListView::ViewState list;
    };
    std::map<std::string, TabState> tabStates;
    void switchTab(const std::shared_ptr<CGui> &gui, const std::string &tab);

    struct JournalParagraph {
        std::string text;
        int y;
        int height;
    };

    void refreshScrollLayout(const std::shared_ptr<CGui> &gui);

    void refreshTextCache(const std::shared_ptr<CGui> &gui);

    void scrollBy(long long delta);

    std::vector<JournalParagraph> paragraphs;
    int paragraphWidth = -1;
    int contentHeight = 0;
    int viewportHeight = 0;
    int lineHeight = 24;
    int scrollOffset = 0;
    int scrollMaximum = 0;
    bool paragraphLayoutDirty = true;
    std::weak_ptr<CTextManager> measuredTextManager;

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
    std::string activeTab = "active";
    std::string cachedDialogueHistory;
    std::string cachedNotificationHistory;
    std::weak_ptr<CGameObject> selectedQuest;
    std::string selectedQuestText;
    int questTextVersion = 0;
    int selectedTextVersion = -1;
    DetailViewport::Layout detailLayout;
    int detailsOffset = 0;
    int detailsMaximum = 0;
    SDL_Rect detailsViewport{};
};
