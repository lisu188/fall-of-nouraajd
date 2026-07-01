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
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGameQuestionPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "object/CDialog.h"
#include "object/CMarket.h"

namespace {
std::shared_ptr<CLayout> create_tooltip_layout(const std::shared_ptr<CGame> &game, const std::string &text, int x,
                                               int y) {
    auto textureSize = game->getGui()->getTextManager()->getTextureSize(text);
    int width = vstd::percent(textureSize.first, 125);
    int height = vstd::percent(textureSize.second, 125);

    auto layout = game->createObject<CLayout>();
    layout->setRect(CUtil::centeredRect(x, y, width, height));
    return layout;
}
} // namespace

CGuiHandler::CGuiHandler() {}

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

std::string CGuiHandler::showSelection(std::shared_ptr<CListString> list) {
    auto game = _game.lock();
    if (!game || !game->getGui()) {
        return "";
    }

    auto values = list ? list->getValues() : std::set<std::string>();
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

    std::shared_ptr<CGamePanel> panel = game->createObject<CGamePanel>("selectionPanel");
    vstd::cast<CCenteredLayout>(panel->getLayout())->setH(vstd::str(75 * values.size()));

    std::shared_ptr<std::string> selected;

    std::set<std::shared_ptr<CGameGraphicsObject>> widgets;
    int i = 0;
    // TODO: unify with CGameDialogPanel
    for (auto item : values) {
        std::string clickName = vstd::str("click") + vstd::str(i);

        panel->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(
            clickName, panel, [item, &selected](CGameGraphicsObject *self, std::shared_ptr<CGui> gui) {
                selected = std::make_shared<std::string>(item);
            });

        std::shared_ptr<CButton> widget = game->createObject<CButton>("CButton");
        widget->setClick(clickName);
        widget->setText(item);

        std::shared_ptr<CLayout> layout = game->createObject<CLayout>("CLayout");
        const int y0 = 100 * i / values.size();
        const int y1 = 100 * (i + 1) / values.size();
        layout->setX(vstd::str(0) + "%");
        layout->setY(vstd::str(y0) + "%");
        layout->setW(vstd::str(100) + "%");
        layout->setH(vstd::str(y1 - y0) + "%");
        widget->setLayout(layout);
        widgets.insert(widget);
        i++;
    }

    panel->setChildren(widgets);

    game->getGui()->pushChild(panel);

    vstd::wait_until([&]() { return selected != nullptr || !panel->getGui(); });

    panel->close();

    return selected ? *selected : "";
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

    std::shared_ptr<CGamePanel> panel = game->createObject<CGamePanel>("selectionPanel");
    const std::size_t rows = classValues.size() > raceValues.size() ? classValues.size() : raceValues.size();
    if (auto centered = vstd::cast<CCenteredLayout>(panel->getLayout())) {
        centered->setW("600");
        centered->setH(vstd::str(75 * rows));
    }

    std::shared_ptr<std::string> selectedClass;
    std::shared_ptr<std::string> selectedRace;
    std::set<std::shared_ptr<CGameGraphicsObject>> widgets;

    // Builds one vertical column of option buttons occupying the [x, x+w] band.
    // `selected` is a pointer to a caller-owned local (valid for the whole call,
    // including the wait_until below); each button captures that pointer by value
    // and writes the picked label into it on click. TODO: unify with showSelection.
    auto buildColumn = [&](const std::set<std::string> &values, std::shared_ptr<std::string> *selected,
                           const std::string &prefix, const std::string &x, const std::string &w) {
        int i = 0;
        for (auto item : values) {
            std::string clickName = prefix + vstd::str(i);

            panel->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(
                clickName, panel, [item, selected](CGameGraphicsObject *self, std::shared_ptr<CGui> gui) {
                    *selected = std::make_shared<std::string>(item);
                });

            std::shared_ptr<CButton> widget = game->createObject<CButton>("CButton");
            widget->setClick(clickName);
            widget->setText(item);

            std::shared_ptr<CLayout> layout = game->createObject<CLayout>("CLayout");
            const int y0 = 100 * i / values.size();
            const int y1 = 100 * (i + 1) / values.size();
            layout->setX(x);
            layout->setY(vstd::str(y0) + "%");
            layout->setW(w);
            layout->setH(vstd::str(y1 - y0) + "%");
            widget->setLayout(layout);
            widgets.insert(widget);
            i++;
        }
    };

    buildColumn(classValues, &selectedClass, "clickClass", "0%", "50%");
    buildColumn(raceValues, &selectedRace, "clickRace", "50%", "50%");

    panel->setChildren(widgets);

    game->getGui()->pushChild(panel);

    // Close once both a class and a race are chosen (or the panel is torn down).
    vstd::wait_until([&]() { return (selectedClass && selectedRace) || !panel->getGui(); });

    panel->close();

    if (!selectedClass || !selectedRace) {
        return {"", ""};
    }
    return {*selectedClass, *selectedRace};
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
    auto panelClas = game->getObjectHandler()->getClass(panel);
    if (auto currentPanel = vstd::cast<CGamePanel>(game->getGui()->findChild(panelClas))) {
        return currentPanel;
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {{"blocking", false}, {"panel", panel}, {"panelKind", "configured"}};
        CPlaytestTrace::addMapContext(fields, game->getMap());
        CPlaytestTrace::record("gui_panel_opened", fields);
    }
    std::shared_ptr<CGamePanel> child = game->createObject<CGamePanel>(panel);
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
