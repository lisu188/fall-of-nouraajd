#include "CTradePanel.h"
#include "CGameView.h"
#include "CPlayerView.h"
#include <QDebug>

CTradePanel::CTradePanel() {
	this->setZValue ( 8 );
}

void CTradePanel::showPanel() {
	this->setVisible ( true );
	this->setPos (
	    view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
	                       view->height() / 2 - this->boundingRect().height() / 2 ) );
	this->update();
}

void CTradePanel::hidePanel() {
	this->setVisible ( false );
}

void CTradePanel::update() {
	this->setPos (
	    view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
	                       view->height() / 2 - this->boundingRect().height() / 2 ) );
	playerInventoryView->setPos ( 0, 0 );
	tradeItemsView->setPos (
	    this->boundingRect().width() -
	    tradeItemsView->boundingRect().width(),
	    0 );
	playerInventoryView->update();
	tradeItemsView->update();
	QGraphicsItem::update();
}

void CTradePanel::setUpPanel ( CGameView *view ) {
	this->view=view;
	this->playerInventoryView= new CPlayerInventoryView ( view );
	this->tradeItemsView=new CTradeItemsView ( view );

	playerInventoryView->setZValue ( 3 );
	playerInventoryView->setParentItem ( this );
	playerInventoryView->setAcceptDrops ( true );
	view->getScene()->addItem ( playerInventoryView );

	tradeItemsView->setZValue ( 3 );
	tradeItemsView->setParentItem ( this );
	tradeItemsView->setAcceptDrops ( true );
	view->getScene()->addItem ( tradeItemsView );
}

QString CTradePanel::getPanelName() {
	return "CTradePanel";
}


QRectF CTradePanel::boundingRect() const {
	return QRectF ( 0, 0, 400, 300 );
}

void CTradePanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * ) {
	painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
}

std::set<CItem *> *CTradePanel::getItems() {
	return &items;
}

void CTradePanel::onClickAction ( CGameObject *object ) {
	qDebug() <<dynamic_cast<CListView*> ( object->toGraphicsItem()->parentItem() )->metaObject()->className() <<":"
	         <<dynamic_cast<QObject*> ( object )->metaObject()->className() <<"\n";
}
