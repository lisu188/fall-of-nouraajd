#pragma once
#include "CGlobal.h"

class CAnimation;
class CAnimatedObject : public QObject, public QGraphicsPixmapItem {
    Q_OBJECT
    Q_PROPERTY ( QString animation READ getAnimation WRITE setAnimation USER true )
public:
    CAnimatedObject();
    virtual ~CAnimatedObject();
    QPointF mapToParent ( int a, int b );
    void setAnimation ( QString path );
    QString getAnimation();
private:
    QString path;
    QTimer *timer=0;
    CAnimation *staticAnimation=0;
    void animate();
};
