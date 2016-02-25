#pragma once

#include "core/CGlobal.h"

class CCreature;

class CFightHandler {
public:
    static void fight(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b);

    static void defeatedCreature(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b);

};
