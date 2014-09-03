#include "CCreature.h"

#include <QGraphicsSceneHoverEvent>
#include <src/CLootProvider.h>
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

#include <src/CInteraction.h>
#include <src/CConfigurationProvider.h>
#include <src/CItem.h>
#include <src/Stats.h>
#include <src/CGameScene.h>
#include <src/CGameView.h>

namespace {
CInteraction *loadAction(CMap *map, const std::string &name) {
    if (name.empty()) return nullptr;
    const Json::Value &config = (*CConfigurationProvider::getConfig("config/object.json"))[name];
    if (config.isNull()) return nullptr;
    if (config.isMember("class")) return map->createMapObject<CInteraction *>(name);
    CInteraction *action = new CInteraction();
    action->setMap(map);
    action->loadFromJson(name);
    return action;
}


int clamp_ratio(int value, int maximum) {
    if (maximum <= 0)
        return 100;
    if (value <= 0)
        return 0;
    return std::min(100, value * 100 / maximum);
}

int stat_resisted(int value, int resist) {
    const int clamped = std::max(0, std::min(90, resist));
    return value * (100 - clamped) / 100;
}

} // namespace

CCreature::CCreature() : CMapObject(0, 0, 0, 2) {
    gold = exp = level = sw = mana = manaMax = hpMax = hp = 0;
    manaRegRate = 1;
    setAcceptHoverEvents(true);
    Json::Value slotConfig = *CConfigurationProvider::getConfig("config/slots.json");
    for (auto it = slotConfig.begin(); it != slotConfig.end(); ++it) equipped[std::atoi(it.memberName())] = 0;
}
CCreature::CCreature(const CCreature &other) : CCreature() { if (!other.typeName.empty()) loadFromJson(other.typeName); }
CCreature::~CCreature() {
    actions.clear();
    effects.clear();
}

int CCreature::getExpRatio() {
    const int required = std::max(1, level * (level + 1) * 500);
    return clamp_ratio(exp, required);
}

// Stats are loaded from the creature's JSON configuration and grow by the
// configured per-level bonus; derived pools follow the current stats.
void CCreature::attribChange() {
    const int oldHpMax = std::max(1, hpMax);
    const int oldManaMax = std::max(1, manaMax);
    const float hpRatio = hpMax > 0 ? static_cast<float>(hp) / oldHpMax : 1.0f;
    const float manaRatio = manaMax > 0 ? static_cast<float>(mana) / oldManaMax : 1.0f;

    hpMax = 60 + stats.getStamina() * 15;
    manaMax = 20 + stats.getIntelligence() * 12;
    manaRegRate = std::max(1, stats.getIntelligence() / 4);

    hp = std::max(1, static_cast<int>(hpRatio * hpMax));
    mana = std::max(0, static_cast<int>(manaRatio * manaMax));
}

void CCreature::heal(int i) {
    if (i <= 0)
        hp = hpMax;
    else
        hp = std::min(hpMax, hp + i);
    alive = hp > 0;
}

void CCreature::healProc(float i) { heal(static_cast<int>(hpMax * i / 100.0f)); }

void CCreature::takeDamage(int i) {
    hp = std::max(0, hp - i);
    if (hp == 0)
        alive = false;
}

void CCreature::hurt(Damage damage) {
    int total = 0;
    total += stat_resisted(damage.getNormal(), stats.getNormalResist());
    total += stat_resisted(damage.getFire(), stats.getFireResist());
    total += stat_resisted(damage.getFrost(), stats.getFrostResist());
    total += stat_resisted(damage.getThunder(), stats.getThunderResist());
    hurt(total);
}

void CCreature::hurt(int i) {
    const int blocked = std::max(0, i - stats.getArmor() / 8);
    takeDamage(blocked);
}

int CCreature::getDmg() {
    if (!alive)
        return 0;
    const int minDamage = std::max(1, stats.getDmgMin());
    const int maxDamage = std::max(minDamage, stats.getDmgMax());
    return minDamage + rand() % (maxDamage - minDamage + 1);
}

void CCreature::fight(CCreature *creature) {
    if (!alive || !creature || !creature->isAlive())
        return;
    if (applyEffects())
        return;

    CInteraction *action = selectAction();
    if (action) {
        action->onAction(this, creature);
    }
}

void CCreature::levelUp() {
    level++;
    stats.addBonus(getLevelStats());
    CInteraction *action = getLevelAction();
    if (action)
        addAction(action);
    attribChange();
    heal(0);
    addMana(0);
}

std::set<CItem *> *CCreature::getLoot() { return getMap()->getLootProvider()->getLoot(std::max(0, getScale())); }

