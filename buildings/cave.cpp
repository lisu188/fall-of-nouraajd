#include "cave.h"

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <creatures/monster.h>

#include <configuration/configurationprovider.h>

int Cave::count=0;
Cave::Cave(Map *map, int x, int y):Building(map,x,y)
{
    className="Cave";
    this->setAnimation("images/buildings/cave/");
    count++;
    enabled=true;
}

void Cave::onEnter()
{
    Building::onEnter();
    if(enabled)
    {
        enabled=false;
        count--;
        for(int i=-1; i<2; i++)
            for(int j=-1; j<2; j++)
            {
                if(j==0&&i==0) {
                    continue;
                }
                if(rand()%5==0)
                {
                    Monster *monster=new Monster(map,"PritzMage");
                    map->addObject(monster);
                    monster->moveTo(getPosX()+2*i,getPosY()+2*j,true);
                }
                else
                {
                    Monster *monster=new Monster(map,"Pritz");
                    map->addObject(monster);
                    monster->moveTo(getPosX()+2*i,getPosY()+2*j,true);
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
            Monster *monster=new Monster(map,"PritzMage");
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),true);
        }
        else
        {
            Monster *monster=new Monster(map,"Pritz");
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),true);
        }
    }
}

bool Cave::canSave() {
    return enabled;
}


void Cave::loadFromJson(Json::Value config)
{
}

Json::Value Cave::saveToJson()
{
    Json::Value config;
    config["name"]=className;
    config["coords"]["x"]=getPosX();
    config["coords"]["y"]=getPosY();
    return config;
}
