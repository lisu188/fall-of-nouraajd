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
	this->playerInventoryView= new CPlayerInventoryView ( this );
	this->tradeItemsView=new CTradeItemsView ( this );

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

void CTradePanel::onClickAction ( CGameObject *object ) {
	if ( CItem*item=dynamic_cast<CItem*> ( object ) ) {
		item->drag();
	}
}

void CTradePanel::handleDrop ( CPlayerView *view, CGameObject *object ) {
	CPlayerView *view2=dynamic_cast<CPlayerView*> ( object->toGraphicsItem()->parentItem() );
	if ( CItem *item=dynamic_cast<CItem*> ( object ) ) {
		CPlayer*player=   this->getView()->getScene()->getMap()->getPlayer();
		if ( player&&player->getMarket() ) {
			int cost=item->getPower() * ( item->getPower()+1 ) *100 ;
			if ( view==playerInventoryView&&view2==tradeItemsView ) {
				if ( player->getGold() >=cost ) {
					player->addItem ( item );
					player->getMarket()->remove ( item );
					player->takeGold ( cost );
				}
			} else  if ( view==tradeItemsView&&view2==playerInventoryView ) {
				player->removeFromInventory ( item );
				player->getMarket()->add ( item );
				player->addGold ( cost );
			}
			qDebug() <<player->getGold() <<"\n";
			this->update();
		}
	}
}