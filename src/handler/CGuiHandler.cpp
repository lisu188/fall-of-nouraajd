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
#include "CGuiHandler.h"
#include "core/CGame.h"
#include "core/CAsync.h"
#include "core/CGameContext.h"
#include "core/CList.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CTooltip.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"
#include "gui/panel/CGameCampaignPanel.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGameQuestionPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "object/CDialog.h"
#include "object/CMarket.h"
#include "object/CPlayer.h"
#include "handler/CScriptHandler.h"
#include "handler/CRngHandler.h"

#include <algorithm>

namespace {
std::string boundedPresentationText(const std::string &value, std::size_t limit) {
    if (value.size() <= limit) {
        return value;
    }
    while (limit > 0 && (static_cast<unsigned char>(value[limit]) & 0xC0) == 0x80) {
        --limit;
    }
    return value.substr(0, limit);
}

void addPresentationContext(json &fields, const std::shared_ptr<CGame> &game) {
    auto map = game->getMap();
    CPlaytestTrace::addMapContext(fields, map);
    if (map && map->getPlayer()) {
        fields["player"] = CPlaytestTrace::objectRef(map->getPlayer());
        fields["playerCoords"] = CPlaytestTrace::coords(map->getPlayer()->getCoords());
    }
}

class TextInputLease {
  public:
    TextInputLease() : started(SDL_IsTextInputActive() != SDL_TRUE) {
        if (started) {
            SDL_StartTextInput();
        }
    }
    ~TextInputLease() {
        if (started) {
            SDL_StopTextInput();
        }
    }

  private:
    bool started;
};

std::shared_ptr<TextInputLease> acquireTextInputLease() {
    if (!vstd::event_loop<>::instance()->isMainThread()) {
        throw std::logic_error("Text input leases must be acquired on the main thread.");
    }
    static std::weak_ptr<TextInputLease> current;
    auto owner = current.lock();
    if (!owner) {
        owner = std::make_shared<TextInputLease>();
        current = owner;
    }
    return owner;
}

struct ModalPanelOwner {
    std::shared_ptr<CGamePanel> panel;
    ~ModalPanelOwner() { panel->close(); }
};

template <typename T>
std::shared_ptr<T> flowObjectArgument(CScriptFlow &flow, const json &arguments, std::size_t index) {
    auto object = flow.takeObjectArgument(arguments.at(index).at("__nativeObject").get<std::string>());
    auto result = vstd::cast<T>(object);
    if (!result) {
        throw std::invalid_argument("UI flow argument must have type " + T::static_meta()->name());
    }
    return result;
}

template <typename T> T runGuiTask(std::shared_ptr<CGame> game, vstd::task<T> task) {
    try {
        if (game) {
            const auto mode = game->getGui() ? game_async::WaitMode::Frames : game_async::WaitMode::PostedWork;
            auto handle = game->getContext()->spawnTask(std::move(task));
            game.reset();
            return handle.finished() ? handle.get() : game_async::wait(handle, mode);
        }
        vstd::task_group group;
        return group.spawn(std::move(task)).get();
    } catch (const vstd::task_cancelled &) {
        if constexpr (!std::is_void_v<T>) {
            return T{};
        }
    }
}

std::shared_ptr<CLayout> create_tooltip_layout(const std::shared_ptr<CGame> &game, const std::string &text, int x,
                                               int y) {
    const auto gui = game->getGui();
    const int padding = 16;
    const int width = std::max(1, std::min(gui->getWidth() - 48, 520));
    const auto textureSize = gui->getTextManager()->measureText(text, std::max(1, width - padding * 2), "body");
    const int height = std::min(std::max(1, gui->getHeight() - 48), textureSize.second + padding * 2);
    auto layout = game->createObject<CLayout>();
    layout->setRect(CUtil::rect(std::clamp(x + 18, 24, std::max(24, gui->getWidth() - width - 24)),
                                std::clamp(y + 18, 24, std::max(24, gui->getHeight() - height - 24)), width, height));
    return layout;
}
} // namespace

CGuiHandler::CGuiHandler() {}

void CGuiHandler::notify(std::string message) {
    auto game = _game.lock();
    if (game && game->getGui()) {
        game->getGui()->notify(std::move(message));
    } else {
        vstd::logger::info(message);
    }
}

void CGuiHandler::showMessage(std::string message) {
    return runGuiTask(_game.lock(), showMessageAsync(std::move(message)));
}

void CGuiHandler::showMessageLater(std::string message) {
    if (auto game = _game.lock()) {
        game->getContext()->spawnTask(showMessageAsync(std::move(message)));
    } else {
        vstd::logger::info(message);
    }
}

