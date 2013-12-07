#ifndef ANIMATEDOBJECT_H
#define ANIMATEDOBJECT_H

#include "animation.h"

#include <QGraphicsPixmapItem>
#include <QTimer>

class AnimatedObject : private QObject,protected QGraphicsPixmapItem
{
    Q_OBJECT
public:
    explicit AnimatedObject();
    ~AnimatedObject();
protected:
    Animation *animation;
    void setPixmap(const QPixmap &pixmap);
    void setAnimation(std::string path);



private:
    QTimer *timer;

private slots:
    void animate();

};

#endif // ANIMATEDOBJECT_H
