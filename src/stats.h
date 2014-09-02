#pragma once
#include <lib/json/json.h>
#include "util.h"
#include <QObject>

#include "../gen/prop.h"

class Stats : public QObject {
	Q_OBJECT
	_Stats
public:
	Stats();
	Stats ( const Stats &stats );
	void setMain ( const char *stat );
	int getMain();

	void addBonus ( Stats stats );
	void removeBonus ( Stats stats );

	const char *getText ( int level );
	void loadFromJson ( Json::Value config );
	Json::Value saveToJson();

	PROPERTY_ACCESSOR
private:
	int *main = 0;
	std::string mainS;
};

class Damage : public QObject {
	Q_OBJECT
	_Damage
public:
	Damage();
	Damage ( const Damage &dmg );
	PROPERTY_ACCESSOR
};
