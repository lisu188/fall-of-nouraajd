#pragma once
#include <QGraphicsPixmapItem>
#include <QDateTime>
#include <set>
#include <map>
#include <list>
#include <string>
#include "CMapObject.h"
#include "CItem.h"
#include "Stats.h"

class CInteraction;
class CEffect;
class CWeapon;
class CArmor;
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
    virtual std::set<CItem *> *getLoot();
    virtual std::set<CItem *> getAllItems();
    void addAction(CInteraction *action);
    void addEffect(CEffect *effect);
    int getMana();
    void setMana(int mana);
    void addMana(int i);
    void addManaProc(float i);
    void takeMana(int i);
    bool isPlayer();
    int getHpRatio();
    void setWeapon(CWeapon *weapon);
    void setArmor(CArmor *armor);
    CWeapon *getWeapon();
    CArmor *getArmor();
    Stats *getStats();
    void addBonus(const Stats &bonus);
    void removeBonus(const Stats &bonus);
    int getManaRatio();
    int getLevel();
    void addExpScaled(int scale);
    void addExp(int exp);
    void addItem(std::set<CItem *> *items);
    void addItem(CItem *item);
    void removeFromInventory(CItem *item);
    void removeFromEquipped(CItem *item);
    std::set<CItem *> *getInventory();
    std::map<int, CItem *> *getEquipped();
    bool applyEffects();
    std::set<CInteraction *> *getActions();
    virtual void onEnter();
    virtual void onMove();
    bool hasEquipped(CItem *item);
    void setItem(int i, CItem *newItem);
    bool hasInInventory(CItem *item);
    bool hasItem(CItem *item);
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
    CItem *getItemAtSlot(int slot);
    int getSlotWithItem(CItem *item);

  protected:
    void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
    std::set<CItem *> inventory;
    std::map<int, CItem *> equipped;
    std::set<CInteraction *> actions;
    std::set<CEffect *> effects;
    int gold;
    int exp;
    int level;
    int sw;
    QString animPath;
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
    friend class CGameView;
    Q_SIGNAL void statsChanged();
    Q_SIGNAL void skillsChanged();
    Q_SIGNAL void inventoryChanged();
    Q_SIGNAL void equippedChanged();
};

class CPlayer : public CCreature {
    Q_OBJECT
    friend class PlayerStatsView;

  public:
    Q_SIGNAL void dead();
    CPlayer();
    CPlayer(const CPlayer &player);
    ~CPlayer();
    std::set<CItem *> *getLoot();
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

  private:
    std::list<CCreature *> fightList;
    int turn;
    qint64 date = QDateTime::currentMSecsSinceEpoch();
    std::list<CMapObject *> entered;
};

class CMonster : public CCreature {
    Q_OBJECT
  public:
    CMonster();
    CMonster(const CMonster &monster);
    virtual void onMove();
    virtual void onEnter();
    virtual void levelUp();
    virtual std::set<CItem *> *getLoot();
};
