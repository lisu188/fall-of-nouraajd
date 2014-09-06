#include "CLootProvider.h"
#include "CReflection.h"
#include "CConfigurationProvider.h"
#include "Util.h"
#include "CItem.h"
#include "CMap.h"

std::set<CItem *> *CLootProvider::getLoot ( int value ) {
	return calculateLoot ( value );
}

CLootProvider::CLootProvider ( CMap *map ) {
	this->map=map;
	QJsonObject config = CConfigurationProvider::getConfig ( "config/object.json" ).toObject();
	QJsonObject::iterator it = config.begin();
	for ( ; it != config.end(); it++ ) {
		if ( CReflection::getInstance()->checkInheritance ( "CItem", ( *it ).toObject() ["class"].toString() ) ) {
			this->insert ( std::pair<QString, int> ( it.key(),
			               ( *it ).toObject() ["power"].toInt()  ) );
		}
	}
}

CLootProvider::~CLootProvider() { erase ( begin(), end() ); }

std::set<CItem *> *CLootProvider::calculateLoot ( int value ) {
	std::set<CItem *> *loot = new std::set<CItem *>();
	while ( value ) {
		int dice = rand() % this->size();
		CLootProvider::iterator it = begin();
		for ( int i = 0; i < dice; i++, it++ )
			;
		int power = ( *it ).second;
		QString name = ( *it ).first;
		if ( power <= value ) {
			loot->insert ( map->createMapObject<CItem*> (  name )  );
			value -= power;
		}
	}
	return loot;
}