vstd::task<void> CGuiHandler::showMessageAsync(std::string message) {
    return [](std::shared_ptr<CGuiHandler> self, std::string message) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            vstd::logger::info(message);
            co_return;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"messageLength", static_cast<unsigned long long>(message.size())},
                           {"panel", "textPanel"},
                           {"panelKind", "message"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameTextPanel> panel = game->createObject<CGameTextPanel>("textPanel");
        panel->setText(message);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_await panel->awaitClosingAsync();
    }(this->ptr<CGuiHandler>(), std::move(message));
}

void CGuiHandler::showInfo(std::string message, bool centered) {
    return runGuiTask(_game.lock(), showInfoAsync(std::move(message), std::move(centered)));
}

vstd::task<void> CGuiHandler::showInfoAsync(std::string message, bool centered) {
    return [](std::shared_ptr<CGuiHandler> self, std::string message, bool centered) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            vstd::logger::info(message);
            co_return;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"centered", centered},
                           {"messageLength", static_cast<unsigned long long>(message.size())},
                           {"panel", "infoPanel"},
                           {"panelKind", "info"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameTextPanel> panel = game->createObject<CGameTextPanel>("infoPanel");
        panel->setText(message);
        panel->setCentered(centered);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_await panel->awaitClosingAsync();
    }(this->ptr<CGuiHandler>(), std::move(message), std::move(centered));
}

bool CGuiHandler::showQuestion(std::string question) {
    return runGuiTask(_game.lock(), showQuestionAsync(std::move(question)));
}

vstd::task<bool> CGuiHandler::showQuestionAsync(std::string question) {
    return [](std::shared_ptr<CGuiHandler> self, std::string question) -> vstd::task<bool> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            vstd::logger::info(question);
            co_return false;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"messageLength", static_cast<unsigned long long>(question.size())},
                           {"panel", "questionPanel"},
                           {"panelKind", "question"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameQuestionPanel> panel = game->createObject<CGameQuestionPanel>("questionPanel");
        panel->setQuestion(question);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_return co_await panel->awaitAnswerAsync();
    }(this->ptr<CGuiHandler>(), std::move(question));
}

bool CGuiHandler::showConfirm(std::string title, std::string body, std::string confirmLabel, std::string cancelLabel) {
    return runGuiTask(_game.lock(), showConfirmAsync(std::move(title), std::move(body), std::move(confirmLabel),
                                                     std::move(cancelLabel)));
}

vstd::task<bool> CGuiHandler::showConfirmAsync(std::string title, std::string body, std::string confirmLabel,
                                               std::string cancelLabel) {
    return [](std::shared_ptr<CGuiHandler> self, std::string title, std::string body, std::string confirmLabel,
              std::string cancelLabel) -> vstd::task<bool> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            co_return false;
        }
        auto panel = game->createObject<CGameQuestionPanel>("questionPanel");
        panel->setTitle(std::move(title));
        panel->setQuestion(std::move(body));
        panel->setConfirmLabel(std::move(confirmLabel));
        panel->setCancelLabel(std::move(cancelLabel));
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_return co_await panel->awaitAnswerAsync();
    }(this->ptr<CGuiHandler>(), std::move(title), std::move(body), std::move(confirmLabel), std::move(cancelLabel));
}

void CGuiHandler::showTrade(std::shared_ptr<CMarket> market) {
    return runGuiTask(_game.lock(), showTradeAsync(std::move(market)));
}

