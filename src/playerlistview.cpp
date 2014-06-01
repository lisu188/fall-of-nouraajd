#include "gamescene.h"
#include "playerlistview.h"

#include <qpainter.h>
#include <QWidget>
#include <QDrag>
#include <QMimeData>

PlayerListView::PlayerListView(std::set<ListItem *, Comparer> *listItems)
    : items(listItems) {
  this->setZValue(3);
  curPosition = 0;
  right = new ScrollObject(this, true);
  left = new ScrollObject(this, false);
  x = 4, y = 4;
  pixmap.load(":/images/item.png");
  pixmap = pixmap.scaled(Map::getTileSize(), Map::getTileSize(),
                         Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
  left->setPos(0, y * Map::getTileSize());
  right->setPos((x - 1) * Map::getTileSize(), y * Map::getTileSize());
  update();
}

void PlayerListView::update() {
  if (curPosition < 0) {
    curPosition = 0;
  }
  if (items->size() - x * y < curPosition) {
    curPosition = items->size() - x * y;
  }
  QList<QGraphicsItem *> list = childItems();
  QList<QGraphicsItem *>::Iterator childIter;
  for (childIter = list.begin(); childIter != list.end(); childIter++) {
    if (*childIter == right || *childIter == left) {
      continue;
    }
    (*childIter)->setParentItem(0);
    (*childIter)->setVisible(false);
  }
  std::set<ListItem *, Comparer>::iterator itemIter;
  int i = 0;
  for (itemIter = items->begin(); itemIter != items->end(); i++, itemIter++) {
    ListItem *item = *itemIter;
    if (GameScene::getPlayer() &&
        item->getMap() != GameScene::getPlayer()->getMap()) {
      item->setMap(GameScene::getPlayer()->getMap());
    }
    item->setVisible(false);
    item->setParentItem(0);
    int position = i - curPosition;
    if (position >= 0 && position < x * y) {
      item->setParentItem(this);
      item->setNumber(position, x);
    }
  }
  right->setVisible(items->size() > x * y);
  left->setVisible(items->size() > x * y);
}

Map *PlayerListView::getMap() {
  if (items->size()) {
    return (*items->begin())->getMap();
  }
  return 0;
}

void PlayerListView::setDraggable() {
  this->setFlag(QGraphicsItem::ItemIsMovable);
}

QRectF PlayerListView::boundingRect() const {
  return QRect(0, 0, pixmap.size().width() * x,
               pixmap.size().height() * (items->size() > x * y ? y + 1 : y));
}

void PlayerListView::paint(QPainter *painter,
                           const QStyleOptionGraphicsItem *option,
                           QWidget *widget) {
  for (int i = 0; i < x; i++)
    for (int j = 0; j < y; j++) {
      painter->drawPixmap(i * Map::getTileSize(), j * Map::getTileSize(),
                          pixmap);
    }
}

void PlayerListView::updatePosition(int i) {
  curPosition += i;
  update();
}

void PlayerListView::setXY(int x, int y) {
  this->x = x;
  this->y = y;
}
std::set<ListItem *, Comparer> *PlayerListView::getItems() const {
  return items;
}

void PlayerListView::setItems(std::set<ListItem *, Comparer> *value) {
  items = value;
  curPosition = 0;
  update();
}

void PlayerListView::dropEvent(QGraphicsSceneDragDropEvent *event) {
  Item *item = (Item *)(event->source());
  event->acceptProposedAction();
  item->onUse(GameScene::getPlayer());
}
