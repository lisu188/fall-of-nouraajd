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

void CGameObject::setProperty(QString name, QVariant property) {
    QByteArray byteArray = name.toUtf8();
    const char* cString = byteArray.constData();
    this->QObject::setProperty ( cString,property );
}

QVariant CGameObject::property(QString name) const {
    QByteArray byteArray = name.toUtf8();
    const char* cString = byteArray.constData();
    return this->QObject::property ( cString );
}

void CGameObject::setStringProperty(QString name, QString value) {
    this->setProperty ( name, value ) ;
}

void CGameObject::setBoolProperty(QString name, bool value) {
    this->setProperty ( name,value );
}

void CGameObject::setNumericProperty(QString name, int value) {
    this->setProperty ( name,value );
}

QString CGameObject::getStringProperty(QString name) const {
    return this->property ( name ).toString();
}

bool CGameObject::getBoolProperty(QString name) const {
    return this->property ( name ).toBool();
}

int CGameObject::getNumericProperty(QString name) const {
    return this->property ( name ).toInt();
}

void CGameObject::incProperty(QString name, int value) {
    this->setNumericProperty ( name,this->getNumericProperty ( name )+value );
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

