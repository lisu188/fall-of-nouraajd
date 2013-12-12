#include "potion.h"
#include <QDebug>
#include <creatures/creature.h>
#include <interactions/interaction.h>
#include <potioneffects/potioneffect.h>

Potion::Potion(const char *path)
{
    singleUse=true;
    initializeFromFile(path);
    effect=PotionEffect::getPotionEffect(className.c_str());
}

void Potion::onUse(Creature *creature)
{
    qDebug() << creature->className.c_str() << "used" << className.c_str();
    effect->effect(creature,power);
}
