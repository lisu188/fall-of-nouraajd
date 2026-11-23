#include "building.h"
#include <QDebug>
#include <src/view/gamescene.h>
#include <src/view/playerstatsview.h>
#include <src/creatures/monster.h>
#include <src/configuration/configurationprovider.h>

Building::Building()
{
    this->setZValue(2);
}

Building::Building(const Building &)
{
}

void Building::onEnter()
{
    qDebug() << "Entered" << className.c_str()<<"\n";
}

bool Building::canSave() {
    return true;
}

void Building::onMove()
{
}

void Building::loadFromJson(Json::Value config)
{
}

Json::Value Building::saveToJson()
{
    Json::Value config;
    config[(unsigned int)0]=getPosX();
    config[(unsigned int)1]=getPosY();
    config[(unsigned int)2]=getPosZ();
    return config;
}

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

Dungeon::Dungeon()
{
    className="Dungeon";
    this->setAnimation("images/buildings/dungeon/");
}

Dungeon::Dungeon(const Dungeon &dungeon):Dungeon()
{
    this->moveTo(dungeon.getPosX(),dungeon.getPosY(),dungeon.getPosZ());
    exit=Coords(getExit());
}

void Dungeon::onEnter()
{
    GameScene::getPlayer()->moveTo(exit.x,exit.y,exit.z,true);
    map->move(0,0);
}

void Dungeon::onMove()
{
}

bool Dungeon::canSave()
{
    return true;
}

Json::Value Dungeon::saveToJson()
{
    Json::Value config;
    config[(unsigned int)0]=getPosX();
    config[(unsigned int)1]=getPosY();
    config[(unsigned int)2]=getPosZ();
    config[(unsigned int)3]=exit.x;
    config[(unsigned int)4]=exit.y;
    config[(unsigned int)5]=exit.z;
    return config;
}

void Dungeon::loadFromJson(Json::Value config)
{
    int x=config[(unsigned int)0].asInt();
    int y=config[(unsigned int)1].asInt();
    int z=config[(unsigned int)2].asInt();
    this->moveTo(x,y,z,true);
    x=config[(unsigned int)3].asInt();
    y=config[(unsigned int)4].asInt();
    z=config[(unsigned int)5].asInt();
    exit=Coords(x,y,z);
}

Coords Dungeon::getExit() const {
    return exit;
}

Teleporter::Teleporter()
{
    className="Teleporter";
    this->setAnimation("images/buildings/teleporter/");
}

Teleporter::Teleporter(const Teleporter &teleporter):Teleporter()
{
    this->moveTo(teleporter.getPosX(),teleporter.getPosY(),teleporter.getPosZ());
}

void Teleporter::onEnter()
{
    if(!enabled)return;
    std::set<MapObject*> *objects=this->getMap()->getObjects();
    std::set<MapObject*>::iterator it;
    std::vector<Teleporter*> teleporters;
    for(it=objects->begin(); it!=objects->end(); it++)
    {
        if((*it)->inherits("Teleporter"))
        {
            teleporters.push_back((Teleporter*)(*it));
        }
    }
    if(teleporters.size()>1) {
        Teleporter *teleporter;
        do
        {
            teleporter=teleporters[rand()%teleporters.size()];
        } while(teleporter==this);
        GameScene::getPlayer()->moveTo(teleporter->getPosX(),teleporter->getPosY(),teleporter->getPosZ(),true);
        map->move(0,0);
    }
}

void Teleporter::onMove()
{
}

bool Teleporter::canSave()
{
    return true;
}

Json::Value Teleporter::saveToJson()
{
    Json::Value config;
    config["x"] = getPosX();
    config["y"] = getPosY();
    config["z"] = getPosZ();
    config["enabled"] = enabled;
    return config;
}

void Teleporter::loadFromJson(Json::Value config)
{
    if (config.isArray()) {
        this->moveTo(config[(unsigned int)0].asInt(), config[(unsigned int)1].asInt(),
                     config[(unsigned int)2].asInt(), true);
        return;
    }
    int x = config["x"].asInt();
    int y = config["y"].asInt();
    int z = config["z"].asInt();
    enabled = config["enabled"].asBool();
    this->moveTo(x, y, z, true);
}

void Teleporter::loadFromProps(Tmx::PropertySet set)
{
    enabled=(set.GetLiteralProperty("enabled").compare("true")==0);
}

void Cave::loadFromProps(Tmx::PropertySet set)
{
    if (set.HasProperty("enabled")) {
        enabled = set.GetLiteralProperty("enabled").compare("true") == 0;
    }
    if (set.HasProperty("monster")) {
        monster = set.GetLiteralProperty("monster");
    }
    if (set.HasProperty("chance")) {
        chance = set.GetNumericProperty("chance");
    }
}

Json::Value Cave::saveToJson()
{
    return Building::saveToJson();
}
