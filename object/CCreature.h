#pragma once
#include <QGraphicsPixmapItem>
#include <QDateTime>
#include <set>

#include "CMapObject.h"
#include "CStats.h"

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
    Q_PROPERTY ( std::shared_ptr<Stats> stats READ getStats WRITE setStats USER true )
    Q_PROPERTY ( std::shared_ptr<Stats> levelStats READ getLevelStats WRITE setLevelStats USER true )
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
    void hurt ( std::shared_ptr<Damage> damage );
    void hurt ( int i );
    int getDmg();
    int getScale();
    bool isAlive();
    void setAlive();
    virtual void fight ( std::shared_ptr<CCreature> creature );
    virtual void trade ( std::shared_ptr<CGameObject> );
    virtual void levelUp();
    virtual std::set<std::shared_ptr<CItem> > getLoot();
    virtual std::set<std::shared_ptr<CItem> > getAllItems();
    void addAction ( std::shared_ptr<CInteraction> action );
    void addEffect ( std::shared_ptr<CEffect> effect );
    int getMana();
    void setMana ( int mana );
    void addMana ( int i );
    void addManaProc ( float i );
    void takeMana ( int i );
    bool isPlayer();
    int getHpRatio();
    void setWeapon ( std::shared_ptr<CWeapon> weapon );
    void setArmor ( std::shared_ptr<CArmor> armor );
    std::shared_ptr<CWeapon> getWeapon();
    std::shared_ptr<CArmor>  getArmor();
    int getManaRatio();
    int getLevel();
    void addExpScaled ( int scale );
    void addExp ( int exp );
    void addItem ( std::set<std::shared_ptr<CItem> > items );
    void addItem ( std::shared_ptr<CItem> item );
    void removeFromInventory ( std::shared_ptr<CItem> item );
    void removeFromEquipped ( std::shared_ptr<CItem> item );
    std::set<std::shared_ptr<CItem> > getInInventory();
    std::map<int, std::shared_ptr<CItem> > getEquipped();
    bool applyEffects();
    std::set<std::shared_ptr<CInteraction>> getInteractions();
    bool hasEquipped ( std::shared_ptr<CItem> item );
    void setItem ( int i, std::shared_ptr<CItem> newItem );
    bool hasInInventory ( std::shared_ptr<CItem> item );
    bool hasItem ( std::shared_ptr<CItem> item );
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
    std::shared_ptr<CItem> getItemAtSlot ( int slot );
    int getSlotWithItem ( std::shared_ptr<CItem> item );
    QVariantMap getLevelling() const;
    void setLevelling ( const QVariantMap &value );
    QVariantMap getInventory() const;
    void setInventory ( const QVariantMap &value );
    std::shared_ptr<Stats> getStats() const;
    void setStats ( std::shared_ptr<Stats> value );
    std::shared_ptr<Stats> getLevelStats() const;
    void setLevelStats ( std::shared_ptr<Stats> value );
    void addBonus ( std::shared_ptr<Stats> bonus );
    void removeBonus ( std::shared_ptr<Stats> bonus );
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
    std::set<std::shared_ptr<CItem>> inventory;
    std::map<int,std::shared_ptr<CItem> > equipped;
    std::set<std::shared_ptr<CInteraction>> actions;
    std::set<std::shared_ptr<CEffect>> effects;
    int gold=0;
    int exp=0;
    int level=0;
    int sw=0;
    int mana=0;
    int manaMax=0;
    int manaRegRate=0;
    int hpMax=0;
    int hp=0;
    std::shared_ptr<Stats> stats=std::make_shared<Stats>();
    std::shared_ptr<Stats> levelStats =std::make_shared<Stats>();
    virtual std::shared_ptr<CInteraction>  selectAction();
    void takeDamage ( int i );
    std::shared_ptr<CInteraction> getLevelAction();
    QVariantMap levelling;
    void defeatedCreature ( std::shared_ptr<CCreature> creature );
};

