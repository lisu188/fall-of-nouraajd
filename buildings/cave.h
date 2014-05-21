#ifndef CAVE_H
#define CAVE_H
#include "building.h"

class Cave: public Building {
		Q_OBJECT
	public:
		Cave();
		Cave(const Cave& cave);
		virtual void onEnter();
		virtual void onMove();
		bool canSave();
		void loadFromJson(Json::Value config);

	private:
		bool enabled;
};
Q_DECLARE_METATYPE(Cave)

#endif // CAVE_H
