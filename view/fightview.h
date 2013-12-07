#include <QGraphicsItem>

#ifndef FIGHTVIEW_H
#define FIGHTVIEW_H
class CreatureFightView;
class Creature;

class FightView : public QGraphicsItem
{
public:
    FightView();
    static Creature *selected;

public:
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
};

class CreatureFightView : public QGraphicsItem
{
private:
    Creature *creature;
public:
    CreatureFightView(Creature *creature);
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);

    // QGraphicsItem interface
protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
};

#endif // FIGHTVIEW_H
