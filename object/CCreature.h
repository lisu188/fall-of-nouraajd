#pragma once
#include <QGraphicsPixmapItem>
#include <QDateTime>
#include "CMapObject.h"
#include "Stats.h"
#include <set>

class CInteraction;
class CEffect;
class CWeapon;
class CArmor;
class Stats;
class CMap;
class IPathFinder;
class CItem;
class CMarket;

class CCreature : public CMapObject, public Moveable {
    Q_OBJECT
    Q_PROPERTY ( int exp READ getExp WRITE setExp USER true )
    Q_PROPERTY ( int gold READ getGold WRITE setGold USER true )
    Q_PROPERTY ( int level READ getLevel USER true )
    Q_PROPERTY ( int mana READ getMana WRITE setMana USER true )
    Q_PROPERTY ( int manaMax READ getManaMax WRITE setManaMax USER true )
    Q_PROPERTY ( int manaRegRate READ getManaRegRate WRITE setManaRegRate USER true )
    Q_PROPERTY ( int hp READ getHp WRITE setHp USER true )
    Q_PROPERTY ( int hpMax READ getHpMax WRITE setHpMax USER true )
    Q_PROPERTY ( int sw READ getSw WRITE setSw USER true )
    Q_PROPERTY ( QVariantMap levelling READ getLevelling WRITE setLevelling USER true )
    Q_PROPERTY ( QVariantMap inventory READ getInventory WRITE setInventory USER true )
    Q_PROPERTY ( Stats stats READ getStats WRITE setStats USER true )
    Q_PROPERTY ( Stats levelStats READ getLevelStats WRITE setLevelStats USER true )
    Q_PROPERTY ( QVariantList actions READ getActions WRITE setActions USER true )
    Q_PROPERTY ( QVariantList items READ getItems WRITE setItems USER true )

    friend class CCreatureFightView;
public:
    CCreature();
    virtual ~CCreature();
    void setActions ( QVariantList &value );
    QVariantList getActions();
    void setItems ( QVariantList &value );
    QVariantList getItems();
    int getExp();
    void setExp ( int exp );
    int getExpReward();
    int getExpRatio();
    void attribChange();
    void heal ( int i );
    void healProc ( float i );
    void hurt ( Damage damage );
    void hurt ( int i );
    int getDmg();
    int getScale();
    bool isAlive();
    void setAlive();
    virtual void fight ( CCreature *creature );
    virtual void trade ( CGameObject * );
    virtual void levelUp();
    virtual std::set<CItem *> getLoot();
    virtual std::set<CItem *> getAllItems();
    void addAction ( CInteraction *action );
    void addEffect ( CEffect *effect );
    int getMana();
    void setMana ( int mana );
    void addMana ( int i );
    void addManaProc ( float i );
    void takeMana ( int i );
    bool isPlayer();
    int getHpRatio();
    void setWeapon ( CWeapon *weapon );
    void setArmor ( CArmor *armor );
    CWeapon *getWeapon();
    CArmor *getArmor();
    int getManaRatio();
    int getLevel();
    void addExpScaled ( int scale );
    void addExp ( int exp );
    void addItem ( std::set<CItem *> items );
    void addItem ( CItem *item );
    void removeFromInventory ( CItem *item );
    void removeFromEquipped ( CItem *item );
    std::set<CItem *> getInInventory();
    std::map<int, CItem *> getEquipped();
    bool applyEffects();
    std::set<CInteraction *> getInteractions();
    bool hasEquipped ( CItem *item );
    void setItem ( int i, CItem *newItem );
    bool hasInInventory ( CItem *item );
    bool hasItem ( CItem *item );
    Coords getCoords();
    int getGold();
    void setGold ( int value );
    int getManaMax();
    void setManaMax ( int value );
    int getManaRegRate();
    void setManaRegRate ( int value );
    int getHp();
    void setHp ( int value );
    int getHpMax();
    void setHpMax ( int value );
    CItem *getItemAtSlot ( int slot );
    int getSlotWithItem ( CItem *item );
    QVariantMap getLevelling() const;
    void setLevelling ( const QVariantMap &value );
    QVariantMap getInventory() const;
    void setInventory ( const QVariantMap &value );
    Stats getStats() const;
    void setStats ( const Stats &value );
    Stats getLevelStats() const;
    void setLevelStats ( const Stats &value );
    void addBonus ( Stats bonus );
    void removeBonus ( Stats bonus );
    int getSw() const;
    void setSw ( int value );
    virtual void beforeMove();
    virtual void afterMove();
    virtual QString getTooltip() const override;
    void addGold ( int gold );
    void takeGold ( int gold );
    Q_SIGNAL void statsChanged();
    Q_SIGNAL void skillsChanged();
    Q_SIGNAL void inventoryChanged();
    Q_SIGNAL void equippedChanged();
protected:
    std::set<CItem *> inventory;
    std::map<int, CItem *> equipped;
    std::set<CInteraction *> actions;
    std::set<CEffect *> effects;
    int gold=0;
    int exp=0;
    int level=0;
    int sw=0;
    int mana=0;
    int manaMax=0;
    int manaRegRate=0;
    int hpMax=0;
    int hp=0;
    Stats stats;
    virtual CInteraction *selectAction();
    void takeDamage ( int i );
    CInteraction *getLevelAction();
    QVariantMap levelling;
    Stats levelStats ;
    void defeatedCreature ( CCreature *creature );

};

