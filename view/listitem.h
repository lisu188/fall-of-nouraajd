#ifndef LISTITEM_H
#define LISTITEM_H

#include <map/map.h>

class ListItem: public MapObject {
	public:
		ListItem(int x = 0, int y = 0, int z = 0, int v = 0);
		void setNumber(int i, int x);
		virtual bool compare(ListItem *item);
	protected:
		std::string tooltip;
		virtual void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
		virtual void hoverLeaveEvent(QGraphicsSceneHoverEvent *event);
		QGraphicsSimpleTextItem statsView;
};

class Comparer {
	public:
		bool operator()(ListItem *first, ListItem *second) {
			if (!first) {
				return false;
			}
			if (!second) {
				return true;
			}
			return first->compare(second);
		}
};

#endif // LISTITEM_H