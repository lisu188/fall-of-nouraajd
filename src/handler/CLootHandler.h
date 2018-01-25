#pragma once

#include "core/CGlobal.h"

class CItem;

class CGame;

class CLootHandler : private std::map<std::string, int> {
public:
    CLootHandler(std::shared_ptr<CGame> map);

    std::set<std::shared_ptr<CItem> > getLoot(int value) const;

private:
    std::set<std::shared_ptr<CItem> > calculateLoot(int value) const;

    std::weak_ptr<CGame> game;
};