vstd::task<void> CGuiHandler::showTradeAsync(std::shared_ptr<CMarket> market) {
    return [](std::shared_ptr<CGuiHandler> self, std::shared_ptr<CMarket> market) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        self->requestedTradeMarket.reset();
        self->requestedTradeMap.reset();
        if (game && market && !game->getGui() && CPlaytestTrace::enabled() && game->getMap() &&
            game->getContext()->isActive()) {
            self->requestedTradeMarket = market;
            self->requestedTradeMap = game->getMap();
            self->requestedTradeGeneration = game->getContext()->captureTransitionGeneration();
        }
        if (game && market && CPlaytestTrace::enabled()) {
            json fields = {{"market", CPlaytestTrace::objectRef(market)},
                           {"sell", market->getSell()},
                           {"buy", market->getBuy()},
                           {"items", CPlaytestTrace::itemRefs(market->getItems())}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("trade_requested", fields);
        }
        if (!game || !game->getGui() || !market) {
            co_return;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"market", CPlaytestTrace::objectRef(market)},
                           {"panel", "tradePanel"},
                           {"panelKind", "trade"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameTradePanel> panel = game->createObject<CGameTradePanel>("tradePanel");
        panel->setMarket(market);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_await panel->awaitClosingAsync();
    }(this->ptr<CGuiHandler>(), std::move(market));
}

std::shared_ptr<CMarket> CGuiHandler::getRequestedTradeMarket() {
    auto game = _game.lock();
    if (!game || !requestedTradeMarket || !game->getMap() || game->getGui() || !CPlaytestTrace::enabled() ||
        game->getMap() != requestedTradeMap.lock() ||
        !game->getContext()->isTransitionGenerationCurrent(requestedTradeGeneration)) {
        requestedTradeMarket.reset();
        requestedTradeMap.reset();
    }
    return requestedTradeMarket;
}

void CGuiHandler::showDialog(std::shared_ptr<CDialog> dialog) {
    return runGuiTask(_game.lock(), showDialogAsync(std::move(dialog)));
}

vstd::task<void> CGuiHandler::showDialogAsync(std::shared_ptr<CDialog> dialog) {
    return [](std::shared_ptr<CGuiHandler> self, std::shared_ptr<CDialog> dialog) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui() || !dialog) {
            co_return;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"dialog", CPlaytestTrace::objectRef(dialog)},
                           {"panel", "dialogPanel"},
                           {"panelKind", "dialog"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("dialog_opened", fields);
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameDialogPanel> panel = game->createObject<CGameDialogPanel>("dialogPanel");
        panel->setDialog(dialog);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        panel->reload();
        game.reset();
        co_await panel->awaitClosingAsync();
    }(this->ptr<CGuiHandler>(), std::move(dialog));
}

void CGuiHandler::showLoot(std::shared_ptr<CCreature> creature, std::set<std::shared_ptr<CItem>> items) {
    return runGuiTask(_game.lock(), showLootAsync(std::move(creature), std::move(items)));
}

vstd::task<void> CGuiHandler::showLootAsync(std::shared_ptr<CCreature> creature,
                                            std::set<std::shared_ptr<CItem>> items) {
    return [](std::shared_ptr<CGuiHandler> self, std::shared_ptr<CCreature> creature,
              std::set<std::shared_ptr<CItem>> items) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui() || !creature) {
            co_return;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"creature", CPlaytestTrace::objectRef(creature)},
                           {"items", CPlaytestTrace::itemRefs(items)},
                           {"panel", "lootPanel"},
                           {"panelKind", "loot"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameLootPanel> panel = game->createObject<CGameLootPanel>("lootPanel");
        panel->setCreature(creature);
        panel->setItems(items);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_await panel->awaitClosingAsync();
    }(this->ptr<CGuiHandler>(), std::move(creature), std::move(items));
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {}

std::string CGuiHandler::showChoice(std::string title, std::string choicesJson, std::string actionLabel,
                                    std::string backLabel) {
    return runGuiTask(_game.lock(), showChoiceAsync(std::move(title), std::move(choicesJson), std::move(actionLabel),
                                                    std::move(backLabel)));
}

vstd::task<std::string> CGuiHandler::showChoiceAsync(std::string title, std::string choicesJson,
                                                     std::string actionLabel, std::string backLabel) {
    return [](std::shared_ptr<CGuiHandler> self, std::string title, std::string choicesJson, std::string actionLabel,
              std::string backLabel) -> vstd::task<std::string> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (game && CPlaytestTrace::enabled()) {
            json fields = {{"title", boundedPresentationText(title, 256)},
                           {"titleLength", static_cast<unsigned long long>(title.size())},
                           {"choicesJson", boundedPresentationText(choicesJson, 16384)},
                           {"choicesJsonLength", static_cast<unsigned long long>(choicesJson.size())},
                           {"actionLabel", boundedPresentationText(actionLabel, 128)},
                           {"backLabel", boundedPresentationText(backLabel, 128)},
                           {"headless", !game->getGui()}};
            addPresentationContext(fields, game);
            CPlaytestTrace::record("choice_requested", fields);
        }
        if (!game || !game->getGui()) {
            co_return "";
        }
        auto options = CGameCampaignBrowserPanel::parseChoices(choicesJson);
        auto panel = game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");
        panel->configureChoices(std::move(title), std::move(options), std::move(actionLabel), std::move(backLabel));
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_return co_await panel->awaitChoiceAsync();
    }(this->ptr<CGuiHandler>(), std::move(title), std::move(choicesJson), std::move(actionLabel), std::move(backLabel));
}

