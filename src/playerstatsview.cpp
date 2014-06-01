#include "playerstatsview.h"

#include <src/gamescene.h>
#include <qpainter.h>
#include <sstream>
#include <src/building.h>

PlayerStatsView::PlayerStatsView() {
  this->player = player;
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

void PlayerStatsView::setPlayer(Player *value) {
  player = value;
  connect(player, SIGNAL(statsChanged()), this, SLOT(update()));
}
