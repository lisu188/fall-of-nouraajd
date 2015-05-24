#include "provider/CProvider.h"
#include "CUtil.h"
#include "object/CObject.h"
#include "CMap.h"
#include "handler/CHandler.h"

std::set<std::shared_ptr<CItem>> CLootHandler::getLoot ( int value ) const {
    return calculateLoot ( value );
}

CLootHandler::CLootHandler ( std::shared_ptr<CMap> map ) :map ( map ) {
    for ( QString  type : map->getObjectHandler()->getAllTypes() ) {
        std::shared_ptr<CItem> item=map->createObject<CItem> ( type ) ;
        if ( item ) {
            int power=item->getPower() ;
            if ( power>0 ) {
                this->insert ( std::make_pair ( type,power ) );
            }
        }
    }
}

std::set<std::shared_ptr<CItem>> CLootHandler::calculateLoot ( int value ) const {
    std::set<std::shared_ptr<CItem>> loot;
    while ( value>0 ) {
        int dice = rand() % this->size();
        auto it = begin();
        for ( int i = 0; i < dice; i++, it++ );
        int power = ( *it ).second;
        QString name = ( *it ).first;
        if ( power <= value ) {
            std::shared_ptr<CItem> item=map.lock()->createObject<CItem> (  name );
            loot.insert ( item );
            value -= power;
        }
    }
    return loot;
}