std::pair<std::string, std::string> CGuiHandler::showCharacterCreationOptions(std::string classesJson,
                                                                              std::string racesJson) {
    return runGuiTask(_game.lock(), showCharacterCreationOptionsAsync(std::move(classesJson), std::move(racesJson)));
}

vstd::task<std::pair<std::string, std::string>> CGuiHandler::showCharacterCreationOptionsAsync(std::string classesJson,
                                                                                               std::string racesJson) {
    return [](std::shared_ptr<CGuiHandler> self, std::string classesJson,
              std::string racesJson) -> vstd::task<std::pair<std::string, std::string>> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            co_return std::pair<std::string, std::string>{"", ""};
        }
        auto classes = CGameCampaignBrowserPanel::parseChoices(classesJson);
        auto races = CGameCampaignBrowserPanel::parseChoices(racesJson);
        if (classes.empty() || races.empty()) {
            co_return std::pair<std::string, std::string>{"", ""};
        }
        auto panel = game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");
        panel->configureCharacterChoices(std::move(classes), std::move(races), self->characterPreview);
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        auto result = co_await panel->awaitCharacterChoiceAsync();
        self->characterPreview = panel->getPreviewedCharacter();
        co_return result;
    }(this->ptr<CGuiHandler>(), std::move(classesJson), std::move(racesJson));
}

void CGuiHandler::showPauseMenu() { runGuiTask(_game.lock(), showPauseMenuAsync()); }

vstd::task<void> CGuiHandler::showPauseMenuAsync() { return runUiFlowAsync("pause"); }

void CGuiHandler::showSaveMenu() { runGuiTask(_game.lock(), showSaveMenuAsync()); }

vstd::task<void> CGuiHandler::showSaveMenuAsync() { return runUiFlowAsync("saveMenu"); }

vstd::task<void> CGuiHandler::showDefeatAsync() { return runUiFlowAsync("showDefeat"); }

vstd::task<void> CGuiHandler::runUiFlowAsync(std::string entry) {
    return [](std::shared_ptr<CGuiHandler> self, std::string entry) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui() || !game->getMap()) {
            co_return;
        }
        auto flow = game->getScriptHandler()->createUiFlow(std::move(entry), std::weak_ptr<CGame>(game));
        game.reset();
        co_await self->runScriptFlowAsync(std::move(flow));
    }(this->ptr<CGuiHandler>(), std::move(entry));
}