void CCreature::addAction(CInteraction *action) {
    if (!action)
        return;
    actions.insert(action);
    Q_EMIT skillsChanged();
}

void CCreature::addEffect(Effect *effect) {
    if (!effect)
        return;
    effects.insert(effect);
}

void CCreature::addItem(std::set<CItem *> *items) {
    for (CItem *item : *items) if (item) inventory.insert(item);
    Q_EMIT inventoryChanged();
}
void CCreature::addItem(CItem *item) { if (item) inventory.insert(item); Q_EMIT inventoryChanged(); }
std::set<CItem *> *CCreature::getInventory() { return (std::set<CItem *> *)&inventory; }
std::map<int, CItem *> *CCreature::getEquipped() { return &equipped; }
std::set<CInteraction *> *CCreature::getActions() { return (std::set<CInteraction *> *)&actions; }
int CCreature::getMana() { return mana; }

void CCreature::addMana(int i) {
    if (i <= 0)
        mana = manaMax;
    else
        mana = std::min(manaMax, mana + i);
}

void CCreature::addManaProc(float i) { addMana(static_cast<int>(manaMax * i / 100.0f)); }

void CCreature::takeMana(int i) { mana = std::max(0, mana - i); }

bool CCreature::isPlayer() { return inherits("CPlayer"); }

int CCreature::getHpRatio() { return clamp_ratio(hp, hpMax); }

void CCreature::setItem(int slot, CItem *item) {
    CItem *previous = equipped[slot];
    if (previous == item) return;
    if (previous) previous->onUnequip(this);
    equipped[slot] = item;
    if (item) item->onEquip(this);
    Q_EMIT equippedChanged();
    Q_EMIT statsChanged();
}
void CCreature::setWeapon(CWeapon *weapon) { setItem(0, weapon); }
void CCreature::setArmor(CArmor *armor) { setItem(3, armor); }
CWeapon *CCreature::getWeapon() { return dynamic_cast<CWeapon *>(equipped[0]); }
CArmor *CCreature::getArmor() { return dynamic_cast<CArmor *>(equipped[3]); }
bool CCreature::hasEquipped(CItem *item) {
    for (const auto &entry : equipped) if (entry.second == item) return true;
    return false;
}
bool CCreature::hasInInventory(CItem *item) { return inventory.find(item) != inventory.end(); }
bool CCreature::hasItem(CItem *item) { return hasInInventory(item) || hasEquipped(item); }
Coords CCreature::getCoords() { return Coords(getPosX(), getPosY(), getPosZ()); }
void CCreature::onEnter() {}
void CCreature::onMove() {}


int CCreature::getExp() { return exp; }
Stats *CCreature::getStats() { return &stats; }

int CCreature::getScale() { return level + sw; }

// The consolidated creature template owns the level-to-action table.
CInteraction *CCreature::getLevelAction() {
    std::ostringstream key;
    key << level;
    Json::Value config = (*CConfigurationProvider::getConfig("config/object.json"))[typeName];
    return loadAction(getMap(), config["levelling"].get(key.str(), "").asString());
}

bool CCreature::isAlive() { return alive; }

void CCreature::setAlive() { alive = true; }

// Creatures are described by a configuration or a saved game: both use the same keys.
void CCreature::loadFromJson(std::string name) {
    typeName = name;
    Json::Value config = (*CConfigurationProvider::getConfig("config/object.json"))[name];
    animPath = config.get("path", "").asString();
    setAnimation(animPath);
    sw = config.get("sw", 0).asInt();
    stats.loadFromJson(config["initStats"]);

    Json::Value names = config["actions"];
    for (unsigned int i = 0; i < names.size(); i++)
        addAction(loadAction(getMap(), names[i].asString()));

    std::set<CItem *> items;
    names = config["items"];
    for (unsigned int i = 0; i < names.size(); i++) {
        CItem *item = getMap()->createMapObject<CItem *>(std::string(names[i].asCString()));
        if (item)
            items.insert(item);
    }
    addItem(&items);

    Json::Value equipment_config = config["equipment"];
    for (Json::Value::iterator it = equipment_config.begin(); it != equipment_config.end(); ++it)
        setItem(std::atoi(it.memberName()), getMap()->createMapObject<CItem *>(std::string((*it).asCString())));
    Json::Value equipment = config["inventory"];
    if (equipment.isMember("weapon")) setWeapon(dynamic_cast<CWeapon *>(getMap()->createMapObject<CItem *>((QString::fromStdString(equipment["weapon"].asString())))));
    if (equipment.isMember("armor")) setArmor(dynamic_cast<CArmor *>(getMap()->createMapObject<CItem *>((QString::fromStdString(equipment["armor"].asString())))));

    if (config.isMember("coords"))
        moveTo(config["coords"].get("x", 0).asInt(), config["coords"].get("y", 0).asInt(),
               config["coords"].get("z", 0).asInt(), true);

    attribChange();
    if (config.isMember("level")) {
        level = config["level"].asInt();
        exp = config.get("exp", 0).asInt();
        hp = config.get("hp", hpMax).asInt();
        mana = config.get("mana", manaMax).asInt();
        alive = hp > 0;
    } else {
        heal(0);
        addMana(0);
        levelUp();
    }
}

