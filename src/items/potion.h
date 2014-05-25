#ifndef POTION_H
#define POTION_H
#include <src/items/item.h>
class PotionEffect;
class Potion : public Item
{
    Q_OBJECT
public:
    Potion();
    Potion(const Potion& potion);
    Potion(std::string name);
    virtual void onUse(Creature *creature);
    void loadFromJson(Json::Value config);
private:
    std::function<void (Creature *, int)> effect;
};
Q_DECLARE_METATYPE(Potion)

void LifeEffect(Creature *creature, int power);
void ManaEffect(Creature *creature, int power);

#endif // POTION_H