vstd::task<void> CGuiHandler::runScriptFlowAsync(std::unique_ptr<CScriptFlow> flow) {
    return [](std::shared_ptr<CGuiHandler> self, std::unique_ptr<CScriptFlow> flow) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        if (!flow) {
            throw std::invalid_argument("Cannot run an empty UI script flow.");
        }
        const auto stop = co_await vstd::thisTaskStopToken();
        auto game = self->_game.lock();
        const auto context = game ? game->getContext() : nullptr;
        game.reset();
        auto checkActive = [&] {
            if (stop.stop_requested() || (context && !context->isActive())) {
                throw vstd::task_cancelled();
            }
        };
        checkActive();
        json answer;
        auto request = flow->next(answer);
        while (request) {
            std::optional<std::string> failure;
            try {
                const auto operation = request->at("operation").get<std::string>();
                if (operation == "questCommitted") {
                    // A callback can grant its reward and shut down before yielding the commit intent.
                    flow->markCommitted();
                } else if (operation == "itemCommitted") {
                    flow->markItemCommitted();
                }
                checkActive();
                const auto &arguments = request->at("args");
                auto stringArgument = [&arguments](std::size_t index) {
                    return arguments.at(index).get<std::string>();
                };
                if (operation == "showChoice") {
                    answer = co_await self->showChoiceAsync(stringArgument(0), stringArgument(1), stringArgument(2),
                                                            stringArgument(3));
                } else if (operation == "showConfirm") {
                    answer = co_await self->showConfirmAsync(stringArgument(0), stringArgument(1), stringArgument(2),
                                                             stringArgument(3));
                } else if (operation == "showTextInput") {
                    answer = co_await self->showTextInputAsync(stringArgument(0), stringArgument(1), stringArgument(2));
                } else if (operation == "showMessage") {
                    co_await self->showMessageAsync(stringArgument(0));
                    answer = nullptr;
                } else if (operation == "showInfo") {
                    co_await self->showInfoAsync(stringArgument(0),
                                                 arguments.size() > 1 ? arguments.at(1).get<bool>() : false);
                    answer = nullptr;
                } else if (operation == "showQuestion") {
                    answer = co_await self->showQuestionAsync(stringArgument(0));
                } else if (operation == "showSelection") {
                    answer = co_await self->showSelectionAsync(flowObjectArgument<CListString>(*flow, arguments, 0));
                } else if (operation == "showCampaignScreen") {
                    co_await self->showCampaignScreenAsync(stringArgument(0), stringArgument(1), stringArgument(2));
                    answer = nullptr;
                } else if (operation == "showCampaignArtworkScreen") {
                    co_await self->showCampaignArtworkScreenAsync(stringArgument(0), stringArgument(1),
                                                                  stringArgument(2), stringArgument(3));
                    answer = nullptr;
                } else if (operation == "showCharacterCreationOptions") {
                    const auto selection =
                        co_await self->showCharacterCreationOptionsAsync(stringArgument(0), stringArgument(1));
                    answer = json::array({selection.first, selection.second});
                } else if (operation == "showTrade") {
                    co_await self->showTradeAsync(flowObjectArgument<CMarket>(*flow, arguments, 0));
                    answer = nullptr;
                } else if (operation == "showDialog") {
                    co_await self->showDialogAsync(flowObjectArgument<CDialog>(*flow, arguments, 0));
                    answer = nullptr;
                } else if (operation == "addRandomLoot") {
                    auto creature = flowObjectArgument<CCreature>(*flow, arguments, 0);
                    auto game = self->_game.lock();
                    if (!game) {
                        throw std::runtime_error("Cannot grant UI flow loot after its game has been destroyed.");
                    }
                    auto rng = game->getRngHandler();
                    auto items = rng->getRandomLoot(arguments.at(1).get<int>());
                    game.reset();
                    co_await rng->addRandomLootAsync(std::move(creature), std::move(items));
                    answer = nullptr;
                } else if (operation == "checkQuests") {
                    co_await flowObjectArgument<CPlayer>(*flow, arguments, 0)->checkQuestsAsync();
                    answer = nullptr;
                } else if (operation == "questCommitted" || operation == "itemCommitted") {
                    answer = nullptr;
                } else if (operation == "moveTo") {
                    auto object = flowObjectArgument<CMapObject>(*flow, arguments, 0);
                    co_await object->moveToAsync(
                        Coords(arguments.at(1).get<int>(), arguments.at(2).get<int>(), arguments.at(3).get<int>()));
                    answer = nullptr;
                } else if (operation == "itemMoveTo") {
                    auto commit = flow->commitCallback();
                    auto object = flowObjectArgument<CMapObject>(*flow, arguments, 0);
                    co_await object->moveToAsync(
                        Coords(arguments.at(1).get<int>(), arguments.at(2).get<int>(), arguments.at(3).get<int>()),
                        std::move(commit));
                    answer = nullptr;
                } else if (operation == "removeObject") {
                    auto map = flowObjectArgument<CMap>(*flow, arguments, 0);
                    auto object = flowObjectArgument<CMapObject>(*flow, arguments, 1);
                    co_await map->removeObjectAsync(std::move(object));
                    answer = nullptr;
                } else if (operation == "addObjectByName") {
                    auto map = flowObjectArgument<CMap>(*flow, arguments, 0);
                    answer = co_await map->addObjectByNameAsync(
                        stringArgument(1),
                        Coords(arguments.at(2).get<int>(), arguments.at(3).get<int>(), arguments.at(4).get<int>()));
                } else if (operation == "startGameWithPlayer") {
                    co_await CGameLoader::startGameWithPlayerAsync(self->_game, stringArgument(0), stringArgument(1),
                                                                   stringArgument(2));
                    answer = nullptr;
                } else if (operation == "startRandomGameWithPlayer") {
                    co_await CGameLoader::startRandomGameWithPlayerAsync(self->_game, stringArgument(0),
                                                                         stringArgument(1));
                    answer = nullptr;
                } else {
                    throw std::runtime_error("Unsupported asynchronous UI operation: " + operation);
                }
            } catch (const vstd::task_cancelled &) {
                throw;
            } catch (const vstd::scheduler_rejected &) {
                throw;
            } catch (const std::exception &error) {
                failure = error.what();
            }
            checkActive();
            request = failure ? flow->fail(*failure) : flow->next(answer);
        }
    }(this->ptr<CGuiHandler>(), std::move(flow));
}

std::string CGuiHandler::showTextInput(std::string title, std::string prompt, std::string initialValue) {
    return runGuiTask(_game.lock(), showTextInputAsync(std::move(title), std::move(prompt), std::move(initialValue)));
}

