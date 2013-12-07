#ifndef MAPOBJECTANIMATION_H
#define MAPOBJECTANIMATION_H

#include <QGraphicsItemAnimation>

class PlayerAnimation : public QGraphicsItemAnimation
{
public:
    explicit PlayerAnimation(QObject *parent = 0);
protected:
    virtual void	afterAnimationStep ( qreal step );
};

#endif // MAPOBJECTANIMATION_H
