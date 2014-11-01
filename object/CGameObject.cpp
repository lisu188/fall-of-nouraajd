#include "CGameObject.h"
#include <QGraphicsSceneHoverEvent>

CGameObject::~CGameObject() {

}

CGameObject::CGameObject() {
	this->setAcceptHoverEvents ( true );
	statsView.setParentItem ( this );
	statsView.setVisible ( true );
	statsView.setText ( " " );
	statsView.setPos ( -this->mapToParent ( 0, 0 ).x(),
	                   -statsView.boundingRect().height() );
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

QString CGameObject::getTooltip() const {
	return tooltip;
}

void CGameObject::setTooltip ( const QString &value ) {
	tooltip = value;
}

void CGameObject::hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) {
	statsView.setVisible ( true );
	statsView.setText ( getTooltip() );
	statsView.setPos ( 0, 0 - statsView.boundingRect().height() );
	event->setAccepted ( true );
}

void CGameObject::hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) {
	statsView.setVisible ( false );
	event->setAccepted ( true );
}

