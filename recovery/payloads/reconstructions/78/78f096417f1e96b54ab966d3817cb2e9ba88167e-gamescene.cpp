#include "gamescene.h"

#include <QGraphicsView>

#include <configuration/configurationprovider.h>

#include <buildings/cave.h>
#include <buildings/dungeon.h>
#include <view/playerstatsview.h>
#include <view/playerlistview.h>
#include <creatures/player.h>
#include <destroyer/destroyer.h>
#include <view/gameview.h>

Player *GameScene::player = 0;
GameScene *GameScene::game = 0;

GameScene::GameScene() {
  srand(time(0));
  game = this;
  map = new Map();

  if (!player) {
    player = new Player("Warrior");
    map->addObject(player);
  }

  map->addRoad(18, -8, 0);
  map->addRiver(16, 6, -5);
  map->addObject(new Cave(5, 2));
  map->ensureSize(player);
}

GameScene::~GameScene() {
  delete map;
  player = 0;
  game = 0;
  Destroyer::terminate();
}

Player *GameScene::getPlayer() { return player; }

void GameScene::setPlayer(Player *pla) { player = pla; }

GameScene *GameScene::getGame() { return game; }

GameView *GameScene::getView() {
  if (!game || game->views().isEmpty())
    return 0;
  return dynamic_cast<GameView *>(game->views().front());
}

void GameScene::playerMove(int dirx, int diry) {
  if (!player)
    return;
  map->move(dirx, diry);

  GameView *view = getView();
  if (view) {
    view->centerOn(player->getPosX() * Tile::size + Tile::size / 2,
                   player->getPosY() * Tile::size + Tile::size / 2);
    map->ensureSize(player);
    player->update();
    if (player->getFightList()->size() > 0) {
      view->showFightView();
    }
  }
}

void GameScene::keyPressEvent(QKeyEvent *keyEvent) {
  if (!keyEvent)
    return;

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
  default:
    QGraphicsScene::keyPressEvent(keyEvent);
    break;
  }
}

void GameScene::addRandomTile(int x, int y) { map->getTile(x, y); }

void GameScene::addTile(Tile *tile) {
  if (tile)
    tile->addToGame();
}

void GameScene::addObject(MapObject *mapObject) { map->addObject(mapObject); }


void GameScene::changeMap() {
  QTimer::singleShot(0, this, [this]() {
  
    if (!player)
      return;
    map->removeObject(player);
    delete map;
    map = new Map();
    map->addObject(player);
    player->moveTo(0, 0, true);
    map->addDungeon(0, 0, 20, 16);
    map->addObject(new Dungeon(3, 3));
    map->ensureSize(player);
    if (getView()) {
      getView()->centerOn(player->getPosX() * Tile::size, player->getPosY() * Tile::size);
      player->update();
    }
  });
}
