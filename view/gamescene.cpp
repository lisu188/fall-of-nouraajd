#include "gamescene.h"
#include "gameview.h"

#include <QGraphicsView>
#include <QPointF>
#include <items/weapon.h>
#include <items/armor.h>
#include <creatures/monster.h>
#include <buildings/cave.h>
#include <buildings/dungeon.h>
#include <QApplication>
#include <QDesktopWidget>
#include "view\playerlistview.h"
#include <animation/animationprovider.h>
#include <configuration/configurationprovider.h>
#include <destroyer/destroyer.h>
#include <view/fightview.h>
#include <fstream>
#include <json/json.h>
#include <compression/compression.h>
#include <QDateTime>
#include <QDebug>
#include <vector>


Player *GameScene::player=0;
GameScene *GameScene::game=0;

void GameScene::startGame()
{
    srand(time(0));
    game=this;
    map=new Map(this);
    map->setTileSize(50);
    map->loadFromJson(*ConfigurationProvider::getConfig("save/game.sav"));
    if(!player)
    {
        delete map;
        map=new Map(this);
        map->setTileSize(50);
        map->loadFromJson(*ConfigurationProvider::getConfig("config/map.json"));
        player=new Player("Sorcerer");
        map->addObject(player);
    }
    player->updateViews();
    map->ensureSize(player);
}

GameScene::~GameScene()
{
    FILE *infile = fopen("save/game.sav", "w+");
    fclose(infile);
    std::fstream jsonFileStream;
    Json::FastWriter writer;
    jsonFileStream.open ("save/game.sav");
    jsonFileStream << writer.write(map->saveToJson());
    jsonFileStream.close();
    delete map;
    Destroyer::terminate();
}

Player *GameScene::getPlayer()
{
    return player;
}

void GameScene::setPlayer(Player *pla) {
    player=pla;
}

GameScene *GameScene::getGame()
{
    return game;
}

void GameScene::addObject(MapObject *mapObject)
{
    map->addObject(mapObject);
}

void GameScene::keyPressEvent(QKeyEvent * keyEvent)
{
    if(keyEvent)
    {
        keyEvent->setAccepted(false);
        switch(keyEvent->key())
        {
        case Qt::Key_Up:
            playerMove(0,-1);
            keyEvent->setAccepted(true);
            break;
        case Qt::Key_Down:
            playerMove(0,1);
            keyEvent->setAccepted(true);
            break;
        case Qt::Key_Left:
            playerMove(-1,0);
            keyEvent->setAccepted(true);
            break;
        case Qt::Key_Right:
            playerMove(1,0);
            keyEvent->setAccepted(true);
            break;
        }
    }
}

void GameScene::playerMove(int dirx,int diry)
{
    unsigned int curClick=(unsigned int)QDateTime::currentMSecsSinceEpoch();
    if(curClick-click<=(getStep()*1.5))
    {
        return;
    }
    click=QDateTime::currentMSecsSinceEpoch();
    if(player->getFightList()->size()>0) {
        return;
    }
    int sizex,sizey;
    if(getView())
    {
        sizex=getView()->width()/map->getTileSize()+1;
        sizey=getView()->height()/map->getTileSize()+1;
    } else
    {
        sizex=QApplication::desktop()->width()/map->getTileSize()+1;
        sizey=QApplication::desktop()->height()/map->getTileSize()+1;
    }
    map->move(dirx,diry);
    if(!player->isAlive()) {
        getView()->close();
    }
}

GameView *GameScene::getView()
{
    if(!GameScene::getGame()->views().size()) {
        return 0;
    }
    return dynamic_cast<GameView*>((*GameScene::getGame()->views().begin()));
}
