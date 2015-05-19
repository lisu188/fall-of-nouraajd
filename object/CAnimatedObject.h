#pragma once
#include "CGlobal.h"

class CAnimation;
class CAnimatedObject : public QObject, protected QGraphicsPixmapItem {
    Q_OBJECT
    Q_PROPERTY ( QString animation READ getAnimation WRITE setAnimation USER true )

    friend class CGame;
    friend class CGameView;
    friend class CListView;
    friend class CItemSlot;
public:
    CAnimatedObject();
    virtual ~CAnimatedObject();
    QPointF mapToParent ( int a, int b );
    void setAnimation ( QString path );
    QString getAnimation();
    QGraphicsItem *toGraphicsItem();
    void drag();
private:
    QString path;
    QTimer *timer=0;
    CAnimation *staticAnimation=0;
    void animate();
};
