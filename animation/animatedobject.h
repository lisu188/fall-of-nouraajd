#ifndef ANIMATEDOBJECT_H
#define ANIMATEDOBJECT_H

#include "animation.h"

#include <QGraphicsPixmapItem>
#include <QTimer>
#include <QWidget>

class AnimatedObject : private QWidget,protected QGraphicsPixmapItem
{
    Q_OBJECT
public:
    explicit AnimatedObject();
    ~AnimatedObject();
    QPoint mapToParent(int a,int b);
protected:
    Animation *animation;
    void setPixmap(const QPixmap &pixmap);
    void setAnimation(std::string path);
private:
    QTimer *timer;
private slots:
    void animate();


    // QGraphicsItem interface
protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
};

#endif // ANIMATEDOBJECT_H
