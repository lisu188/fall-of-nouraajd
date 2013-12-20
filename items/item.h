#include <animation/animatedobject.h>

#include <view/listitem.h>

#include <stats/stats.h>

#ifndef ITEM_H
#define ITEM_H
class Creature;
class Interaction;
class Item : private ListItem
{
public:
    bool isSingleUse();
    void setPos(QPointF point);
    virtual void onEquip(Creature *creature);
    virtual void onUnequip(Creature *creature);

    static Item *getItem(const char *name);
    std::string className;

protected:
    void setAnimation(std::string path);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    virtual void onUse(Creature *creature)=0;
    bool singleUse;
    Stats bonus;

    void loadFromJson(Json::Value config);
    Interaction *interaction;
    int power;
    Item();
};

#endif // ITEM_H
