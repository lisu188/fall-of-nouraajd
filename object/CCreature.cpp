#include "CCreature.h"
#include "CPathFinder.h"
#include "CGame.h"
#include "CMap.h"
#include "CStats.h"
#include "CUtil.h"
#include "object/CObject.h"
#include "gui/CGui.h"
void CCreature::setActions ( QVariantList &value ) {
    for ( auto it=value.begin(); it!=value.end(); it++ ) {
        this->actions.insert ( this->getMap()->getObjectHandler()->createObject<CInteraction*> ( ( *it ).toString() ) );
    }
}

QVariantList CCreature::getActions() {
    return QVariantList();
}

int CCreature::getExp() { return exp; }

void CCreature::setExp ( int exp ) {
    this->exp = exp;
    this->addExp ( 0 );
}

CCreature::CCreature() {
    this->setZValue ( 2 );
}

CCreature::~CCreature() {
    actions.clear();
}

int CCreature::getExpReward() {
    return level * 750;
}

void CCreature::addExpScaled ( int scale ) {
    int rank = level - scale;
    this->addExp ( 250 * pow ( 2, -rank ) );
}

void CCreature::addExp ( int exp ) {
    if ( !isAlive() ) {
        return;
    }
    this->exp += exp;
    while ( this->exp >= level * ( level + 1 ) * 500 ) {
        this->levelUp();
    }
    Q_EMIT statsChanged();
}

CInteraction *CCreature::getLevelAction() {
    QString levelString=QString::number ( level );
    if ( levelling.contains ( levelString ) ) {
        return this->getMap()->getObjectHandler()->createObject<CInteraction*> ( levelling[levelString].toString() );
    } else {
        return nullptr;
    }
}

Stats CCreature::getLevelStats() const {
    return levelStats;
}

void CCreature::setLevelStats ( const Stats &value ) {
    levelStats = value;
}

void CCreature::addBonus ( Stats bonus ) {
    this->stats.addBonus ( bonus );
}

void CCreature::removeBonus ( Stats bonus ) {
    this->stats.removeBonus ( bonus );
}


void CCreature::addItem ( CItem *item ) {
    std::set<CItem *> list;
    list.insert ( item );
    addItem ( list );
}

void CCreature::removeFromInventory ( CItem *item ) {
    if ( inventory.find ( item ) != inventory.end() ) {
        inventory.erase ( inventory.find ( item ) );
    }
    Q_EMIT inventoryChanged();
}

void CCreature::removeFromEquipped ( CItem *item ) {
    if ( hasEquipped ( item ) ) {
        setItem ( getSlotWithItem ( item ),nullptr );
    }
    removeFromInventory ( item );
}

std::set<CItem *> CCreature::getInInventory() {
    return inventory;
}

std::set<CInteraction *> CCreature::getInteractions() {
    return actions;
}

std::map<int, CItem *> CCreature::getEquipped() {
    return equipped;
}

void CCreature::addItem ( std::set<CItem *> items ) {
    for ( CItem* it : items ) {
        inventory.insert ( it );
    }
    Q_EMIT inventoryChanged();
}

void CCreature::heal ( int i ) {
    if ( i < 0 ) {
        throw 0;
    }
    if ( hp > hpMax ) {
        return;
    }
    if ( i == 0 ) {
        hp = hpMax;
    } else {
        hp += i;
    }
    if ( hp > hpMax ) {
        hp = hpMax;
    }
    Q_EMIT statsChanged();
}

void CCreature::healProc ( float i ) {
    int tmp = hp;
    heal ( i / 100.0 * hpMax );
    qDebug() << getObjectType() << "restored" << hp - tmp << "hp"<<"\n";
}

void CCreature::hurt ( int i ) {
    Damage damage;
    damage.setNormal ( i );
    hurt ( damage );
}

int CCreature::getExpRatio() {
    return ( float ) ( ( exp - level * ( level - 1 ) * 500 ) ) /
           ( float ) ( level * ( level + 1 ) * 500 - level * ( level - 1 ) * 500 ) * 100.0;
}

void CCreature::takeDamage ( int i ) {
    if ( rand() < stats.getBlock() ) {
        return;
    }
    if ( i < 0 ) {
        qFatal ( "damage less than 0 taken" );
        return;
    }
    hp -= i * ( ( 100 - stats.getArmor() ) / 100.0 );
    Q_EMIT statsChanged();
}

