#include "CGameObject.h"
#include "CMap.h"
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

std::shared_ptr<CMap> CGameObject::getMap() {
    return map.lock();
}

void CGameObject::setMap ( std::shared_ptr<CMap> map ) {
    this->map=map;
}

QString CGameObject::getTooltip() const {
    return tooltip;
}

void CGameObject::setTooltip ( const QString &value ) {
    tooltip = value;
}

void CGameObject::setVisible ( bool vis ) {
    QGraphicsPixmapItem::setVisible ( vis );
}

void CGameObject::drag() {
    if ( std::shared_ptr<CGameObject> object= this->ptr()  ) {
        QDrag *drag = new QDrag ( this );
        drag->setMimeData ( new CObjectData ( object ) );
        drag->setPixmap ( this->pixmap() );
        drag->exec();
    }
}

void CGameObject::hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) {
    if ( hasTooltip ) {
        statsView.setVisible ( true );
        QString tooltipText=getTooltip();
        if ( tooltipText=="" ) {
            tooltipText=getObjectType();
        }
        statsView.setText ( tooltipText );
        statsView.setPos ( 0, 0 - statsView.boundingRect().height() );
        event->setAccepted ( true );
    }
}

void CGameObject::hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) {
    statsView.setVisible ( false );
    event->setAccepted ( true );
}

void CGameObject::mousePressEvent ( QGraphicsSceneMouseEvent * ) {
    getMap()->getMouseHandler()->handleClick ( this->ptr() );
}

