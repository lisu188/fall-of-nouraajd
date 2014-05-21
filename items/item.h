#include <animation/animatedobject.h>

#include <view/listitem.h>

#include <stats/stats.h>

#ifndef ITEM_H
#define ITEM_H
class Creature;
class Interaction;
class Item: public ListItem {
		Q_OBJECT
	public:
		Item();
		Item(const Item&);
		bool isSingleUse();
		virtual void onEquip(Creature *creature);
		virtual void onUnequip(Creature *creature);
		static Item *getItem(std::string name);
		virtual void onUse(Creature *creature);
		virtual void onEnter();
		virtual void onMove() {
		}
		virtual Json::Value saveToJson();
		virtual bool canSave();
	protected:
		virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
		bool singleUse;
		Stats bonus;
		void loadFromJson(Json::Value config);
		Interaction *interaction;
		int power;
	private:
		int slot = 0;
};
Q_DECLARE_METATYPE(Item)

#endif // ITEM_H