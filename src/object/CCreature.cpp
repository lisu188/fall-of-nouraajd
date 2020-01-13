/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "core/CJsonUtil.h"
#include "CCreature.h"
#include "core/CGame.h"
#include "core/CController.h"
#include "core/CMap.h"

void CCreature::setActions(std::set<std::shared_ptr<CInteraction>> value) {
    actions = value;
}

std::set<std::shared_ptr<CInteraction>> CCreature::getActions() {
    return actions;
}

int CCreature::getExp() { return exp; }

void CCreature::setExp(int exp) {
    this->exp = exp;
    this->addExp(0);
}

CCreature::CCreature() {
}

CCreature::~CCreature() {

}

int CCreature::getExpReward() {
    return level * 750;
}

void CCreature::addExpScaled(int scale) {
    int rank = level - scale;
    //TODO: rethink this
    this->addExp(250 * pow(2, -rank));
}

void CCreature::addExp(int exp) {
    if (!isAlive()) {
        return;
    }
    this->exp += exp;
    while (this->exp >= getExpForNextLevel()) {
        this->levelUp();
    }
}

int CCreature::getExpForNextLevel() {
    return getExpForLevel(level + 1);
}

std::shared_ptr<CInteraction> CCreature::getLevelAction() {
    std::string levelString = std::to_string(level);
    if (vstd::ctn(levelling, levelString)) {
        return getGame()->getObjectHandler()->clone<CInteraction>(levelling[levelString]);
    } else {
        return nullptr;
    }
}

std::shared_ptr<Stats> CCreature::getLevelStats() const {
    return levelStats;
}

void CCreature::setLevelStats(std::shared_ptr<Stats> _value) {
    levelStats = _value;
}

void CCreature::addBonus(std::shared_ptr<Stats> bonus) {
    stats->addBonus(bonus);
}

void CCreature::removeBonus(std::shared_ptr<Stats> bonus) {
    stats->removeBonus(bonus);
}


void CCreature::addItem(std::shared_ptr<CItem> item) {
    std::set<std::shared_ptr<CItem>> list;
    list.insert(item);
    addItem(list);
}

void CCreature::removeItem(std::shared_ptr<CItem> item, bool quest) {
    //TODO: this check should be more polymorphic
    if (!quest && vstd::castable<CPlayer>(this->ptr<CCreature>()) && item->hasTag("quest")) {
        vstd::logger::fatal("Tried to drop quest item");
    } else {
        if (items.erase(item)) {
            getMap()->getEventHandler()->gameEvent(this->ptr<CCreature>(),
                                                   std::make_shared<CGameEvent>(CGameEvent::Type::inventoryChanged));
        }
    }
}

