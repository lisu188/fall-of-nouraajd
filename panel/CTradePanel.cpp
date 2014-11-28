#include "CTradePanel.h"

CTradePanel::CTradePanel() {
}


void CTradePanel::showPanel() {
    this->setVisible ( true );
}

void CTradePanel::hidePanel() {
    this->setVisible ( false );
}

void CTradePanel::update() {
}

void CTradePanel::setUpPanel ( CGameView * ) {
}

QString CTradePanel::getPanelName() {
    return "CTradePanel";
}


QRectF CTradePanel::boundingRect() const {
    return QRect ( 0,0 ,0,0);
}

void CTradePanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget ) {
}
