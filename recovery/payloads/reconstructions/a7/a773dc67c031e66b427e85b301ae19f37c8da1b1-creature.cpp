#include "creature.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

#include <interactions/interaction.h>
#include <configuration/configurationprovider.h>
#include <items/armor.h>
#include <items/weapon.h>
#include <stats/stats.h>
#include <view/gamescene.h>
#include <view/gameview.h>

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

Creature::Creature(std::string name, Json::Value config, Map *map) : MapObject(map, 0, 0, 2) {
    className = name;
    exp = 0;
    level = 0;
    sw = 0;
    mana = 0;
    manaMax = 0;
    manaRegRate = 1;
    hpMax = 0;
    hp = 0;
    alive = true;
    gold = 0;

    loadFromJson(config);
}

Creature::Creature(std::string name, Map *map)
    : Creature(name, (*ConfigurationProvider::getConfig("config/creatures.json"))[name], map) {
    className = name;
}

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
    stats.addBonus(bonusLevel);
    Interaction *action = getLevelAction();
    if (action)
        addAction(action);
    attribChange();
    heal(0);
    addMana(0);
}

std::list<Item *> *Creature::getLoot() { return new std::list<Item *>(); }

void Creature::addAction(Interaction *action) {
    if (!action)
        return;
    actions.push_back(action);
}

void Creature::addEffect(Effect *effect) {
    if (!effect)
        return;
    effects.push_back(effect);
}

void Creature::addItem(std::list<Item *> *items) {
    inventory.merge(*items);
    // Players show their inventory; a creature still being constructed is not yet one.
    Player *player = dynamic_cast<Player *>(this);
    if (player)
        player->updateViews();
}

void Creature::addItem(Item *item) {
    std::list<Item *> list;
    list.push_back(item);
    addItem(&list);
}

void Creature::loseItem(Item *item) {
    inventory.remove(item);
    Player *player = dynamic_cast<Player *>(this);
    if (player)
        player->updateViews();
}

std::list<Item *> *Creature::getInventory() { return &inventory; }

int Creature::getMana() { return mana; }

void Creature::addMana(int i) {
    if (i <= 0)
        mana = manaMax;
    else
        mana = std::min(manaMax, mana + i);
}

void Creature::addManaProc(float i) { addMana(static_cast<int>(manaMax * i / 100.0f)); }

void Creature::takeMana(int i) { mana = std::max(0, mana - i); }

bool Creature::isPlayer() {
    return className == "Player" || className == "Mage" || className == "Warrior" || className == "Rogue";
}

int Creature::getHpRatio() { return clamp_ratio(hp, hpMax); }

void Creature::setItem(void *pointer, Item *newItem) {
    Item **slot = static_cast<Item **>(pointer);
    if (*slot == newItem)
        return;

    if (*slot) {
        (*slot)->onUnequip(this);
        equipped.remove(*slot);
    }
    *slot = newItem;
    if (*slot) {
        equipped.push_back(*slot);
        (*slot)->onEquip(this);
    }
}

void Creature::setWeapon(Weapon *weapon) { setItem(&this->weapon, weapon); }

void Creature::setArmor(Armor *armor) { setItem(&this->armor, armor); }

Weapon *Creature::getWeapon() { return weapon; }

Armor *Creature::getArmor() { return armor; }

Stats *Creature::getStats() { return &stats; }

int Creature::getScale() { return level + sw; }

// The consolidated creature template owns the level-to-action table.
Interaction *Creature::getLevelAction() {
    std::ostringstream key;
    key << level;
    Json::Value config = (*ConfigurationProvider::getConfig("config/creatures.json"))[className];
    return Interaction::getInteraction(config["levelling"].get(key.str(), "").asString());
}

bool Creature::isAlive() const { return alive; }

void Creature::setAlive() { alive = true; }

// Creatures are described by a configuration or a saved game: both use the same keys.
void Creature::loadFromJson(Json::Value config) {
    animPath = config.get("path", "").asString();
    setAnimation(animPath);
    sw = config.get("sw", 0).asInt();
    stats.loadFromJson(config["initStats"]);
    bonusLevel.loadFromJson(config["levelStats"]);

    Json::Value names = config["actions"];
    for (unsigned int i = 0; i < names.size(); i++)
        addAction(Interaction::getInteraction(names[i].asString()));

    std::list<Item *> items;
    names = config["items"];
    for (unsigned int i = 0; i < names.size(); i++) {
        Item *item = Item::getItem(names[i].asCString());
        if (item)
            items.push_back(item);
    }
    addItem(&items);

    Json::Value equipment = config["inventory"];
    setWeapon(dynamic_cast<Weapon *>(Item::getItem(equipment.get("weapon", "").asCString())));
    setArmor(dynamic_cast<Armor *>(Item::getItem(equipment.get("armor", "").asCString())));

    if (config.isMember("coords"))
        moveTo(config["coords"].get("X", 0).asInt(), config["coords"].get("Y", 0).asInt(), true);

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
bool Creature::canSave() { return alive; }

Json::Value Creature::saveToJson() {
    Json::Value config;
    config["path"] = animPath;
    config["sw"] = sw;
    config["level"] = level;
    config["exp"] = exp;
    config["hp"] = hp;
    config["mana"] = mana;
    config["initStats"] = stats.saveToJson();
    config["levelStats"] = bonusLevel.saveToJson();
    config["coords"]["X"] = getPosX();
    config["coords"]["Y"] = getPosY();
    Json::Value names(Json::arrayValue);
    for (std::list<Interaction *>::iterator it = actions.begin(); it != actions.end(); ++it)
        names.append((*it)->className);
    config["actions"] = names;
    Json::Value items(Json::arrayValue);
    for (std::list<Item *>::iterator it = inventory.begin(); it != inventory.end(); ++it)
        items.append((*it)->className);
    config["items"] = items;
    if (weapon)
        config["inventory"]["weapon"] = weapon->className;
    if (armor)
        config["inventory"]["armor"] = armor->className;
    return config;
}

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
            effects.remove(effect);
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

    for (std::list<Interaction *>::iterator it = actions.begin(); it != actions.end(); ++it) {
        if ((*it)->getManaCost() <= mana)
            return *it;
    }
    return actions.front();
}

void Creature::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    Player *player = GameScene::getPlayer();
    if (!player || player == this || !alive)
        return;

    std::list<Creature *> *fightList = player->getFightList();
    if (std::find(fightList->begin(), fightList->end(), this) == fightList->end()) {
        player->addToFightList(this);
    }

    if (GameScene::getView()) {
        GameScene::getView()->showFightView();
    }
    if (event)
        event->setAccepted(true);
}

void Creature::mouseReleaseEvent(QGraphicsSceneMouseEvent *event) {
    if (event)
        event->setAccepted(true);
}
