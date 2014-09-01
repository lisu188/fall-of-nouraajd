#pragma once
#include <QGraphicsItem>
#include "CReflection.h"

class Creature;
class GameView;
class PlayerListView;
class PlayerEquippedView;

class GamePanel : public QGraphicsObject {
	Q_OBJECT
public:
	GamePanel();
	GamePanel ( const GamePanel& );
	virtual void showPanel ( GameView *view );
	virtual void setUpPanel ( GameView * view );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget );
};


class CharPanel : public GamePanel {
	Q_OBJECT
public:
	CharPanel();
	CharPanel ( const CharPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel ( GameView *view );
	virtual void setUpPanel ( GameView * view );
private:
	PlayerListView *playerInventoryView;
	PlayerEquippedView *playerEquippedView;
};

class FightPanel : public GamePanel {
	Q_OBJECT
public:
	FightPanel();
	FightPanel ( const FightPanel& );
	static Creature *selected;
	void update();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel ( GameView *view );
	void setUpPanel ( GameView *view );
private:
	PlayerListView *playerSkillsView;

};

