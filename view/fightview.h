#include <QGraphicsItem>

#ifndef FIGHTVIEW_H
#define FIGHTVIEW_H
class CreatureFightView;
class Creature;

class FightView: public QGraphicsItem {
	public:
		FightView();
		static Creature *selected;
		void update();
		virtual QRectF boundingRect() const;
		virtual void paint(QPainter *painter,
				const QStyleOptionGraphicsItem *option, QWidget *widget);
};

class CreatureFightView: public QGraphicsItem {
	private:
		Creature *creature;
	public:
		CreatureFightView(Creature *creature);
		virtual QRectF boundingRect() const;
		virtual void paint(QPainter *painter,
				const QStyleOptionGraphicsItem *option, QWidget *widget);
	protected:
		virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
};

#endif // FIGHTVIEW_H