// Defeated creatures are left out of saved games.




int CCreature::getHp() { return hp; }

int CCreature::getHpMax() { return hpMax; }

int CCreature::getManaMax() { return manaMax; }

int CCreature::getLevel() { return level; }

// Applies every active effect for this turn. Returns true when an effect (such as
// Stun) prevents the creature from acting; finished effects are dropped.
bool CCreature::applyEffects() {
    bool skipTurn = false;
    std::list<Effect *> active(effects.begin(), effects.end());
    for (std::list<Effect *>::iterator it = active.begin(); it != active.end(); ++it) {
        Effect *effect = *it;
        if (effect->apply(this))
            skipTurn = true;
        if (effect->getTimeLeft() <= 0) {
            effects.erase(effect);
            delete effect;
        }
    }
    return skipTurn;
}

int CCreature::getManaRatio() { return clamp_ratio(mana, manaMax); }

void CCreature::addExpScaled(int scale) { addExp(std::max(1, scale) * 150); }

void CCreature::addExp(int exp) {
    this->exp += exp;
    const int required = std::max(1, level * (level + 1) * 500);
    while (this->exp >= required) {
        this->exp -= required;
        levelUp();
    }
}

CInteraction *CCreature::selectAction() {
    if (actions.empty())
        return 0;

    for (auto it = actions.begin(); it != actions.end(); ++it) {
        if ((*it)->getManaCost() <= mana)
            return *it;
    }
    return *actions.begin();
}

Stats CCreature::getLevelStats() {
    Stats bonus;
    Json::Value config = (*CConfigurationProvider::getConfig("config/object.json"))[typeName];
    bonus.loadFromJson(config["levelStats"]);
    return bonus;
}

void CCreature::hoverEnterEvent(QGraphicsSceneHoverEvent *event) {
    std::ostringstream text;
    text << typeName << "\nHP: " << hp << "/" << hpMax << "\nMana: " << mana << "/" << manaMax;
    statsView.setText(text.str().c_str());
    statsView.setPos(0, -statsView.boundingRect().height());
    statsView.setVisible(true);
    if (event)
        event->accept();
}


void CCreature::setExp(int value) { exp = value; Q_EMIT statsChanged(); }
int CCreature::getExpReward() { return std::max(1, getScale()) * 150; }
int CCreature::getGold() { return gold; }
void CCreature::setGold(int value) { gold = value; Q_EMIT statsChanged(); }

void CCreature::setMana(int mana) { this->mana = mana; }

void CCreature::setManaMax(int value) { manaMax = value; }

int CCreature::getManaRegRate() { return manaRegRate; }

void CCreature::setManaRegRate(int value) { manaRegRate = value; }

void CCreature::setHp(int value) { hp = value; }

void CCreature::setHpMax(int value) { hpMax = value; }

void CCreature::removeFromInventory(CItem *item) {
    inventory.erase(item);
    Q_EMIT inventoryChanged();
}

CItem *CCreature::getItemAtSlot(int slot) {
    std::map<int, CItem *>::iterator it = equipped.find(slot);
    return it == equipped.end() ? NULL : it->second;
}

int CCreature::getSlotWithItem(CItem *item) {
    for (std::map<int, CItem *>::iterator it = equipped.begin(); it != equipped.end(); ++it) {
        if (it->second == item) {
            return it->first;
        }
    }
    return -1;
}

void CCreature::removeFromEquipped(CItem *item) {
    int slot = getSlotWithItem(item);
    if (slot != -1) {
        setItem(slot, NULL);
    }
}

std::set<CItem *> CCreature::getAllItems() {
    std::set<CItem *> items(inventory.begin(), inventory.end());
    for (std::map<int, CItem *>::iterator it = equipped.begin(); it != equipped.end(); ++it) {
        if (it->second) {
            items.insert(it->second);
        }
    }
    return items;
}

#include <src/CPlayerView.h>
#include <src/CPlayerView.h>
#include <math.h>
#include <QDebug>
#include <QBitmap>
#include <QEventLoop>
#include <QApplication>

