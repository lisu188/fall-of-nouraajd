#include "gamescene.h"

#include <QGraphicsView>

#include <buildings/cave.h>
#include <creatures/players/mage.h>
#include <destroyer/destroyer.h>
#include <view/gameview.h>

Player *GameScene::player = 0;
GameScene *GameScene::game = 0;

GameScene::GameScene() {
  srand(time(0));
  game = this;
  map = new Map();

  if (!player) {
    player = new Mage(map, 0, 0);
    map->addObject(player);
  }

  map->addRoad(18, -8, 0);
  map->addRiver(16, 6, -5);
  map->addObject(new Cave(map, 5, 2));
  ensureSize(24, 16);
  player->update();
}

GameScene::~GameScene() {
  delete map;
  player = 0;
  game = 0;
  Destroyer::terminate();
}

Player *GameScene::getPlayer() { return player; }

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
    ensureSize(view->width() / Tile::size + 2, view->height() / Tile::size + 2);
    player->update();
    if (player->getFightList()->size() > 0) {
      view->showFightView();
    }
  }
}

void GameScene::ensureSize(int sizex, int sizey) {
  if (!player)
    return;

  const int halfx = sizex / 2;
  const int halfy = sizey / 2;
  for (int x = player->getPosX() - halfx; x <= player->getPosX() + halfx; ++x) {
    for (int y = player->getPosY() - halfy; y <= player->getPosY() + halfy;
         ++y) {
      if (!map->contains(x, y)) {
        addTile(Tile::getRandomTile(x, y));
      }
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

void GameScene::addRandomTile(int x, int y) {
  addTile(Tile::getRandomTile(x, y));
}

void GameScene::addTile(Tile *tile) {
  if (tile)
    map->addTile(tile);
}

void GameScene::addObject(MapObject *mapObject) { map->addObject(mapObject); }
