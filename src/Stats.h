#pragma once
#include <QJsonObject>
#include "Util.h"
#include <QObject>

#include "../gen/prop.h"

class Stats : public QObject {
	Q_OBJECT
	_Stats
public:
	Stats();
	Stats ( const Stats &stats );
	void setMain ( QString stat );
	int getMain();

	void addBonus ( Stats stats );
	void removeBonus ( Stats stats );

	const char *getText ( int level );
	void loadFromJson ( QJsonObject config );
	QJsonObject saveToJson();

	PROPERTY_ACCESSOR
private:
	int *main = 0;
	QString mainS;
};

class Damage : public QObject {
	Q_OBJECT
	_Damage
public:
	Damage();
	Damage ( const Damage &dmg );
	PROPERTY_ACCESSOR
};
