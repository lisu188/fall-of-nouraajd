#include "armor.h"

#include <view/gamescene.h>

Armor::Armor(const char *path)
{
    initializeFromFile(path);
}

Interaction *Armor::getInteraction() {
    return interaction;
}

void Armor::onUse(Creature *creature)
{
    creature->setArmor(this);
}
