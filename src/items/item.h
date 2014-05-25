#include <src/animation/animatedobject.h>

#include <src/view/listitem.h>

#include <src/stats/stats.h>

#ifndef ITEM_H
#define ITEM_H
class Creature;
class Interaction;
class Item : public ListItem
{
    Q_OBJECT
public:
    Item();
    Item(const Item&);
    bool isSingleUse();
    virtual void onEquip(Creature *creature);
    virtual void onUnequip(Creature *creature);
    static Item *getItem(std::string name);
    virtual void onUse(Creature *creature);
    virtual void onEnter();
    virtual void onMove();
    virtual Json::Value saveToJson();
    virtual bool canSave();
protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    bool singleUse;
    Stats bonus;
    void loadFromJson(Json::Value config);
    Interaction *interaction;
    int power;
private:
    int slot = 0;

    // MapObject interface
public:
    virtual void loadFromProps(Tmx::PropertySet props);

    // QGraphicsItem interface
};
Q_DECLARE_METATYPE(Item)

class Armor : public Item
{
    Q_OBJECT
public:
    Armor();
    Armor(const Armor &armor);
    Armor(std::string name);
    Interaction *getInteraction();
};
Q_DECLARE_METATYPE(Armor)

class Belt : public Item
{
    Q_OBJECT
public:
    Belt();
    Belt(const Belt& belt);
};
Q_DECLARE_METATYPE(Belt)

class Helmet : public Item
{
    Q_OBJECT
public:
    Helmet();
    Helmet(const Helmet& helmet);
};
Q_DECLARE_METATYPE(Helmet)

class Boots : public Item
{
    Q_OBJECT
public:
    Boots();
    Boots(const Boots& boots);
};
Q_DECLARE_METATYPE(Boots)

class Gloves : public Item
{
    Q_OBJECT
public:
    Gloves();
    Gloves(const Gloves& gloves);
};
Q_DECLARE_METATYPE(Gloves)

class Weapon : public Item
{
    Q_OBJECT
public:
    Weapon();
    Weapon(const Weapon &weapon);
    Interaction *getInteraction();
    Stats *getStats();
};
Q_DECLARE_METATYPE(Weapon)

class SmallWeapon : public Weapon
{
    Q_OBJECT
public:
    SmallWeapon();
    SmallWeapon(const SmallWeapon &weapon);
};
Q_DECLARE_METATYPE(SmallWeapon)

#endif // ITEM_H
