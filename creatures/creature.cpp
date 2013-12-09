// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
// Reconstructed for the surviving December 2013 value-based creature API and authored JSON definitions.
#include "creature.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>

#include <creatures/players/player.h>
#include <effects/stun.h>
#include <interactions/attacks/attack.h>
#include <interactions/interaction.h>
#include <items/armors/armor.h>
#include <items/weapons/weapon.h>
#include <stats/stats.h>
#include <view/gamescene.h>
#include <view/gameview.h>

namespace {
int ratio(int value, int maximum) { return maximum > 0 ? std::max(0, std::min(100, value * 100 / maximum)) : 0; }

int resisted(int amount, int resistance) {
    return std::max(0, amount) * (100 - std::max(0, std::min(90, resistance))) / 100;
}

Json::Value readCreatureConfig(const std::string &path) {
    std::ifstream input(path.c_str());
    Json::Value config;
    Json::Reader reader;
    if (!input || !reader.parse(input, config) || !config.isObject()) {
        throw std::runtime_error("Cannot load historical creature configuration: " + path);
    }
    return config;
}
} // namespace

Creature::Creature(Map *map, int x, int y) : MapObject(map, x, y, 2) {
    className = "Creature";
    exp = 0;
    level = 1;
    sw = 0;
    mana = manaMax = 0;
    manaRegRate = 1;
    hp = hpMax = 0;
    alive = true;
    weapon = nullptr;
    armor = nullptr;
    addAction(new Attack());
    attribChange();
    heal(0);
    addMana(0);
}

Creature::~Creature() {
    for (Effect *effect : effects) {
        delete effect;
    }
    // Actions may also belong to graphics-item parents; those parents own their visual lifetimes.
    actions.clear();
}

void Creature::initializeFromFile(char *filePath) {
    path = filePath;
    const Json::Value config = readCreatureConfig(path);
    className = config.get("name", "Creature").asString();
    sw = config.get("sw", 0).asInt();
    stats.init(config["initStats"]);
    bonusLevel.init(config["levelStats"]);
    level = std::max(1, level);
    setAnimation(config.get("path", "").asString());
    attribChange();
    heal(0);
    addMana(0);
    addAction(getLevelAction());
}

Stats *Creature::getLevelBonus() { return &bonusLevel; }

Interaction *Creature::getLevelAction() {
    if (path.empty()) {
        return nullptr;
    }
    const Json::Value config = readCreatureConfig(path);
    return Interaction::getAction(config["levelling"].get(std::to_string(level), "").asString());
}

int Creature::getExpRatio() { return ratio(exp, std::max(1, level * (level + 1) * 500)); }

void Creature::attribChange() {
    const double hpRatio = hpMax > 0 ? static_cast<double>(hp) / hpMax : 1.0;
    const double manaRatio = manaMax > 0 ? static_cast<double>(mana) / manaMax : 1.0;
    hpMax = std::max(1, 60 + stats.getStamina() * 15);
    manaMax = std::max(1, 20 + stats.getIntelligence() * 12);
    manaRegRate = std::max(1, stats.getIntelligence() / 4);
    hp = std::max(0, std::min(hpMax, static_cast<int>(hpRatio * hpMax)));
    mana = std::max(0, std::min(manaMax, static_cast<int>(manaRatio * manaMax)));
}

void Creature::heal(int amount) {
    hp = amount <= 0 ? hpMax : std::min(hpMax, hp + amount);
    alive = hp > 0;
}

void Creature::healProc(float percent) { heal(static_cast<int>(hpMax * percent / 100.0f)); }

void Creature::takeDamage(int amount) {
    hp = std::max(0, hp - std::max(0, amount));
    alive = hp > 0;
}

void Creature::hurt(Damage damage) {
    takeDamage(resisted(damage.getNormal(), stats.getNormalResist()) +
               resisted(damage.getFire(), stats.getFireResist()) + resisted(damage.getFrost(), stats.getFrostResist()) +
               resisted(damage.getThunder(), stats.getThunderResist()));
}

void Creature::hurt(int amount) { takeDamage(std::max(0, amount - stats.getArmor() / 8)); }

