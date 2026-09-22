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

#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "core/CStats.h"
#include "core/CSceneManager.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"
#include "gui/object/CWidget.h"
#define GAME_UNIT_TESTS
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CGameQuestionPanel.h"
#undef GAME_UNIT_TESTS
#include "handler/CObjectHandler.h"
#include "object/CDialog.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "plugin/CPluginRegistrar.h"
#include "plugin/NativePlugin.h"
#include "test_harness.h"
#include <cstdio>

#include <pybind11/embed.h>

namespace {
namespace py = pybind11;

struct DialogueHarness {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CGui> gui = std::make_shared<CGui>();
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();
    std::shared_ptr<CDialog> dialog = std::make_shared<CDialog>();
    std::shared_ptr<CDialogOption> option = std::make_shared<CDialogOption>();
    std::shared_ptr<CDialogState> entry = std::make_shared<CDialogState>();
    std::shared_ptr<CGameDialogPanel> panel = std::make_shared<CGameDialogPanel>();
    int actionCount = 0;
    bool allowed = true;
    bool departed = false;
    bool changeMap = false;
    bool queueMapChange = false;

    DialogueHarness() {
        game->setMap(map);
        game->setGui(gui);
        map->setGame(game);
        gui->setGame(game);
        CPluginRegistrar registrar(game);
        native_plugin::register_gameplay_types(registrar);
        for (const auto &[name, builder] : *CTypes::builders()) {
            game->getObjectHandler()->registerType(name, builder);
        }
        player->setGame(game);
        player->setBaseStats(std::make_shared<CStats>());
        map->setPlayer(player);
        dialog->setGame(game);
        dialog->setStringProperty("speaker", "The witness");
        option->setNumber(1);
        option->setText("I will help.");
        option->setAction("acceptQuest");
        option->setNextStateId("EXIT");
        entry->setStateId("ENTRY");
        entry->setText("Will you help me find the amulet?");
        entry->setOptions({option});
        dialog->setStates({entry});

        py::dict scope;
        scope["perform"] = py::cpp_function([this](const std::string &) {
            ++actionCount;
            departed = true;
            if (changeMap) {
                auto destination = std::make_shared<CMap>();
                destination->setGame(game);
                game->setMap(destination);
            }
            if (queueMapChange) {
                game->getSceneManager()->requestMapChange(game, "test");
            }
            return true;
        });
        scope["condition"] =
            py::cpp_function([this](const std::string &name) { return name == "hasLeft" ? departed : allowed; });
        py::exec(R"(
class DialogueCallbacks:
    def invokeAction(self, action):
        return perform(action)
    def invokeCondition(self, name):
        return condition(name)
callbacks = DialogueCallbacks()
)",
                 scope);
        CPythonOverrides::retain(dialog, scope["callbacks"]);
        panel->setGame(game);
        auto layout = std::make_shared<CLayout>();
        layout->setRect(0, 0, 800, 600);
        panel->setLayout(layout);
        panel->setDialog(dialog);
        gui->pushChild(panel);
        panel->reload();
    }

    ~DialogueHarness() {
        panel->close();
        CPythonOverrides::release(dialog.get());
    }

    std::string history() const { return player->getStringProperty("uiDialogueHistory"); }

    void key(SDL_Keycode value) { panel->keyboardEvent(gui, SDL_KEYDOWN, value); }
};

void testEscapeAndUnfocusedEnterNeverCommitAReply() {
    DialogueHarness harness;
    const auto history = harness.history();
    auto button = vstd::cast<CWidget>(*harness.panel->getChildren().begin());
    const auto retainedClick = button->getClick();
    harness.key(SDLK_RETURN);
    expect_true(harness.panel->getGui() != nullptr, "Enter without a chosen reply must leave the conversation open");
    harness.key(SDLK_ESCAPE);
    expect_true(!harness.panel->getGui(), "Escape must close the conversation");
    harness.panel->meta()->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>>(retainedClick, harness.panel,
                                                                                           harness.gui);
    expect_true(harness.actionCount == 0, "Escape and unfocused Enter must never invoke a reply action");
    expect_true(harness.history() == history, "cancelling must not record a reply that was never selected");
}

