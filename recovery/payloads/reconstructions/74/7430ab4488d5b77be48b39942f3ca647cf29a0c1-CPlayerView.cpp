#include "CInteraction.h"
#include <algorithm>
#include "CCreature.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CItem.h"
#include "CMap.h"
#include "CPlayerView.h"
#include <QGraphicsSceneDragDropEvent>
#include <QGraphicsSceneMouseEvent>
#include <QPainter>
#include <sstream>

namespace {
CItem *draggedItem(QGraphicsSceneDragDropEvent *event) {
  const CObjectData *data =
      dynamic_cast<const CObjectData *>(event->mimeData());
  return data ? dynamic_cast<CItem *>(data->getSource()) : nullptr;
}
} // namespace

CPlayerListView::CPlayerListView(CGameView *view) : view(view) {
  this->setZValue(3);
  curPosition = 0;
  right = new CScrollObject(this, true);
  left = new CScrollObject(this, false);
  x = 4, y = 4;
  pixmap.load("images/item.png");
  pixmap =
      pixmap.scaled(50, 50, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
  left->setPos(0, y * 50);
  right->setPos((x - 1) * 50, y * 50);
}

void CPlayerListView::update() {
  auto entries = getItems();
  const auto capacity = x * y;
  curPosition = std::min(curPosition, entries.size() > capacity
                                        ? static_cast<unsigned>(entries.size() - capacity) : 0u);
  QList<QGraphicsItem *> list = childItems();
  QList<QGraphicsItem *>::Iterator childIter;
  for (childIter = list.begin(); childIter != list.end(); childIter++) {
    if (*childIter == right || *childIter == left) {
      continue;
    }
    (*childIter)->setParentItem(0);
    (*childIter)->setVisible(false);
  }
  std::set<CMapObject *>::iterator itemIter;
  int i = 0;
  for (itemIter = entries.begin(); itemIter != entries.end(); i++, itemIter++) {
    CMapObject *item = *itemIter;
    if (item->getMap()) { // SigSegv for interaction
      item->setMap(item->getMap()->getScene()->getPlayer()->getMap());
    }
    item->setVisible(false);
    item->setParentItem(0);
    int position = i - curPosition;
    if (position >= 0 && position < x * y) {
      item->setParentItem(this);
      item->setNumber(position, x);
    }
  }
  right->setVisible(entries.size() > x * y);
  left->setVisible(entries.size() > x * y);
}

CMap *CPlayerListView::getMap() { return view->getScene()->getMap(); }

void CPlayerListView::setDraggable() {
  this->setFlag(QGraphicsItem::ItemIsMovable);
}

QRectF CPlayerListView::boundingRect() const {
  return QRect(0, 0, pixmap.size().width() * x,
               pixmap.size().height() * (getItems().size() > x * y ? y + 1 : y));
}

void CPlayerListView::paint(QPainter *painter,
                            const QStyleOptionGraphicsItem *option,
                            QWidget *widget) {
  for (int i = 0; i < x; i++)
    for (int j = 0; j < y; j++) {
      painter->drawPixmap(i * 50, j * 50, pixmap);
    }
}

void CPlayerListView::updatePosition(int i) {
  curPosition = static_cast<unsigned>(std::max(0, static_cast<int>(curPosition) + i));
  update();
}

void CPlayerListView::setXY(int x, int y) {
  this->x = x;
  this->y = y;
}
CPlayerInventoryrView::CPlayerInventoryrView(CGameView *view) : CPlayerListView(view) { update(); }
CPlayerIteractionView::CPlayerIteractionView(CGameView *view) : CPlayerListView(view) { update(); }

std::set<CMapObject *> CPlayerInventoryrView::getItems() const {
  auto *player = view->getScene()->getPlayer();
  if (!player) return {};
  auto *inventory = player->getInventory();
  return {inventory->begin(), inventory->end()};
}

std::set<CMapObject *> CPlayerIteractionView::getItems() const {
  auto *player = view->getScene()->getPlayer();
  if (!player) return {};
  auto *actions = player->getActions();
  return {actions->begin(), actions->end()};
}

void CPlayerListView::dropEvent(QGraphicsSceneDragDropEvent *event) {
  CItem *item = draggedItem(event);
  if (!item) {
    event->ignore();
    return;
  }
  event->acceptProposedAction();
  item->onUse(this->getMap()->getScene()->getPlayer());
}

CPlayerEquippedView::CPlayerEquippedView(CGameView *view) {
  auto *equipped = view->getScene()->getPlayer()->getEquipped();
  for (int i = 0; i < equipped->size(); i++) {
    CItemSlot *slot = new CItemSlot(i, view);
    slot->setParentItem(this);
    slot->setPos(i % 4 * 50, i / 4 * 50);
    itemSlots.push_back(slot);
  }
  update();
}

QRectF CPlayerEquippedView::boundingRect() const {
  return QRectF(0, 0, 4 * 50, 2 * 50);
}

void CPlayerEquippedView::paint(QPainter *painter,
                                const QStyleOptionGraphicsItem *option,
                                QWidget *widget) {}

void CPlayerEquippedView::update() {
  for (std::list<CItemSlot *>::iterator it = itemSlots.begin();
       it != itemSlots.end(); it++) {
    (*it)->update();
  }
  QGraphicsObject::update();
}

PlayerStatsView::PlayerStatsView() {
  this->player = nullptr;
  setFixedSize(250, 75);
}

void PlayerStatsView::paintEvent(QPaintEvent *) {
  if (!player) {
    return;
  }
  QPainter painter;
  painter.begin(this);
  painter.setRenderHint(QPainter::Antialiasing);
  QTextOption opt(Qt::AlignCenter);
  float barx = 250;
  float bary = 25;
  painter.fillRect(0, 0, barx, bary * 3, QColor("GREEN"));
  std::ostringstream hpStream;
  hpStream << player->hp;
  hpStream << "/";
  hpStream << player->hpMax;
  painter.fillRect(0, bary * 0, barx * player->getHpRatio() / 100.0, bary,
                   QColor("RED"));
  painter.drawText(QRectF(0, bary * 0, barx, bary), hpStream.str().c_str(),
                   opt);
  std::ostringstream manaStream;
  manaStream << player->mana;
  manaStream << "/";
  manaStream << player->manaMax;
  painter.fillRect(0, bary * 1, barx * player->getManaRatio() / 100.0, bary,
                   QColor("BLUE"));
  painter.drawText(QRectF(0, bary * 1, barx, bary), manaStream.str().c_str(),
                   opt);
  std::ostringstream expStream;
  expStream << player->exp;
  expStream << "/";
  expStream << (player->level) * (player->level + 1) * 500;
  painter.fillRect(0, bary * 2, barx * player->getExpRatio() / 100.0, bary,
                   QColor("YELLOW"));
  painter.drawText(QRectF(0, bary * 2, barx, bary), expStream.str().c_str(),
                   opt);
  painter.end();
}

void PlayerStatsView::setPlayer(CPlayer *value) {
  player = value;
  connect(player, SIGNAL(statsChanged()), this, SLOT(update()));
}

CScrollObject::CScrollObject(CPlayerListView *stats, bool isRight) {
  this->isRight = isRight;
  this->setZValue(1);
  this->stats = stats;
  int size = 50;
  if (!isRight) {
    this->setAnimation("images/arrows/left");
  } else {
    this->setAnimation("images/arrows/right");
  }
  setParentItem(stats);
}

void PlayerStatsView::update() { QWidget::update(); }

void CScrollObject::setVisible(bool visible) {
  if (visible && this->scene() != stats->scene()) {
    stats->scene()->addItem(this);
  }
  QGraphicsItem::setVisible(visible);
}

void CScrollObject::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  if (isRight) {
    stats->updatePosition(1);
  }
  if (!isRight) {
    stats->updatePosition(-1);
  }
}