int Creature::getDmg() {
    if (!alive) {
        return 0;
    }
    const int minimum = std::max(1, stats.getDmgMin());
    const int maximum = std::max(minimum, stats.getDmgMax());
    return minimum + rand() % (maximum - minimum + 1) + std::max(0, stats.getDamage());
}

int Creature::getScale() { return std::max(1, level + sw); }
bool Creature::isAlive() const { return alive; }
void Creature::setAlive() { alive = true; }

void Creature::fight(Creature *creature) {
    if (!alive || !creature || !creature->isAlive() || applyEffects()) {
        return;
    }
    Interaction *action = selectAction();
    if (action && action->getManaCost() <= mana) {
        action->action(this, creature);
        takeMana(action->getManaCost());
    }
}

void Creature::levelUp() {
    ++level;
    stats.addBonus(getLevelBonus());
    addAction(getLevelAction());
    attribChange();
    heal(0);
    addMana(0);
}

void Creature::addAction(Interaction *action) {
    if (action) {
        actions.push_back(action);
    }
}

void Creature::addEffect(Effect *effect) {
    if (effect) {
        effects.push_back(effect);
    }
}

bool Creature::applyEffects() {
    bool blocked = false;
    for (auto it = effects.begin(); it != effects.end();) {
        Effect *effect = *it;
        blocked = blocked || (effect->getDuration() > 0 && dynamic_cast<Stun *>(effect));
        if (effect->apply(this)) {
            ++it;
        } else {
            delete effect;
            it = effects.erase(it);
        }
    }
    return blocked || !alive;
}

int Creature::getMana() { return mana; }
void Creature::addMana(int amount) { mana = amount <= 0 ? manaMax : std::min(manaMax, mana + amount); }
void Creature::addManaProc(float percent) { addMana(static_cast<int>(manaMax * percent / 100.0f)); }
void Creature::takeMana(int amount) { mana = std::max(0, mana - std::max(0, amount)); }
bool Creature::isPlayer() { return dynamic_cast<Player *>(this) != nullptr; }
int Creature::getHpRatio() { return ratio(hp, hpMax); }
int Creature::getManaRatio() { return ratio(mana, manaMax); }
Stats *Creature::getStats() { return &stats; }
int Creature::getHp() { return hp; }
int Creature::getHpMax() { return hpMax; }
int Creature::getManaMax() { return manaMax; }
int Creature::getLevel() { return level; }

void Creature::setItem(void *pointer, Item *newItem) {
    Item **slot = static_cast<Item **>(pointer);
    if (*slot == newItem) {
        return;
    }
    if (*slot) {
        (*slot)->onUnequip(this);
    }
    *slot = newItem;
    if (*slot) {
        (*slot)->onEquip(this);
    }
    attribChange();
}

void Creature::setWeapon(Weapon *newWeapon) { setItem(&weapon, newWeapon); }
void Creature::setArmor(Armor *newArmor) { setItem(&armor, newArmor); }
Weapon *Creature::getWeapon() { return weapon; }
Armor *Creature::getArmor() { return armor; }

void Creature::addExpScaled(int scale) { addExp(std::max(1, scale) * 150); }

void Creature::addExp(int amount) {
    exp += std::max(0, amount);
    while (exp >= std::max(1, level * (level + 1) * 500)) {
        exp -= std::max(1, level * (level + 1) * 500);
        levelUp();
    }
}

Interaction *Creature::selectAction() {
    for (Interaction *action : actions) {
        if (action->getManaCost() <= mana) {
            return action;
        }
    }
    return nullptr;
}

void Creature::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    Player *player = GameScene::getPlayer();
    if (!player || player == this || !alive) {
        return;
    }
    auto *fights = player->getFightList();
    if (std::find(fights->begin(), fights->end(), this) == fights->end()) {
        player->addToFightList(this);
    }
    if (GameScene::getView()) {
        GameScene::getView()->showFightView();
    }
    if (event) {
        event->setAccepted(true);
    }
}

void Creature::mouseReleaseEvent(QGraphicsSceneMouseEvent *event) {
    if (event) {
        event->setAccepted(true);
    }
}