void testQuestContextOnlyShowsRelatedActiveObjectivesAndIsReadOnly() {
    DialogueHarness harness;
    harness.dialog->setStringProperty("questIds", "amuletQuest,hiddenQuest");
    auto amulet = std::make_shared<CQuest>();
    amulet->setTypeId("amuletQuest");
    amulet->setObjective("Return the recovered amulet to the old woman.");
    auto unrelated = std::make_shared<CQuest>();
    unrelated->setTypeId("anotherQuest");
    unrelated->setObjective("An unrelated objective must stay out of this conversation.");
    harness.player->setQuests({unrelated});
    harness.panel->reload();
    expect_true(harness.panel->getQuestContext().empty(), "unaccepted and unrelated quests must not be disclosed");
    harness.player->setQuests({amulet, unrelated});
    harness.panel->reload();
    expect_true(harness.panel->getQuestContext() == amulet->getObjective(),
                "the context must use the authoritative objective of a related active quest");
    const auto history = harness.history();
    harness.key(SDLK_o);
    expect_true(harness.panel->getTitle() == "Current objective" && harness.panel->getChildren().empty(),
                "the objective must have a full scrollable reader for enlarged or long text");
    harness.key(SDLK_1);
    harness.key(SDLK_RETURN);
    expect_true(harness.actionCount == 0 && harness.history() == history,
                "reading objective details must not select replies or impersonate spoken dialogue");
    harness.key(SDLK_ESCAPE);
    expect_true(harness.panel->getTitle() == "The witness" && harness.panel->getGui() != nullptr,
                "Escape must return to the conversation without dismissing it");
    harness.player->setQuests({unrelated});
    harness.panel->reload();
    expect_true(harness.panel->getQuestContext().empty(), "completed quests must leave the current context");
}

void testHistoryIsReadOnlyAndReturnsToTheSameConversation() {
    DialogueHarness harness;
    const auto history = harness.history();
    expect_true(json::parse(history).size() == 1, "opening a conversation must record its first speech once");
    harness.panel->reload();
    harness.key(SDLK_h);
    expect_true(harness.panel->getTitle() == "Conversation history", "history must use a clear reader title");
    expect_true(harness.panel->getChildren().empty(), "history must not expose executable reply buttons");
    harness.key(SDLK_1);
    harness.key(SDLK_RETURN);
    expect_true(harness.actionCount == 0, "numeric shortcuts and Enter must not run actions in history");
    expect_true(harness.history() == history, "reading and reloading history must not duplicate transcript entries");
    harness.key(SDLK_ESCAPE);
    expect_true(harness.panel->getGui() != nullptr && harness.panel->getTitle() == "The witness",
                "Escape from history must return to the same conversation");
    expect_true(!harness.panel->getChildren().empty(), "returning from history must restore the original replies");
    harness.key(SDLK_1);
    expect_true(harness.actionCount == 1, "an explicit reply must still execute exactly once");
    const auto entries = json::parse(harness.history());
    expect_true(entries.size() == 2 && entries[1]["kind"].get<std::string>() == "reply",
                "the transcript must append the selected reply after the speech");
}

void testAReplyRechecksItsConditionAfterTheButtonWasCreated() {
    DialogueHarness harness;
    harness.option->setCondition("questAvailable");
    harness.panel->reload();
    auto child = *harness.panel->getChildren().begin();
    auto button = vstd::cast<CWidget>(child);
    expect_true(button != nullptr, "an available reply must create a clickable button");
    if (!button)
        return;
    const auto click = button->getClick();
    const auto history = harness.history();
    harness.allowed = false;
    harness.panel->meta()->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>>(click, harness.panel,
                                                                                           harness.gui);
    expect_true(harness.actionCount == 0, "a stale button must not invoke an action whose condition no longer holds");
    expect_true(harness.history() == history, "a rejected stale reply must not appear in the transcript");
    expect_true(harness.panel->getChildren().empty(), "rechecking a stale reply must refresh available choices");
}

void testActionOutcomeChoosesTheActualDepartureSpeech() {
    DialogueHarness harness;
    auto departure = std::make_shared<CDialogState>();
    departure->setStateId("GONE");
    departure->setText("I have said enough. Farewell.");
    harness.dialog->setStates({harness.entry, departure});
    harness.option->setStringProperty("afterCondition", "hasLeft");
    harness.option->setStringProperty("afterStateId", "GONE");
    harness.key(SDLK_1);
    const auto history = json::parse(harness.history());
    expect_true(harness.actionCount == 1 && harness.panel->getGui() != nullptr,
                "the action must run once and keep the actual outcome speech readable");
    expect_true(history.size() == 3 && history[2]["state"].get<std::string>() == "GONE",
                "an action that causes departure must record the departure speech instead of stale banter");
}