QVariantMap CCreature::getLevelling() const {
    return levelling;
}

void CCreature::setLevelling ( const QVariantMap &value ) {
    levelling = value;
}

QVariantMap CCreature::getInventory() const {
    return QVariantMap();
}

void CCreature::setInventory ( const QVariantMap &value ) {
    for ( auto it=value.begin(); it!=value.end(); it++ ) {
        int slot=it.key().toInt();
        CItem *item=getMap()->getObjectHandler()->createObject<CItem*> ( it.value().toString() );
        this->setItem ( slot,item );
    }
}

void CCreature::setItems ( QVariantList &value ) {
    for ( auto it=value.begin(); it!=value.end(); it++ ) {
        CItem *item=this->getMap()->getObjectHandler()->createObject<CItem*> ( ( *it ).toString()  );
        this->addItem ( item  );
    }
}

QVariantList CCreature::getItems() {
    return QVariantList();
}

void CCreature::hurt ( Damage damage ) {
    takeDamage ( damage.getNormal() * ( 100 - stats.getNormalResist() ) / 100.0 );
    takeDamage ( damage.getThunder() * ( 100 - stats.getThunderResist() ) / 100.0 );
    takeDamage ( damage.getFrost() * ( 100 - stats.getFrostResist() ) / 100.0 );
    takeDamage ( damage.getFire() * ( 100 - stats.getFireResist() ) / 100.0 );
    takeDamage ( damage.getShadow() * ( 100 - stats.getShadowResist() ) / 100.0 );
    qDebug() << getObjectType() << "took damage:"
             << "normal(" << damage.getNormal() << ")thunder("
             << damage.getThunder() << ")frost(" << damage.getFrost() << ")fire("
             << damage.getFire() << ")shadow(" << damage.getShadow() << ")";
}

int CCreature::getDmg() {
    int critDice = rand() % 100;
    int attDice = rand() % 100;
    int dmg =
        rand() % ( stats.getDmgMax() + 1 - stats.getDmgMin() ) + stats.getDmgMin();
    dmg += stats.getDamage();
    attDice -= stats.getAttack();
    if ( attDice < stats.getHit() ) {
        if ( critDice < stats.getCrit() ) {
            dmg *= 2;
            qDebug() << "Critical hit";
        }
        return dmg;
    } else {
        qDebug() << "Missed";
        return 0;
    }
}

int CCreature::getScale() {
    return level + sw;
}

bool CCreature::isAlive() {
    return hp>=0;
}

void CCreature::fight ( CCreature *creature ) {
    if ( applyEffects() ) {
        return;
    }
    if ( !isAlive() ) {
        creature->defeatedCreature ( this );
        return;
    }
    CInteraction *action = selectAction();
    if ( action ) {
        action->onAction ( this, creature );
        if ( creature->getArmor() ) {
            if ( creature->getArmor()->getInteraction() ) {
                creature->getArmor()->getInteraction()->onAction ( creature, this );
            }
        }
        qDebug() << "";
    }
    creature->fight ( this );
}

void CCreature::trade ( CGameObject * ) {

}

void CCreature::addAction ( CInteraction *action ) {
    if ( !action ) {
        return;
    }
    action->setMap ( this->getMap() );
    actions.insert ( action );
    Q_EMIT skillsChanged();
}

void CCreature::addEffect ( CEffect* effect ) {
    qDebug() << effect->getObjectType() << "starts for"
             << this-> getObjectType();
    effects.insert ( effect );
}

int CCreature::getMana() {
    return mana;
}

void CCreature::setMana ( int mana ) {
    this->mana = mana;
}

void CCreature::addMana ( int i ) {
    if ( i < 0 ) {
        throw 0;
    }
    if ( mana > manaMax ) {
        return;
    }
    if ( i == 0 ) {
        mana = manaMax;
    } else {
        mana += i;
    }
    if ( mana > manaMax ) {
        mana = manaMax;
    }
    Q_EMIT statsChanged();
}

void CCreature::addManaProc ( float i ) {
    int tmp = mana;
    addMana ( i / 100.0 * manaMax );
    qDebug() <<  getObjectType() << "restored" << mana - tmp << "mana"<<"\n";
}

