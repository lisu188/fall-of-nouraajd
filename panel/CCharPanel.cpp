#include "CGamePanel.h"
#include "CGameScene.h"
#include <qpainter.h>
#include <sstream>
#include <QDebug>
#include <qpainter.h>
#include "CGameView.h"
#include "CPlayerView.h"
#include "CCreature.h"
#include <QBitmap>
#include <QFont>
#include "CResourcesHandler.h"


CCharPanel::CCharPanel() {
	setZValue ( 6 );
	setVisible ( false );
}

CCharPanel::CCharPanel ( const CCharPanel & ) {

}


QRectF CCharPanel::boundingRect() const {
	return QRectF ( 0, 0, 400, 300 );
}

void CCharPanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                         QWidget * ) {
	painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
}

void CCharPanel::showPanel () {
	this->setVisible ( true );
	this->update();
}

void CCharPanel::hidePanel() {
	this->setVisible ( false );
}

void CCharPanel::setUpPanel ( CGameView *view ) {
	this->view=view;
	playerInventoryView = new CPlayerInventoryrView ( view );
	playerInventoryView->setZValue ( 3 );
	playerInventoryView->setParentItem ( this );
	playerInventoryView->setAcceptDrops ( true );
	view->getScene()->addItem ( playerInventoryView );
	playerEquippedView = new CPlayerEquippedView ( view );
	playerEquippedView->setZValue ( 3 );
	playerEquippedView->setParentItem ( this );
	view->getScene()->addItem ( playerEquippedView );
	backpack=new BackPackObject ( view ,this );
	backpack->show();
}

void CCharPanel::update() {
	this->setPos (
	    view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
	                       view->height() / 2 - this->boundingRect().height() / 2 ) );
	playerInventoryView->setPos ( 0, 0 );
	playerEquippedView->setPos (
	    this->boundingRect().width() -
	    playerEquippedView->boundingRect().width(),
	    0 );
	backpack->move ( 0, view->size().height() - backpack->height() );
	playerInventoryView->update();
	playerEquippedView->update();
	QGraphicsItem::update();
}

QString CCharPanel::getPanelName() {
	return "CCharPanel";
}

BackPackObject::BackPackObject ( CGameView* view ,CCharPanel *panel ) :QWidget ( view ) {
	this->panel=panel;
	pixmap.load ( CResourcesHandler::getInstance()->getPath ( "images/backpack.png" ) );
	pixmap.setMask ( pixmap.createHeuristicMask() );
	pixmap =
	    pixmap.scaled ( 75, 75, Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
	setFixedSize ( 75, 75 );
	time = QDateTime::currentMSecsSinceEpoch();
}

void BackPackObject::mousePressEvent ( QMouseEvent * ) {
	if ( (   int ) QDateTime::currentMSecsSinceEpoch() - time >
	        (   int ) 500 ) {
		if ( !panel->isShown() ) {
			panel->showPanel();
		} else {
			panel->hidePanel();
		}
		time = QDateTime::currentMSecsSinceEpoch();
	}
}

void BackPackObject::paintEvent ( QPaintEvent * ) {
	QPainter painter;
	painter.begin ( this );
	painter.setRenderHint ( QPainter::Antialiasing );
	painter.drawPixmap ( 0, 0, 75, 75, pixmap );
	painter.end();
}

