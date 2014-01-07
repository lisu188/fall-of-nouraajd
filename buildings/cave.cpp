#include "cave.h"

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <creatures/monster.h>

#include <configuration/configurationprovider.h>

Cave::Cave(int x, int y,int z):Building(x,y,z)
{
    className="Cave";
    this->setAnimation("images/buildings/cave/");
    enabled=true;
}

void Cave::onEnter()
{
    Building::onEnter();
    if(enabled)
    {
        enabled=false;
        for(int i=-1; i<2; i++)
            for(int j=-1; j<2; j++)
            {
                if(j==0&&i==0) {
                    continue;
                }
                if(rand()%5==0)
                {
                    Monster *monster=new Monster("PritzMage");
                    map->addObject(monster);
                    monster->moveTo(getPosX()+1*i,getPosY()+1*j,true);
                }
                else
                {
                    Monster *monster=new Monster("Pritz");
                    map->addObject(monster);
                    monster->moveTo(getPosX()+1*i,getPosY()+1*j,true);
                }
            }
        this->removeFromGame();
    }
}

void Cave::onMove()
{
    if(enabled&&rand()%100==0)
    {
        if(rand()%5==0)
        {
            Monster *monster=new Monster("PritzMage");
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),true);
        }
        else
        {
            Monster *monster=new Monster("Pritz");
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),true);
        }
    }
}

bool Cave::canSave() {
    return enabled;
}



