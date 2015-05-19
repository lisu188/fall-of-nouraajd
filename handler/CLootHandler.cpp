#include "provider/CProvider.h"
#include "CUtil.h"
#include "object/CObject.h"
#include "CMap.h"
#include "handler/CHandler.h"

std::set<CItem *> CLootHandler::getLoot ( int value ) const {
    return calculateLoot ( value );
}

CLootHandler::CLootHandler ( CMap *map ) :map(map) {
    for ( QString  type : map->getConfigHandler()->getAllTypes()) {
        CItem *item=map->getObjectHandler()->createObject<CItem*> ( type ) ;
        if ( item ) {
            int power=item->getPower() ;
            if ( power>0 ) {
                this->insert ( std::make_pair ( type,power ) );
            }
            delete item;
        }
    }
}

CLootHandler::~CLootHandler() {
    erase ( begin(), end() );
}

std::set<CItem *> CLootHandler::calculateLoot ( int value ) const {
    std::set<CItem *> loot;
    while ( value ) {
        int dice = rand() % this->size();
        auto it = begin();
        for ( int i = 0; i < dice; i++, it++ );
        int power = ( *it ).second;
        QString name = ( *it ).first;
        if ( power <= value ) {
            CItem *item=map->getObjectHandler()->createObject<CItem*> (  name );
            loot.insert ( item );
            value -= power;
        }
    }
    return loot;
}
