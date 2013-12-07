#include "animatedobject.h"
#include "animationprovider.h"

#include <destroyer/destroyer.h>

AnimatedObject::AnimatedObject()
{
    Destroyer::add(this);
    timer=0;
    setShapeMode(QGraphicsPixmapItem::BoundingRectShape);
}

AnimatedObject::~AnimatedObject()
{
    Destroyer::remove(this);
    if(timer)delete timer;
}


void AnimatedObject::setPixmap(const QPixmap &pixmap)
{
    QGraphicsPixmapItem::setPixmap(pixmap);
}

void AnimatedObject::setAnimation(std::string path)
{
    animation=AnimationProvider::getAnim(path);
    animate();
}

void AnimatedObject::animate()
{
    int time=animation->getTime();
    setPixmap(*animation->getImage());
    if(time==-1)return;
    if(!timer)
    {
        timer = new QTimer(this);
        connect(timer, SIGNAL(timeout()), this, SLOT(animate()));
    }
    if(time==0)time=rand()%3000;
    timer->start(time);
    animation->next();
}
