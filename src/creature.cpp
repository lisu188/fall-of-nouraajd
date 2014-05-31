#include "creature.h"

#include <QGraphicsSceneHoverEvent>
#include <src/lootprovider.h>
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

#include <src/interaction.h>
#include <src/configurationprovider.h>
#include <src/item.h>
#include <src/item.h>
#include <src/stats.h>
#include <src/gamescene.h>
#include <src/gameview.h>

namespace {

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

Creature::Creature() : ListItem(0, 0, 0, 2) {
    gold = exp = level = sw = mana = manaMax = hpMax = hp = 0;
    manaRegRate = 1;
    setAcceptHoverEvents(true);
    Json::Value slots = *ConfigurationProvider::getConfig("config/slots.json");
    for (auto it = slots.begin(); it != slots.end(); ++it) equipped[std::atoi(it.memberName())] = 0;
}
Creature::Creature(const Creature &other) : Creature() { if (!other.typeName.empty()) loadFromJson(other.typeName); }
Creature *Creature::createCreature(QString name) { return dynamic_cast<Creature *>(MapObject::createMapObject(name)); }
Creature::~Creature() {
    actions.clear();
    effects.clear();
}

int Creature::getExpRatio() {
    const int required = std::max(1, level * (level + 1) * 500);
    return clamp_ratio(exp, required);
}

// Stats are loaded from the creature's JSON configuration and grow by the
// configured per-level bonus; derived pools follow the current stats.
void Creature::attribChange() {
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

void Creature::heal(int i) {
    if (i <= 0)
        hp = hpMax;
    else
        hp = std::min(hpMax, hp + i);
    alive = hp > 0;
}

void Creature::healProc(float i) { heal(static_cast<int>(hpMax * i / 100.0f)); }

void Creature::takeDamage(int i) {
    hp = std::max(0, hp - i);
    if (hp == 0)
        alive = false;
}

void Creature::hurt(Damage damage) {
    int total = 0;
    total += stat_resisted(damage.getNormal(), stats.getNormalResist());
    total += stat_resisted(damage.getFire(), stats.getFireResist());
    total += stat_resisted(damage.getFrost(), stats.getFrostResist());
    total += stat_resisted(damage.getThunder(), stats.getThunderResist());
    hurt(total);
}

void Creature::hurt(int i) {
    const int blocked = std::max(0, i - stats.getArmor() / 8);
    takeDamage(blocked);
}

int Creature::getDmg() {
    if (!alive)
        return 0;
    const int minDamage = std::max(1, stats.getDmgMin());
    const int maxDamage = std::max(minDamage, stats.getDmgMax());
    return minDamage + rand() % (maxDamage - minDamage + 1);
}

void Creature::fight(Creature *creature) {
    if (!alive || !creature || !creature->isAlive())
        return;
    if (applyEffects())
        return;

    Interaction *action = selectAction();
    if (action) {
        action->onAction(this, creature);
    }
}

void Creature::levelUp() {
    level++;
    stats.addBonus(getLevelStats());
    Interaction *action = getLevelAction();
    if (action)
        addAction(action);
    attribChange();
    heal(0);
    addMana(0);
}

std::set<Item *> *Creature::getLoot() { return LootProvider::getLoot(std::max(0, getScale())); }

void Creature::addAction(Interaction *action) {
    if (!action)
        return;
    actions.insert(action);
    Q_EMIT skillsChanged();
}

void Creature::addEffect(std::string type, Creature *caster) {
    if (type.empty())
        return;
    effects.insert(new Effect(type, caster));
}

void Creature::addItem(std::set<Item *> *items) {
    for (Item *item : *items) if (item) inventory.insert(item);
    Q_EMIT inventoryChanged();
}
void Creature::addItem(Item *item) { if (item) inventory.insert(item); Q_EMIT inventoryChanged(); }
void Creature::loseItem(Item *item) { inventory.erase(item); Q_EMIT inventoryChanged(); }
std::set<Item *> *Creature::getInventory() { return (std::set<Item *> *)&inventory; }
std::map<int, Item *> *Creature::getEquipped() { return &equipped; }
std::set<Interaction *> *Creature::getActions() { return (std::set<Interaction *> *)&actions; }
int Creature::getMana() { return mana; }

void Creature::addMana(int i) {
    if (i <= 0)
        mana = manaMax;
    else
        mana = std::min(manaMax, mana + i);
}

void Creature::addManaProc(float i) { addMana(static_cast<int>(manaMax * i / 100.0f)); }

void Creature::takeMana(int i) { mana = std::max(0, mana - i); }

bool Creature::isPlayer() { return inherits("Player"); }

int Creature::getHpRatio() { return clamp_ratio(hp, hpMax); }

void Creature::setItem(int slot, Item *item) {
    Item *previous = equipped[slot];
    if (previous == item) return;
    if (previous) previous->onUnequip(this);
    equipped[slot] = item;
    if (item) item->onEquip(this);
    Q_EMIT equippedChanged();
    Q_EMIT statsChanged();
}
void Creature::setWeapon(Weapon *weapon) { setItem(0, weapon); }
void Creature::setArmor(Armor *armor) { setItem(3, armor); }
Weapon *Creature::getWeapon() { return dynamic_cast<Weapon *>(equipped[0]); }
Armor *Creature::getArmor() { return dynamic_cast<Armor *>(equipped[3]); }
bool Creature::hasEquipped(Item *item) {
    for (const auto &entry : equipped) if (entry.second == item) return true;
    return false;
}
bool Creature::hasInInventory(Item *item) { return inventory.find(item) != inventory.end(); }
bool Creature::hasItem(Item *item) { return hasInInventory(item) || hasEquipped(item); }
Coords Creature::getCoords() { return Coords(getPosX(), getPosY(), getPosZ()); }
void Creature::onEnter() {}
void Creature::onMove() {}


int Creature::getExp() { return exp; }
Stats *Creature::getStats() { return &stats; }

int Creature::getScale() { return level + sw; }

// The consolidated creature template owns the level-to-action table.
Interaction *Creature::getLevelAction() {
    std::ostringstream key;
    key << level;
    Json::Value config = (*ConfigurationProvider::getConfig("config/object.json"))[typeName];
    return Interaction::getInteraction(config["levelling"].get(key.str(), "").asString());
}

bool Creature::isAlive() { return alive; }

void Creature::setAlive() { alive = true; }

// Creatures are described by a configuration or a saved game: both use the same keys.
void Creature::loadFromJson(std::string name) {
    typeName = name;
    Json::Value config = (*ConfigurationProvider::getConfig("config/object.json"))[name];
    animPath = config.get("path", "").asString();
    setAnimation(animPath);
    sw = config.get("sw", 0).asInt();
    stats.loadFromJson(config["initStats"]);

    Json::Value names = config["actions"];
    for (unsigned int i = 0; i < names.size(); i++)
        addAction(Interaction::getInteraction(names[i].asString()));

    std::set<Item *> items;
    names = config["items"];
    for (unsigned int i = 0; i < names.size(); i++) {
        Item *item = Item::createItem(names[i].asCString());
        if (item)
            items.insert(item);
    }
    addItem(&items);

    Json::Value equipment_config = config["equipment"];
    for (Json::Value::iterator it = equipment_config.begin(); it != equipment_config.end(); ++it)
        setItem(std::atoi(it.memberName()), Item::createItem((*it).asCString()));
    Json::Value equipment = config["inventory"];
    if (equipment.isMember("weapon")) setWeapon(dynamic_cast<Weapon *>(Item::createItem(QString::fromStdString(equipment["weapon"].asString()))));
    if (equipment.isMember("armor")) setArmor(dynamic_cast<Armor *>(Item::createItem(QString::fromStdString(equipment["armor"].asString()))));

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




int Creature::getHp() { return hp; }

int Creature::getHpMax() { return hpMax; }

int Creature::getManaMax() { return manaMax; }

int Creature::getLevel() { return level; }

// Applies every active effect for this turn. Returns true when an effect (such as
// Stun) prevents the creature from acting; finished effects are dropped.
bool Creature::applyEffects() {
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

int Creature::getManaRatio() { return clamp_ratio(mana, manaMax); }

void Creature::addExpScaled(int scale) { addExp(std::max(1, scale) * 150); }

void Creature::addExp(int exp) {
    this->exp += exp;
    const int required = std::max(1, level * (level + 1) * 500);
    while (this->exp >= required) {
        this->exp -= required;
        levelUp();
    }
}

Interaction *Creature::selectAction() {
    if (actions.empty())
        return 0;

    for (auto it = actions.begin(); it != actions.end(); ++it) {
        if ((*it)->getManaCost() <= mana)
            return *it;
    }
    return *actions.begin();
}

Stats Creature::getLevelStats() {
    Stats bonus;
    Json::Value config = (*ConfigurationProvider::getConfig("config/object.json"))[typeName];
    bonus.loadFromJson(config["levelStats"]);
    return bonus;
}

void Creature::hoverEnterEvent(QGraphicsSceneHoverEvent *event) {
    std::ostringstream text;
    text << typeName << "\nHP: " << hp << "/" << hpMax << "\nMana: " << mana << "/" << manaMax;
    statsView.setText(text.str().c_str());
    statsView.setPos(0, -statsView.boundingRect().height());
    statsView.setVisible(true);
    if (event)
        event->accept();
}


void Creature::setExp(int value) { exp = value; Q_EMIT statsChanged(); }
int Creature::getExpReward() { return std::max(1, getScale()) * 150; }
int Creature::getGold() { return gold; }
void Creature::setGold(int value) { gold = value; Q_EMIT statsChanged(); }

void Creature::setMana(int mana) { this->mana = mana; }

void Creature::setManaMax(int value) { manaMax = value; }

int Creature::getManaRegRate() { return manaRegRate; }

void Creature::setManaRegRate(int value) { manaRegRate = value; }

void Creature::setHp(int value) { hp = value; }

void Creature::setHpMax(int value) { hpMax = value; }
