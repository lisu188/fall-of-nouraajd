#include "cave.h"

#include <view/gamescene.h>
#include <view/playerstatsview.h>

#include <creatures/monster.h>

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
                    Monster *monster=new Monster("config/monsters/pritzmage.json",map);
                    map->addObject(monster);
                    monster->moveTo(getPosX()+2*i,getPosY()+2*j,true);
                }
                else
                {
                    Monster *monster=new Monster("config/monsters/pritz.json",map);
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
            Monster *monster=new Monster("config/monsters/pritzmage.json",map);
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),true);
        }
        else
        {
            Monster *monster=new Monster("config/monsters/pritz.json",map);
            map->addObject(monster);
            monster->moveTo(getPosX(),getPosY(),true);
        }
    }
}