void testMapTransitionDoesNotReviveTheOldDialogue() {
    DialogueHarness harness;
    auto next = std::make_shared<CDialogState>();
    next->setStateId("OLD_SCENE");
    next->setText("This speech belongs to the outgoing map.");
    harness.dialog->setStates({harness.entry, next});
    harness.option->setNextStateId("OLD_SCENE");
    harness.changeMap = true;
    harness.key(SDLK_1);
    expect_true(harness.actionCount == 1 && harness.game->getMap() != harness.map,
                "the selected transition action must change the active map exactly once");
    expect_true(!harness.panel->getGui(), "a map-changing action must leave the outgoing conversation detached");
    expect_true(json::parse(harness.history()).size() == 2,
                "a transition must record the selected reply without entering the old scene's next state");
}

void testQueuedMapTransitionClosesBeforeOutgoingSpeechCanReload() {
    DialogueHarness harness;
    auto next = std::make_shared<CDialogState>();
    next->setStateId("OLD_SCENE");
    next->setText("The captive is still trapped here.");
    harness.dialog->setStates({harness.entry, next});
    harness.option->setNextStateId("OLD_SCENE");
    harness.queueMapChange = true;
    harness.key(SDLK_1);
    expect_true(harness.game->getMap() == harness.map && harness.game->getSceneManager()->isTransitionPending(),
                "the fixture must queue a real transition without pumping its deferred work");
    expect_true(harness.actionCount == 1 && !harness.panel->getGui(),
                "a pending map transition must detach the outgoing conversation immediately");
    expect_true(json::parse(harness.history()).size() == 2,
                "a queued transition must not record stale outgoing speech before the scene changes");
}

void testActionLabelsPrecedeTheAuthoredResponse() {
    DialogueHarness harness;
    harness.option->setStringProperty("actionLabel", "Accept the quest");
    harness.panel->reload();
    auto button = vstd::cast<CButton>(*harness.panel->getChildren().begin());
    expect_true(button && button->getText() == "1  Accept the quest\nI will help.",
                "the consequence must appear before the retained character response");
}

void testReaderAndHistoryRequireMatchingMousePresses() {
    DialogueHarness harness;
    const int historyY = 600 - UiTheme::scaled(harness.gui, 40);
    harness.panel->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 100, historyY);
    expect_true(harness.panel->getTitle() == "The witness", "an unmatched release must not open history");
    harness.panel->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 100, historyY);
    harness.panel->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 100, historyY);
    expect_true(harness.panel->getTitle() == "Conversation history", "a deliberate footer click must open history");
    auto reader = std::make_shared<CGameTextPanel>();
    reader->setGame(harness.game);
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 800, 600);
    reader->setLayout(layout);
    reader->setText("A recovered letter.");
    harness.gui->pushChild(reader);
    std::shared_ptr<CGameGraphicsObject> control = reader;
    const int continueY = 600 - UiTheme::scaled(harness.gui, 48);
    control->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 100, continueY);
    expect_true(reader->getGui() != nullptr, "opening input must not dismiss the letter on mouse release");
    control->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 100, continueY);
    control->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 100, 100);
    control->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 100, continueY);
    expect_true(reader->getGui() != nullptr, "releasing outside Continue must cancel its press");
    control->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 100, continueY);
    control->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 100, continueY);
    expect_true(!reader->getGui(), "a deliberate Continue click must close the letter");
}

void testHistoryRecoversFromMalformedSavesAndHasABoundedSize() {
    DialogueHarness harness;
    harness.player->setStringProperty("uiDialogueHistory", "not JSON");
    harness.panel->setDialog(harness.dialog);
    harness.panel->reload();
    expect_true(json::parse(harness.history()).size() == 1, "malformed saved history must recover on the next speech");
    for (int index = 0; index < 90; ++index) {
        harness.entry->setText("Speech " + std::to_string(index));
        harness.panel->setDialog(harness.dialog);
        harness.panel->reload();
    }
    auto history = json::parse(harness.history());
    expect_true(history.size() == 80 && history[79]["text"].get<std::string>() == "Speech 89",
                "history must retain the most recent 80 entries in reading order");
    harness.entry->setText(std::string(10000, 'x'));
    for (int index = 0; index < 6; ++index) {
        harness.panel->setDialog(harness.dialog);
        harness.panel->reload();
    }
    expect_true(harness.history().size() <= 32768, "long speeches must obey the saved transcript byte limit");
}

