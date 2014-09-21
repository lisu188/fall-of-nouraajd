#include "CConfigurationProvider.h"
#include "CGuiHandler.h"
#include "CCreature.h"
#include "CGamePanel.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CInteraction.h"
#include "CLootProvider.h"
#include "CObjectHandler.h"
#include "CPathFinder.h"
#include "CPlayerView.h"
#include "CTypeHandler.h"
#include <QDebug>
#include <QGraphicsSceneHoverEvent>
#include <QJsonArray>
#include <QThreadPool>
#include <cmath>

namespace {
QJsonObject creatureProperties(QString name) {
  return CConfigurationProvider::getConfig("config/objects/monsters.json")
      .toObject()[name]
      .toObject()["properties"]
      .toObject();
}

Stats readStats(QJsonObject properties) {
  Stats value;
  for (auto it = properties.begin(); it != properties.end(); ++it) {
    value.setProperty(it.key(), it.value().toVariant());
  }
  return value;
}
} // namespace

CCreature::CCreature()
    : gold(0), exp(0), level(0), sw(0), mana(0), manaMax(0), manaRegRate(0),
      hpMax(0), hp(0) {
  setZValue(2);
  QJsonObject slot_config =
      CConfigurationProvider::getConfig("config/slots.json").toObject();
  for (auto it = slot_config.begin(); it != slot_config.end(); ++it) {
    equipped[it.key().toInt()] = nullptr;
  }
}

CCreature::CCreature(const CCreature &creature) : CCreature() {
  typeName = creature.typeName;
  gold = creature.gold;
  exp = creature.exp;
  level = creature.level;
  sw = creature.sw;
  mana = creature.mana;
  manaMax = creature.manaMax;
  manaRegRate = creature.manaRegRate;
  hpMax = creature.hpMax;
  hp = creature.hp;
  alive = creature.alive;
  stats = creature.stats;
}

CCreature::~CCreature() { actions.clear(); }

CCreature *CCreature::createCreature(QString name) {
  QJsonObject config =
      CConfigurationProvider::getConfig("config/objects/monsters.json")
          .toObject()[name]
          .toObject();
  CCreature *creature = dynamic_cast<CCreature *>(
      CTypeHandler().create(config["class"].toString()));
  if (creature) {
    creature->typeName = name;
    QJsonObject properties = creatureProperties(name);
    creature->stats = readStats(properties["stats"].toObject());
    creature->sw = properties["sw"].toInt();
    creature->setAnimation(properties["animation"].toString());
    creature->attribChange();
    creature->heal(0);
    creature->addMana(0);
  }
  return creature;
}

void CCreature::setAlive() { alive = true; }
Stats *CCreature::getStats() { return &stats; }
std::set<CItem *> *CCreature::getInventory() {
  return reinterpret_cast<std::set<CItem *> *>(&inventory);
}
std::set<CInteraction *> *CCreature::getActions() {
  return reinterpret_cast<std::set<CInteraction *> *>(&actions);
}
std::map<int, CItem *> *CCreature::getEquipped() { return &equipped; }
std::set<CItem *> *CCreature::getLoot() { return getInventory(); }

void CCreature::addItem(CItem *item) {
  if (item) {
    inventory.insert(item);
    Q_EMIT inventoryChanged();
  }
}
void CCreature::addItem(std::set<CItem *> *items) {
  if (items) {
    inventory.insert(items->begin(), items->end());
    Q_EMIT inventoryChanged();
  }
}

CInteraction *CCreature::getLevelAction() {
  QString name = creatureProperties(typeName)["levelling"]
                     .toObject()[QString::number(level)]
                     .toString();
  return map && !name.isEmpty()
             ? map->getObjectHandler()->createMapObject<CInteraction *>(name)
             : nullptr;
}
Stats CCreature::getLevelStats() {
  return readStats(creatureProperties(typeName)["levelStats"].toObject());
}

void CCreature::setItem(int slot, CItem *item) {
  if (item && !CItemSlot::checkType(slot, item)) {
    qFatal("Item has the wrong equipment slot");
  }
  CItem *previous = getItemAtSlot(slot);
  if (previous) {
    previous->onUnequip(this);
    addItem(previous);
    if (previous == item) {
      item = nullptr;
    }
  }
  if (item) {
    item->onEquip(this);
    removeFromInventory(item);
  }
  equipped[slot] = item;
  attribChange();
  Q_EMIT equippedChanged();
  Q_EMIT statsChanged();
}