vstd::task<std::string> CGuiHandler::showTextInputAsync(std::string title, std::string prompt,
                                                        std::string initialValue) {
    return [](std::shared_ptr<CGuiHandler> self, std::string title, std::string prompt,
              std::string initialValue) -> vstd::task<std::string> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            co_return "";
        }
        auto panel = game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");
        panel->configureTextInput(std::move(title), std::move(prompt), std::move(initialValue));
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        auto inputOwner = acquireTextInputLease();
        game.reset();
        const auto value = co_await panel->awaitChoiceAsync();
        co_return value;
    }(this->ptr<CGuiHandler>(), std::move(title), std::move(prompt), std::move(initialValue));
}

void CGuiHandler::showLoading(std::string message) {
    hideLoading();
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return;
    }
    auto panel = game->createObject<CGameTextPanel>("infoPanel");
    panel->setTitle("Please wait");
    panel->setText(std::move(message));
    panel->setCloseable(false);
    game->getGui()->pushChild(panel);
    loadingPanel = panel;
    game->getGui()->render(0);
}

void CGuiHandler::hideLoading() {
    if (auto panel = loadingPanel.lock()) {
        panel->close();
    }
    loadingPanel.reset();
}

std::string CGuiHandler::showSelection(std::shared_ptr<CListString> list) {
    return runGuiTask(_game.lock(), showSelectionAsync(std::move(list)));
}

vstd::task<std::string> CGuiHandler::showSelectionAsync(std::shared_ptr<CListString> list) {
    return [](std::shared_ptr<CGuiHandler> self, std::shared_ptr<CListString> list) -> vstd::task<std::string> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            co_return "";
        }
        const auto values = list ? list->getValues() : std::set<std::string>();
        if (values.empty()) {
            vstd::logger::warning("Selection requested with an empty option list.");
            co_return "";
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"optionCount", static_cast<unsigned long long>(values.size())},
                           {"panel", "selectionPanel"},
                           {"panelKind", "selection"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }

        auto choices = json::array();
        for (const auto &value : values) {
            choices[choices.size()] = json({{"id", value}, {"label", value}, {"detail", ""}});
        }
        game.reset();
        co_return co_await self->showChoiceAsync("Choose an option", choices.dump(), "Select", "Back");
    }(this->ptr<CGuiHandler>(), std::move(list));
}

std::pair<std::string, std::string> CGuiHandler::showCharacterCreation(std::shared_ptr<CListString> classes,
                                                                       std::shared_ptr<CListString> races) {
    return runGuiTask(_game.lock(), showCharacterCreationAsync(std::move(classes), std::move(races)));
}

vstd::task<std::pair<std::string, std::string>>
CGuiHandler::showCharacterCreationAsync(std::shared_ptr<CListString> classes, std::shared_ptr<CListString> races) {
    return [](std::shared_ptr<CGuiHandler> self, std::shared_ptr<CListString> classes,
              std::shared_ptr<CListString> races) -> vstd::task<std::pair<std::string, std::string>> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            co_return std::pair<std::string, std::string>{"", ""};
        }

        auto classValues = classes ? classes->getValues() : std::set<std::string>();
        auto raceValues = races ? races->getValues() : std::set<std::string>();
        if (classValues.empty() || raceValues.empty()) {
            // Nothing to compose a two-column chooser from; let the caller fall back.
            co_return std::pair<std::string, std::string>{"", ""};
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"classCount", static_cast<unsigned long long>(classValues.size())},
                           {"raceCount", static_cast<unsigned long long>(raceValues.size())},
                           {"panel", "selectionPanel"},
                           {"panelKind", "characterCreation"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }

        auto classChoices = json::array();
        auto raceChoices = json::array();
        for (const auto &value : classValues) {
            classChoices[classChoices.size()] = json({{"id", value}, {"label", value}, {"detail", ""}});
        }
        for (const auto &value : raceValues) {
            raceChoices[raceChoices.size()] = json({{"id", value}, {"label", value}, {"detail", ""}});
        }
        game.reset();
        co_return co_await self->showCharacterCreationOptionsAsync(classChoices.dump(), raceChoices.dump());
    }(this->ptr<CGuiHandler>(), std::move(classes), std::move(races));
}

void CGuiHandler::showCampaignScreen(std::string title, std::string body, std::string actionLabel) {
    return runGuiTask(_game.lock(), showCampaignScreenAsync(std::move(title), std::move(body), std::move(actionLabel)));
}

vstd::task<void> CGuiHandler::showCampaignScreenAsync(std::string title, std::string body, std::string actionLabel) {
    return [](std::shared_ptr<CGuiHandler> self, std::string title, std::string body,
              std::string actionLabel) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        co_await self->showCampaignArtworkScreenAsync(std::move(title), std::move(body), std::move(actionLabel), "");
    }(this->ptr<CGuiHandler>(), std::move(title), std::move(body), std::move(actionLabel));
}

