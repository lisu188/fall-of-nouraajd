#ifndef PLAYERSTATSVIEW_H
#define PLAYERSTATSVIEW_H

#include "scrollobject.h"

#include <QGraphicsItem>
#include <creatures/player.h>

class PlayerStatsView : public QGraphicsItem
{
public:
    explicit PlayerStatsView(Player *player);
private:
    Player* player;

    // QGraphicsItem interface
public:
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *);
};

#endif // PLAYERSTATSVIEW_H