void CCreature::takeMana ( int i ) {
    if ( i < 0 ) {
        throw 0;
    }
    mana -= i;
    Q_EMIT statsChanged();
}

CInteraction *CCreature::selectAction() {
    for ( CInteraction* it:actions ) {
        if ( it ->getManaCost() < mana ) {
            return it ;
        }
    }
    return 0;
}

bool CCreature::applyEffects() {
    if ( effects.size() == 0 ) {
        return false;
    }
    int i = 0;
    std::set<CEffect *>::iterator it = effects.begin();
    for ( it = effects.begin(); it != effects.end(); ) {
        if ( ( *it )->getTimeLeft() == 0 ) {
            qDebug() <<  getObjectType() << "is now free from"
                     << ( *it )->getObjectType() ;
            i++;
            effects.erase ( it );
            it = effects.begin();
        } else {
            it++;
        }
    }
    bool isStopped = false;
    for ( CEffect* effect:effects ) {
        qDebug() <<  getObjectType()  << "suffers from" << effect->getObjectType() ;
        i++;
        isStopped = isStopped || effect->apply ( this );
        if ( !isAlive() ) {
            effect->getCaster()->defeatedCreature ( this );
            return true;
        }
    }
    if ( i > 0 ) {
        qDebug() << "";
    }
    return isStopped;
}

bool CCreature::isPlayer() {
    return getMap()->getPlayer() == this;
}

int CCreature::getHpRatio() {
    if ( hp > hpMax ) {
        return 100;
    }
    return ( float ) hp / ( float ) hpMax * 100.0;
}

int CCreature::getManaRatio() {
    if ( mana > manaMax ) {
        return 100;
    }
    if ( manaMax==0 ) {
        return 100;
    }
    if ( mana<0 ) {
        return 0;
    }
    return ( float ) mana / ( float ) manaMax * 100.0;
}

int CCreature::getHp() {
    return hp;
}

int CCreature::getManaMax() {
    return manaMax;
}

int CCreature::getLevel() {
    return level;
}

void CCreature::setWeapon ( CWeapon *weapon ) {
    this->setItem ( 0, weapon );
}

void CCreature::setArmor ( CArmor *armor ) {
    this->setItem ( 3, armor );
}

void CCreature::setItem ( int i, CItem *newItem ) {
    if ( equipped.find ( i ) == equipped.end() ) {
        equipped.insert ( std::pair<int, CItem *> ( i, 0 ) );
    }
    if ( newItem && !CItemSlot::checkType ( i, newItem ) ) {
        qFatal ( QString ( "Tried to insert" +newItem->getObjectType()
                           +"into slot" + i ).toStdString().c_str() );
    }
    CItem *oldItem = equipped.at ( i );
    if ( oldItem ) {
        getMap()->getEventHandler()->gameEvent ( oldItem,new CGameEventCaused ( CGameEvent::onUnequip,this ) );
        this->addItem ( oldItem );
        if ( newItem == oldItem ) {
            newItem = 0;
        }
    }
    if ( newItem ) {
        getMap()->getEventHandler()->gameEvent ( newItem , new CGameEventCaused ( CGameEvent::onEquip,this ) );
    }
    removeFromInventory ( newItem );
    attribChange();
    equipped.erase ( i );
    equipped.insert ( std::pair<int, CItem *> ( i, newItem ) );
    Q_EMIT equippedChanged();
    Q_EMIT statsChanged();
}

bool CCreature::hasInInventory ( CItem *item ) {
    return inventory.find ( item ) != inventory.end();
}

bool CCreature::hasItem ( CItem *item ) {
    return hasInInventory ( item ) || hasEquipped ( item );
}

Coords CCreature::getCoords() {
    Coords coords ( getPosX(), getPosY(), getPosZ() );
    return coords;
}

CWeapon *CCreature::getWeapon() {
    return dynamic_cast<CWeapon *> ( getItemAtSlot ( 0 ) );
}

CArmor *CCreature::getArmor() {
    return dynamic_cast<CArmor *> ( getItemAtSlot ( 3 ) );
}

