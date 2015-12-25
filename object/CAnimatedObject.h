#pragma once

#include "core/CGlobal.h"
#include "core/CDefines.h"

class CAnimation;

class CAnimatedObject : public QObject, public QGraphicsPixmapItem {
Q_OBJECT
    Q_PROPERTY (QString animation
                        READ
                                getAnimation
                        WRITE
                                setAnimation
                        USER
                        true)
public:
    CAnimatedObject();

    virtual ~CAnimatedObject();

    QPointF mapToParent(int a, int b);

    void setAnimation(QString path);

    QString getAnimation();

private:
    QString path;
    QTimer *timer = 0;
    std::shared_ptr<CAnimation> staticAnimation;

    void animate();
};

GAME_PROPERTY (CAnimatedObject)
