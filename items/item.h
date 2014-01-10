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
    bool isSingleUse();
    void setPos(QPointF point);
    virtual void onEquip(Creature *creature);
    virtual void onUnequip(Creature *creature);
    static Item *getItem(const char *name);
    virtual void onUse(Creature *creature)=0;

protected:
    void setAnimation(std::string path);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    bool singleUse;
    Stats bonus;
    void loadFromJson(Json::Value config);
    Interaction *interaction;
    int power;
    Item();

    // MapObject interface
public:
    virtual void onEnter();
    virtual void onMove() {}
    virtual Json::Value saveToJson();
    virtual bool canSave();

    // QGraphicsItem interface
};

#endif // ITEM_H
