#include "CMapObject.h"
#include "CMap.h"
#include "CGameScene.h"
#include "CCreature.h"
#include "CTile.h"
#include "CScriptEngine.h"

CMapObject::CMapObject() {
	connect ( this,&CGameObject::mapChanged,this,&CMapObject::onMapChanged );
//	statsView.setParentItem ( this );
//	statsView.setVisible ( true );
//	statsView.setText ( " " );
//	statsView.setPos ( -this->mapToParent ( 0, 0 ).x(),
//	                   -statsView.boundingRect().height() );
}

CMapObject::~CMapObject() {

}

CGameObject::~CGameObject() {

}

QString CMapObject::getTooltip() const {
	return tooltip;
}

void CMapObject::setTooltip ( const QString &value ) {
	tooltip = value;
}

void CMapObject::move ( int x, int y ,int z ) {
	if ( dynamic_cast<Moveable*> ( this ) ) {
		if ( !getMap()->getTile ( posx + x, posy + y, posz )->canStep() ) {
			return;
		}
		dynamic_cast<Moveable*> ( this ) ->beforeMove();
	}

	posx += x;
	posy += y;
	posz += z;
	setPos ( posx * 50, posy * 50 );

	if ( dynamic_cast<Moveable*> ( this ) ) {
		dynamic_cast<Moveable*> ( this ) ->afterMove();
	}
}

void CMapObject::move ( Coords coords ) {
	this->move ( coords.x,coords.y,coords.z );
}

void CMapObject::moveTo ( int x, int y, int z ) {
	move ( x - posx, y - posy ,z-posz );
}

void CMapObject::moveTo ( Coords coords ) {
	this->moveTo ( coords.x,coords.y,coords.z );
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

void CMapObject::onTurn ( CGameEvent * ) {

}

void CMapObject::onCreate ( CGameEvent * ) {

}

void CMapObject::onDestroy ( CGameEvent * ) {

}

void CMapObject::onMapChanged() {
	this->QObject::setParent ( getMap() );
	//	statsView.setParentItem ( this );
	//	statsView.setVisible ( false );
	//	statsView.setPos ( 50, 0 );
	//	statsView.setZValue ( this->zValue() + 1 );
	if ( this->scene() != getMap()->getScene() ) {
		getMap()->getScene()->addItem ( this );
	}
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
    getMap()->getScriptEngine()->callFunction ( "game.switchClass", boost::ref ( event ),getMap()->getScriptEngine()->getObject ( getMap()->getMapName()+"."+value )  );
}

void CEvent::onEnter ( CGameEvent * ) {

}

void CEvent::onLeave ( CGameEvent * ) {

}

QString CGameObject::getObjectType() const {
	return this->objectType;
}

void CGameObject::setObjectType ( const QString &value ) {
	this->objectType=value;
}

CMap *CGameObject::getMap() {
	return this->map;
}

void CGameObject::setMap ( CMap *map ) {
	this->map=map;
	Q_EMIT mapChanged();
}