void CCreature::fight(CCreature *creature) {
  if (applyEffects()) {
    return;
  }
  if (!isAlive()) {
    if (CPlayer *player = dynamic_cast<CPlayer *>(creature)) {
      player->removeFromFightList(this);
    }
    return;
  }
  CInteraction *action = selectAction();
  if (action) {
    action->onAction(this, creature);
    if (creature->getArmor() && creature->getArmor()->getInteraction()) {
      creature->getArmor()->getInteraction()->onAction(creature, this);
    }
  }
  creature->fight(this);
}

void CCreature::addEffect(Effect *effect) {
  if (effect) {
    effects.insert(effect);
  }
}
bool CCreature::applyEffects() {
  for (auto it = effects.begin(); it != effects.end();) {
    if ((*it)->getTimeLeft() == 0) {
      it = effects.erase(it);
    } else {
      ++it;
    }
  }
  bool stopped = false;
  for (Effect *effect : effects) {
    stopped = effect->apply(this) || stopped;
    if (!isAlive()) {
      if (CPlayer *player = dynamic_cast<CPlayer *>(effect->getCaster())) {
        player->removeFromFightList(this);
      }
      return true;
    }
  }
  return stopped;
}

void CCreature::onEnter() { CMapObject::onEnter(); }
void CCreature::onMove() { CMapObject::onMove(); }
void CCreature::hoverEnterEvent(QGraphicsSceneHoverEvent *event) {
  CMapObject::hoverEnterEvent(event);
}
int CCreature::getExp() { return exp; }

void CCreature::setExp(int exp) {
  this->exp = exp;
  this->addExp(0);
}

int CCreature::getExpReward() { return level * 750; }

void CCreature::addExpScaled(int scale) {
  int rank = level - scale;
  this->addExp(250 * pow(2, -rank));
}

void CCreature::addExp(int exp) {
  if (!isAlive()) {
    return;
  }
  this->exp += exp;
  while (this->exp >= level * (level + 1) * 500) {
    this->levelUp();
  }
  Q_EMIT statsChanged();
}

void CCreature::removeFromInventory(CItem *item) {
  if (inventory.find(item) != inventory.end()) {
    inventory.erase(inventory.find(item));
  }
  Q_EMIT inventoryChanged();
}

void CCreature::removeFromEquipped(CItem *item) {
  if (hasEquipped(item)) {
    setItem(getSlotWithItem(item), nullptr);
  }
  removeFromInventory(item);
}

void CCreature::heal(int i) {
  if (i < 0) {
    throw 0;
  }
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
  Q_EMIT statsChanged();
}

void CCreature::healProc(float i) {
  int tmp = hp;
  heal(i / 100.0 * hpMax);
  qDebug() << getTypeName() << "restored" << hp - tmp << "hp" << "\n";
}

void CCreature::hurt(int i) {
  Damage damage;
  damage.setNormal(i);
  hurt(damage);
}

int CCreature::getExpRatio() {
  return (float)((exp - level * (level - 1) * 500)) /
         (float)(level * (level + 1) * 500 - level * (level - 1) * 500) * 100.0;
}

void CCreature::takeDamage(int i) {
  if (rand() < stats.getBlock()) {
    return;
  }
  if (i < 0) {
    qFatal("damage less than 0 taken");
    return;
  }
  hp -= i * ((100 - stats.getArmor()) / 100.0);
  Q_EMIT statsChanged();
}

