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
#include "view/playerlistview.h"
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
#include <cmath>

Player *GameScene::player = 0;
GameScene *GameScene::game = 0;

void GameScene::startGame() {
    srand(time(0));
    game = this;
    map = new Map(this);
    map->setTileSize(ConfigurationProvider::getConfig("save/game.sav")->get("gameSize", 50).asInt());
    map->loadFromJson(*ConfigurationProvider::getConfig("save/game.sav"));
    if (!player) {
        delete map;
        map = new Map(this);
        map->setTileSize(50);
        map->loadFromJson(*ConfigurationProvider::getConfig("config/map.json"));
        player = new Player("Sorcerer");
        map->addObject(player);
    }
    player->updateViews();
    map->ensureSize(player);
    stepTimer.stop();
    stepTimer.setDirx(0);
    stepTimer.setDiry(0);
    stepTimer.setInterval(getStep() * 2);
    connect(&stepTimer, SIGNAL(timeout()), this, SLOT(clickMove()), Qt::UniqueConnection);
}

GameScene::~GameScene() {
    FILE *infile = fopen("save/game.sav", "w+");
    fclose(infile);
    std::fstream jsonFileStream;
    Json::FastWriter writer;
    jsonFileStream.open("save/game.sav");
    jsonFileStream << writer.write(map->saveToJson());
    jsonFileStream.close();
    delete map;
    Destroyer::terminate();
}

Player *GameScene::getPlayer() { return player; }

void GameScene::setPlayer(Player *pla) { player = pla; }

GameScene *GameScene::getGame() { return game; }

void GameScene::addObject(MapObject *mapObject) { map->addObject(mapObject); }

void GameScene::keyPressEvent(QKeyEvent *keyEvent) {
    if (keyEvent) {
        keyEvent->setAccepted(false);
        switch (keyEvent->key()) {
        case Qt::Key_Up:
            playerMove(0, -1);
            keyEvent->setAccepted(true);
            break;
        case Qt::Key_Down:
            playerMove(0, 1);
            keyEvent->setAccepted(true);
            break;
        case Qt::Key_Left:
            playerMove(-1, 0);
            keyEvent->setAccepted(true);
            break;
        case Qt::Key_Right:
            playerMove(1, 0);
            keyEvent->setAccepted(true);
            break;
        }
    }
}

void GameScene::playerMove(int dirx, int diry) {
    unsigned int curClick = (unsigned int)QDateTime::currentMSecsSinceEpoch();
    if (curClick - click <= (getStep() * 1.5)) {
        return;
    }
    click = QDateTime::currentMSecsSinceEpoch();
    if (player->getFightList()->size() > 0) {
        return;
    }
    int sizex, sizey;
    if (getView()) {
        sizex = getView()->width() / map->getTileSize() + 1;
        sizey = getView()->height() / map->getTileSize() + 1;
    } else {
        sizex = QApplication::desktop()->width() / map->getTileSize() + 1;
        sizey = QApplication::desktop()->height() / map->getTileSize() + 1;
    }
    map->move(dirx, diry);
    if (!player->isAlive()) {
        getView()->close();
    }
}

GameView *GameScene::getView() {
    if (!GameScene::getGame() || !GameScene::getGame()->views().size()) {
        return 0;
    }
    return dynamic_cast<GameView *>((*GameScene::getGame()->views().begin()));
}

int GameScene::StepTimer::getDirx() const { return dirx; }
void GameScene::StepTimer::setDirx(int value) { dirx = value; }
int GameScene::StepTimer::getDiry() const { return diry; }
void GameScene::StepTimer::setDiry(int value) { diry = value; }

void GameScene::adjustStepTimer(QGraphicsSceneMouseEvent *event) {
    if (!event || !player || !map)
        return;
    const int size = map->getTileSize();
    const qreal dx = event->scenePos().x() - (player->getPosX() * size + size / 2.0);
    const qreal dy = event->scenePos().y() - (player->getPosY() * size + size / 2.0);
    int dirx = 0, diry = 0;
    if (std::abs(dx) >= size / 2.0 || std::abs(dy) >= size / 2.0) {
        if (std::abs(dx) > std::abs(dy))
            dirx = dx > 0 ? 1 : -1;
        else
            diry = dy > 0 ? 1 : -1;
    }
    stepTimer.setDirx(dirx);
    stepTimer.setDiry(diry);
}

void GameScene::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    QGraphicsScene::mousePressEvent(event);
    if (!event || event->button() != Qt::LeftButton || event->isAccepted() || !player || !map)
        return;
    adjustStepTimer(event);
    clickMove();
    if (stepTimer.getDirx() || stepTimer.getDiry())
        stepTimer.start();
    event->accept();
}

void GameScene::mouseMoveEvent(QGraphicsSceneMouseEvent *event) {
    if (event && stepTimer.isActive() && (event->buttons() & Qt::LeftButton)) {
        adjustStepTimer(event);
        event->accept();
        return;
    }
    QGraphicsScene::mouseMoveEvent(event);
}

void GameScene::mouseReleaseEvent(QGraphicsSceneMouseEvent *event) {
    if (event && event->button() == Qt::LeftButton)
        stepTimer.stop();
    QGraphicsScene::mouseReleaseEvent(event);
}

void GameScene::clickMove() {
    if (!player || !map || !player->isAlive() || (!stepTimer.getDirx() && !stepTimer.getDiry())) {
        stepTimer.stop();
        return;
    }
    playerMove(stepTimer.getDirx(), stepTimer.getDiry());
}
