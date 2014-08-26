#ifndef LOOTPROVIDER_H
#define LOOTPROVIDER_H
#include "item.h"

class LootProvider : private std::map<std::string, int> {
public:
	std::set<Item *> *getLoot ( int value );
	LootProvider ( Map *map );
	~LootProvider();
private:
	std::set<Item *> *calculateLoot ( int value );
	Map* map;
};

#endif // LOOTPROVIDER_H