int CCreature::getDmg() {
  int critDice = rand() % 100;
  int attDice = rand() % 100;
  int dmg =
      rand() % (stats.getDmgMax() + 1 - stats.getDmgMin()) + stats.getDmgMin();
  dmg += stats.getDamage();
  attDice -= stats.getAttack();
  if (attDice < stats.getHit()) {
    if (critDice < stats.getCrit()) {
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
  QVariant configured_scale = property("sw");
  return level + (configured_scale.isValid() ? configured_scale.toInt() : sw);
}

bool CCreature::isAlive() { return hp >= 0; }

void CCreature::addAction(CInteraction *action) {
  if (!action) {
    return;
  }
  action->setMap(this->getMap());
  actions.insert(action);
  Q_EMIT skillsChanged();
}

int CCreature::getMana() { return mana; }

void CCreature::setMana(int mana) { this->mana = mana; }

void CCreature::addMana(int i) {
  if (i < 0) {
    throw 0;
  }
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
  Q_EMIT statsChanged();
}

void CCreature::addManaProc(float i) {
  int tmp = mana;
  addMana(i / 100.0 * manaMax);
  qDebug() << getTypeName() << "restored" << mana - tmp << "mana" << "\n";
}

void CCreature::takeMana(int i) {
  if (i < 0) {
    throw 0;
  }
  mana -= i;
  Q_EMIT statsChanged();
}

CInteraction *CCreature::selectAction() {
  for (CInteraction *it : actions) {
    if (it->getManaCost() < mana) {
      return it;
    }
  }
  return 0;
}

bool CCreature::isPlayer() { return getMap()->getPlayer() == this; }

int CCreature::getHpRatio() {
  if (hp > hpMax) {
    return 100;
  }
  return (float)hp / (float)hpMax * 100.0;
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
  return (float)mana / (float)manaMax * 100.0;
}

int CCreature::getHp() { return hp; }

int CCreature::getManaMax() { return manaMax; }

int CCreature::getLevel() { return level; }

void CCreature::setWeapon(CWeapon *weapon) { this->setItem(0, weapon); }

void CCreature::setArmor(CArmor *armor) { this->setItem(3, armor); }

bool CCreature::hasInInventory(CItem *item) {
  return inventory.find(item) != inventory.end();
}

bool CCreature::hasItem(CItem *item) {
  return hasInInventory(item) || hasEquipped(item);
}

Coords CCreature::getCoords() {
  Coords coords(getPosX(), getPosY(), getPosZ());
  return coords;
}

CWeapon *CCreature::getWeapon() {
  return dynamic_cast<CWeapon *>(getItemAtSlot(0));
}

CArmor *CCreature::getArmor() {
  return dynamic_cast<CArmor *>(getItemAtSlot(3));
}

void CCreature::levelUp() {
  level++;
  stats.addBonus(getLevelStats());
  addAction(getLevelAction());
  attribChange();
  if (level > 1) {
    qDebug() << getTypeName() << "is now level:" << level << "\n";
  }
}

std::set<CItem *> CCreature::getAllItems() {
  std::set<CItem *> allItems;
  allItems.insert(inventory.begin(), inventory.end());
  for (auto it : equipped) {
    if (it.second) {
      allItems.insert(it.second);
    }
  }
  return allItems;
}

void CCreature::attribChange() {
  hpMax = stats.getStamina() * 7;
  manaRegRate = stats.getMainValue() / 10 + 1;
  manaMax = stats.getMainValue() * 7;
}

bool CCreature::hasEquipped(CItem *item) {
  for (unsigned int i = 0; i < equipped.size(); i++) {
    auto it = equipped.find(i);
    if (it != equipped.end() && (*it).second == item) {
      return true;
    }
  }
  return false;
}

int CCreature::getHpMax() { return hpMax; }

void CCreature::setHpMax(int value) { hpMax = value; }

CItem *CCreature::getItemAtSlot(int slot) {
  if (equipped.find(slot) != equipped.end()) {
    return equipped.at(slot);
  }
  return nullptr;
}

int CCreature::getSlotWithItem(CItem *item) {
  for (auto it = equipped.begin(); it != equipped.end(); it++) {
    if ((*it).second == item) {
      return (*it).first;
    }
  }
  return -1;
}

void CCreature::setHp(int value) { hp = value; }

int CCreature::getManaRegRate() { return manaRegRate; }

void CCreature::setManaRegRate(int value) { manaRegRate = value; }

void CCreature::setManaMax(int value) { manaMax = value; }

int CCreature::getGold() { return gold; }

void CCreature::setGold(int value) { gold = value; }

void CCreature::hurt(Damage damage) {
  takeDamage(damage.getNormal() * (100 - stats.getNormalResist()) / 100.0);
  takeDamage(damage.getThunder() * (100 - stats.getThunderResist()) / 100.0);
  takeDamage(damage.getFrost() * (100 - stats.getFrostResist()) / 100.0);
  takeDamage(damage.getFire() * (100 - stats.getFireResist()) / 100.0);
  takeDamage(damage.getShadow() * (100 - stats.getShadowResist()) / 100.0);
  qDebug() << getTypeName() << "took damage:" << "normal(" << damage.getNormal()
           << ")thunder(" << damage.getThunder() << ")frost("
           << damage.getFrost() << ")fire(" << damage.getFire() << ")shadow("
           << damage.getShadow() << ")";
}

void CPlayer::updateViews() {
  for (auto it = inventory.begin(); it != inventory.end(); it++) {
    CItem *item = *it;
    if (map && item->getMap() != map) {
      item->setMap(map);
    }
  }
  for (auto it = actions.begin(); it != actions.end(); it++) {
    CInteraction *action = *it;
    if (map && action->getMap() != map) {
      action->setMap(map);
    }
  }
  for (std::map<int, CItem *>::iterator it = equipped.begin();
       it != equipped.end(); it++) {
    CItem *item = (*it).second;
    if (map && item && item->getMap() != map) {
      item->setMap(map);
    }
  }
}

void CPlayer::init() {
  gold = 0;
  turn = 0;
}

void CPlayer::setMap(CMap *map) {
  CMapObject::setMap(map);
  updateViews();
}

CPlayer::CPlayer() { init(); }

CPlayer::CPlayer(const CPlayer &player) : CCreature(player) { init(); }

CPlayer::~CPlayer() { inventory.clear(); }

std::set<CItem *> *CPlayer::getLoot() {
  return (std::set<CItem *> *)&inventory;
}

void CPlayer::onMove() {
  addMana(manaRegRate);
  turn++;
}

void CPlayer::onEnter() {}

void CPlayer::addToFightList(CCreature *creature) {
  fightList.push_back(creature);
}

std::list<CCreature *> *CPlayer::getFightList() { return &fightList; }

void CPlayer::removeFromFightList(CCreature *creature) {
  if (creature == this) {
    return;
  }
  qDebug() << typeName << "defeated" << creature->typeName << "\n";
  addExpScaled(creature->getScale());
  addItem(creature->getLoot());
  creature->removeFromGame();
  getFightList()->remove(creature);
  if (getFightList()->size() == 0) {
    map->getGuiHandler()->getPanel("CFightPanel")->setVisible(false);
    CFightPanel::selected = 0;
  } else {
    CFightPanel::selected = getFightList()->front();
  }
  map->getGuiHandler()->getPanel("CFightPanel")->update();
  Q_EMIT statsChanged();
}

void CPlayer::performAction(CInteraction *action, CCreature *creature) {
  action->onAction(this, creature);
  takeMana(action->getManaCost());
  CArmor *armor = creature->getArmor();
  if (armor) {
    CInteraction *interaction = armor->getInteraction();
    if (interaction) {
      interaction->onAction(creature, this);
    }
  }
  if (!creature->isAlive()) {
    removeFromFightList(creature);
  } else {
    qDebug() << "";
    std::list<CCreature *> tmpList(*getFightList());
    for (std::list<CCreature *>::iterator it = tmpList.begin();
         it != tmpList.end(); it++) {
      (*it)->fight(this);
    }
  }
  map->getGuiHandler()->getPanel("CFightPanel")->update();
  if (!isAlive()) {
    map->getScene()->getView()->close();
  }
}

void CPlayer::addEntered(CMapObject *object) { entered.push_back(object); }

std::list<CMapObject *> *CPlayer::getEntered() { return &entered; }

void CPlayer::fight(CCreature *creature) {
  if (applyEffects()) {
    creature->fight(this);
  }
}

void CPlayer::update() {
  updateViews();
  Q_EMIT statsChanged();
}

CMonster::CMonster() : CCreature() {}

CMonster::CMonster(const CMonster &monster) : CCreature(monster) {}

void CMonster::onMove() {
  if (!isAlive()) {
    return;
  }
  APathFinder *finder;
  if ((this->getCoords().getDist(
          this->getMap()->getScene()->getPlayer()->getCoords())) < 25) {
    finder = new CSmartPathFinder();
  } else {
    finder = new CRandomPathFinder();
  }
  this->addExp(rand() % 25);
  QThreadPool::globalInstance()->start(
      new PathFinderWorker(this, map->getScene()->getPlayer(), finder));
}

void CMonster::onEnter() {
  if (!isAlive()) {
    return;
  }
  map->getScene()->getPlayer()->addToFightList(this);
}

void CMonster::levelUp() {
  CCreature::levelUp();
  heal(0);
  addMana(0);
}

std::set<CItem *> *CMonster::getLoot() {
  return this->getMap()->getLootProvider()->getLoot(getScale());
}
