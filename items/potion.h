#include <items/item.h>

#ifndef POTION_H
#define POTION_H
class PotionEffect;
class Potion : public Item
{
public:
    Potion(const char *path);

    // Item interface
protected:
    virtual void onUse(Creature *creature);
private:
    std::function<void (Creature *, int)> effect;
};

void LifeEffect(Creature *creature,int power);
void ManaEffect(Creature *creature,int power);


#endif // POTION_H