void CGuiHandler::showCampaignArtworkScreen(std::string title, std::string body, std::string actionLabel,
                                            std::string artwork) {
    return runGuiTask(_game.lock(), showCampaignArtworkScreenAsync(std::move(title), std::move(body),
                                                                   std::move(actionLabel), std::move(artwork)));
}

vstd::task<void> CGuiHandler::showCampaignArtworkScreenAsync(std::string title, std::string body,
                                                             std::string actionLabel, std::string artwork) {
    return [](std::shared_ptr<CGuiHandler> self, std::string title, std::string body, std::string actionLabel,
              std::string artwork) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (game && CPlaytestTrace::enabled()) {
            json fields = {{"title", boundedPresentationText(title, 256)},
                           {"titleLength", static_cast<unsigned long long>(title.size())},
                           {"body", boundedPresentationText(body, 4096)},
                           {"bodyLength", static_cast<unsigned long long>(body.size())},
                           {"actionLabel", boundedPresentationText(actionLabel, 128)},
                           {"headless", !game->getGui()}};
            addPresentationContext(fields, game);
            CPlaytestTrace::record("reader_requested", fields);
        }
        if (!game || !game->getGui()) {
            // Headless execution: log the full presentation content and return
            // immediately so automated campaign runs never block on input.
            vstd::logger::info("Campaign screen:", title, body, actionLabel);
            co_return;
        }
        if (CPlaytestTrace::enabled()) {
            json fields = {{"actionLabel", actionLabel},
                           {"blocking", true},
                           {"bodyLength", static_cast<unsigned long long>(body.size())},
                           {"panel", "campaignPanel"},
                           {"panelKind", "campaign"},
                           {"title", title}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }
        std::shared_ptr<CGameCampaignPanel> panel = game->createObject<CGameCampaignPanel>("campaignPanel");
        panel->setCloseable(false);
        panel->setTitle(title);
        panel->setBody(body);
        panel->setArtwork(std::move(artwork));
        panel->setActionLabel(actionLabel);
        // The configured action button carries a placeholder label; stamp the
        // caller-supplied one (BEGIN / CONTINUE / RETURN) before showing.
        for (const auto &child : panel->getChildren()) {
            if (auto button = vstd::cast<CButton>(child)) {
                button->setText(actionLabel);
            }
        }
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);
        game.reset();
        co_await panel->awaitDismissalAsync();
    }(this->ptr<CGuiHandler>(), std::move(title), std::move(body), std::move(actionLabel), std::move(artwork));
}

std::string CGuiHandler::showCampaignSelection(std::shared_ptr<CMapStringString> titles,
                                               std::shared_ptr<CMapStringString> descriptions,
                                               std::shared_ptr<CMapStringInt> scenarioCounts) {
    return runGuiTask(_game.lock(), showCampaignSelectionAsync(std::move(titles), std::move(descriptions),
                                                               std::move(scenarioCounts)));
}

vstd::task<std::string> CGuiHandler::showCampaignSelectionAsync(std::shared_ptr<CMapStringString> titles,
                                                                std::shared_ptr<CMapStringString> descriptions,
                                                                std::shared_ptr<CMapStringInt> scenarioCounts) {
    return [](std::shared_ptr<CGuiHandler> self, std::shared_ptr<CMapStringString> titles,
              std::shared_ptr<CMapStringString> descriptions,
              std::shared_ptr<CMapStringInt> scenarioCounts) -> vstd::task<std::string> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui()) {
            // Headless execution cannot browse; resolve to the empty stable id.
            co_return "";
        }

        auto titleValues = titles ? titles->getValues() : string_string_map();
        if (titleValues.empty()) {
            vstd::logger::warning("Campaign selection requested with no campaigns.");
            co_return "";
        }
        auto descriptionValues = descriptions ? descriptions->getValues() : string_string_map();
        auto countValues = scenarioCounts ? scenarioCounts->getValues() : string_int_map();

        if (CPlaytestTrace::enabled()) {
            json fields = {{"blocking", true},
                           {"campaignCount", static_cast<unsigned long long>(titleValues.size())},
                           {"panel", "campaignBrowserPanel"},
                           {"panelKind", "campaignBrowser"}};
            CPlaytestTrace::addMapContext(fields, game->getMap());
            CPlaytestTrace::record("gui_panel_opened", fields);
        }

        std::shared_ptr<CGameCampaignBrowserPanel> panel =
            game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");

        std::vector<CGameCampaignBrowserPanel::ChoiceOption> options;
        for (const auto &[campaignId, title] : titleValues) {
            std::string description;
            auto descriptionIt = descriptionValues.find(campaignId);
            if (descriptionIt != descriptionValues.end()) {
                description = descriptionIt->second;
            }
            int scenarios = 0;
            auto countIt = countValues.find(campaignId);
            if (countIt != countValues.end()) {
                scenarios = countIt->second;
            }
            options.push_back({campaignId, title, description + "\n\nChapters: " + vstd::str(scenarios), true});
        }

        panel->configureChoices("Choose a campaign", std::move(options), "Create character", "Back");
        ModalPanelOwner panelOwner{panel};
        game->getGui()->pushChild(panel);

        game.reset();

        co_return co_await panel->awaitChoiceAsync();
    }(this->ptr<CGuiHandler>(), std::move(titles), std::move(descriptions), std::move(scenarioCounts));
}