void CCreature::removeItem(std::function<bool(std::shared_ptr<CItem>)> item_pred, bool quest) {
    for (auto item:items) {
        if (item_pred(item)) {
            removeItem(item, quest);
        }
    }
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

void CCreature::setEquipped(CItemMap
                            value) {
    equipped = value;//TODO: rethink equipped changed here
}

void CCreature::addItem(std::set<std::shared_ptr<CItem> > items) {
    for (std::shared_ptr<CItem> it : items) {
        this->items.insert(it);
        getMap()->getEventHandler()->gameEvent(this->ptr<CCreature>(),
                                               std::make_shared<CGameEvent>(CGameEvent::Type::inventoryChanged));
    }
}

void CCreature::addItem(std::string item) {
    addItem(getGame()->createObject<CItem>(item));
}

void CCreature::heal(int i) {
    vstd::fail_if(i < 0, "Tried to heal negative value!");
    if (hp > hpMax) {
        return;
    }
    if (i == 0) {
        hp = hpMax;
    } else {
        hp += i;
    }
    if (hp > hpMax) {
        hp = hpMax;
    }
}

void CCreature::healProc(float i) {
    int tmp = hp;
    heal(i / 100.0 * hpMax);
    vstd::logger::debug(to_string(), "restored", hp - tmp, "hp");
}

void CCreature::hurt(int i) {
    std::shared_ptr<Damage> damage = std::make_shared<Damage>();
    damage->setNormal(i);
    hurt(damage);
}

void CCreature::hurt(float i) {
    hurt(int(round(i)));
}

int CCreature::getExpRatio() {
    return (float) ((exp - getExpForLevel(level))) /
           (float) (getExpForLevel(level + 1) - getExpForLevel(level)) * 100.0;
}

//TODO: resistance and blocking to be more generic
void CCreature::takeDamage(int rawDamage) {
    if (rawDamage < 0) {
        rawDamage = 0;
    }
    int damageAfterArmor = rawDamage * ((100 - stats->getArmor()) / 100.0);
    if (damageAfterArmor < 0) {
        damageAfterArmor = 0;
    }
    if (rand() >= stats->getBlock()) {
        vstd::logger::debug(to_string(), "armor saved from", rawDamage - damageAfterArmor, "damage");
        hp -= damageAfterArmor;
    } else {
        vstd::logger::debug(getName(), "blocked", rawDamage, "damage");
    }
}

CInteractionMap CCreature::getLevelling() {
    return levelling;
}

void CCreature::setLevelling(CInteractionMap
                             value) {
    levelling = value;
}

void CCreature::setItems(std::set<std::shared_ptr<CItem> > value) {
    items = value;//TODO: rethink inventory changed here
}

std::set<std::shared_ptr<CItem>> CCreature::getItems() {
    return items;
}

void CCreature::hurt(std::shared_ptr<Damage> damage) {
    takeDamage(damage->getNormal() * (100 - stats->getNormalResist()) / 100.0);
    takeDamage(damage->getThunder() * (100 - stats->getThunderResist()) / 100.0);
    takeDamage(damage->getFrost() * (100 - stats->getFrostResist()) / 100.0);
    takeDamage(damage->getFire() * (100 - stats->getFireResist()) / 100.0);
    takeDamage(damage->getShadow() * (100 - stats->getShadowResist()) / 100.0);

    vstd::logger::debug(getType(), "took damage:", JSONIFY(damage));
}

int CCreature::getDmg() {
    int critDice = rand() % 100;
    int attDice = rand() % 100;
    int dmg =
            rand() % (stats->getDmgMax() + 1 - stats->getDmgMin()) + stats->getDmgMin();
    dmg += stats->getDamage();
    attDice -= stats->getAttack();
    if (attDice < stats->getHit()) {
        if (critDice < stats->getCrit()) {
            dmg *= 2;
            vstd::logger::debug("Critical!");
        }
        return dmg;
    } else {
        vstd::logger::debug("Missed!");
        return 0;
    }
}

int CCreature::getScale() {
    return level + sw;
}

bool CCreature::isAlive() {
    return hp > 0;
}


void CCreature::addAction(std::shared_ptr<CInteraction> action) {
    if (!action) {
        return;
    }
    actions.insert(action);
}

void CCreature::addEffect(std::shared_ptr<CEffect> effect) {
    if (vstd::ctn(effects, effect, CGameObject::name_comparator)) {
        vstd::logger::debug(effect->to_string(), "skipping already present effect for", this->to_string());
    } else {
        vstd::logger::debug(effect->to_string(), "starts for", this->to_string());
        effects.insert(effect);
    }
}

int CCreature::getMana() {
    return mana;
}

void CCreature::setMana(int mana) {
    this->mana = mana;
}

void CCreature::addMana(int i) {
    vstd::fail_if(i < 0, "Tried to add negative mana!");
    if (mana > manaMax) {
        return;
    }
    if (i == 0) {
        mana = manaMax;
    } else {
        mana += i;
    }
    if (mana > manaMax) {
        mana = manaMax;
    }
}

void CCreature::addManaProc(float i) {
    int tmp = mana;
    addMana(i / 100.0 * manaMax);
    vstd::logger::debug(to_string(), "restored", mana - tmp, "mana");
}

void CCreature::takeMana(int i) {
    vstd::fail_if(i < 0, "Tried to take negative mana value!");
    mana -= i;
}


bool CCreature::isPlayer() {
    return getMap()->getPlayer() == this->ptr<CPlayer>();
}

int CCreature::getHpRatio() {
    if (hp > hpMax) {
        return 100;
    }
    return (float) hp / (float) hpMax * 100.0;
}

int CCreature::getManaRatio() {
    if (mana > manaMax) {
        return 100;
    }
    if (manaMax == 0) {
        return 100;
    }
    if (mana < 0) {
        return 0;
    }
    return (float) mana / (float) manaMax * 100.0;
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

void CCreature::setWeapon(std::shared_ptr<CWeapon> weapon) {
    this->equipItem(std::to_string(0), weapon);
}

void CCreature::setArmor(std::shared_ptr<CArmor> armor) {
    this->equipItem(std::to_string(3), armor);
}

//TODO: make method unequip instead of equip null
void CCreature::equipItem(std::string i, std::shared_ptr<CItem> newItem) {
    vstd::fail_if(newItem && !getMap()->getGame()->getSlotConfiguration()->canFit(i, newItem),
                  "Tried to insert" + (newItem ? newItem->getType() : "null") + "into slot" + i);

    if (vstd::ctn(equipped, i)) {
        std::shared_ptr<CItem> oldItem = equipped.at(i);

        getMap()->getEventHandler()->gameEvent(oldItem,
                                               std::make_shared<CGameEventCaused>(CGameEvent::Type::onUnequip,
                                                                                  this->ptr<CCreature>()));
        this->addItem(oldItem);
        if (newItem == oldItem) {
            newItem = nullptr;
        }
    }
    if (newItem) {
        getMap()->getEventHandler()->gameEvent(newItem,
                                               std::make_shared<CGameEventCaused>(CGameEvent::Type::onEquip,
                                                                                  this->ptr<CCreature>()));
        removeItem(newItem);
        attribChange();
        equipped[i] = newItem;
        getMap()->getEventHandler()->gameEvent(this->ptr<CCreature>(),
                                               std::make_shared<CGameEvent>(CGameEvent::Type::equippedChanged));
    } else {
        if (equipped.erase(i)) {
            getMap()->getEventHandler()->gameEvent(this->ptr<CCreature>(),
                                                   std::make_shared<CGameEvent>(CGameEvent::Type::equippedChanged));
        }
    }
}

bool CCreature::hasInInventory(std::shared_ptr<CItem> item) {
    return vstd::ctn(items, item);
}

bool CCreature::hasInInventory(std::function<bool(std::shared_ptr<CItem>)> item) {
    return std::any_of(items.begin(), items.end(), item);
}

bool CCreature::hasItem(std::shared_ptr<CItem> item) {
    return hasInInventory(item) || hasEquipped(item);
}

bool CCreature::hasItem(std::function<bool(std::shared_ptr<CItem>)> item) {
    return hasInInventory(item) || hasEquipped(item);
}

std::shared_ptr<CWeapon> CCreature::getWeapon() {
    return vstd::cast<CWeapon>(getItemAtSlot("0"));
}

std::shared_ptr<CArmor> CCreature::getArmor() {
    return vstd::cast<CArmor>(getItemAtSlot("3"));
}

void CCreature::levelUp() {
    level++;
    stats->addBonus(getLevelStats());
    addAction(getLevelAction());
    attribChange();
    if (level > 1) {
        vstd::logger::debug(to_string(), "is now level:", level);
    }
}

std::set<std::shared_ptr<CItem> > CCreature::getAllItems() {
    std::set<std::shared_ptr<CItem> > allItems;
    allItems.insert(items.begin(), items.end());
    for (auto it:equipped) {
        if (it.second) {
            allItems.insert(it.second);
        }
    }
    return allItems;
}

void CCreature::attribChange() {
    hpMax = stats->getStamina() * 7;
    manaRegRate = stats->getMainValue() / 10 + 1;
    manaMax = stats->getMainValue() * 7;
}

bool CCreature::hasEquipped(std::function<bool(std::shared_ptr<CItem>)> item) {
    for (auto it:equipped) {
        if (item(it.second)) {
            return true;
        }
    }
    return false;
}

bool CCreature::hasEquipped(std::shared_ptr<CItem> item) {
    for (auto it:equipped) {
        if (it.second == item) {
            return true;
        }
    }
    return false;
}


int CCreature::getSw() const {
    return sw;
}

void CCreature::setSw(int _value) {
    sw = _value;
}

std::shared_ptr<Stats> CCreature::getStats() const {
    return stats;
}

void CCreature::setStats(std::shared_ptr<Stats> _value) {
    stats = _value;
}

int CCreature::getHpMax() {
    return hpMax;
}

void CCreature::setHpMax(int value) {
    hpMax = value;
}

std::shared_ptr<CItem> CCreature::getItemAtSlot(std::string slot) {
    if (vstd::ctn(equipped, slot)) {
        return equipped.at(slot);
    }
    return nullptr;
}

std::string CCreature::getSlotWithItem(std::shared_ptr<CItem> item) {
    for (auto it = equipped.begin(); it != equipped.end(); it++) {
        if ((*it).second == item) {
            return (*it).first;
        }
    }
    return "-1";
}

void CCreature::setHp(int value) {
    hp = value;
}

int CCreature::getManaRegRate() {
    return manaRegRate;
}

void CCreature::setManaRegRate(int value) {
    manaRegRate = value;
}

void CCreature::setManaMax(int value) {
    manaMax = value;
}

int CCreature::getGold() {
    return gold;
}

void CCreature::setGold(int value) {
    gold = value;
}

void CCreature::beforeMove() {
    auto pred = [this](std::shared_ptr<CMapObject> object) {
        return vstd::cast<Visitable>(object) && this->getCoords() == object->getCoords();
    };

    auto func = [this](std::shared_ptr<CMapObject> object) {
        this->getMap()->getEventHandler()->gameEvent(object,
                                                     std::make_shared<CGameEventCaused>(CGameEvent::Type::onLeave,
                                                                                        this->ptr<CCreature>()));
    };

    this->getMap()->forObjects(func, pred);
}

void CCreature::afterMove() {
    auto pred = [this](std::shared_ptr<CMapObject> object) {
        return vstd::cast<Visitable>(object) && this->getCoords() == object->getCoords();
    };

    auto func = [this](std::shared_ptr<CMapObject> object) {
        getMap()->getEventHandler()->gameEvent(object, std::make_shared<CGameEventCaused>(CGameEvent::Type::onEnter,
                                                                                          this->ptr<CCreature>()));
    };

    getMap()->forObjects(func, pred);

    if (getMap()->getTile(this->getCoords())) {
        getMap()->getTile(this->getCoords())->onStep(this->ptr<CCreature>());
    }
}

std::string CCreature::getTooltip() {
    return vstd::join({getType(), std::to_string(level)}, " ");
}

void CCreature::addGold(int gold) {
    this->setGold(this->getGold() + gold);
}

void CCreature::takeGold(int gold) {
    this->setGold(this->getGold() - gold);
}

std::set<std::shared_ptr<CEffect> > CCreature::getEffects() const {
    return effects;
}

void CCreature::onDestroy(std::shared_ptr<CGameEvent>) {
    effects.clear();
}

void CCreature::setEffects(const std::set<std::shared_ptr<CEffect> > &value) {
    effects = value;
}

std::shared_ptr<CController> CCreature::getController() {
    return controller ? controller : std::make_shared<CController>();
}

void CCreature::setController(std::shared_ptr<CController> controller) {
    this->controller = controller;
}

std::string CCreature::to_string() {
    return vstd::join({CGameObject::to_string(), "(",
                       vstd::join({vstd::str(getPosX()), vstd::str(getPosY()), vstd::str(getPosZ())}, ","), ")"},
                      "");
}

std::shared_ptr<CFightController> CCreature::getFightController() {
    return fightController;
}

void CCreature::setFightController(std::shared_ptr<CFightController> fightController) {
    CCreature::fightController = fightController;
}

//TODO: make this a CGameEvent
void CCreature::useAction(std::shared_ptr<CInteraction> action, std::shared_ptr<CCreature> creature) {
    vstd::fail_if(!vstd::ctn(actions, action));
    action->onAction(this->ptr<CCreature>(), creature);
    if (creature->getArmor()) {
        if (creature->getArmor()->getInteraction()) {
            creature->getArmor()->getInteraction()->onAction(creature, this->ptr<CCreature>());
        }
    }
}

void CCreature::removeEffect(std::shared_ptr<CEffect> effect) {
    effects.erase(effect);
}

void CCreature::useItem(std::shared_ptr<CItem> item) {
    vstd::fail_if(!vstd::ctn(items, item), "Tried to use item not in inventory!");
    if (item->isDisposable()) {
        getMap()->getEventHandler()->gameEvent(item,
                                               std::make_shared<CGameEventCaused>(CGameEvent::Type::onUse,
                                                                                  this->ptr()));

        removeItem(item);
    }
}

void CCreature::setLevel(int level) {
    this->level = level;
}

int CCreature::getExpForLevel(int level) {
    return (level - 1) * level * 500;
}

void CCreature::removeQuestItem(std::shared_ptr<CItem> item) {
    removeItem(item, true);
}

void CCreature::removeQuestItem(std::function<bool(std::shared_ptr<CItem>)> item) {
    removeItem(item, true);
}
