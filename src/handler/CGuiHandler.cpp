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
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "core/CGame.h"
#include "gui/panel/CGameTextPanel.h"
#include "core/CMap.h"

CGuiHandler::CGuiHandler() {

}

void CGuiHandler::showMessage(std::string message) {
    std::shared_ptr<CGameTextPanel> panel = _game.lock()->createObject<CGameTextPanel>("textPanel");
    panel->setText(message);
    _game.lock()->getGui()->addObject(panel);
}

bool CGuiHandler::showDialog(std::string question) {
    std::shared_ptr<CGameDialogPanel> panel = _game.lock()->createObject<CGameDialogPanel>("dialogPanel");
    panel->setQuestion(question);
    _game.lock()->getGui()->addObject(panel);
    return panel->awaitAnswer();
}

void CGuiHandler::showTrade(std::shared_ptr<CMarket> market) {
    std::shared_ptr<CGameTradePanel> panel = _game.lock()->createObject<CGameTradePanel>("tradePanel");
    panel->setMarket(market);
    _game.lock()->getGui()->addObject(panel);
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {

}
