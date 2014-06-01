#include "lootprovider.h"

#include <src/configurationprovider.h>
#include <src/util.h>

std::set<Item *> *LootProvider::getLoot(int value) {
  static LootProvider instance;
  return instance.calculateLoot(value);
}

LootProvider::LootProvider() {
  Json::Value config = *ConfigurationProvider::getConfig("config/object.json");
  Json::Value::iterator it = config.begin();
  for (; it != config.end(); it++) {
    if (checkInheritance("Item", (*it).get("class", "").asCString())) {
      this->insert(std::pair<std::string, int>(it.memberName(),
                                               (*it).get("power", 1).asInt()));
    }
  }
}

LootProvider::~LootProvider() { erase(begin(), end()); }

std::set<Item *> *LootProvider::calculateLoot(int value) {
  std::set<Item *> *loot = new std::set<Item *>();
  while (value) {
    int dice = rand() % this->size();
    LootProvider::iterator it = begin();
    for (int i = 0; i < dice; i++, it++)
      ;
    int power = (*it).second;
    std::string name = (*it).first;
    if (power <= value) {
      loot->insert(Item::createItem(QString::fromStdString(name)));
      value -= power;
    }
  }
  return loot;
}
