#include "object/CObject.h"

CAnimatedObject::CAnimatedObject() {
    setShapeMode(QGraphicsPixmapItem::BoundingRectShape);
    this->setAcceptHoverEvents(true);
}

CAnimatedObject::~CAnimatedObject() {

}

QPointF CAnimatedObject::mapToParent(int a, int b) {
    return QGraphicsItem::mapToParent(QPointF(a, b));
}

void CAnimatedObject::setAnimation(QString path) {
    this->path = path;
    staticAnimation = CAnimationProvider::getAnim(path);
    if (staticAnimation) {
        animate();
    }
}

QString CAnimatedObject::getAnimation() {
    return this->path;
}


void CAnimatedObject::animate() {
    int time = staticAnimation->getTime();
    setPixmap(*staticAnimation->getImage());
    if (time == -1) {
        return;
    }
    if (!timer) {
        timer = new QTimer(this);
        timer->setSingleShot(true);
        connect(timer, &QTimer::timeout, this, &CAnimatedObject::animate);
    }
    if (time == 0) {
        time = rand() % 3000;
    }
    timer->setInterval(time);
    timer->start();
    staticAnimation->next();
}
