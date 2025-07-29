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
#include "CCreature.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"

bool visitablePredicate(std::shared_ptr<CMapObject> object) {
  return vstd::cast<Visitable>(object).operator bool();
};

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

CCreature::CCreature() {}

CCreature::~CCreature() {}

void CCreature::addExpScaled(int scale) {
  int rank = level - scale;
  // TODO: rethink this
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

int CCreature::getExpForNextLevel() { return getExpForLevel(level + 1); }

std::shared_ptr<CInteraction> CCreature::getLevelAction() {
  std::string levelString = std::to_string(level);
  if (vstd::ctn(levelling, levelString)) {
    return getGame()->getObjectHandler()->clone<CInteraction>(
        levelling[levelString]);
  } else {
    return nullptr;
  }
}

std::shared_ptr<Stats> CCreature::getLevelStats() { return levelStats; }

void CCreature::setLevelStats(std::shared_ptr<Stats> _value) {
  levelStats = _value;
}

void CCreature::addItem(std::shared_ptr<CItem> item) {
  std::set<std::shared_ptr<CItem>> list;
  list.insert(item);
  addItems(list);
}

void CCreature::removeItem(std::shared_ptr<CItem> item, bool quest) {
  // TODO: this check should be more polymorphic
  if (!quest && vstd::castable<CPlayer>(this->ptr<CCreature>()) &&
      item->hasTag("quest")) {
    vstd::logger::fatal("Tried to drop quest item");
  } else {
    if (items.erase(item)) {
      signal("inventoryChanged");
    }
  }
}

void CCreature::removeItem(
    std::function<bool(std::shared_ptr<CItem>)> item_pred, bool quest) {
  for (auto item : items) {
    if (item_pred(item)) {
      removeItem(item, quest);
    }
  }
}

std::set<std::shared_ptr<CItem>> CCreature::getInInventory() { return items; }

std::set<std::shared_ptr<CInteraction>> CCreature::getInteractions() {
  return actions;
}

CItemMap CCreature::getEquipped() { return equipped; }

void CCreature::setEquipped(CItemMap value) {
  equipped = value; // TODO: rethink equipped changed here
}

void CCreature::addItems(std::set<std::shared_ptr<CItem>> items) {
  for (std::shared_ptr<CItem> it : items) {
    this->items.insert(it);
    signal("inventoryChanged");
  }
}

void CCreature::addItem(std::string item) {
  addItem(getGame()->createObject<CItem>(item));
}

void CCreature::heal(int i) {
  vstd::fail_if(i < 0, "Tried to heal negative value!");
  auto hpMax = getHpMax();
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
  heal(i / 100.0 * getHpMax());
  vstd::logger::debug(to_string(), "restored", hp - tmp, "hp");
}

void CCreature::hurt(int i) {
  std::shared_ptr<Damage> damage = std::make_shared<Damage>();
  damage->setNormal(i);
  hurt(damage);
}

void CCreature::hurt(float i) { hurt(int(round(i))); }

int CCreature::getExpRatio() {
  return (float)((exp - getExpForLevel(level))) /
         (float)(getExpForLevel(level + 1) - getExpForLevel(level)) * 100.0;
}

// TODO: resistance and blocking to be more generic
void CCreature::takeDamage(int rawDamage) {
  auto stats = getStats();
  if (rawDamage < 0) {
    rawDamage = 0;
  }
  int damageAfterArmor = rawDamage * ((100 - stats->getArmor()) / 100.0);
  if (damageAfterArmor < 0) {
    damageAfterArmor = 0;
  }
  if (rand() >= stats->getBlock()) {
    vstd::logger::debug(to_string(), "armor saved from",
                        rawDamage - damageAfterArmor, "damage");
    hp -= damageAfterArmor;
  } else {
    vstd::logger::debug(getName(), "blocked", rawDamage, "damage");
  }
}

CInteractionMap CCreature::getLevelling() { return levelling; }

void CCreature::setLevelling(CInteractionMap value) { levelling = value; }

void CCreature::setItems(std::set<std::shared_ptr<CItem>> value) {
  items = value; // TODO: rethink inventory changed here
}

std::set<std::shared_ptr<CItem>> CCreature::getItems() { return items; }

void CCreature::hurt(std::shared_ptr<Damage> damage) {
  auto stats = getStats();
  takeDamage(damage->getNormal() * (100 - stats->getNormalResist()) / 100.0);
  takeDamage(damage->getThunder() * (100 - stats->getThunderResist()) / 100.0);
  takeDamage(damage->getFrost() * (100 - stats->getFrostResist()) / 100.0);
  takeDamage(damage->getFire() * (100 - stats->getFireResist()) / 100.0);
  takeDamage(damage->getShadow() * (100 - stats->getShadowResist()) / 100.0);

  vstd::logger::debug(getType(), "took damage:", JSONIFY(damage));
}

int CCreature::getDmg() {
  auto stats = getStats();
  int critDice = rand() % 100;
  int attDice = rand() % 100;
  // TODO: crashes if min damage is greater than max. duh.
  int dmg = rand() % (stats->getDmgMax() + 1 - stats->getDmgMin()) +
            stats->getDmgMin();
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

int CCreature::getScale() { return level + sw; }

bool CCreature::isAlive() { return hp > 0; }

void CCreature::addAction(std::shared_ptr<CInteraction> action) {
  if (!action) {
    return;
  }
  actions.insert(action);
  signal("interactionsChanged");
}

void CCreature::addEffect(std::shared_ptr<CEffect> effect) {
  if (vstd::ctn(effects, effect, CGameObject::name_comparator)) {
    vstd::logger::debug(effect->to_string(),
                        "skipping already present effect for",
                        this->to_string());
  } else {
    vstd::logger::debug(effect->to_string(), "starts for", this->to_string());
    effects.insert(effect);
    signal("effectsChanged");
  }
}

int CCreature::getMana() { return mana; }

void CCreature::setMana(int mana) { this->mana = mana; }

void CCreature::addMana(int i) {
  vstd::fail_if(i < 0, "Tried to add negative mana!");
  auto manaMax = getManaMax();
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
  addMana(i / 100.0 * getManaMax());
  vstd::logger::debug(to_string(), "restored", mana - tmp, "mana");
}

void CCreature::takeMana(int i) {
  vstd::fail_if(i < 0, "Tried to take negative mana value!");
  mana -= i;
}

bool CCreature::isPlayer() {
  const std::shared_ptr<CPlayer> player = getMap()->getPlayer();
  return player && player == this->ptr<CPlayer>();
}

int CCreature::getHpRatio() {
  auto hpMax = getHpMax();
  if (hp > hpMax) {
    return 100;
  }
  return (float)hp / (float)hpMax * 100.0;
}

int CCreature::getManaRatio() {
  auto manaMax = getManaMax();
  if (mana > manaMax) {
    return 100;
  }
  if (manaMax == 0) {
    return 100;
  }
  if (mana < 0) {
    return 0;
  }
  return (float)mana / (float)manaMax * 100.0;
}

int CCreature::getHp() { return hp; }

int CCreature::getManaMax() { return getStats()->getMainValue() * 7; }

int CCreature::getLevel() { return level; }

void CCreature::setWeapon(std::shared_ptr<CWeapon> weapon) {
  this->equipItem(std::to_string(0), weapon);
}

void CCreature::setArmor(std::shared_ptr<CArmor> armor) {
  this->equipItem(std::to_string(3), armor);
}

// TODO: make method unequip instead of equip null
void CCreature::equipItem(std::string i, std::shared_ptr<CItem> newItem) {
  vstd::fail_if(newItem && !getMap()->getGame()->getSlotConfiguration()->canFit(
                               i, newItem),
                "Tried to insert" + (newItem ? newItem->getType() : "null") +
                    "into slot" + i);

  if (vstd::ctn(equipped, i)) {
    std::shared_ptr<CItem> oldItem = equipped.at(i);

    getMap()->getEventHandler()->gameEvent(
        oldItem, std::make_shared<CGameEventCaused>(CGameEvent::Type::onUnequip,
                                                    this->ptr<CCreature>()));
    this->addItem(oldItem);
    if (newItem == oldItem) {
      newItem = nullptr;
    }
  }
  if (newItem) {
    getMap()->getEventHandler()->gameEvent(
        newItem, std::make_shared<CGameEventCaused>(CGameEvent::Type::onEquip,
                                                    this->ptr<CCreature>()));
    removeItem(newItem);
    equipped[i] = newItem;
    signal("equippedChanged");
  } else {
    if (equipped.erase(i)) {
      signal("equippedChanged");
    }
  }
}

bool CCreature::hasInInventory(std::shared_ptr<CItem> item) {
  return vstd::ctn(items, item);
}

bool CCreature::hasInInventory(
    std::function<bool(std::shared_ptr<CItem>)> item) {
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

// TODO: get rid of this, calculate level automatically
void CCreature::levelUp() {
  level++;
  // TODO: dynamic action calculation
  addAction(getLevelAction());
  heal(0);
  addMana(0);
  if (level > 1) {
    vstd::logger::debug(to_string(), "is now level:", level);
  }
}

std::set<std::shared_ptr<CItem>> CCreature::getAllItems() {
  std::set<std::shared_ptr<CItem>> allItems;
  allItems.insert(items.begin(), items.end());
  for (auto it : equipped) {
    if (it.second) {
      allItems.insert(it.second);
    }
  }
  return allItems;
}

bool CCreature::hasEquipped(std::function<bool(std::shared_ptr<CItem>)> item) {
  for (auto it : equipped) {
    if (item(it.second)) {
      return true;
    }
  }
  return false;
}

bool CCreature::hasEquipped(std::shared_ptr<CItem> item) {
  for (auto it : equipped) {
    if (it.second == item) {
      return true;
    }
  }
  return false;
}

int CCreature::getSw() const { return sw; }

void CCreature::setSw(int _value) { sw = _value; }

std::shared_ptr<Stats> CCreature::getBaseStats() { return baseStats; }

void CCreature::setBaseStats(std::shared_ptr<Stats> _value) {
  baseStats = _value;
}

int CCreature::getHpMax() {
  return getStats()->getStamina() * 7;
  ;
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

void CCreature::setHp(int value) { hp = value; }

int CCreature::getManaRegRate() { return getStats()->getMainValue() / 10 + 1; }

int CCreature::getGold() { return gold; }

void CCreature::setGold(int value) { gold = value; }

void CCreature::beforeMove() {
  auto self = this->ptr<CCreature>();

  auto func = [self](std::shared_ptr<CMapObject> object) {
    self->getMap()->getEventHandler()->gameEvent(
        object,
        std::make_shared<CGameEventCaused>(CGameEvent::Type::onLeave, self));
  };

  getMap()->forObjectsAtCoords(getCoords(), func, visitablePredicate);
}

void CCreature::afterMove() {
  auto self = this->ptr<CCreature>();

  if (getMap()->getTile(this->getCoords())) {
    getMap()->getTile(this->getCoords())->onStep(this->ptr<CCreature>());
  }

  auto fightPred = [self](std::shared_ptr<CMapObject> object) {
    return vstd::cast<CCreature>(object) && self != object &&
           !self->isAffiliatedWith(object)
           // TODO: better
           && self->getMap()->getObjectByName(self->getName()) &&
           object->getMap()->getObjectByName(object->getName());
  };

  auto fightAction = [self](auto object) {
    CFightHandler::fight(self, vstd::cast<CCreature>(object));
  };

  auto eventAction = [self](auto object) {
    self->getMap()->getEventHandler()->gameEvent(
        object,
        std::make_shared<CGameEventCaused>(CGameEvent::Type::onEnter, self));
  };

  getMap()->forObjectsAtCoords(this->getCoords(), fightAction, fightPred);
  getMap()->forObjectsAtCoords(this->getCoords(), eventAction,
                               visitablePredicate);
}

void CCreature::addGold(int gold) { this->setGold(this->getGold() + gold); }

void CCreature::takeGold(int gold) { this->setGold(this->getGold() - gold); }

std::set<std::shared_ptr<CEffect>> CCreature::getEffects() const {
  return effects;
}

void CCreature::onEnter(std::shared_ptr<CGameEvent>) {}

void CCreature::onLeave(std::shared_ptr<CGameEvent>) {}

void CCreature::onDestroy(std::shared_ptr<CGameEvent>) { effects.clear(); }

void CCreature::setEffects(const std::set<std::shared_ptr<CEffect>> &value) {
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
                     vstd::join({vstd::str(getPosX()), vstd::str(getPosY()),
                                 vstd::str(getPosZ())},
                                ","),
                     ")"},
                    "");
}

std::shared_ptr<CFightController> CCreature::getFightController() {
  return fightController;
}

void CCreature::setFightController(
    std::shared_ptr<CFightController> fightController) {
  CCreature::fightController = fightController;
}

// TODO: make this a CGameEvent
void CCreature::useAction(std::shared_ptr<CInteraction> action,
                          std::shared_ptr<CCreature> creature) {
  vstd::fail_if(!vstd::ctn(actions, action));
  action->onAction(this->ptr<CCreature>(), creature);
  if (creature->getArmor()) {
    if (creature->getArmor()->getInteraction()) {
      creature->getArmor()->getInteraction()->onAction(creature,
                                                       this->ptr<CCreature>());
    }
  }
}

void CCreature::removeEffect(std::shared_ptr<CEffect> effect) {
  effects.erase(effect);
  signal("effectsChanged");
}

void CCreature::useItem(std::shared_ptr<CItem> item) {
  vstd::fail_if(!vstd::ctn(items, item), "Tried to use item not in inventory!");
  getMap()->getEventHandler()->gameEvent(
      item,
      std::make_shared<CGameEventCaused>(CGameEvent::Type::onUse, this->ptr()));
  if (item->isDisposable()) {
    removeItem(item);
  }
}

void CCreature::setLevel(int level) { this->level = level; }

int CCreature::getExpForLevel(int level) { return (level - 1) * level * 500; }

void CCreature::removeQuestItem(std::shared_ptr<CItem> item) {
  removeItem(item, true);
}

void CCreature::removeQuestItem(
    std::function<bool(std::shared_ptr<CItem>)> item) {
  removeItem(item, true);
}

std::shared_ptr<Stats> CCreature::getStats() {
  std::shared_ptr<Stats> ret = std::make_shared<Stats>();
  ret->setMainStat(getBaseStats()->getMainStat());
  ret->addBonus(getBaseStats());
  for (int i = 0; i < level; i++) {
    ret->addBonus(getLevelStats());
  }
  for (auto [slot, item] : getEquipped()) {
    ret->addBonus(item->getBonus());
  }
  for (auto effect : getEffects()) {
    ret->addBonus(effect->getBonus());
  }
  return ret;
}