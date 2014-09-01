#include "lootprovider.h"
#include "CReflection.h"
#include "CConfigurationProvider.h"
#include <src/util.h>

std::set<Item *> *LootProvider::getLoot ( int value ) {
	return calculateLoot ( value );
}

LootProvider::LootProvider ( Map *map ) {
	this->map=map;
	Json::Value config = *CConfigurationProvider::getConfig ( "config/object.json" );
	Json::Value::iterator it = config.begin();
	for ( ; it != config.end(); it++ ) {
		if ( CReflection::getInstance()->checkInheritance ( "Item", ( *it ).get ( "class", "" ).asCString() ) ) {
			this->insert ( std::pair<std::string, int> ( it.memberName(),
			               ( *it ).get ( "power", 1 ).asInt() ) );
		}
	}
}

LootProvider::~LootProvider() { erase ( begin(), end() ); }

std::set<Item *> *LootProvider::calculateLoot ( int value ) {
	std::set<Item *> *loot = new std::set<Item *>();
	while ( value ) {
		int dice = rand() % this->size();
		LootProvider::iterator it = begin();
		for ( int i = 0; i < dice; i++, it++ )
			;
		int power = ( *it ).second;
		std::string name = ( *it ).first;
		if ( power <= value ) {
			loot->insert ( map->createMapObject<Item*> ( QString::fromStdString ( name ) ) );
			value -= power;
		}
	}
	return loot;
}
