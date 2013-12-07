#include "pritz.h"

#include <items/potions/manapotion.h>

#include <buildings/cave.h>

Pritz::Pritz(Map *map, int x, int y):Monster(map,x,y)
{
    className="Pritz";
    sw=1;
    this->setAnimation("images/monsters/pritz/");
    stats->setMain("S");
    bonusLevel->setDmgMin(2);
    bonusLevel->setDmgMax(3);

    bonusLevel->setStamina(2);
    bonusLevel->setStrength(3);

    bonusLevel->setHit(3);
    bonusLevel->setCrit(1);

    bonusLevel->setNormalResist(5);
}

std::list<Item *> *Pritz::getLoot()
{
    std::list<Item *>* list=new std::list<Item *>();
    if(rand()%3==0)list->push_back(new ManaPotion());
    else list->push_back(new LifePotion());
    return list;
}

void Pritz::levelUp()
{
    Creature::levelUp();
    heal(0);
    addMana(0);
}

void Pritz::onMove()
{
    Monster::onMove();
    this->addExp(rand()%25);
}
