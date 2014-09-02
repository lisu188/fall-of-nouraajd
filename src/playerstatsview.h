#pragma once
#include <QGraphicsItem>
#include "CCreature.h"

class PlayerStatsView : public QWidget {
	Q_OBJECT
public:
	explicit PlayerStatsView();
	void setPlayer ( Player *value );

protected:
	void paintEvent ( QPaintEvent * );

private:
	Player *player = 0;
};
