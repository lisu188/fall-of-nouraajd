#include "CCreature.h"
#include "CPathFinder.h"
#include "CGame.h"
#include "CMap.h"
#include "CStats.h"
#include "CUtil.h"
#include "object/CObject.h"
#include "gui/CGui.h"

void CCreature::setActions ( std::set<std::shared_ptr<CInteraction>> value ) {
    actions=value;
}

std::set<std::shared_ptr<CInteraction>> CCreature::getActions() {
    return actions;
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

std::shared_ptr<CInteraction> CCreature::getLevelAction() {
    QString levelString=QString::number ( level );
    if ( ctn ( levelling, levelString ) ) {
        return getMap()->getObjectHandler()->clone<CInteraction> ( levelling[levelString] );
    } else {
        return nullptr;
    }
}

std::shared_ptr<Stats> CCreature::getLevelStats() const {
    return levelStats;
}

void CCreature::setLevelStats ( std::shared_ptr<Stats> value ) {
    levelStats = value;
}

void CCreature::addBonus ( std::shared_ptr<Stats> bonus ) {
    stats->addBonus ( bonus );
}

void CCreature::removeBonus ( std::shared_ptr<Stats> bonus ) {
    stats->removeBonus ( bonus );
}


void CCreature::addItem ( std::shared_ptr<CItem> item ) {
    std::set<std::shared_ptr<CItem>> list;
    list.insert ( item );
    addItem ( list );
}

void CCreature::removeFromInventory ( std::shared_ptr<CItem> item ) {
    items.erase ( item );
    Q_EMIT inventoryChanged();
}

void CCreature::removeFromEquipped ( std::shared_ptr<CItem> item ) {
    if ( hasEquipped ( item ) ) {
        setItem ( getSlotWithItem ( item ),nullptr );
    }
    removeFromInventory ( item );
}

std::set<std::shared_ptr<CItem> > CCreature::getInInventory() {
    return items;
}

std::set<std::shared_ptr<CInteraction>> CCreature::getInteractions() {
    return actions;
}

CItemMap CCreature::getEquipped() {
    return equipped;
}

void CCreature::setEquipped ( CItemMap value ) {
    equipped=value;
}

void CCreature::addItem ( std::set<std::shared_ptr<CItem> > items ) {
    for ( std::shared_ptr<CItem> it : items ) {
        items.insert ( it );
    }
    Q_EMIT inventoryChanged();
}

void CCreature::heal ( int i ) {
    if ( i < 0 ) {
        qFatal ( "Tried to heal negative value!" );
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
    std::shared_ptr<Damage> damage=std::make_shared<Damage>();
    damage->setNormal ( i );
    hurt ( damage );
}

int CCreature::getExpRatio() {
    return ( float ) ( ( exp - level * ( level - 1 ) * 500 ) ) /
           ( float ) ( level * ( level + 1 ) * 500 - level * ( level - 1 ) * 500 ) * 100.0;
}

void CCreature::takeDamage ( int i ) {
    if ( rand() < stats->getBlock() ) {
        return;
    }
    if ( i < 0 ) {
        qFatal ( "damage less than 0 taken" );
        return;
    }
    hp -= i * ( ( 100 - stats->getArmor() ) / 100.0 );
    Q_EMIT statsChanged();
}

CInteractionMap CCreature::getLevelling() {
    return levelling;
}

void CCreature::setLevelling ( CInteractionMap value ) {
    levelling = value;
}

void CCreature::setItems ( std::set<std::shared_ptr<CItem> > value ) {
    items=value;
}

std::set<std::shared_ptr<CItem>> CCreature::getItems() {
    return items;
}

void CCreature::hurt ( std::shared_ptr<Damage> damage ) {
    takeDamage ( damage->getNormal() * ( 100 - stats->getNormalResist() ) / 100.0 );
    takeDamage ( damage->getThunder() * ( 100 - stats->getThunderResist() ) / 100.0 );
    takeDamage ( damage->getFrost() * ( 100 - stats->getFrostResist() ) / 100.0 );
    takeDamage ( damage->getFire() * ( 100 - stats->getFireResist() ) / 100.0 );
    takeDamage ( damage->getShadow() * ( 100 - stats->getShadowResist() ) / 100.0 );
    qDebug() << getObjectType() << "took damage:"
             << "normal(" << damage->getNormal() << ")thunder("
             << damage->getThunder() << ")frost(" << damage->getFrost() << ")fire("
             << damage->getFire() << ")shadow(" << damage->getShadow() << ")";
}

int CCreature::getDmg() {
    int critDice = rand() % 100;
    int attDice = rand() % 100;
    int dmg =
        rand() % ( stats->getDmgMax() + 1 - stats->getDmgMin() ) + stats->getDmgMin();
    dmg += stats->getDamage();
    attDice -= stats->getAttack();
    if ( attDice < stats->getHit() ) {
        if ( critDice < stats->getCrit() ) {
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

void CCreature::fight ( std::shared_ptr<CCreature> creature ) {
    if ( applyEffects() ) {
        return;
    }
    if ( !isAlive() ) {
        creature->defeatedCreature ( this->ptr<CCreature>() );
        return;
    }
    std::shared_ptr<CInteraction> action = selectAction();
    if ( action ) {
        action->onAction ( this->ptr<CCreature>(), creature );
        if ( creature->getArmor() ) {
            if ( creature->getArmor()->getInteraction() ) {
                creature->getArmor()->getInteraction()->onAction ( creature, this->ptr<CCreature>() );
            }
        }
        qDebug() << "";
    }
    creature->fight ( this->ptr<CCreature>() );
}

void CCreature::trade ( std::shared_ptr<CGameObject> ) {

}

void CCreature::addAction ( std::shared_ptr<CInteraction> action ) {
    if ( !action ) {
        return;
    }
    actions.insert ( action );
    Q_EMIT skillsChanged();
}

void CCreature::addEffect ( std::shared_ptr<CEffect> effect ) {
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
        qFatal ( "Tried to add negative mana!" );
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
    qDebug() << getObjectType() << "restored" << mana - tmp << "mana"<<"\n";
}

void CCreature::takeMana ( int i ) {
    if ( i < 0 ) {
        qFatal ( "Tried to take negative mana value!" );
    }
    mana -= i;
    Q_EMIT statsChanged();
}

std::shared_ptr<CInteraction> CCreature::selectAction() {
    for ( std::shared_ptr<CInteraction> it:actions ) {
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
    std::set<std::shared_ptr<CEffect> >::iterator it = effects.begin();
    for ( it = effects.begin(); it != effects.end(); ) {
        if ( ( *it )->getTimeLeft() == 0 ) {
            qDebug() << getObjectType() << "is now free from"
                     << ( *it )->getObjectType() ;
            i++;
            effects.erase ( it );
            it = effects.begin();
        } else {
            it++;
        }
    }
    bool isStopped = false;
    for ( std::shared_ptr<CEffect> effect:effects ) {
        qDebug() << getObjectType() << "suffers from" << effect->getObjectType() ;
        i++;
        isStopped = isStopped || effect->apply ( this );
        if ( !isAlive() ) {
            effect->getCaster()->defeatedCreature ( this->ptr<CCreature>() );
            return true;
        }
    }
    if ( i > 0 ) {
        qDebug() << "";
    }
    return isStopped;
}

bool CCreature::isPlayer() {
    return getMap()->getPlayer() == this->ptr<CPlayer>();
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

void CCreature::setWeapon ( std::shared_ptr<CWeapon> weapon ) {
    this->setItem ( QString::number ( 0 ), weapon );
}

void CCreature::setArmor ( std::shared_ptr<CArmor> armor ) {
    this->setItem ( QString::number ( 3 ), armor );
}

void CCreature::setItem ( QString i, std::shared_ptr<CItem> newItem ) {
    if ( !ctn ( equipped,i ) ) {
        equipped.insert ( std::make_pair ( i, std::shared_ptr<CItem>() ) );
    }
    if ( newItem && !CItemSlot::checkType ( i, newItem ) ) {
        qFatal ( QString ( "Tried to insert" +newItem->getObjectType()
                           +"into slot" + i ).toStdString().c_str() );
    }
    std::shared_ptr<CItem> oldItem = equipped.at ( i );
    if ( oldItem ) {
        getMap()->getEventHandler()->gameEvent ( oldItem,std::make_shared<CGameEventCaused> ( CGameEvent::onUnequip,this->ptr<CCreature>() ) );
        this->addItem ( oldItem );
        if ( newItem == oldItem ) {
            newItem = nullptr;
        }
    }
    if ( newItem ) {
        getMap()->getEventHandler()->gameEvent ( newItem , std::make_shared<CGameEventCaused> ( CGameEvent::onEquip,this->ptr<CCreature>() ) );
    }
    removeFromInventory ( newItem );
    attribChange();
    equipped[i]=newItem;
    Q_EMIT equippedChanged();
    Q_EMIT statsChanged();
}

bool CCreature::hasInInventory ( std::shared_ptr<CItem> item ) {
    return ctn ( items,item );
}

bool CCreature::hasItem ( std::shared_ptr<CItem> item ) {
    return hasInInventory ( item ) || hasEquipped ( item );
}

Coords CCreature::getCoords() {
    Coords coords ( getPosX(), getPosY(), getPosZ() );
    return coords;
}

std::shared_ptr<CWeapon> CCreature::getWeapon() {
    return cast<CWeapon> ( getItemAtSlot ( "0" ) );
}

std::shared_ptr<CArmor> CCreature::getArmor() {
    return cast<CArmor> ( getItemAtSlot ( "3" ) );
}

void CCreature::levelUp() {
    level++;
    stats->addBonus ( getLevelStats() );
    addAction ( getLevelAction() );
    attribChange();
    if ( level > 1 ) {
        qDebug() << getObjectType() << "is now level:" << level << "\n";
    }
}

std::set<std::shared_ptr<CItem>> CCreature::getLoot() {
    std::set<std::shared_ptr<CItem>> items= this->getMap()->getLootHandler()->getLoot ( getScale() );
    for ( std::shared_ptr<CItem> item:getInInventory() ) {
        this->removeFromInventory ( item );
        items.insert ( item );
    }
    return items;
}

std::set<std::shared_ptr<CItem> > CCreature::getAllItems() {
    std::set<std::shared_ptr<CItem> > allItems;
    allItems.insert ( items.begin(),items.end() );
    for ( auto it:equipped ) {
        if ( it.second ) {
            allItems.insert ( it.second );
        }
    }
    return allItems;
}

void CCreature::attribChange() {
    hpMax = stats->getStamina() * 7;
    manaRegRate = stats->getMainValue() / 10 + 1;
    manaMax = stats->getMainValue() * 7;
}

bool CCreature::hasEquipped ( std::shared_ptr<CItem> item ) {
    for ( auto it:equipped ) {
        if ( it.second==item ) {
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

std::shared_ptr<Stats> CCreature::getStats() const {
    return stats;
}

void CCreature::setStats ( std::shared_ptr<Stats> value ) {
    stats = value;
}

int CCreature::getHpMax() {
    return hpMax;
}

void CCreature::setHpMax ( int value ) {
    hpMax = value;
}

std::shared_ptr<CItem> CCreature::getItemAtSlot ( QString slot ) {
    if ( ctn ( equipped,slot ) ) {
        return equipped.at ( slot );
    }
    return nullptr;
}

QString CCreature::getSlotWithItem ( std::shared_ptr<CItem> item ) {
    for ( auto it=equipped.begin(); it!=equipped.end(); it++ ) {
        if ( ( *it ).second==item ) {
            return ( *it ).first;
        }
    }
    return "-1";
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

void CCreature::defeatedCreature ( std::shared_ptr<CCreature> creature ) {
    qDebug() << getObjectType() <<objectName() << "defeated" << creature->getObjectType() <<creature->objectName()
             << "\n";
    addExpScaled ( creature->getScale() );
    addItem ( creature->getLoot() );
    getMap()->removeObject ( creature );
}

void CCreature::beforeMove() {
    auto pred=[this] ( std::shared_ptr<CMapObject> object ) {
        return cast<Visitable> ( object ) && this->getCoords() == object->getCoords();
    } ;

    auto func=[this] ( std::shared_ptr<CMapObject> object ) {
        this->getMap()->getEventHandler()->gameEvent ( object ,std::make_shared<CGameEventCaused> ( CGameEvent::Type::onLeave, this->ptr<CCreature>() ) );
    };

    this->getMap()->forObjects ( func,pred );
}

void CCreature::afterMove() {
    auto pred=[this] ( std::shared_ptr<CMapObject> object ) {
        return cast<Visitable> ( object ) &&this->getCoords() ==object->getCoords();
    } ;

    auto func=[this] ( std::shared_ptr<CMapObject> object ) {
        getMap()->getEventHandler()->gameEvent ( object, std::make_shared<CGameEventCaused> ( CGameEvent::Type::onEnter,this->ptr<CCreature>() ) );
    };

    getMap()->forObjects ( func,pred );

    getMap()->getTile ( this->getCoords() )->onStep ( this );
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
