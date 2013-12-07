#include "creature.h"

#include <algorithm>
#include <cstdlib>
#include <sstream>

#include <interactions/attacks/attack.h>
#include <interactions/interaction.h>
#include <items/armors/armor.h>
#include <items/weapons/weapon.h>
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

Creature::Creature(Map *map, int x, int y) : MapObject(map, x, y, 2) {
  className = "Creature";
  exp = 0;
  level = 1;
  sw = 0;
  mana = 0;
  manaMax = 0;
  manaRegRate = 1;
  hpMax = 0;
  hp = 0;
  alive = true;
  actions = new std::list<Interaction *>();
  weapon = 0;
  armor = 0;
  stats = new Stats();
  bonusLevel = new Stats();
  stun = 0;

  addAction(new Attack());
  attribChange();
  heal(0);
  addMana(0);
}

Creature::~Creature() {
  if (actions) {
    actions->clear();
    delete actions;
  }
  delete stats;
  delete bonusLevel;
}

int Creature::getExpRatio() {
  const int required = std::max(1, level * (level + 1) * 500);
  return clamp_ratio(exp, required);
}

void Creature::attribChange() {
  const int effectiveLevel = std::max(1, level + sw);
  const int oldHpMax = std::max(1, hpMax);
  const int oldManaMax = std::max(1, manaMax);
  const float hpRatio = hpMax > 0 ? static_cast<float>(hp) / oldHpMax : 1.0f;
  const float manaRatio =
      manaMax > 0 ? static_cast<float>(mana) / oldManaMax : 1.0f;

  stats->setStrength(effectiveLevel + bonusLevel->getStrength());
  stats->setStamina(effectiveLevel + bonusLevel->getStamina());
  stats->setAgility(effectiveLevel + bonusLevel->getAgility());
  stats->setIntelligence(effectiveLevel + bonusLevel->getIntelligence());

  stats->setArmor(bonusLevel->getArmor() + stats->getStamina() / 2);
  stats->setBlock(bonusLevel->getBlock() + stats->getAgility() / 3);

  stats->setDmgMin(std::max(1, effectiveLevel + bonusLevel->getDmgMin() +
                                   stats->getStrength() / 2));
  stats->setDmgMax(std::max(stats->getDmgMin(), effectiveLevel +
                                                    bonusLevel->getDmgMax() +
                                                    stats->getStrength()));
  stats->setHit(bonusLevel->getHit() + effectiveLevel + stats->getAgility());
  stats->setCrit(bonusLevel->getCrit() + stats->getAgility() / 2);

  stats->setFireResist(bonusLevel->getFireResist());
  stats->setThunderResist(bonusLevel->getThunderResist());
  stats->setFrostResist(bonusLevel->getFrostResist());
  stats->setNormalResist(bonusLevel->getNormalResist());

  stats->setDamage(bonusLevel->getDamage() + stats->getStrength() / 2);
  stats->setAttack(bonusLevel->getAttack() + effectiveLevel +
                   stats->getAgility());

  hpMax = 60 + stats->getStamina() * 15;
  manaMax = 20 + stats->getIntelligence() * 12;
  manaRegRate = std::max(1, stats->getIntelligence() / 4);

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
  total += stat_resisted(damage.getNormal(), stats->getNormalResist());
  total += stat_resisted(damage.getFire(), stats->getFireResist());
  total += stat_resisted(damage.getFrost(), stats->getFrostResist());
  total += stat_resisted(damage.getThunder(), stats->getThunderResist());
  hurt(total);
}

void Creature::hurt(int i) {
  const int blocked = std::max(0, i - stats->getArmor() / 8);
  takeDamage(blocked);
}

int Creature::getDmg() {
  if (!alive)
    return 0;
  const int minDamage = std::max(1, stats->getDmgMin());
  const int maxDamage = std::max(minDamage, stats->getDmgMax());
  return minDamage + rand() % (maxDamage - minDamage + 1);
}

void Creature::fight(Creature *creature) {
  if (!alive || !creature || !creature->isAlive())
    return;
  if (isStun())
    return;

  Interaction *action = selectAction();
  if (action) {
    action->action(this, creature);
  }
}

void Creature::levelUp() {
  level++;
  attribChange();
  heal(0);
  addMana(0);
}

std::list<Item *> *Creature::getLoot() { return new std::list<Item *>(); }

void Creature::addAction(Interaction *action) {
  if (!action)
    return;
  actions->push_back(action);
}

int Creature::getMana() { return mana; }

void Creature::addMana(int i) {
  if (i <= 0)
    mana = manaMax;
  else
    mana = std::min(manaMax, mana + i);
}

void Creature::addManaProc(float i) {
  addMana(static_cast<int>(manaMax * i / 100.0f));
}

void Creature::takeMana(int i) { mana = std::max(0, mana - i); }

bool Creature::isPlayer() {
  return className == "Player" || className == "Mage" ||
         className == "Warrior" || className == "Rogue";
}

int Creature::getHpRatio() { return clamp_ratio(hp, hpMax); }

void Creature::setItem(void *pointer, Item *newItem) {
  Item **slot = static_cast<Item **>(pointer);
  if (*slot == newItem)
    return;

  if (*slot) {
    (*slot)->onUnequip(this);
  }
  *slot = newItem;
  if (*slot) {
    (*slot)->onEquip(this);
  }
}

void Creature::setWeapon(Weapon *weapon) { setItem(&this->weapon, weapon); }

void Creature::setArmor(Armor *armor) { setItem(&this->armor, armor); }

Weapon *Creature::getWeapon() { return weapon; }

Armor *Creature::getArmor() { return armor; }

bool Creature::isStun() {
  if (stun <= 0)
    return false;
  stun--;
  return true;
}

void Creature::addStun(int i) { stun = std::max(stun, i); }

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
  if (actions->empty())
    return 0;

  for (std::list<Interaction *>::iterator it = actions->begin();
       it != actions->end(); ++it) {
    if ((*it)->getManaCost() <= mana)
      return *it;
  }
  return actions->front();
}

void Creature::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  Player *player = GameScene::getPlayer();
  if (!player || player == this || !alive)
    return;

  std::list<Creature *> *fightList = player->getFightList();
  if (std::find(fightList->begin(), fightList->end(), this) ==
      fightList->end()) {
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
