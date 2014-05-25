#ifndef LOOTPROVIDER_H
#define LOOTPROVIDER_H
#include "item.h"

class LootProvider : private std::map<std::string, int>
{
public:
    static std::set<Item *> *getLoot(int value);
private:
    LootProvider();
    ~LootProvider();
    std::set<Item *>  *calculateLoot(int value);
};

#endif // LOOTPROVIDER_H
