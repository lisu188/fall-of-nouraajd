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
    int getScale();

    bool isAlive() const;
    void setAlive();

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

    Stats *getStats();
    int getManaRatio();

    int getHp();
    int getHpMax();

    int getManaMax();

    int getLevel();
    void addExpScaled(int scale);
    void addExp(int exp);

    Stats *getLevelBonus();
    Interaction *getLevelAction();
protected:
    int exp;
    int level;
    int sw;
    std::string path;

    int mana,manaMax,manaRegRate;
    int hpMax,hp;

    bool alive;

    std::list<Interaction *> actions;
    std::list<Effect *> effects;

    Weapon *weapon;
    Armor *armor;

    Stats stats;
    Stats bonusLevel;

    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    virtual void mouseReleaseEvent(QGraphicsSceneMouseEvent *event);

    bool applyEffects();
    void initializeFromFile(char *path);

private:
    Interaction *selectAction();
    void setItem(void *pointer, Item *newItem);
    void takeDamage(int i);



};

#endif // CREATURE_H
