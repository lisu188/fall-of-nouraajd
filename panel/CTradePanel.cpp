#include "CTradePanel.h"
#include "CGameView.h"

CTradePanel::CTradePanel() {
	this->setZValue ( 8 );
}


void CTradePanel::showPanel() {
	this->setVisible ( true );
	this->setPos (
	    view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
	                       view->height() / 2 - this->boundingRect().height() / 2 ) );
}

void CTradePanel::hidePanel() {
	this->setVisible ( false );
}

void CTradePanel::update() {
}

void CTradePanel::setUpPanel ( CGameView *view ) {
	this->view=view;
}

QString CTradePanel::getPanelName() {
	return "CTradePanel";
}


QRectF CTradePanel::boundingRect() const {
	return QRectF ( 0, 0, 400, 300 );
}

void CTradePanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget ) {
	painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
}
