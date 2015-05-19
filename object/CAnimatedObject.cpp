#include "object/CObject.h"
#include "provider/CProvider.h"
#include "CGame.h"
#include "CUtil.h"

CAnimatedObject::CAnimatedObject() {
    setShapeMode ( QGraphicsPixmapItem::BoundingRectShape );
    this->setAcceptHoverEvents ( true );
}

CAnimatedObject::~CAnimatedObject() {

}

QPointF CAnimatedObject::mapToParent ( int a, int b ) {
    return QGraphicsItem::mapToParent ( QPointF ( a, b ) );
}

void CAnimatedObject::setAnimation ( QString path ) {
    this->path=path;
    staticAnimation = CAnimationProvider::getAnim ( path );
    if ( staticAnimation ) {
        animate();
    }
}

QString CAnimatedObject::getAnimation() {
    return this->path;
}

QGraphicsItem *CAnimatedObject::toGraphicsItem() {
    return dynamic_cast<QGraphicsItem*> ( this );
}

void CAnimatedObject::drag() {
    if ( CGameObject *object=dynamic_cast<CGameObject*> ( this ) ) {
        QDrag *drag = new QDrag ( this );
        drag->setMimeData ( new CObjectData ( object ) );
        drag->setPixmap ( this->pixmap() );
        drag->exec();
    }
}

void CAnimatedObject::animate() {
    int time = staticAnimation->getTime();
    setPixmap ( *staticAnimation->getImage() );
    if ( time == -1 ) {
        return;
    }
    if ( !timer ) {
        timer = new QTimer ( this );
        timer->setSingleShot ( true );
        connect ( timer,&QTimer:: timeout, this,&CAnimatedObject::animate );
    }
    if ( time == 0 ) {
        time = rand() % 3000;
    }
    timer->setInterval ( time );
    timer->start();
    staticAnimation->next();
}
