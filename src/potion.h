#ifndef POTION_H
#define POTION_H
#include <src/item.h>
class PotionEffect;
class Potion : public Item {
	Q_OBJECT
public:
	Potion();
	Potion ( const Potion & );
	virtual void onUse ( CCreature *creature );
	virtual void loadFromJson ( std::string name );

private:
	std::function<void ( CCreature *, int ) > effect;
};

void LifeEffect ( CCreature *creature, int power );
void ManaEffect ( CCreature *creature, int power );

#endif // POTION_H
