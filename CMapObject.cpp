#include "CMapObject.h"
#include "CMap.h"
#include "CGameScene.h"
#include "CCreature.h"
#include "CTile.h"
#include "CScriptEngine.h"

CMapObject::CMapObject() {
//	statsView.setParentItem ( this );
//	statsView.setVisible ( true );
//	statsView.setText ( " " );
//	statsView.setPos ( -this->mapToParent ( 0, 0 ).x(),
//	                   -statsView.boundingRect().height() );
}


CMapObject::~CMapObject() {

}
QString CMapObject::getTypeName() const {
	return typeName;
}

void CMapObject::setTypeName ( const QString &value ) {
	typeName = value;
}
QString CMapObject::getTooltip() const {
	return tooltip;
}

void CMapObject::setTooltip ( const QString &value ) {
	tooltip = value;
}

int CMapObject::getPosY() const { return posy; }

int CMapObject::getPosZ() const { return posz; }

int CMapObject::getPosX() const { return posx; }

void CMapObject::move ( int x, int y ) {
	bool canStep =map->getTile ( posx + x, posy + y, posz )->canStep();
	if ( !canStep ) {
		return;
	}
	if ( x == 0 && y == 0 ) {
		return;
	}
	posx += x;
	posy += y;
	if ( map ) {
		setPos ( posx * 50, posy * 50 );
		if ( map->getScene()->getPlayer() ==this ) {
			map->ensureSize();
		}
	}
}

void CMapObject::moveTo ( int x, int y, int z ) {
	posz = z;
	move ( x - posx, y - posy );
}


void CMapObject::onEnter() {

}

void CMapObject::onMove() {

}

void CMapObject::onCreate() {

}

void CMapObject::onDestroy() {

}

void CMapObject::setMap ( CMap *map ) {
	if ( !map ) {
		return;
	}
	this->map = map;
//	statsView.setParentItem ( this );
//	statsView.setVisible ( false );
//	statsView.setPos ( 50, 0 );
//	statsView.setZValue ( this->zValue() + 1 );
	if ( this->scene() != map->getScene() ) {
		map->getScene()->addItem ( this );
	}
}

CMap *CMapObject::getMap() { return map; }

void CMapObject::setVisible ( bool vis ) {
	QGraphicsPixmapItem::setVisible ( vis );
}

Coords CMapObject::getCoords() {
	return Coords ( posx,posy,posz );
}

void CMapObject::setCoords ( Coords coords ) {
	this->moveTo ( coords.x,coords.y,coords.z );
}

void CMapObject::setNumber ( int i, int x ) {
	this->QGraphicsItem::setVisible ( true );
	int px = i % x * 50;
	int py = i / x * 50;
	this->QGraphicsItem::setPos ( px, py );
}

void CMapObject::hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) {
//	statsView.setVisible ( true );
//	statsView.setText ( tooltip );
//	statsView.setPos ( 0, 0 - statsView.boundingRect().height() );
	event->setAccepted ( true );
}

void CMapObject::hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) {
	//statsView.setVisible ( false );
	event->setAccepted ( true );
}

CEvent::CEvent() {

}

CEvent::CEvent ( const CEvent & ) {

}

void CEvent::onEnter() {
	if ( this->isEnabled() ) {
		CEvent* event=this;
		getMap()->getEvents() [this->objectName().toStdString().c_str()] ( boost::ref ( event ) );
	}
}

bool CEvent::isEnabled() {
	return enabled;
}

void CEvent::setEnabled ( bool enabled ) {
	this->enabled = enabled;
}

