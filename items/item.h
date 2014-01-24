#include <animation/animatedobject.h>

#include <view/listitem.h>

#include <stats/stats.h>

#ifndef ITEM_H
#define ITEM_H
class Creature;
class Interaction;
class Item : public ListItem
{
public:
    Item();
    bool isSingleUse();
    void setPos(QPointF point);
    virtual void onEquip(Creature *creature);
    virtual void onUnequip(Creature *creature);
    static Item *getItem(std::string name);
    virtual void onUse(Creature *creature)=0;
    virtual void onEnter();
    virtual void onMove() {}
    virtual Json::Value saveToJson();
    virtual bool canSave();

protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    bool singleUse;
    Stats bonus;
    void loadFromJson(Json::Value config);
    Interaction *interaction;
    int power;
};

#endif // ITEM_H
