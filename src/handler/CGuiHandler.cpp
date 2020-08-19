/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "gui/CLayout.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "core/CGame.h"
#include "gui/panel/CGameTextPanel.h"
#include "core/CMap.h"
#include "gui/object/CWidget.h"
#include "gui/CTextManager.h"
#include "core/CList.h"
#include "gui/CTooltip.h"
#include "CGuiHandler.h"


CGuiHandler::CGuiHandler() {

}

void CGuiHandler::showMessage(std::string message) {
    std::shared_ptr<CGameTextPanel> panel = _game.lock()->createObject<CGameTextPanel>("textPanel");
    panel->setText(message);
    _game.lock()->getGui()->pushChild(panel);
}

void CGuiHandler::showInfo(std::string message) {
    std::shared_ptr<CGameTextPanel> panel = _game.lock()->createObject<CGameTextPanel>("infoPanel");
    panel->setText(message);
    _game.lock()->getGui()->pushChild(panel);
}

bool CGuiHandler::showDialog(std::string question) {
    std::shared_ptr<CGameDialogPanel> panel = _game.lock()->createObject<CGameDialogPanel>("dialogPanel");
    panel->setQuestion(question);
    _game.lock()->getGui()->pushChild(panel);
    return panel->awaitAnswer();
}

void CGuiHandler::showTrade(std::shared_ptr<CMarket> market) {
    std::shared_ptr<CGameTradePanel> panel = _game.lock()->createObject<CGameTradePanel>("tradePanel");
    panel->setMarket(market);
    _game.lock()->getGui()->pushChild(panel);
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {

}

std::string CGuiHandler::showSelection(std::shared_ptr<CListString> list) {
    std::shared_ptr<CGameGraphicsObject> panel = _game.lock()->createObject<CGameGraphicsObject>("selectionPanel");
    vstd::cast<CCenteredLayout>(panel->getLayout())->setH(75 * list->getValues().size());

    std::shared_ptr<std::string> selected;

    std::set<std::shared_ptr<CGameGraphicsObject>> widgets;
    int i = 0;
    for (auto item : list->getValues()) {
        std::string clickName = vstd::str("click") + vstd::str(i);
        std::string renderName = vstd::str("render") + vstd::str(i);

        panel->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(clickName, panel,
                                                                                    [item, &selected](
                                                                                            CGameGraphicsObject *self,
                                                                                            std::shared_ptr<CGui> gui) {
                                                                                        selected = std::make_shared<std::string>(
                                                                                                item);
                                                                                    });


        std::shared_ptr<CButton> widget = _game.lock()->createObject<CButton>("CButton");
        widget->setClick(clickName);
        widget->setText(item);

        std::shared_ptr<CPercentLayout> layout = _game.lock()->createObject<CPercentLayout>("CPercentLayout");
        double percentSize = 100.0 / list->getValues().size();
        layout->setX(0);
        layout->setY(percentSize * i);
        layout->setW(100);
        layout->setH(percentSize);
        widget->setLayout(layout);
        widgets.insert(widget);
        i++;
    }

    panel->setChildren(widgets);

    _game.lock()->getGui()->pushChild(panel);

    vstd::wait_until([&]() {
        return selected != nullptr;
    });

    _game.lock()->getGui()->removeChild(panel);

    return *selected;
}


void CGuiHandler::showTooltip(std::string text, int x,
                              int y) {
    if (text.length() > 0) {
        auto layout = _game.lock()->createObject<CSimpleLayout>();

        auto textureSize = _game.lock()->getGui()->getTextManager()->getTextureSize(text);

        int width = vstd::percent(textureSize.first, 125);
        int height = vstd::percent(textureSize.second, 125);

        layout->setW(width);//TODO: layout should accept functions;
        layout->setH(height);//TODO: layout should accept functions;

        layout->setX(x - width / 2);//TODO: extract to util
        layout->setY(y - height / 2);//TODO: extract to util

        auto tooltip = _game.lock()->createObject<CTooltip>();
        tooltip->setText(text);
        tooltip->setLayout(layout);
        _game.lock()->getGui()->pushChild(tooltip);
    }
}

std::shared_ptr<CGamePanel> CGuiHandler::flipPanel(std::string panel) {
    std::shared_ptr<CGame> game = _game.lock();
    auto panelClas = game->getObjectHandler()->getClass(panel);
    if (auto currentPanel = game->getGui()->findChild(panelClas)) {
        game->getGui()->removeChild(currentPanel);
    } else {
        std::shared_ptr<CGamePanel> child = game->createObject<CGamePanel>(panel);
        game->getGui()->pushChild(child);
        return child;
    }
    return nullptr;
}

