#pragma once

#include "core/CGlobal.h"

class CItem;

class CMap;

class CLootHandler : private std::map<QString, int> {
public:
    CLootHandler(std::shared_ptr<CMap> map);

    std::set<std::shared_ptr<CItem> > getLoot(int value) const;

private:
    std::set<std::shared_ptr<CItem> > calculateLoot(int value) const;

    std::weak_ptr<CMap> map;
};