void CPlayer::updateViews() {
	for ( std::set<CItem *>::iterator it = inventory.begin(); it != inventory.end();
	        it++ ) {
		CItem *item = *it;
		if ( map && item->getMap() != map ) {
			item->setMap ( map );
		}
	}
	for ( std::set<CInteraction *>::iterator it = actions.begin();
	        it != actions.end(); it++ ) {
		CInteraction *action = *it;
		if ( map && action->getMap() != map ) {
			action->setMap ( map );
		}
	}
	for ( std::map<int, CItem *>::iterator it = equipped.begin();
	        it != equipped.end(); it++ ) {
		CItem *item = ( *it ).second;
		if ( map && item && item->getMap() != map ) {
			item->setMap ( map );
		}
	}
}

void CPlayer::init() {
	gold = 0;
	turn = 0;
}

void CPlayer::setMap ( CMap *map ) {
	CMapObject::setMap ( map );
	updateViews();
}

CPlayer::CPlayer ( CMap *map, std::string name ) {
	this->map=map;
	init();
	this->name = "PLAYER";
	this->loadFromJson ( name );
}

CPlayer::CPlayer() {}

CPlayer::CPlayer ( const CPlayer &player ) {}

CPlayer::~CPlayer() { inventory.clear(); }

std::set<CItem *> *CPlayer::getLoot() { return ( std::set<CItem *> * ) &inventory; }

void CPlayer::onMove() {
	addMana ( manaRegRate );
	turn++;
}

void CPlayer::onEnter() {}

void CPlayer::addToFightList ( CCreature *creature ) {
	fightList.push_back ( creature );
}

std::list<CCreature *> *CPlayer::getFightList() { return &fightList; }

void CPlayer::removeFromFightList ( CCreature *creature ) {
	if ( creature == this ) {
		return;
	}
	qDebug() << typeName.c_str() << "defeated" << creature->typeName.c_str()
	         << "\n";
	addExpScaled ( creature->getScale() );
	addItem ( creature->getLoot() );
	creature->removeFromGame();
	getFightList()->remove ( creature );
	if ( getFightList()->size() == 0 ) {
		map->getScene()->getView()->getFightView()->setVisible ( false );
		CFightPanel::selected = 0;
	} else {
		CFightPanel::selected = getFightList()->front();
	}
	map->getScene()->getView()->getFightView()->update();
	Q_EMIT statsChanged();
}

void CPlayer::performAction ( CInteraction *action, CCreature *creature ) {
	action->onAction ( this, creature );
	takeMana ( action->getManaCost() );
	CArmor *armor = creature->getArmor();
	if ( armor ) {
		CInteraction *interaction = armor->getInteraction();
		if ( interaction ) {
			interaction->onAction ( creature, this );
		}
	}
	if ( !creature->isAlive() ) {
		removeFromFightList ( creature );
	} else {
		qDebug() << "";
		std::list<CCreature *> tmpList ( *getFightList() );
		for ( std::list<CCreature *>::iterator it = tmpList.begin();
		        it != tmpList.end(); it++ ) {
			( *it )->fight ( this );
		}
	}
	map->getScene()->getView()->getFightView()->update();
	if ( !isAlive() ) {
		map->getScene()->getView()->close();
	}
}

void CPlayer::addEntered ( CMapObject *object ) { entered.push_back ( object ); }

std::list<CMapObject *> *CPlayer::getEntered() { return &entered; }

void CPlayer::fight ( CCreature *creature ) {
	if ( applyEffects() ) {
		creature->fight ( this );
	}
}

#include <src/CPathFinder.h>
#include "CConfigurationProvider.h"
#include <QThreadPool>

CMonster::CMonster() : CCreature() {}

CMonster::CMonster ( const CMonster &monster ) {}

void CMonster::onMove() {
	if ( !isAlive() ) {
		return;
	}
	APathFinder *finder;
	if ( ( this->getCoords().getDist ( this->getMap()->getScene()->getPlayer()->getCoords() ) ) < 25 ) {
		finder = new CSmartPathFinder();
	} else {
		finder = new CRandomPathFinder();
	}
	this->addExp ( rand() % 25 );
	QThreadPool::globalInstance()->start ( new PathFinderWorker ( this,map->getScene()->getPlayer(), finder ) );
}

void CMonster::onEnter() {
	if ( !isAlive() ) {
		return;
	}
	map->getScene()->getPlayer()->addToFightList ( this );
}

void CMonster::levelUp() {
	CCreature::levelUp();
	heal ( 0 );
	addMana ( 0 );
}

std::set<CItem *> *CMonster::getLoot() {
	return this->getMap()->getLootProvider()->getLoot ( getScale() );
}
