#pragma once
#include <string>
#include <map>
#include <set>

class CItem;
class CMap;
class CLootProvider : private std::map<std::string, int> {
public:
	std::set<CItem *> *getLoot ( int value );
	CLootProvider ( CMap *map );
	~CLootProvider();
private:
	std::set<CItem *> *calculateLoot ( int value );
	CMap* map;
};
