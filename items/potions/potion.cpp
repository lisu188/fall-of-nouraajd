#include "potion.h"
#include <QDebug>
#include <creatures/creature.h>

Potion::Potion()
{
    className="Potion";
    singleUse=true;
}

void Potion::onUse(Creature *creature)
{
    qDebug() << creature->className.c_str() << "used" << className.c_str();
}
