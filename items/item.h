#include <animation/animatedobject.h>

#include <view/listitem.h>

#include <stats/stats.h>


#ifndef ITEM_H
#define ITEM_H
class Creature;
class Item : private ListItem
{
public:
    Item();
    ~Item();
    bool isSingleUse() {
        return singleUse;
    }
    void setPos(QPointF point);
    virtual void onEquip(Creature *creature);
    virtual void onUnequip(Creature *creature);

protected:
    void setAnimation(std::string path);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    virtual void onUse(Creature *creature)=0;
    bool singleUse;
    Stats *bonus=0;
    std::string className;
};

#endif // ITEM_H