void testQuestionDefaultsToCancelAndSupportsExplicitActions() {
    auto question = std::make_shared<CGameQuestionPanel>();
    question->setQuestion("Buy the selected equipment for 50 gold?");
    question->setConfirmLabel("Buy for 50 gold");
    question->setCancelLabel("Keep browsing");
    question->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_RETURN);
    expect_true(!question->awaitAnswer(), "Enter on a newly opened confirmation must use the safe cancel choice");
    question->setQuestion("Buy the selected equipment for 50 gold?");
    question->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_RIGHT);
    question->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_RETURN);
    expect_true(question->awaitAnswer(), "deliberately selecting the confirm action must return acceptance");
    question->setQuestion("Buy the selected equipment for 50 gold?");
    question->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_ESCAPE);
    expect_true(!question->awaitAnswer(), "Escape must never accept a confirmation");
    expect_true(question->getConfirmLabel() == "Buy for 50 gold" && question->getCancelLabel() == "Keep browsing",
                "confirmation copy must retain the caller's explicit action labels");
}

void testLongConfirmationCanBeReviewedWithoutActivatingTheFooter() {
    DialogueHarness harness;
    harness.panel->close();
    auto question = std::make_shared<CGameQuestionPanel>();
    question->setGame(harness.game);
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 800, 600);
    question->setLayout(layout);
    std::string items = "Buy this equipment for 250 gold?\n";
    for (int index = 0; index < 40; ++index) {
        items += "Item " + std::to_string(index) + ": 1 owned / 1 selected\n";
    }
    question->setQuestion(items);
    question->setConfirmLabel("Buy for 250 gold");
    harness.gui->pushChild(question);
    question->renderQuestion(harness.gui, CUtil::rect(24, 72, 740, 300), 0);
    expect_true(question->getQuestionScrollMaximumForTest() > 0, "a long transaction must provide a scrollable body");
    question->keyboardEvent(harness.gui, SDL_KEYDOWN, SDLK_PAGEDOWN);
    expect_true(question->getQuestionScrollForTest() > 0 && question->getGui() != nullptr,
                "Page Down must reveal more of the transaction without committing or closing it");
    question->keyboardEvent(harness.gui, SDL_KEYDOWN, SDLK_END);
    expect_true(question->getQuestionScrollForTest() == question->getQuestionScrollMaximumForTest(),
                "End must reach the final transaction lines");
    question->mouseWheelEvent(harness.gui, SDL_MOUSEWHEEL, 0, 0, 0, 1);
    expect_true(question->getQuestionScrollForTest() < question->getQuestionScrollMaximumForTest(),
                "mouse wheel must move back through a long confirmation");
    question->keyboardEvent(harness.gui, SDL_KEYDOWN, SDLK_HOME);
    expect_true(question->getQuestionScrollForTest() == 0, "Home must return to the transaction heading");
    question->keyboardEvent(harness.gui, SDL_KEYDOWN, SDLK_RETURN);
    expect_true(!question->awaitAnswer(), "scrolling must preserve the initial safe cancel selection");
}

void testTextScalingInvalidatesConfirmationMeasurements() {
    DialogueHarness harness;
    const auto original = harness.gui->getUiPreferences();
    auto preferences = json::parse(original);
    preferences["uiScale"] = 100;
    preferences["textScale"] = 100;
    expect_true(harness.gui->applyUiPreferences(preferences.dump()), "baseline text scale must be accepted");
    auto question = std::make_shared<CGameQuestionPanel>();
    question->setGame(harness.game);
    question->setQuestion(std::string(1000, 'W'));
    auto rect = CUtil::rect(0, 0, 600, 240);
    question->renderQuestion(harness.gui, rect, 0);
    const auto initialMaximum = question->getQuestionScrollMaximumForTest();
    preferences["textScale"] = 200;
    expect_true(harness.gui->applyUiPreferences(preferences.dump()), "enlarged text scale must be accepted");
    question->renderQuestion(harness.gui, rect, 0);
    expect_true(question->getQuestionScrollMaximumForTest() > initialMaximum,
                "changing text scale without UI scale must remeasure the full scrollable confirmation");
    expect_true(harness.gui->applyUiPreferences(original), "the test must restore its original preferences");
}

