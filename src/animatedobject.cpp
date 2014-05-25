#include "animatedobject.h"
#include "animationprovider.h"

#include <src/destroyer.h>

#include <src/gamescene.h>
#include <QDrag>
#include <QMimeData>

AnimatedObject::AnimatedObject()
{
    Destroyer::add(this);
    timer = 0;
    setShapeMode(QGraphicsPixmapItem::BoundingRectShape);
}

AnimatedObject::~AnimatedObject()
{
    Destroyer::remove(this);
    if (timer) {
        delete timer;
    }
}

QPointF AnimatedObject::mapToParent(int a, int b)
{
    return QGraphicsItem::mapToParent(QPointF(a, b));
}

void AnimatedObject::setAnimation(std::string path, int size)
{
    staticAnimation = AnimationProvider::getAnim(path, size);
    if (staticAnimation) {
        animate();
    }
}

void AnimatedObject::animate()
{
    int time = staticAnimation->getTime();
    setPixmap(*staticAnimation->getImage());
    if (time == -1) {
        return;
    }
    if (!timer) {
        timer = new QTimer(this);
        timer->setSingleShot(true);
        connect(timer, SIGNAL(timeout()), this, SLOT(animate()));
    }
    if (time == 0) {
        time = rand() % 3000;
    }
    timer->setInterval(time);
    timer->start();
    staticAnimation->next();
}

void AnimatedObject::mousePressEvent(QGraphicsSceneMouseEvent *)
{
    QDrag *drag = new QDrag(this);
    QMimeData *mimeData = new QMimeData();
    drag->setMimeData(mimeData);
    drag->setPixmap(this->pixmap());
    drag->exec();
}
