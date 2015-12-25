#include "handler/CHandler.h"
#include "core/CGame.h"

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : game(game) {
    initPanels();
}

void CGuiHandler::showMessage(QString msg) {
    std::shared_ptr<AGamePanel> panel = getPanel("CTextPanel");
    panel->setStringProperty("text", msg);
    panel->showPanel();
}

std::shared_ptr<AGamePanel> CGuiHandler::getPanel(QString panel) {
    return panels[panel];
}

void CGuiHandler::showPanel(QString panel) {
    panels[panel]->showPanel();
}

void CGuiHandler::hidePanel(QString panel) {
    panels[panel]->hidePanel();
}

void CGuiHandler::flipPanel(QString panelName) {
    std::shared_ptr<AGamePanel> panel = getPanel(panelName);
    if (panel->isShown()) {
        panel->hidePanel();
    } else {
        panel->showPanel();
    }
}

bool CGuiHandler::isAnyPanelVisible() {
    for (auto it:panels) {
        if (it.second->isShown()) {
            return true;
        }
    }
    return false;
}

void CGuiHandler::refresh() {
    for (auto it:panels) {
        std::shared_ptr<AGamePanel> panel = it.second;
        if (panel->isShown()) {
            panel->update();
        }
    }
}

void CGuiHandler::initPanels() {
    std::list<std::shared_ptr<AGamePanel>> viewList{
            std::make_shared<CFightPanel>(),
            std::make_shared<CCharPanel>(),
            std::make_shared<CTextPanel>(),
            std::make_shared<CTradePanel>()};
    for (std::shared_ptr<AGamePanel> it:viewList) {
        panels[it->getPanelName()] = it;
        game.lock()->addObject(it);
        it->setUpPanel(game.lock()->getView());
        qDebug() << "Initialized panel:" << it->metaObject()->className() << "\n";
    }
}
