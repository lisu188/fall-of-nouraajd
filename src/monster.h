#ifndef MONSTER_H
#define MONSTER_H
#include <src/creature.h>

class Monster : public Creature {
	Q_OBJECT
public:
	Monster();
	Monster ( const Monster &monster );
	virtual void onMove();
	virtual void onEnter();
	virtual void levelUp();
	virtual std::set<Item *> *getLoot();
};

#endif // MONSTER_H
