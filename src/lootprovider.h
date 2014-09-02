#pragma once
#include <string>
#include <map>
#include <set>

class Item;
class CMap;
class CLootProvider : private std::map<std::string, int> {
public:
	std::set<Item *> *getLoot ( int value );
	CLootProvider ( CMap *map );
	~CLootProvider();
private:
	std::set<Item *> *calculateLoot ( int value );
	CMap* map;
};
