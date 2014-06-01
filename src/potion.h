#ifndef POTION_H
#define POTION_H
#include <src/item.h>
class PotionEffect;
class Potion : public Item {
  Q_OBJECT
public:
  Potion();
  Potion(const Potion &);
  virtual void onUse(Creature *creature);
  virtual void loadFromJson(std::string name);

private:
  std::function<void(Creature *, int)> effect;
};
Q_DECLARE_METATYPE(Potion)
Q_DECLARE_METATYPE(Potion *)

void LifeEffect(Creature *creature, int power);
void ManaEffect(Creature *creature, int power);

#endif // POTION_H
