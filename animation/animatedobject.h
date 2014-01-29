#ifndef ANIMATEDOBJECT_H
#define ANIMATEDOBJECT_H

#include "animation.h"

#include <QGraphicsPixmapItem>
#include <QTimer>
#include <QWidget>

class AnimatedObject : public QWidget,public QGraphicsPixmapItem
{
    Q_OBJECT
public:
    explicit AnimatedObject();
    ~AnimatedObject();
    QPointF mapToParent(int a,int b);
protected:
    Animation *animation;
    void setAnimation(std::string path, int size);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *);
private:
    QTimer *timer;
private slots:
    void animate();

};

#endif // ANIMATEDOBJECT_H
