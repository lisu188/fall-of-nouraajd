/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include "core/CStats.h"
#include "object/CMapObject.h"

class CInteraction;

class CEffect;

class CWeapon;

class CArmor;

class Stats;

class CMap;

class CItem;

class CMarket;

class CController;

class CFightController;

typedef std::map<std::string, std::shared_ptr<CInteraction>> CInteractionMap;
typedef std::map<std::string, std::shared_ptr<CItem>> CItemMap;

class CCreature : public CMapObject, public Moveable, public Visitable {

    V_META(CCreature, CMapObject, V_PROPERTY(CCreature, int, exp, getExp, setExp),
           V_PROPERTY(CCreature, int, gold, getGold, setGold), V_PROPERTY(CCreature, int, level, getLevel, setLevel),
           V_PROPERTY(CCreature, int, mana, getMana, setMana), V_PROPERTY(CCreature, int, hp, getHp, setHp),
           V_PROPERTY(CCreature, int, sw, getSw, setSw),
           V_PROPERTY(CCreature, CInteractionMap, levelling, getLevelling, setLevelling),
           V_PROPERTY(CCreature, CItemMap, equipped, getEquipped, setEquipped),
           V_PROPERTY(CCreature, std::shared_ptr<Stats>, baseStats, getBaseStats, setBaseStats),
           V_PROPERTY(CCreature, std::shared_ptr<Stats>, levelStats, getLevelStats, setLevelStats),
           V_PROPERTY(CCreature, std::set<std::shared_ptr<CInteraction>>, actions, getActions, setActions),
           V_PROPERTY(CCreature, std::set<std::shared_ptr<CItem>>, items, getItems, setItems),
           V_PROPERTY(CCreature, std::set<std::shared_ptr<CEffect>>, effects, getEffects, setEffects),
           V_PROPERTY(CCreature, std::shared_ptr<CController>, controller, getController, setController),
           V_PROPERTY(CCreature, std::shared_ptr<CFightController>, fightController, getFightController,
                      setFightController),
           V_PROPERTY(CCreature, bool, npc, isNpc, setNpc), V_METHOD(CCreature, getManaMax, int),
           V_METHOD(CCreature, getHpMax, int), V_METHOD(CCreature, getManaRegRate, int))

  public:
    CCreature();

    virtual ~CCreature();

    void setActions(std::set<std::shared_ptr<CInteraction>> value);

    std::set<std::shared_ptr<CInteraction>> getActions();

    void setItems(std::set<std::shared_ptr<CItem>> value);

    std::set<std::shared_ptr<CItem>> getItems();

    std::set<std::shared_ptr<CEffect>> getEffects() const;

    virtual void onEnter(std::shared_ptr<CGameEvent>) override;

    virtual void onLeave(std::shared_ptr<CGameEvent>) override;

    virtual void onDestroy(std::shared_ptr<CGameEvent>);

    void setEffects(const std::set<std::shared_ptr<CEffect>> &value);

    int getExp();

    void setExp(int exp);

    int getExpRatio();

    int getExpForNextLevel();

    int getExpForLevel(int level);

    void heal(int i);

    void healProc(float i);

    void hurt(std::shared_ptr<Damage> damage);

    void hurt(int i);

    void hurt(float i);

    int getDmg();

    int getScale();

    bool isAlive();

    virtual std::set<std::shared_ptr<CItem>> getAllItems();

    void addAction(std::shared_ptr<CInteraction> action);

    void addEffect(std::shared_ptr<CEffect> effect);

    void removeEffect(std::shared_ptr<CEffect> effect);

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

    void setLevel(int level);

    void addExpScaled(int scale);

    void addExp(int exp);

    void addItems(std::set<std::shared_ptr<CItem>> items);

    void addItem(std::shared_ptr<CItem> item);

    void addItem(std::string item);

    void removeItem(std::shared_ptr<CItem> item, bool quest = false);

    void removeItem(std::function<bool(std::shared_ptr<CItem>)> item, bool quest = false);

    void removeQuestItem(std::shared_ptr<CItem> item);

    void removeQuestItem(std::function<bool(std::shared_ptr<CItem>)> item);

    std::set<std::shared_ptr<CItem>> getInInventory();

    CItemMap getEquipped();

    void setEquipped(CItemMap value);

    std::set<std::shared_ptr<CInteraction>> getInteractions();

    bool hasEquipped(std::shared_ptr<CItem> item);

    bool hasEquipped(std::function<bool(std::shared_ptr<CItem>)> item);

    void equipItem(std::string i, std::shared_ptr<CItem> newItem);

    bool hasInInventory(std::shared_ptr<CItem> item);

    bool hasInInventory(std::function<bool(std::shared_ptr<CItem>)> item);

    bool hasItem(std::shared_ptr<CItem> item);

    bool hasItem(std::function<bool(std::shared_ptr<CItem>)> item);

    int getGold();

    void setGold(int value);

    int getManaMax();

    int getManaRegRate();

    int getHp();

    void setHp(int value);

    int getHpMax();

    std::shared_ptr<CItem> getItemAtSlot(std::string slot);

    std::string getSlotWithItem(std::shared_ptr<CItem> item);

    CInteractionMap getLevelling();

    void setLevelling(CInteractionMap value);

    std::shared_ptr<Stats> getBaseStats();

    void setBaseStats(std::shared_ptr<Stats> value);

    std::shared_ptr<Stats> getLevelStats();

    void setLevelStats(std::shared_ptr<Stats> value);

    int getSw() const;

    void setSw(int value);

    virtual void beforeMove();

    virtual void afterMove();

    void addGold(int gold);

    void takeGold(int gold);

    std::shared_ptr<CController> getController();

    void setController(std::shared_ptr<CController> controller);

    virtual std::string to_string() override;

    std::shared_ptr<CFightController> getFightController();

    void setFightController(std::shared_ptr<CFightController> fightController);
    bool isNpc();
    void setNpc(bool value);

    void useAction(std::shared_ptr<CInteraction> action, std::shared_ptr<CCreature> creature);

    void useItem(std::shared_ptr<CItem> item);

    std::shared_ptr<Stats> getStats();

  protected:
    virtual void levelUp();

  private:
    std::set<std::shared_ptr<CItem>> items;
    std::set<std::shared_ptr<CInteraction>> actions;
    std::set<std::shared_ptr<CEffect>> effects;

    std::map<std::string, std::shared_ptr<CItem>> equipped;
    std::map<std::string, std::shared_ptr<CInteraction>> levelling;

    std::shared_ptr<CController> controller;

    std::shared_ptr<CFightController> fightController;

    int gold = 0;
    int exp = 0;
    int level = 0;
    int sw = 0;
    int mana = 0;
    int hp = 0;

    std::shared_ptr<Stats> baseStats = std::make_shared<Stats>();
    std::shared_ptr<Stats> levelStats = std::make_shared<Stats>();

    void takeDamage(int i);

    std::shared_ptr<CInteraction> getLevelAction();

    bool npc = false;
};
