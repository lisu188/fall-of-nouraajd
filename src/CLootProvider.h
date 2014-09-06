#pragma once
#include <string>
#include <map>
#include <set>
#include <QString>

class CItem;
class CMap;
class CLootProvider : private std::map<QString, int> {
public:
	std::set<CItem *> *getLoot ( int value );
	CLootProvider ( CMap *map );
	~CLootProvider();
private:
	std::set<CItem *> *calculateLoot ( int value );
	CMap* map;
};
