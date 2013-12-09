#include <QGraphicsPixmapItem>
#include <effects/effect.h>
#include <items/item.h>
#include <map/map.h>
#include <map/tiles/tile.h>
#include <stats/damage.h>

#ifndef CREATURE_H
#define CREATURE_H

class Interaction;
class Weapon;
class Armor;
class Stats;

class Creature : public MapObject
{
public:
    Creature(Map *map, int x, int y);
    ~Creature();

    int getExp() {
        return level*750;
    }
    int getExpRatio();

    void attribChange();

    void heal(int i);

    void healProc(float i);

    void hurt(Damage damage);
    void hurt(int i);

    virtual int getDmg();
    int getScale() {
        return level+sw;
    }

    inline bool isAlive() const {
        return alive;
    }
    inline void setAlive() {
        alive=true;
    }

    virtual void fight(Creature *creature);
    virtual void levelUp();
    virtual std::list<Item*>* getLoot()=0;

    void addAction(Interaction *action);
    void addEffect(Effect *effect);

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

    bool isStun();
    void addStun(int i);

    Stats *getStats() {
        return stats;
    }
    int getManaRatio();

    int getHp() {
        return hp;
    }
    int getHpMax() {
        return hpMax;
    }

    int getManaMax() {
        return manaMax;
    }

    int getLevel() {
        return level;
    }
    void addExpScaled(int scale);
    void addExp(int exp);
protected:
    int exp;
    int level;
    int sw;

    int mana,manaMax,manaRegRate;
    int hpMax,hp;

    bool alive;

    std::list<Interaction *> actions;
    std::list<Effect *> effects;

    Weapon *weapon;
    Armor *armor;

    Stats *stats;
    Stats *bonusLevel;

    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    virtual void mouseReleaseEvent(QGraphicsSceneMouseEvent *event);

private:
    Interaction *selectAction();
    void setItem(void *pointer, Item *newItem);
    int stun;
    void takeDamage(int i);



};

#endif // CREATURE_H
