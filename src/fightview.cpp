#include "fightview.h"
#include "gamescene.h"

#include <qpainter.h>
#include <sstream>
#include <QDebug>

Creature *FightView::selected = 0;

FightView::FightView() {
  setZValue(5);
  setVisible(false);
}

void FightView::update() {
  Player *player = dynamic_cast<GameScene*>(this->scene())->getPlayer();
  std::list<Creature *> *creatures = player->getFightList();
  std::list<Creature *>::iterator it;
  int i = 0;
  for (it = creatures->begin(); it != creatures->end(); i++, it++) {
    CreatureFightView *fightView = new CreatureFightView(*it);
    fightView->setParentItem(this);
    fightView->setPos((i % 4) * 100, (i / 4 * 100));
  }
  QGraphicsItem::update();
}

QRectF FightView::boundingRect() const { return QRectF(0, 0, 400, 300); }

void FightView::paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                      QWidget *) {
  painter->fillRect(boundingRect(), QColor("BLACK"));
}

CreatureFightView::CreatureFightView(Creature *creature) {
  this->creature = creature;
  creature->setParentItem(this);
}

QRectF CreatureFightView::boundingRect() const {
  return QRectF(0, 0, 100, 100);
}

void CreatureFightView::paint(QPainter *painter,
                              const QStyleOptionGraphicsItem *option,
                              QWidget *widget) {
  QGraphicsItem *item = *childItems().begin();
  if (childItems().size() == 0) {
    return;
  }
  item->setPos(((boundingRect().width() - item->boundingRect().width()) / 2),
               0);
  painter->fillRect(0, boundingRect().height() - 50, boundingRect().width(), 25,
                    QColor("ORANGE"));
  painter->fillRect(0, boundingRect().height() - 50,
                    boundingRect().width() * creature->getHpRatio() / 100.0, 25,
                    QColor("RED"));
  QTextOption opt(Qt::AlignCenter);
  std::ostringstream hpStream;
  hpStream << creature->getHp();
  hpStream << "/";
  hpStream << creature->getHpMax();
  painter->drawText(
      QRectF(0, boundingRect().height() - 50, boundingRect().width(), 25),
      hpStream.str().c_str(), opt);
  painter->fillRect(0, boundingRect().height() - 25, boundingRect().width(), 25,
                    QColor("CYAN"));
  painter->fillRect(0, boundingRect().height() - 25,
                    boundingRect().width() * creature->getManaRatio() / 100.0,
                    25, QColor("BLUE"));
  std::ostringstream manaStream;
  manaStream << creature->getMana();
  manaStream << "/";
  manaStream << creature->getManaMax();
  painter->drawText(
      QRectF(0, boundingRect().height() - 25, boundingRect().width(), 25),
      manaStream.str().c_str(), opt);
}

void CreatureFightView::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  FightView::selected = creature;
}
