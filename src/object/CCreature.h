#pragma once

#include "object/CMapObject.h"
#include "core/CStats.h"

class CInteraction;

class CEffect;

class CWeapon;

class CArmor;

class Stats;

class CMap;

class IPathFinder;

class CItem;

class CMarket;

class CController;

class CFightController;

typedef std::map<std::string, std::shared_ptr<CInteraction> > CInteractionMap;
typedef std::map<std::string, std::shared_ptr<CItem> > CItemMap;

class CCreature : public CMapObject, public Moveable {

V_META(CCreature, CMapObject,
       V_PROPERTY(CCreature, int, exp, getExp, setExp),
       V_PROPERTY(CCreature, int, gold, getGold, setGold),
       V_PROPERTY(CCreature, int, level, getLevel, setLevel),
       V_PROPERTY(CCreature, int, mana, getMana, setMana),
       V_PROPERTY(CCreature, int, manaMax, getManaMax, setManaMax),
       V_PROPERTY(CCreature, int, manaRegRate, getManaRegRate, setManaRegRate),
       V_PROPERTY(CCreature, int, hp, getHp, setHp),
       V_PROPERTY(CCreature, int, hpMax, getHpMax, setHpMax),
       V_PROPERTY(CCreature, int, sw, getSw, setSw),
       V_PROPERTY(CCreature, CInteractionMap, levelling, getLevelling, setLevelling),
       V_PROPERTY(CCreature, CItemMap, equipped, getEquipped, setEquipped),
       V_PROPERTY(CCreature, std::shared_ptr<Stats>, stats, getStats, setStats),
       V_PROPERTY(CCreature, std::shared_ptr<Stats>, levelStats, getLevelStats, setLevelStats),
       V_PROPERTY(CCreature, std::set<std::shared_ptr<CInteraction>>, actions, getActions, setActions),
       V_PROPERTY(CCreature, std::set<std::shared_ptr<CItem>>, items, getItems, setItems),
       V_PROPERTY(CCreature, std::set<std::shared_ptr<CEffect>>, effects, getEffects, setEffects),
       V_PROPERTY(CCreature, std::shared_ptr<CController>, controller, getController, setController),
       V_PROPERTY(CCreature, std::shared_ptr<CFightController>, fightController, getFightController, setFightController)
)

public:
    CCreature();

    virtual ~CCreature();

    void setActions(std::set<std::shared_ptr<CInteraction> > value);

    std::set<std::shared_ptr<CInteraction> > getActions();

    void setItems(std::set<std::shared_ptr<CItem>> value);

    std::set<std::shared_ptr<CItem> > getItems();

    std::set<std::shared_ptr<CEffect> > getEffects() const;

    virtual void onDestroy(std::shared_ptr<CGameEvent>);

    void setEffects(const std::set<std::shared_ptr<CEffect> > &value);

    int getExp();

    void setExp(int exp);

    int getExpReward();

    int getExpRatio();

    void attribChange();

    void heal(int i);

    void healProc(float i);

    void hurt(std::shared_ptr<Damage> damage);

    void hurt(int i);

    void hurt(float i);

    int getDmg();

    int getScale();

    bool isAlive();

    void setAlive() {
        //TODO:
    }

    virtual void fight(std::shared_ptr<CCreature> creature, int draw = 5);

    virtual void trade(std::shared_ptr<CMarket>);

    virtual void levelUp();

    virtual std::set<std::shared_ptr<CItem> > getLoot();

    virtual std::set<std::shared_ptr<CItem> > getAllItems();

    void addAction(std::shared_ptr<CInteraction> action);

    void addEffect(std::shared_ptr<CEffect> effect);

    int getMana();

    void setMana(int mana);

    void addMana(int i);

    void addManaProc(float i);

    void takeMana(int i);

    bool isPlayer();

    int getHpRatio();

    void setWeapon(std::shared_ptr<CWeapon> weapon);

    void setArmor(std::shared_ptr<CArmor> armor);

    std::shared_ptr<CWeapon> getWeapon();

    std::shared_ptr<CArmor> getArmor();

    int getManaRatio();

    int getLevel();

    void setLevel(int level) {
        this->level = level;
    }

    void addExpScaled(int scale);

    void addExp(int exp);

    void addItem(std::set<std::shared_ptr<CItem> > items);

    void addItem(std::shared_ptr<CItem> item);

    void removeFromInventory(std::shared_ptr<CItem> item);

    void removeFromEquipped(std::shared_ptr<CItem> item);

    std::set<std::shared_ptr<CItem> > getInInventory();

    CItemMap getEquipped();

    void setEquipped(CItemMap value);

    bool applyEffects();

    std::set<std::shared_ptr<CInteraction>> getInteractions();

    bool hasEquipped(std::shared_ptr<CItem> item);

    void setItem(std::string i, std::shared_ptr<CItem> newItem);

    bool hasInInventory(std::shared_ptr<CItem> item);

    bool hasItem(std::shared_ptr<CItem> item);

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

    std::shared_ptr<CItem> getItemAtSlot(std::string slot);

    std::string getSlotWithItem(std::shared_ptr<CItem> item);

    CInteractionMap getLevelling();

    void setLevelling(CInteractionMap value);

    std::shared_ptr<Stats> getStats() const;

    void setStats(std::shared_ptr<Stats> value);

    std::shared_ptr<Stats> getLevelStats() const;

    void setLevelStats(std::shared_ptr<Stats> value);

    void addBonus(std::shared_ptr<Stats> bonus);

    void removeBonus(std::shared_ptr<Stats> bonus);

    int getSw() const;

    void setSw(int value);

    virtual void beforeMove();

    virtual void afterMove();

    virtual std::string getTooltip();

    void addGold(int gold);

    void takeGold(int gold);

    std::shared_ptr<CController> getController();

    void setController(std::shared_ptr<CController> controller);

    virtual std::string to_string() override;

    std::shared_ptr<CFightController> getFightController();

    void setFightController(std::shared_ptr<CFightController> fightController);
protected:
    std::set<std::shared_ptr<CItem>> items;
    std::set<std::shared_ptr<CInteraction>> actions;
    std::set<std::shared_ptr<CEffect>> effects;

    std::map<std::string, std::shared_ptr<CItem> > equipped;
    std::map<std::string, std::shared_ptr<CInteraction>> levelling;

    std::shared_ptr<CController> controller;

protected:
    std::shared_ptr<CFightController> fightController;

    int gold = 0;
    int exp = 0;
    int level = 0;
    int sw = 0;
    int mana = 0;
    int manaMax = 0;
    int manaRegRate = 0;
    int hpMax = 0;
    int hp = 0;

    std::shared_ptr<Stats> stats = std::make_shared<Stats>();
    std::shared_ptr<Stats> levelStats = std::make_shared<Stats>();

    virtual std::shared_ptr<CInteraction> selectAction();

    void takeDamage(int i);

    std::shared_ptr<CInteraction> getLevelAction();


};


