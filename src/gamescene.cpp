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

void GameScene::startGame(std::string file) {
  srand(time(0));
  map = new Map(this,file);
  player = new Player("Sorcerer");
  map->addObject(player);
  player->moveTo(map->getEntryX(), map->getEntryY(), map->getEntryZ(), true);
  player->updateViews();
  QTimer *timer = new QTimer();
  timer->setInterval(0);
  timer->setSingleShot(true);
  for (int i = -10; i < map->getCurrentXBound() + 10; i++)
    for (int j = -10; j < map->getCurrentYBound() + 10; j++) {
          map->ensureTile(i,j);
      }
  connect(timer, &QTimer::timeout, map,&Map::ensureSize);
  connect(timer, SIGNAL(timeout()), timer, SLOT(deleteLater()));
  timer->start();
}

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
    case Qt::Key_C:
      getView()->showCharView();
      keyEvent->setAccepted(true);
      break;
    }
  }
}

void GameScene::playerMove(int dirx, int diry) {
  if (!CompletionListener::getInstance()->isCompleted()) {
    return;
  }
  if (player->getFightList()->size() > 0 ||
      getView()->getCharView()->isVisible()) {
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

void GameScene::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  QGraphicsScene::mousePressEvent(event);
}

void GameScene::mouseMoveEvent(QGraphicsSceneMouseEvent *event) {
  QGraphicsScene::mouseMoveEvent(event);
}

void GameScene::mouseReleaseEvent(QGraphicsSceneMouseEvent *event) {
  QGraphicsScene::mouseReleaseEvent(event);
}
Map *GameScene::getMap() const
{
    return map;
}

void GameScene::setMap(Map *value)
{
    map = value;
}

GameView *GameScene::getView(){
    return dynamic_cast<GameView*>(this->views()[0]);
}

Player *GameScene::getPlayer() const
{
    return player;
}

void GameScene::setPlayer(Player *value)
{
    player = value;
}

