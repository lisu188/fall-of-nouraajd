#pragma once

#include "core/CGlobal.h"

class CCreature;

class CFightHandler {
    static void fight(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b);

private:
    static void defeatedCreature(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b);

};
