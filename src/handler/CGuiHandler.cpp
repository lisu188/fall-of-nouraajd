
#include "panel/CGamePanel.h"
#include "core/CGame.h"
#include "panel/CGameTextPanel.h"

CGuiHandler::CGuiHandler() {

}

void CGuiHandler::showMessage(std::string message) {
    std::shared_ptr<CGameTextPanel> panel = std::make_shared<CGameTextPanel>();
    panel->setText(message);
    _game.lock()->getGui()->addObject(panel);
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {

}
