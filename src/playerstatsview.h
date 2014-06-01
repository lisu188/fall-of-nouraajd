#ifndef PLAYERSTATSVIEW_H
#define PLAYERSTATSVIEW_H

#include "scrollobject.h"

#include <QGraphicsItem>
#include <src/player.h>

class PlayerStatsView : public QWidget {
  Q_OBJECT
public:
  explicit PlayerStatsView();
  void setPlayer(Player *value);

protected:
  void paintEvent(QPaintEvent *);

private:
  Player *player = 0;
};

#endif // PLAYERSTATSVIEW_H
