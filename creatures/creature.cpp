#include "creature.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

#include <interactions/interaction.h>
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

Creature::Creature(char *path, Map *map, int x, int y)
    : MapObject(map, x, y, 2) {
  className = "Creature";
  exp = 0;
  level = 0;
  sw = 0;
  mana = 0;
  manaMax = 0;
  manaRegRate = 1;
  hpMax = 0;
  hp = 0;
  alive = true;
  weapon = 0;
  armor = 0;
  gold = 0;

  addAction(Interaction::getInteraction("Attack"));
  initializeFromFile(path);
  levelUp();
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
  const float manaRatio =
      manaMax > 0 ? static_cast<float>(mana) / oldManaMax : 1.0f;

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
  stats.addBonus(getLevelBonus());
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

std::string Creature::getCoordsString() {
  std::ostringstream coords;
  coords << "(" << getPosX() << "," << getPosY() << ")";
  return coords.str();
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

Stats *Creature::getStats() { return &stats; }

int Creature::getScale() { return level + sw; }

Stats Creature::getLevelBonus() { return bonusLevel; }

// The creature's configuration names the interaction learned at each level.
Interaction *Creature::getLevelAction() {
  if (path.empty())
    return 0;
  std::fstream jsonFileStream;
  jsonFileStream.open(path.c_str());

  Json::Value config;
  Json::Reader reader;
  reader.parse(jsonFileStream, config);
  jsonFileStream.close();

  std::ostringstream key;
  key << level;
  return Interaction::getInteraction(config["levelling"].get(key.str(), "").asString());
}

bool Creature::isAlive() const { return alive; }

void Creature::setAlive() { alive = true; }

void Creature::initializeFromFile(char *path) {
  this->path = path;
  std::fstream jsonFileStream;
  jsonFileStream.open(path);

  Json::Value config;
  Json::Reader reader;
  reader.parse(jsonFileStream, config);
  jsonFileStream.close();

  className = config.get("name", "").asCString();
  setAnimation(config.get("path", "").asCString());
  sw = config.get("sw", 0).asInt();
  stats.init(config["initStats"]);
  bonusLevel.init(config["levelStats"]);

  std::list<Item *> items;
  Json::Value names = config["items"];
  for (unsigned int i = 0; i < names.size(); i++) {
    Item *item = Item::getItem(names[i].asCString());
    if (item)
      items.push_back(item);
  }
  addItem(&items);

  attribChange();
  heal(0);
  addMana(0);
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
  for (std::list<Effect *>::iterator it = active.begin(); it != active.end();
       ++it) {
    Effect *effect = *it;
    if (effect->apply(this))
      skipTurn = true;
    if (effect->getDuration() <= 0) {
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

  for (std::list<Interaction *>::iterator it = actions.begin();
       it != actions.end(); ++it) {
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
