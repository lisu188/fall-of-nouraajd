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

QString CMapObject::getObjectType() const {
	return objectType;
}

void CMapObject::setObjectType ( const QString &value ) {
	objectType = value;
}

QString CMapObject::getTooltip() const {
	return tooltip;
}

void CMapObject::setTooltip ( const QString &value ) {
	tooltip = value;
}

void CMapObject::setVisitor ( CMapObject *visitor ) {
	this->visitor=visitor;
}

CMapObject *CMapObject::getVisitor() {
	return visitor;
}

void CMapObject::move ( int x, int y ,int z ) {
	if ( CCreature *creature=dynamic_cast<CCreature*> ( this ) ) {
		CTile*tile=getMap()->getTile ( posx + x, posy + y, posz );
		if ( tile->canStep() ) {
			tile->onStep ( creature );
		} else {
			return;
		}
	}
	if ( x == 0 && y == 0 ) {
		return;
	}
	posx += x;
	posy += y;
	posz += z;
	if ( getMap() ) {
		setPos ( posx * 50, posy * 50 );
		if (  dynamic_cast<CPlayer*> ( this ) ) {
			getMap()->ensureSize();
		}
	}
}

void CMapObject::moveTo ( int x, int y, int z ) {
	move ( x - posx, y - posy ,z-posz );
}

int CMapObject::getPosY() const {
	return posy;
}

int CMapObject::getPosZ() const {
	return posz;
}

int CMapObject::getPosX() const {
	return posx;
}

void CMapObject::onEnter () {

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

CMap *CMapObject::getMap() {
	return map;
}

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

bool CEvent::isEnabled() {
	return enabled;
}

void CEvent::setEnabled ( bool enabled ) {
	this->enabled = enabled;
}

QString CEvent::getEventClass() {
	return eventClass;
}

void CEvent::setEventClass ( const QString &value ) {
	this->eventClass=value;
	CEvent* event=this;
	CScriptEngine::getInstance()->callFunction ( "game.switchClass", boost::ref ( event ),CScriptEngine::getInstance()->getObject ( getMap()->getMapName()+"."+value )  );
}


