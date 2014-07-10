#include <QGraphicsPixmapItem>
#include <src/item.h>
#include <src/map.h>
#include <src/stats.h>

#ifndef CREATURE_H
#define CREATURE_H

class Interaction;
class Effect;
class Weapon;
class Armor;
class Stats;

class Creature : public MapObject {
  Q_OBJECT
  Q_PROPERTY(int exp READ getExp WRITE setExp USER true)
  Q_PROPERTY(int gold READ getGold WRITE setGold USER true)
  Q_PROPERTY(int level READ getLevel USER true)
  Q_PROPERTY(int mana READ getMana WRITE setMana USER true)
  Q_PROPERTY(int manaMax READ getManaMax WRITE setManaMax USER true)
  Q_PROPERTY(int manaRegRate READ getManaRegRate WRITE setManaRegRate USER true)
  Q_PROPERTY(int hp READ getHp WRITE setHp USER true)
  Q_PROPERTY(int hpMax READ getHpMax WRITE setHpMax USER true)
public:
  int getExp();
  void setExp(int exp);
  static Creature *createCreature(QString name);
  Creature();
  Creature(const Creature &creature);
  ~Creature();
  int getExpReward();
  int getExpRatio();
  void attribChange();
  void heal(int i);
  void healProc(float i);
  void hurt(Damage damage);
  void hurt(int i);
  int getDmg();
  int getScale();
  bool isAlive();
  void setAlive();
  virtual void fight(Creature *creature);
  virtual void levelUp();
  virtual std::set<Item *> *getLoot();
  virtual std::set<Item *> getAllItems();
  void addAction(Interaction *action);
  void addEffect(std::string type, Creature *caster);
  int getMana();
  void setMana(int mana);
  void addMana(int i);
  void addManaProc(float i);
  void takeMana(int i);
  bool isPlayer();
  int getHpRatio();
  void setWeapon(Weapon *weapon);
  void setArmor(Armor *armor);
  Weapon *getWeapon();
  Armor *getArmor();
  Stats *getStats();
  int getManaRatio();
  int getLevel();
  void addExpScaled(int scale);
  void addExp(int exp);
  void addItem(std::set<Item *> *items);
  void addItem(Item *item);
  void removeFromInventory(Item *item);
  void removeFromEquipped(Item *item);
  std::set<Item *> *getInventory();
  std::map<int, Item *> *getEquipped();
  void loadFromJson(std::string name);
  bool applyEffects();
  std::set<Interaction *> *getActions();
  virtual void onEnter();
  virtual void onMove();
  bool hasEquipped(Item *item);
  void setItem(int i, Item *newItem);
  bool hasInInventory(Item *item);
  bool hasItem(Item *item);
  Coords getCoords();
  int getGold();
  void setGold(int value);
  int getManaMax();
  void setManaMax(int value);
  int getManaRegRate();
  void setManaRegRate(int value);
  int getHp();
  void setHp(int value);
  int getHpMax();
  void setHpMax(int value);
  Item *getItemAtSlot(int slot);
  int getSlotWithItem(Item *item);

protected:
  void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
  std::set<Item *, Comparer> inventory;
  std::map<int, Item *> equipped;
  std::set<Interaction *, Comparer> actions;
  std::set<Effect *> effects;
  int gold;
  int exp;
  int level;
  int sw;
  std::string animPath;
  int mana;
  int manaMax;
  int manaRegRate;
  int hpMax;
  int hp;
  bool alive = true;
  Stats stats;
  Interaction *selectAction();
  void takeDamage(int i);
  Interaction *getLevelAction();
  Stats getLevelStats();
  Q_SIGNAL void statsChanged();
  Q_SIGNAL void skillsChanged();
  Q_SIGNAL void inventoryChanged();
  Q_SIGNAL void equippedChanged();
};
Q_DECLARE_METATYPE(Creature)

#endif // CREATURE_H
