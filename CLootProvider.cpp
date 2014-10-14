#include "CLootProvider.h"
#include "CReflection.h"
#include "CConfigurationProvider.h"
#include "Util.h"
#include "CItem.h"
#include "CMap.h"
#include "CObjectHandler.h"

std::set<CItem *> *CLootProvider::getLoot ( int value ) const {
	return calculateLoot ( value );
}

CLootProvider::CLootProvider ( CMap *map ) :QObject ( map ) {
	this->map=map;
	const QJsonObject *config = map->getObjectHandler()->getObjectConfig();
	for ( auto  it = config->begin(); it != config->end(); it++ ) {
		CItem *item=map->getObjectHandler()->createMapObject<CItem*> ( it.key() ) ;
		if ( item ) {
			int power=item->getPower() ;
			if ( power>0 ) {
				this->insert ( std::pair<QString, int> ( it.key(),power ) );
			}
			delete item;
		}
	}
}

CLootProvider::~CLootProvider() {
	erase ( begin(), end() );
}

std::set<CItem *> *CLootProvider::calculateLoot ( int value ) const {
	std::set<CItem *> *loot = new std::set<CItem *>();
	while ( value ) {
		int dice = rand() % this->size();
		auto it = begin();
		for ( int i = 0; i < dice; i++, it++ );
		int power = ( *it ).second;
		QString name = ( *it ).first;
		if ( power <= value ) {
			loot->insert ( map->getObjectHandler()->createMapObject<CItem*> (  name )  );
			value -= power;
		}
	}
	return loot;
}
