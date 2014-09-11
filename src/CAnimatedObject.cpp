#include <QDrag>
#include <QMimeData>
#include <QThread>
#include <QApplication>
#include "CAnimatedObject.h"
#include "CAnimationProvider.h"
#include "CGameScene.h"
#include "QDebug"
#include "Util.h"

CAnimatedObject::CAnimatedObject() {
	this->moveToThread ( QApplication::instance()->thread() );
	timer = 0;
	setShapeMode ( QGraphicsPixmapItem::BoundingRectShape );
}

CAnimatedObject::~CAnimatedObject() {
	if ( timer ) {
		delete timer;
	}
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

void CAnimatedObject::animate() {
	int time = staticAnimation->getTime();
	setPixmap ( *staticAnimation->getImage() );
	if ( time == -1 ) {
		return;
	}
	if ( !timer ) {
		timer = new QTimer ( this );
		timer->setSingleShot ( true );
		connect ( timer, SIGNAL ( timeout() ), this, SLOT ( animate() ) );
	}
	if ( time == 0 ) {
		time = rand() % 3000;
	}
	timer->setInterval ( time );
	timer->start();
	staticAnimation->next();
}

void CAnimatedObject::mousePressEvent ( QGraphicsSceneMouseEvent * ) {
	QDrag *drag = new QDrag ( this );
	drag->setMimeData ( new CObjectData ( this ) );
	drag->setPixmap ( this->pixmap() );
	drag->exec();
}
