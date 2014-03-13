#include "cave.h"

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <creatures/monster.h>

#include <configuration/configurationprovider.h>

Cave::Cave()
{
    className="Cave";
    this->setAnimation("images/buildings/cave/");
    enabled=true;
}

Cave::Cave(const Cave &cave):Cave()
{
    this->moveTo(cave.getPosX(),cave.getPosY(),cave.getPosZ(),true);
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
                    monster->moveTo(getPosX()+1*i,getPosY()+1*j,getPosZ(),true);
                }
                else
                {
                    Monster *monster=new Monster("Pritz");
                    map->addObject(monster);
                    monster->moveTo(getPosX()+1*i,getPosY()+1*j,getPosZ(),true);
                }
            }
        this->removeFromGame();
    }
}

void Cave::onMove()
{
    if(enabled&&rand()%10==0)
    {
        if(rand()%5==0)
        {
            Monster *monster=new Monster("PritzMage");
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),getPosZ(),true);
        }
        else
        {
            Monster *monster=new Monster("Pritz");
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),getPosZ(),true);
        }
    }
}

bool Cave::canSave() {
    return enabled;
}

void Cave::loadFromJson(Json::Value config)
{
    int x=config[(unsigned int)0].asInt();
    int y=config[(unsigned int)1].asInt();
    int z=config[(unsigned int)2].asInt();
    this->moveTo(x,y,z,true);
}