void CCreature::levelUp() {
    level++;
    stats.addBonus ( getLevelStats() );
    addAction ( getLevelAction() );
    attribChange();
    if ( level > 1 ) {
        qDebug() << getObjectType()  << "is now level:" << level << "\n";
    }
}

std::set<CItem *> CCreature::getLoot() {
    std::set<CItem *>  items= this->getMap()->getLootHandler()->getLoot ( getScale() );
    for ( CItem *item:getInInventory() ) {
        this->removeFromInventory ( item );
        items.insert ( item );
    }
    return items;
}

std::set<CItem *> CCreature::getAllItems() {
    std::set<CItem *> allItems;
    allItems.insert ( inventory.begin(),inventory.end() );
    for ( auto it:equipped ) {
        if ( it.second ) {
            allItems.insert ( it.second );
        }
    }
    return allItems;
}

void CCreature::attribChange() {
    hpMax = stats.getStamina() * 7;
    manaRegRate = stats.getMainValue() / 10 + 1;
    manaMax = stats.getMainValue() * 7;
}

bool CCreature::hasEquipped ( CItem *item ) {
    for ( unsigned   int i = 0; i < equipped.size(); i++ ) {
        auto it=equipped.find ( i );
        if ( it!=equipped.end() && ( *it ).second == item ) {
            return true;
        }
    }
    return false;
}

int CCreature::getSw() const {
    return sw;
}

void CCreature::setSw ( int value ) {
    sw = value;
}

Stats CCreature::getStats() const {
    return stats;
}

void CCreature::setStats ( const Stats &value ) {
    stats = value;
}

int CCreature::getHpMax() {
    return hpMax;
}

void CCreature::setHpMax ( int value ) {
    hpMax = value;
}

CItem *CCreature::getItemAtSlot ( int slot ) {
    if ( equipped.find ( slot ) !=equipped.end() ) {
        return equipped.at ( slot );
    }
    return nullptr;
}

int CCreature::getSlotWithItem ( CItem *item ) {
    for ( auto it=equipped.begin(); it!=equipped.end(); it++ ) {
        if ( ( *it ).second==item ) {
            return ( *it ).first;
        }
    }
    return -1;
}

void CCreature::setHp ( int value ) {
    hp = value;
}

int CCreature::getManaRegRate() {
    return manaRegRate;
}

void CCreature::setManaRegRate ( int value ) {
    manaRegRate = value;
}

void CCreature::setManaMax ( int value ) {
    manaMax = value;
}

int CCreature::getGold() {
    return gold;
}

void CCreature::setGold ( int value ) {
    gold = value;
}

void CCreature::defeatedCreature ( CCreature *creature ) {
    qDebug() << getObjectType()  <<objectName() << "defeated" << creature->getObjectType() <<creature->objectName()
             << "\n";
    addExpScaled ( creature->getScale() );
    addItem ( creature->getLoot() );
    getMap()->removeObject ( creature );
}

void CCreature::beforeMove() {
    auto pred=[this] ( CMapObject *object ) {
        return dynamic_cast<Visitable*> ( object ) &&this->getCoords() ==object->getCoords();
    } ;

    auto func=[this] ( CMapObject *object ) {
        this->getMap()->getEventHandler()->gameEvent ( object ,new CGameEventCaused ( CGameEvent::Type::onLeave,this ) );
    };

    this->getMap()->forAll ( func,pred );
}

void CCreature::afterMove() {
    CMap *map=getMap();
    auto pred=[this] ( CMapObject *object ) {
        return dynamic_cast<Visitable*> ( object ) &&this->getCoords() ==object->getCoords();
    } ;

    auto func=[this,map] ( CMapObject *object ) {
        map->getEventHandler()->gameEvent ( object, new CGameEventCaused ( CGameEvent::Type::onEnter,this ) );
    };

    map->forAll ( func,pred );

    map->getTile ( this->getCoords() )->onStep ( this );
}

QString CCreature::getTooltip() const {
    QString tooltipText=getObjectType();
    tooltipText.append ( " " );
    tooltipText.append ( QString::number ( level ) );
    return tooltipText;
}

void CCreature::addGold ( int gold ) {
    this->setGold ( this->getGold()+gold );
}

void CCreature::takeGold ( int gold ) {
    this->setGold ( this->getGold()-gold );
}
