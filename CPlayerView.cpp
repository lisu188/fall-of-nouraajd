#include "CPlayerView.h"
#include "object/CObject.h"
#include "handler/CHandler.h"
#include "CMap.h"
#include <qpainter.h>
#include <QWidget>
#include <QDrag>
#include <QMimeData>
#include "CGameScene.h"
#include <qpainter.h>
#include <sstream>
#include "CGameView.h"

PlayerStatsView::PlayerStatsView() {
	this->player = player;
	setFixedSize ( 250, 75 );
}

void PlayerStatsView::paintEvent ( QPaintEvent * ) {
	if ( !player ) {
		return;
	}
	QPainter painter;
	painter.begin ( this );
	painter.setRenderHint ( QPainter::Antialiasing );
	QTextOption opt ( Qt::AlignCenter );
	float barx = 250;
	float bary = 25;
	painter.fillRect ( 0, 0, barx, bary * 3, QColor ( "GREEN" ) );
	std::ostringstream hpStream;
	hpStream << player->hp;
	hpStream << "/";
	hpStream << player->hpMax;
	painter.fillRect ( 0, bary * 0, barx * player->getHpRatio() / 100.0, bary,
	                   QColor ( "RED" ) );
	painter.drawText ( QRectF ( 0, bary * 0, barx, bary ), hpStream.str().c_str(),
	                   opt );
	std::ostringstream manaStream;
	manaStream << player->mana;
	manaStream << "/";
	manaStream << player->manaMax;
	painter.fillRect ( 0, bary * 1, barx * player->getManaRatio() / 100.0, bary,
	                   QColor ( "BLUE" ) );
	painter.drawText ( QRectF ( 0, bary * 1, barx, bary ), manaStream.str().c_str(),
	                   opt );
	std::ostringstream expStream;
	expStream << player->exp;
	expStream << "/";
	expStream << ( player->level ) * ( player->level + 1 ) * 500;
	painter.fillRect ( 0, bary * 2, barx * player->getExpRatio() / 100.0, bary,
	                   QColor ( "YELLOW" ) );
	painter.drawText ( QRectF ( 0, bary * 2, barx, bary ), expStream.str().c_str(),
	                   opt );
	painter.end();
}

void PlayerStatsView::setPlayer ( CPlayer *value ) {
	player = value;
	connect ( player,&CPlayer::statsChanged, this,&PlayerStatsView::update );
}

void PlayerStatsView::update() {
	QWidget::update();
}

