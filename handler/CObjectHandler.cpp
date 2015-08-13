#include "CHandler.h"
#include "provider/CProvider.h"
#include "CMap.h"
#include "CGame.h"
#include "CSerialization.h"

CObjectHandler::CObjectHandler ( std::shared_ptr<CObjectHandler> parent ) :parent ( parent ) {

}

void CObjectHandler::registerConfig ( QString path ) {
    std::shared_ptr<QJsonObject> config=CConfigurationProvider::getConfig ( path );
    for ( auto it=config->begin(); it!=config->end(); it++ ) {
        objectConfig[it.key()]=std::make_shared<QJsonObject> ( it.value().toObject() );
    }
}

std::shared_ptr<QJsonObject> CObjectHandler::getConfig ( QString type ) {
    if ( vstd::ctn ( objectConfig,type ) ) {
        return objectConfig[type];
    } else if ( parent.lock() ) {
        return parent.lock()->getConfig ( type );
    }
    return std::make_shared<QJsonObject>();
}

std::set<QString> CObjectHandler::getAllTypes() {
    std::set<QString> types;
    for ( QString val:objectConfig | boost::adaptors::map_keys ) {
        types.insert ( val );
    }
    if ( parent.lock() ) {
        for ( QString val:parent.lock()->getAllTypes() ) {
            types.insert ( val );
        }
    }
    return types;
}

std::shared_ptr<CGameObject> CObjectHandler::getType ( QString name ) {
    if ( vstd::ctn ( constructors,name ) ) {
        return constructors[name]() ;
    } else if ( parent.lock() ) {
        return parent.lock()->getType ( name );
    }
    return std::shared_ptr<CGameObject>();
}

void CObjectHandler::registerType ( QString name,std::function<std::shared_ptr<CGameObject>() > constructor ) {
    constructors.insert ( std::make_pair ( name,constructor ) );
}

std::shared_ptr<CGameObject> CObjectHandler::_createObject ( std::shared_ptr<CMap> map, QString type ) {
    std::shared_ptr<QJsonObject> config=getConfig ( type );
    if ( ( *config ).isEmpty() ) {
        ( *config ) ["class"]=type;
    }
    return CSerialization::deserialize<std::shared_ptr<QJsonObject>,std::shared_ptr<CGameObject>> ( map,config );
}

std::shared_ptr<CGameObject> CObjectHandler::_clone ( std::shared_ptr<CGameObject> object ) {
    return CSerialization::deserialize<std::shared_ptr<QJsonObject>,std::shared_ptr<CGameObject>> ( object->getMap(),
            CSerialization::serialize<std::shared_ptr<QJsonObject>,std::shared_ptr<CGameObject>> ( object ) ) ;
}










