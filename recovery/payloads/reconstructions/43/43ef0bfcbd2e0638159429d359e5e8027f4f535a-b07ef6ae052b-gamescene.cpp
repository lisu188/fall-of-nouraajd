#include "gamescene.h"
#include "gameview.h"
#include "pathfinder.h"

#include <QGraphicsView>
#include <QPointF>
#include <src/monster.h>
#include <QApplication>
#include <QDesktopWidget>
#include <src/playerlistview.h>
#include <src/animationprovider.h>
#include <src/configurationprovider.h>
#include <src/destroyer.h>
#include <src/fightview.h>
#include <fstream>
#include <lib/json/json.h>
#include <QDateTime>
#include <QDebug>
#include <vector>
#include <QThreadPool>


Player *GameScene::player = 0;
GameScene *GameScene::game = 0;
Map *GameScene::map = 0;

void GameScene::startGame()
{
    srand(time(0));
    game = this;
    stepTimer.setDirx(0); stepTimer.setDiry(0); stepTimer.setInterval(getStep());
    connect(&stepTimer, SIGNAL(timeout()), this, SLOT(clickMove()));
    map = new Map(this);
    Tmx::Map tmxMap;
    QFile file(":/config/map.tmx");
    file.open(QIODevice::ReadOnly);
    QByteArray data = file.readAll();
    std::string dataString = data.data();
    tmxMap.ParseText(dataString);
    map->loadMapFromTmx(tmxMap);
    file.close();
    player = new Player("Sorcerer");
    map->addObject(player);
    player->moveTo(map->getEntryX(), map->getEntryY(), map->getEntryZ(), true);
    player->updateViews();
    map->ensureSize(player);
}


Player *GameScene::getPlayer()
{
    return player;
}

void GameScene::setPlayer(Player *pla)
{
    player = pla;
}

GameScene *GameScene::getGame()
{
    return game;
}

void GameScene::keyPressEvent(QKeyEvent * keyEvent)
{
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
        case Qt::Key_C:
            getView()->showCharView();
            keyEvent->setAccepted(true);
            break;
        }
    }
}


void GameScene::playerMove(int dirx, int diry)
{
    if (player->getFightList()->size() > 0 || getView()->getCharView()->isVisible()) {
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
}

GameView *GameScene::getView()
{
    if (!GameScene::getGame() || !GameScene::getGame()->views().size()) {
        return 0;
    }
    return dynamic_cast<GameView*>((*GameScene::getGame()->views().begin()));
}

unsigned int GameScene::getStep()
{
    return 250;
}

Map *GameScene::getMap()
{
    return map;
}

int GameScene::StepTimer::getDirx() const { return dirx; }
void GameScene::StepTimer::setDirx(int value) { dirx = value; }
int GameScene::StepTimer::getDiry() const { return diry; }
void GameScene::StepTimer::setDiry(int value) { diry = value; }
void GameScene::adjustStepTimer(QGraphicsSceneMouseEvent *event) {
    if (!player) return;
    QPointF delta = event->scenePos() - player->QGraphicsItem::pos();
    stepTimer.setDirx(qAbs(delta.x()) >= qAbs(delta.y()) ? (delta.x() > 0 ? 1 : -1) : 0);
    stepTimer.setDiry(qAbs(delta.y()) > qAbs(delta.x()) ? (delta.y() > 0 ? 1 : -1) : 0);
}
void GameScene::clickMove() { playerMove(stepTimer.getDirx(), stepTimer.getDiry()); }
void GameScene::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    QGraphicsScene::mousePressEvent(event);
    if (!event->isAccepted() && event->button() == Qt::LeftButton) {
        adjustStepTimer(event);
        clickMove();
        stepTimer.start();
        event->accept();
    }
}
void GameScene::mouseMoveEvent(QGraphicsSceneMouseEvent *event) {
    QGraphicsScene::mouseMoveEvent(event);
    if (stepTimer.isActive()) adjustStepTimer(event);
}
void GameScene::mouseReleaseEvent(QGraphicsSceneMouseEvent *event) {
    stepTimer.stop();
    QGraphicsScene::mouseReleaseEvent(event);
}
