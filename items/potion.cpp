#include "potion.h"
#include <QDebug>
#include <creatures/creature.h>

Potion::Potion(const char *path)
{
    singleUse=true;
    initializeFromFile(path);
    if((std::string(path).find("LifePotion") != std::string::npos))
    {
        effect=&LifeEffect;
    } else if(std::string(path).find("ManaPotion") != std::string::npos) {
        effect=&ManaEffect;
    }
}

void Potion::onUse(Creature *creature)
{
    qDebug() << creature->className.c_str() << "used" << className.c_str();
    effect(creature,power);
}

void LifeEffect(Creature *creature,int power)
{
    creature->healProc(power*20);
}

void ManaEffect(Creature *creature,int power)
{
    creature->addManaProc(power*20);
}
