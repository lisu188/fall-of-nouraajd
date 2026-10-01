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
#include "core/CList.h"
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
#include "handler/CScriptHandler.h"

#include <algorithm>

namespace {
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
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        vstd::logger::info(message);
        return;
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
    game->getGui()->pushChild(panel);
    panel->awaitClosing();
}

void CGuiHandler::showInfo(std::string message, bool centered) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        vstd::logger::info(message);
        return;
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
    game->getGui()->pushChild(panel);
    panel->awaitClosing();
}

bool CGuiHandler::showQuestion(std::string question) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        vstd::logger::info(question);
        return false;
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
    game->getGui()->pushChild(panel);
    return panel->awaitAnswer();
}

bool CGuiHandler::showConfirm(std::string title, std::string body, std::string confirmLabel, std::string cancelLabel) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return false;
    }
    auto panel = game->createObject<CGameQuestionPanel>("questionPanel");
    panel->setTitle(std::move(title));
    panel->setQuestion(std::move(body));
    panel->setConfirmLabel(std::move(confirmLabel));
    panel->setCancelLabel(std::move(cancelLabel));
    game->getGui()->pushChild(panel);
    return panel->awaitAnswer();
}

void CGuiHandler::showTrade(std::shared_ptr<CMarket> market) {
    auto game = _game.lock();
    if (!game || !game->getGui() || !market) {
        return;
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
    game->getGui()->pushChild(panel);
    panel->awaitClosing();
}

void CGuiHandler::showDialog(std::shared_ptr<CDialog> dialog) {
    auto game = _game.lock();
    if (!game || !game->getGui() || !dialog) {
        return;
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
    game->getGui()->pushChild(panel);
    panel->reload();
    panel->awaitClosing();
}

void CGuiHandler::showLoot(std::shared_ptr<CCreature> creature, std::set<std::shared_ptr<CItem>> items) {
    auto game = _game.lock();
    if (!game || !game->getGui() || !creature) {
        return;
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
    game->getGui()->pushChild(panel);
    panel->awaitClosing();
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {}

std::string CGuiHandler::showChoice(std::string title, std::string choicesJson, std::string actionLabel,
                                    std::string backLabel) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return "";
    }
    auto options = CGameCampaignBrowserPanel::parseChoices(choicesJson);
    auto panel = game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");
    panel->configureChoices(std::move(title), std::move(options), std::move(actionLabel), std::move(backLabel));
    game->getGui()->pushChild(panel);
    return panel->awaitChoice();
}

std::pair<std::string, std::string> CGuiHandler::showCharacterCreationOptions(std::string classesJson,
                                                                              std::string racesJson) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return {"", ""};
    }
    auto classes = CGameCampaignBrowserPanel::parseChoices(classesJson);
    auto races = CGameCampaignBrowserPanel::parseChoices(racesJson);
    if (classes.empty() || races.empty()) {
        return {"", ""};
    }
    auto panel = game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");
    panel->configureCharacterChoices(std::move(classes), std::move(races), characterPreview);
    game->getGui()->pushChild(panel);
    auto result = panel->awaitCharacterChoice();
    characterPreview = panel->getPreviewedCharacter();
    return result;
}

void CGuiHandler::showPauseMenu() {
    auto game = _game.lock();
    if (!game || !game->getGui() || !game->getMap()) {
        return;
    }
    pybind11::gil_scoped_acquire gil;
    game->getScriptHandler()->call_created_function("import ui\nui.pause(game)", {"game"}, game);
}

void CGuiHandler::showSaveMenu() {
    auto game = _game.lock();
    if (!game || !game->getGui() || !game->getMap()) {
        return;
    }
    pybind11::gil_scoped_acquire gil;
    game->getScriptHandler()->call_created_function("import ui\nui.saveMenu(game)", {"game"}, game);
}

std::string CGuiHandler::showTextInput(std::string title, std::string prompt, std::string initialValue) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return "";
    }
    auto panel = game->createObject<CGameCampaignBrowserPanel>("campaignBrowserPanel");
    panel->configureTextInput(std::move(title), std::move(prompt), std::move(initialValue));
    game->getGui()->pushChild(panel);
    const bool wasTextInputActive = SDL_IsTextInputActive() == SDL_TRUE;
    if (!wasTextInputActive)
        SDL_StartTextInput();
    const auto value = panel->awaitChoice();
    if (!wasTextInputActive)
        SDL_StopTextInput();
    return value;
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
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return "";
    }
    const auto values = list ? list->getValues() : std::set<std::string>();
    if (values.empty()) {
        vstd::logger::warning("Selection requested with an empty option list.");
        return "";
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
    return showChoice("Choose an option", choices.dump(), "Select", "Back");
}

std::pair<std::string, std::string> CGuiHandler::showCharacterCreation(std::shared_ptr<CListString> classes,
                                                                       std::shared_ptr<CListString> races) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return {"", ""};
    }

    auto classValues = classes ? classes->getValues() : std::set<std::string>();
    auto raceValues = races ? races->getValues() : std::set<std::string>();
    if (classValues.empty() || raceValues.empty()) {
        // Nothing to compose a two-column chooser from; let the caller fall back.
        return {"", ""};
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
    return showCharacterCreationOptions(classChoices.dump(), raceChoices.dump());
}

void CGuiHandler::showCampaignScreen(std::string title, std::string body, std::string actionLabel) {
    showCampaignArtworkScreen(std::move(title), std::move(body), std::move(actionLabel), "");
}

void CGuiHandler::showCampaignArtworkScreen(std::string title, std::string body, std::string actionLabel,
                                            std::string artwork) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        // Headless execution: log the full presentation content and return
        // immediately so automated campaign runs never block on input.
        vstd::logger::info("Campaign screen:", title, body, actionLabel);
        return;
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
    game->getGui()->pushChild(panel);
    panel->awaitDismissal();
}

std::string CGuiHandler::showCampaignSelection(std::shared_ptr<CMapStringString> titles,
                                               std::shared_ptr<CMapStringString> descriptions,
                                               std::shared_ptr<CMapStringInt> scenarioCounts) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        // Headless execution cannot browse; resolve to the empty stable id.
        return "";
    }

    auto titleValues = titles ? titles->getValues() : string_string_map();
    if (titleValues.empty()) {
        vstd::logger::warning("Campaign selection requested with no campaigns.");
        return "";
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
    game->getGui()->pushChild(panel);

    return panel->awaitChoice();
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
    std::shared_ptr<CGame> game = _game.lock();
    if (!game || !game->getGui() || hotkey.empty()) {
        return;
    }
    auto panelClas = game->getObjectHandler()->getClass(panel);
    if (auto currentPanel = vstd::cast<CGamePanel>(game->getGui()->findChild(panelClas))) {
        currentPanel->close();
    } else {
        std::shared_ptr<CGamePanel> child = openPanel(panel);
        if (!child) {
            return;
        }
        if (panel == "inventoryPanel" || panel == "characterPanel" || panel == "questPanel") {
            return;
        }

        auto keyPred = [hotkey](std::shared_ptr<CGui> gui, std::shared_ptr<CGameGraphicsObject> self,
                                SDL_Event *event) {
            return event->type == SDL_KEYDOWN && event->key.keysym.sym == hotkey[0];
        };
        auto _self = this->ptr<CGuiHandler>();
        child->registerEventCallback(keyPred, [_self, panel, hotkey](std::shared_ptr<CGui> gui,
                                                                     std::shared_ptr<CGameGraphicsObject> self,
                                                                     SDL_Event *event) {
            _self->flipPanel(panel, hotkey);
            return true;
        });

        child->awaitClosing();
    }
}