CListView::CListView ( AGamePanel *panel ) :CPlayerView ( panel ) {
	this->setZValue ( 3 );
	curPosition = 0;
	right = new CScrollObject ( this, true );
	left = new CScrollObject ( this, false );
	x = 4, y = 4;
	pixmap.load ( CResourcesProvider::getInstance()->getPath ( "images/item.png" ) );
	pixmap = pixmap.scaled ( 50,50,
	                         Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
	left->setPos ( 0, y *50 );
	right->setPos ( ( x - 1 ) *50, y *50 );
}

void CListView::update() {
	this->QGraphicsObject::update();
	auto items=getItems();
	if ( items.size() - x * y < curPosition ) {
		curPosition = items.size() - x * y;
	}
	QList<QGraphicsItem *> list = childItems();
	for ( auto childIter = list.begin(); childIter != list.end(); childIter++ ) {
		if ( *childIter == right || *childIter == left ) {
			continue;
		}
		( *childIter )->setParentItem ( 0 );
		( *childIter )->setVisible ( false );
	}
	int i = 0;
	for ( auto itemIter = items.begin(); itemIter != items.end(); i++, itemIter++ ) {
		QGraphicsItem *item = *itemIter;
		item->setVisible ( false );
		item->setParentItem ( 0 );
		unsigned int position = i - curPosition;
		if ( position < x * y ) {
			item->setParentItem ( this );
			item->setVisible ( true );
			setNumber ( item, position, x );
		}
	}
	right->setVisible ( items.size() > x * y );
	left->setVisible ( items.size() > x * y );
}

QRectF CListView::boundingRect() const {
	auto items=getItems();
	return QRect ( 0, 0, pixmap.size().width() * x,
	               pixmap.size().height() * ( items.size() > x * y ? y + 1 : y ) );
}

void CListView::paint ( QPainter *painter,
                        const QStyleOptionGraphicsItem *,
                        QWidget * ) {
	for ( unsigned  int i = 0; i < x; i++ )
		for ( unsigned  int j = 0; j < y; j++ ) {
			painter->drawPixmap ( i *50, j *50,
			                      pixmap );
		}
}

void CListView::updatePosition ( int i ) {
	if ( curPosition==0&&i<0 ) {
		return;
	}
	curPosition += i;
	update();
}

void CListView::setXY ( int x, int y ) {
	this->x = x;
	this->y = y;
}

CPlayerView::CPlayerView ( AGamePanel *panel ) :panel ( panel ) {

}

void CPlayerView::dropEvent ( QGraphicsSceneDragDropEvent *event ) {
	const CObjectData *helper=dynamic_cast<const CObjectData*> ( event->mimeData() );
	panel->handleDrop ( this,helper->getSource() );
}

CScrollObject::CScrollObject ( CListView *stats, bool isRight ) {
	this->isRight = isRight;
	this->setZValue ( 1 );
	this->stats = stats;
	if ( !isRight ) {
		this->setAnimation ( "images/arrows/left" );
	} else {
		this->setAnimation ( "images/arrows/right" );
	}
	setParentItem ( stats );
}

void CScrollObject::setVisible ( bool visible ) {
	if ( visible && this->scene() != stats->scene() ) {
		stats->scene()->addItem ( this );
	}
	QGraphicsItem::setVisible ( visible );
}

void CScrollObject::mousePressEvent ( QGraphicsSceneMouseEvent * ) {
	if ( isRight ) {
		stats->updatePosition ( 1 );
	} else  {
		stats->updatePosition ( -1 );
	}
}

CPlayerEquippedView::CPlayerEquippedView ( AGamePanel *panel ) :CPlayerView ( panel ) {
	for ( unsigned  int i = 0; i < 8; i++ ) {
		CItemSlot *slot = new CItemSlot ( i,panel );
		slot->setParentItem ( this );
		slot->setPos ( i % 4 *50, i / 4 *50 );
		itemSlots.push_back ( slot );
	}
}

CItemSlot::CItemSlot ( int number,AGamePanel *panel ) :
	number ( number ),panel ( panel ) {
	pixmap.load ( CResourcesProvider::getInstance()->getPath ( "images/item.png" )  );
	pixmap = pixmap.scaled ( 50, 50,
	                         Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
	this->setAcceptDrops ( true );
}

QRectF CItemSlot::boundingRect() const {
	return QRectF ( 0, 0, 50, 50 );
}

void CItemSlot::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                        QWidget * ) {
	painter->drawPixmap ( 0, 0, pixmap );
}

bool CItemSlot::checkType ( int slot,CItem *item ) {
	QJsonArray config =
	    CConfigurationProvider::getConfig (
	        "slots.json" ).toObject()  [QString::number ( slot )].toObject() ["types"].toArray();
	for (   int i = 0; i < config.size(); i++ ) {
		if ( item->inherits ( config[i].toString().toStdString().c_str() ) ) {
			return true;
		}
	}
	return false;
}

void CItemSlot::update() {
	auto player=panel->getView()->getScene()->getMap()->getPlayer();
	if ( !player ) {
		return;
	}
	auto equipped=player->getEquipped();
	if ( equipped.find ( number ) !=equipped.end() ) {
		CItem *item = equipped.at ( number );
		if ( item ) {
			item->setParentItem ( this );
			item->setPos ( 0, 0 );
			item->setVisible ( true );
			item->QGraphicsItem::update();
		}
	}
	QGraphicsObject::update();
}

int CItemSlot::getNumber() {
	return number;
}

void CItemSlot::dragMoveEvent ( QGraphicsSceneDragDropEvent *event ) {
	QGraphicsObject::dragMoveEvent ( event );
	const CObjectData *helper=dynamic_cast<const CObjectData*> ( event->mimeData() );
	CItem *item = dynamic_cast<CItem*> (  helper->getSource() );
	event->setAccepted ( checkType ( number, item ) );
}

void CItemSlot::dropEvent ( QGraphicsSceneDragDropEvent *event ) {
	QGraphicsObject::dropEvent ( event );
	const CObjectData *helper=dynamic_cast<const CObjectData*> ( event->mimeData() );
	CItem *item = dynamic_cast<CItem*> (  helper->getSource() );
	if ( checkType ( number, item ) ) {
		dynamic_cast<CGameScene*> ( this->scene() )->getMap()->getPlayer()->setItem ( number, item );
	}
	event->acceptProposedAction();
	event->accept();
}


QRectF CPlayerEquippedView::boundingRect() const {
	return QRectF ( 0, 0, 4 *50, 2 *50 );
}

void CPlayerEquippedView::paint ( QPainter *,
                                  const QStyleOptionGraphicsItem *,
                                  QWidget * ) {}

void CPlayerEquippedView::update() {
	for ( std::list<CItemSlot *>::iterator it = itemSlots.begin();
	        it != itemSlots.end(); it++ ) {
		( *it )->update();
	}
	QGraphicsObject::update();
}

CPlayerInventoryView::CPlayerInventoryView ( AGamePanel *panel ) :CListView ( panel ) {

}

std::set<QGraphicsItem *> CPlayerInventoryView::getItems() const {
	std::set<QGraphicsItem *> set;
	auto player=panel->getView()->getScene()->getMap()->getPlayer();
	if ( !player ) {
		return set;
	}
	for ( CItem*  it:player->getInInventory() ) {
		set.insert ( it ->toGraphicsItem() );
	}
	return set;
}


CPlayerIteractionView::CPlayerIteractionView ( AGamePanel *panel ) :CListView ( panel ) {

}

std::set<QGraphicsItem *> CPlayerIteractionView::getItems() const {
	std::set<QGraphicsItem *> set;
	auto player=panel->getView()->getScene()->getMap()->getPlayer();
	if ( !player ) {
		return set;
	}
	for ( CInteraction *  it:player->getInteractions() ) {
		set.insert ( it ->toGraphicsItem() );
	}
	return set;
}

void CListView::setNumber ( QGraphicsItem *item, int i, int x ) {
	item->setVisible ( true );
	int px = i % x * 50;
	int py = i / x * 50;
	item->setPos ( px, py );
}

CTradeItemsView::CTradeItemsView ( AGamePanel *panel  ) :CListView ( panel ) {
}

std::set<QGraphicsItem *> CTradeItemsView::getItems() const {
	std::set<QGraphicsItem *> set;
	CGameScene *scene=panel->getView()->getScene();
	CPlayer* player=scene->getMap()->getPlayer();
	if ( !player || !player->getMarket() ) {
		return set;
	}
	for ( CItem*  it:player->getMarket()->getTradeItems() ) {
		set.insert ( it ->toGraphicsItem() );
	}
	return set;
}
