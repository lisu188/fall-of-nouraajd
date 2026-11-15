#pragma once
#include <QGraphicsPixmapItem>
#include <QDateTime>
#include <set>
#include <map>
#include <list>
#include <string>
#include "CMapObject.h"
#include "item.h"
#include "stats.h"
#include "CMap.h"

class CInteraction;
class Effect;
class Weapon;
class Armor;
class CMap;
class CGameEvent;
class PlayerStatsView;

class CCreature : public CMapObject {
    Q_OBJECT
    Q_PROPERTY(int exp READ getExp WRITE setExp USER true)
    Q_PROPERTY(int gold READ getGold WRITE setGold USER true)
    Q_PROPERTY(int level READ getLevel USER true)
    Q_PROPERTY(int mana READ getMana WRITE setMana USER true)
    Q_PROPERTY(int manaMax READ getManaMax WRITE setManaMax USER true)
    Q_PROPERTY(int manaRegRate READ getManaRegRate WRITE setManaRegRate USER true)
    Q_PROPERTY(int hp READ getHp WRITE setHp USER true)
    Q_PROPERTY(int hpMax READ getHpMax WRITE setHpMax USER true)
  public:
    int getExp();
    void setExp(int exp);
    static CCreature *createCreature(QString name);
    CCreature();
    CCreature(const CCreature &creature);
    ~CCreature();
    int getExpReward();
    int getExpRatio();
    void attribChange();
    void heal(int i);
    void healProc(float i);
    void hurt(Damage damage);
    void hurt(int i);
    int getDmg();
    int getScale();
    bool isAlive();
    void setAlive();
    virtual void fight(CCreature *creature);
    virtual void levelUp();
    virtual std::set<Item *> *getLoot();
    virtual std::set<Item *> getAllItems();
    void addAction(CInteraction *action);
    void addEffect(Effect *effect);
    int getMana();
    void setMana(int mana);
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
    int getLevel();
    void addExpScaled(int scale);
    void addExp(int exp);
    void addItem(std::set<Item *> *items);
    void addItem(Item *item);
    void removeFromInventory(Item *item);
    void removeFromEquipped(Item *item);
    std::set<Item *> *getInventory();
    std::map<int, Item *> *getEquipped();
    void loadFromJson(std::string name);
    bool applyEffects();
    std::set<CInteraction *> *getActions();
    virtual void onEnter();
    virtual void onMove();
    bool hasEquipped(Item *item);
    void setItem(int i, Item *newItem);
    bool hasInInventory(Item *item);
    bool hasItem(Item *item);
    Coords getCoords();
    int getGold();
    void setGold(int value);
    int getManaMax();
    void setManaMax(int value);
    int getManaRegRate();
    void setManaRegRate(int value);
    int getHp();
    void setHp(int value);
    int getHpMax();
    void setHpMax(int value);
    Item *getItemAtSlot(int slot);
    int getSlotWithItem(Item *item);

  protected:
    void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
    std::set<Item *, Comparer> inventory;
    std::map<int, Item *> equipped;
    std::set<CInteraction *, Comparer> actions;
    std::set<Effect *> effects;
    int gold;
    int exp;
    int level;
    int sw;
    std::string animPath;
    int mana;
    int manaMax;
    int manaRegRate;
    int hpMax;
    int hp;
    bool alive = true;
    Stats stats;
    CInteraction *selectAction();
    void takeDamage(int i);
    CInteraction *getLevelAction();
    Stats getLevelStats();
    Q_SIGNAL void statsChanged();
    Q_SIGNAL void skillsChanged();
    Q_SIGNAL void inventoryChanged();
    Q_SIGNAL void equippedChanged();
};

class Player : public CCreature {
    Q_OBJECT
    friend class PlayerStatsView;

  public:
    Player(CMap *map, std::string name);
    Player();
    Player(const Player &player);
    ~Player();
    std::set<Item *> *getLoot();
    virtual void fight(CCreature *creature);
    void onMove();
    void onEnter();
    void update();
    void updateViews();
    void addToFightList(CCreature *creature);
    void removeFromFightList(CCreature *creature);
    std::list<CCreature *> *getFightList();
    void performAction(CInteraction *action, CCreature *creature);
    void addEntered(CMapObject *object);
    std::list<CMapObject *> *getEntered();
    void init();
    virtual void setMap(CMap *map);

  private:
    std::list<CCreature *> fightList;
    int turn;
    qint64 date = QDateTime::currentMSecsSinceEpoch();
    std::list<CMapObject *> entered;
};

class Monster : public CCreature {
    Q_OBJECT
  public:
    Monster();
    Monster(const Monster &monster);
    virtual void onMove();
    virtual void onEnter();
    virtual void levelUp();
    virtual std::set<Item *> *getLoot();
};
