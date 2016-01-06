#include "CGameObject.h"
#include "core/CMap.h"

CGameObject::~CGameObject() {

}

CGameObject::CGameObject() {
    //TODO: tooltip
//    this->setAcceptHoverEvents ( true );
//    statsView.setParentItem ( this );
//    statsView.setVisible ( true );
//    statsView.setText ( " " );
//    statsView.setPos ( -this->mapToParent ( 0, 0 ).x(),
//                       -statsView.boundingRect().height() );
}

std::shared_ptr<CMap> CGameObject::getMap() {
    return map.lock();
}

void CGameObject::setMap ( std::shared_ptr<CMap> map ) {
    this->map = map;
}

void CGameObject::setStringProperty ( std::string name, std::string value ) {
    this->setProperty ( name, value );
}

void CGameObject::setBoolProperty ( std::string name, bool value ) {
    this->setProperty ( name, value );
}

void CGameObject::setNumericProperty ( std::string name, int value ) {
    this->setProperty ( name, value );
}

std::string CGameObject::getStringProperty ( std::string name ) const {
    return this->getProperty<std::string> ( name );
}

bool CGameObject::getBoolProperty ( std::string name ) const {
    return this->getProperty<bool> ( name );
}

int CGameObject::getNumericProperty ( std::string name ) const {
    return this->getProperty<int> ( name );
}

void CGameObject::incProperty ( std::string name, int value ) {
    this->setNumericProperty ( name, this->getNumericProperty ( name ) + value );
}

//std::string CGameObject::getTooltip() const {
//    return tooltip;
//}
//
//void CGameObject::setTooltip ( const std::string &value ) {
//    tooltip = value;
//}
//TODO: drag
//void CGameObject::drag() {
//    if ( std::shared_ptr<CGameObject> object = this->ptr() ) {
//        QDrag *drag = new QDrag ( this );
//        drag->setMimeData ( new CObjectData ( object ) );
//        drag->setPixmap ( this->pixmap() );
//        drag->exec();
//    }
//}
//TODO: tooltip
//
//void CGameObject::hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) {
//    if ( hasTooltip ) {
//        statsView.setVisible ( true );
//        std::string tooltipText = getTooltip();
//        if ( tooltipText == "" ) {
//            tooltipText = getType();
//        }
//        statsView.setText ( tooltipText );
//        statsView.setPos ( 0, 0 - statsView.boundingRect().height() );
//        event->setAccepted ( true );
//    }
//}
//
//void CGameObject::hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) {
//    statsView.setVisible ( false );
//    event->setAccepted ( true );
//}

//TODO: mouse click
//void CGameObject::mousePressEvent ( QGraphicsSceneMouseEvent * ) {
//    getMap()->getMouseHandler()->handleClick ( this->ptr() );
//}

