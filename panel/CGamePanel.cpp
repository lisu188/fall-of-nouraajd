#include "CGamePanel.h"

AGamePanel::AGamePanel() {
    this->hasTooltip=false;
    this->setVisible ( false );
}

AGamePanel::~AGamePanel() {

}

void AGamePanel::handleDrop ( std::shared_ptr<CPlayerView>, std::shared_ptr<CGameObject> ) {
    fail ( "No drop handler implemented" );
}

bool AGamePanel::isShown() {
    return this->isVisible();
}

std::shared_ptr<CGameView> AGamePanel::getView() {
    return view.lock();
}

void AGamePanel::onClickAction ( std::shared_ptr<CGameObject> ) {
    this->hidePanel();
}

