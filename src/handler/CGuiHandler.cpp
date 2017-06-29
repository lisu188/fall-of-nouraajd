
#include "gui/panel/CGameTradePanel.h"
#include "core/CGame.h"
#include "gui/panel/CGameTextPanel.h"

CGuiHandler::CGuiHandler() {

}

void CGuiHandler::showMessage(std::string message) {
    std::shared_ptr<CGameTextPanel> panel = _game.lock()->getMap()->createObject<CGameTextPanel>("textPanel");
    panel->setText(message);
    _game.lock()->getGui()->addObject(panel);
}

void CGuiHandler::showTrade(std::shared_ptr<CMarket> market) {
    std::shared_ptr <CGameTradePanel> panel = _game.lock()->getMap()->createObject<CGameTradePanel>("tradePanel");
    panel->setMarket(market);
    _game.lock()->getGui()->addObject(panel);
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {

}
