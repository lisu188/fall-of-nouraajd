#include <QGraphicsPixmapItem>
#include <items/item.h>
#include <map/map.h>
#include <stats/damage.h>

#ifndef CREATURE_H
#define CREATURE_H

class Interaction;
class Effect;
class Weapon;
class Armor;
class Stats;

class Creature : public MapObject
{
public:
    Creature(std::string name, Json::Value config);
    Creature(std::string name);
    ~Creature();

    int getExp();
    int getExpRatio();

    void attribChange();

    void heal(int i);

    void healProc(float i);

    void hurt(Damage damage);
    void hurt(int i);

    int getDmg();

    int getScale();

    bool isAlive() const;
    void setAlive();

    virtual void fight(Creature *creature);
    virtual void levelUp();
    virtual std::list<Item*>* getLoot()=0;

    void addAction(Interaction *action);
    void addEffect(std::string type, Creature *caster);

    int getMana();
    void addMana(int i);
    void addManaProc(float i);
    void takeMana(int i);

    bool isPlayer();

    int getHpRatio();

    void setWeapon(Weapon *weapon);
    void setArmor(Armor *armor);

    Weapon *getWeapon();
    Armor *getArmor();

    Stats *getStats();
    int getManaRatio();

    int getHp();
    int getHpMax();

    int getManaMax();

    int getLevel();
    void addExpScaled(int scale);
    void addExp(int exp);



    void addItem(std::list<Item *> *items);
    void addItem(Item *item);
    void loseItem(Item *item);
    std::list<Item *> *getInventory();

    void loadFromJson(Json::Value config);
    Json::Value saveToJson();

    bool canSave();
    bool applyEffects();

protected:
    int gold;
    std::list<Item*> inventory;
    std::list<Item*> equipped;
    int exp;
    int level;
    int sw;
    std::string animPath;

    int mana,manaMax,manaRegRate;
    int hpMax,hp;

    bool alive;

    std::list<Interaction *> actions;
    std::list<Effect *> effects;

    Weapon *weapon=0;
    Armor *armor=0;

    Stats stats;

    virtual void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
    virtual void hoverLeaveEvent(QGraphicsSceneHoverEvent *event);



    Interaction *selectAction();
    void setItem(void *pointer, Item *newItem);
    void takeDamage(int i);

    Interaction *getLevelAction();
    Stats getLevelStats();

};

#endif // CREATURE_H