void CGuiHandler::showTooltip(std::string text, int x, int y) {
    if (text.length() > 0) {
        auto game = _game.lock();
        if (!game || !game->getGui()) {
            return;
        }
        auto layout = create_tooltip_layout(game, text, x, y);
        auto tooltip = game->createObject<CTooltip>();
        tooltip->setText(text);
        tooltip->setLayout(layout);
        game->getGui()->pushChild(tooltip);
    }
}

std::shared_ptr<CGamePanel> CGuiHandler::openPanel(std::string panel) {
    std::shared_ptr<CGame> game = _game.lock();
    if (!game || !game->getGui()) {
        return nullptr;
    }
    const bool management = panel == "inventoryPanel" || panel == "characterPanel" || panel == "questPanel";
    if (management) {
        if (managementMap.lock() != game->getMap()) {
            for (const auto &[name, cached] : managementPanels)
                cached->close();
            managementPanels.clear();
            managementMap = game->getMap();
        }
        for (const auto *name : {"inventoryPanel", "characterPanel", "questPanel"}) {
            if (panel != name) {
                auto otherClass = game->getObjectHandler()->getClass(name);
                if (auto other = vstd::cast<CGamePanel>(game->getGui()->findChild(otherClass)))
                    other->close();
            }
        }
    }
    auto panelClas = game->getObjectHandler()->getClass(panel);
    if (auto currentPanel = vstd::cast<CGamePanel>(game->getGui()->findChild(panelClas))) {
        return currentPanel;
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {{"blocking", false}, {"panel", panel}, {"panelKind", "configured"}};
        CPlaytestTrace::addMapContext(fields, game->getMap());
        CPlaytestTrace::record("gui_panel_opened", fields);
    }
    std::shared_ptr<CGamePanel> child;
    if (management && managementPanels.contains(panel)) {
        child = managementPanels.at(panel);
    } else {
        child = game->createObject<CGamePanel>(panel);
        if (management && child)
            managementPanels[panel] = child;
    }
    if (!child)
        return nullptr;
    game->getGui()->pushChild(child);
    return child;
}

void CGuiHandler::flipPanel(std::string panel, std::string hotkey) {
    runGuiTask(_game.lock(), flipPanelAsync(std::move(panel), std::move(hotkey)));
}

vstd::task<void> CGuiHandler::flipPanelAsync(std::string panel, std::string hotkey) {
    return [](std::shared_ptr<CGuiHandler> self, std::string panel, std::string hotkey) -> vstd::task<void> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        auto game = self->_game.lock();
        if (!game || !game->getGui() || hotkey.empty()) {
            co_return;
        }
        auto panelClass = game->getObjectHandler()->getClass(panel);
        if (auto currentPanel = vstd::cast<CGamePanel>(game->getGui()->findChild(panelClass))) {
            currentPanel->close();
            co_return;
        }
        auto child = self->openPanel(panel);
        if (!child || panel == "inventoryPanel" || panel == "characterPanel" || panel == "questPanel") {
            co_return;
        }
        auto keyPred = [hotkey](std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *event) {
            return event->type == SDL_KEYDOWN && event->key.keysym.sym == hotkey[0];
        };
        child->registerEventCallback(keyPred, [self, panel, hotkey](std::shared_ptr<CGui> gui,
                                                                    std::shared_ptr<CGameGraphicsObject>, SDL_Event *) {
            if (auto game = gui ? gui->getGame() : nullptr) {
                game->getContext()->spawnTask(self->flipPanelAsync(panel, hotkey));
            }
            return true;
        });
        ModalPanelOwner panelOwner{child};
        game.reset();
        co_await child->awaitClosingAsync();
    }(this->ptr<CGuiHandler>(), std::move(panel), std::move(hotkey));
}