void testEnlargedTextKeepsHeadersBodiesAndActionsSeparate() {
    DialogueHarness harness;
    const auto original = harness.gui->getUiPreferences();
    auto preferences = json::parse(original);
    preferences["uiScale"] = 100;
    preferences["textScale"] = 200;
    expect_true(harness.gui->applyUiPreferences(preferences.dump()), "independent enlarged text must be accepted");
    harness.panel->getLayout()->setRect(0, 0, 640, 480);
    harness.panel->reload();
    auto body = harness.panel->getBodyRectForTest();
    auto footer = harness.panel->getFooterRectForTest();
    expect_true(body && footer && body->y >= harness.panel->getShellHeaderHeight(harness.gui) && body->h >= 48 &&
                    body->y + body->h < footer->y,
                "dialogue text must remain below the measured title and above the action footer at 200% text");
    for (const auto &button : harness.panel->getChildren()) {
        auto rect = button->getLayout()->getRect(button);
        expect_true(rect->y >= body->y + body->h && rect->y + rect->h <= footer->y,
                    "reply buttons must fit between the conversation and footer");
    }
    auto reader = std::make_shared<CGameTextPanel>();
    reader->setGame(harness.game);
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 640, 480);
    reader->setLayout(layout);
    reader->setTitle("A recovered letter");
    reader->setText(std::string(6000, 'W'));
    harness.gui->pushChild(reader);
    std::shared_ptr<CGameGraphicsObject> readerControl = reader;
    readerControl->renderObject(harness.gui, CUtil::rect(0, 0, 640, 480), 0);
    body = reader->getBodyRectForTest();
    footer = reader->getContinueRectForTest();
    expect_true(body && footer && body->y >= reader->getShellHeaderHeight(harness.gui) && body->h >= 48 &&
                    body->y + body->h < footer->y,
                "a long reader must preserve a readable viewport between its title and Continue control");
    expect_true(footer->h >= harness.gui->getTextManager()->measureText("Continue", footer->w).second,
                "Continue must grow to contain independently enlarged text");
    auto question = std::make_shared<CGameQuestionPanel>();
    question->setGame(harness.game);
    auto questionLayout = std::make_shared<CLayout>();
    questionLayout->setRect(0, 0, 640, 480);
    question->setLayout(questionLayout);
    question->setTitle("Review this transaction");
    question->setConfirmLabel("Buy for 400 gold");
    harness.gui->pushChild(question);
    question->renderObject(harness.gui, CUtil::rect(0, 0, 640, 480), 0);
    body = question->getBodyRectForTest();
    footer = question->getFooterRectForTest();
    expect_true(body && footer && body->y >= question->getShellHeaderHeight(harness.gui) && body->h >= 48 &&
                    body->y + body->h < footer->y,
                "transaction content must remain between its measured title and confirmation actions");
    const int buttonTextWidth = (footer->w - UiTheme::scaled(harness.gui, 16)) / 2 - UiTheme::scaled(harness.gui, 16);
    expect_true(footer->h >= harness.gui->getTextManager()->measureText("Buy for 400 gold", buttonTextWidth).second,
                "the confirmation footer must contain the full action label at 200% text");
    question->close();
    reader->close();
    expect_true(harness.gui->applyUiPreferences(original), "the test must restore its original preferences");
}
} // namespace

int main() {
    const char *preferences = "ui-dialogue-preferences.json";
    std::remove(preferences);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferences, 1);
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    pybind11::scoped_interpreter interpreter{};
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    type_registration::registerGuiWidgetTypes();
    testEscapeAndUnfocusedEnterNeverCommitAReply();
    testQuestContextOnlyShowsRelatedActiveObjectivesAndIsReadOnly();
    testHistoryIsReadOnlyAndReturnsToTheSameConversation();
    testAReplyRechecksItsConditionAfterTheButtonWasCreated();
    testActionOutcomeChoosesTheActualDepartureSpeech();
    testMapTransitionDoesNotReviveTheOldDialogue();
    testQueuedMapTransitionClosesBeforeOutgoingSpeechCanReload();
    testActionLabelsPrecedeTheAuthoredResponse();
    testReaderAndHistoryRequireMatchingMousePresses();
    testHistoryRecoversFromMalformedSavesAndHasABoundedSize();
    testQuestionDefaultsToCancelAndSupportsExplicitActions();
    testLongConfirmationCanBeReviewedWithoutActivatingTheFooter();
    testTextScalingInvalidatesConfirmationMeasurements();
    testEnlargedTextKeepsHeadersBodiesAndActionsSeparate();
    std::remove(preferences);
    return finish_tests();
}
