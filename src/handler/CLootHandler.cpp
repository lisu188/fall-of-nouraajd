#include "core/CUtil.h"
#include "object/CObject.h"

std::set<std::shared_ptr<CItem>> CLootHandler::getLoot(int value) const {
    return calculateLoot(value);
}

CLootHandler::CLootHandler(std::shared_ptr<CMap> map) : map(map) {
    //TODO: consider using getAllSubTypes
    for (std::string type : map->getObjectHandler()->getAllTypes()) {
        std::shared_ptr<CItem> item = map->createObject<CItem>(type);
        if (item) {
            int power = item->getPower();
            if (power > 0) {
                this->insert(std::make_pair(type, power));
            }
        }
    }
}

std::set<std::shared_ptr<CItem>> CLootHandler::calculateLoot(int value) const {
    std::set<std::shared_ptr<CItem>> loot;
    std::list<int> powers;
    while (value > 0) {
        int pow = rand() % value + 1;
        value -= pow;
        powers.push_back(pow);
    }
    for (int val:powers) {
        std::vector<std::string> names;
        for (std::pair<std::string, int> it:*this) {
            if (it.second == val) {
                names.push_back(it.first);
            }
        }
        if (names.size() > 0) {
            std::random_shuffle(names.begin(), names.end());
            loot.insert(map.lock()->createObject<CItem>(names.front()));
        }
    }
    return loot;
}
