#ifndef POTION_H
#define POTION_H
#include <items/item.h>
class PotionEffect;
class Potion : public Item
{
public:
    Potion(std::string name);
    virtual void onUse(Creature *creature);
private:
    std::function<void (Creature *, int)> effect;
};

void LifeEffect(Creature *creature,int power);
void ManaEffect(Creature *creature,int power);

#endif // POTION_H