#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CGameScene.h"
#include "CMap.h"
#include "CPlayerView.h"
#include "Util.h"
#include <QGraphicsSceneDragDropEvent>
#include <qpainter.h>

CItemSlot::CItemSlot(int number, CGameView *view)
    : number(number), view(view) {
  pixmap.load(":/images/item.png"); // change to slot items path in json
  pixmap =
      pixmap.scaled(50, 50, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
  this->setAcceptDrops(true);
}

QRectF CItemSlot::boundingRect() const { return QRectF(0, 0, 50, 50); }

void CItemSlot::paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                      QWidget *) {
  painter->drawPixmap(0, 0, pixmap);
}

bool CItemSlot::checkType(int slot, CItem *widget) {
  if (widget) {
    QJsonArray config = CConfigurationProvider::getConfig("slots.json")
                            .toObject()[QString::number(slot)]
                            .toObject()["types"]
                            .toArray();
    for (int i = 0; i < config.size(); i++) {
      if (widget->inherits(config[i].toString().toStdString().c_str())) {
        return true;
      }
    }
  }
  return false;
}

void CItemSlot::update() {
  auto *equipped = view->getScene()->getPlayer()->getEquipped();
  auto slot = equipped->find(number);
  CItem *item = slot == equipped->end() ? nullptr : slot->second;
  if (item) {
    item->setParentItem(this);
    item->setPos(0, 0);
    item->setVisible(true);
    item->QGraphicsItem::update();
  }
  QGraphicsObject::update();
}

void CItemSlot::dragMoveEvent(QGraphicsSceneDragDropEvent *event) {
  QGraphicsObject::dragMoveEvent(event);
  event->setAccepted(checkType(number, draggedItem(event)));
}

void CItemSlot::dropEvent(QGraphicsSceneDragDropEvent *event) {
  QGraphicsObject::dropEvent(event);
  if (checkType(number, draggedItem(event))) {
    dynamic_cast<CGameScene *>(this->scene())
        ->getPlayer()
        ->setItem(number, draggedItem(event));
  }
  event->acceptProposedAction();
  event->accept();
}

int CItemSlot::getNumber() { return number; }
