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
    PotionEffect *effect;
};

#endif // POTION_H
