#include "CHandler.h"
#include "core/CGame.h"

CObjectHandler::CObjectHandler ( std::shared_ptr<CObjectHandler> parent ) : parent ( parent ) {

}

void CObjectHandler::registerConfig ( std::string path ) {
    std::shared_ptr<QJsonObject> config = CConfigurationProvider::getConfig ( path );
    for ( auto it = config->begin(); it != config->end(); it++ ) {
        objectConfig[it.key()] = std::make_shared<QJsonObject> ( it.value().toObject() );
    }
}

std::shared_ptr<QJsonObject> CObjectHandler::getConfig ( std::string type ) {
    if ( vstd::ctn ( objectConfig, type ) ) {
        return objectConfig[type];
    } else if ( parent.lock() ) {
        return parent.lock()->getConfig ( type );
    }
    return std::make_shared<QJsonObject>();
}

std::set<std::string> CObjectHandler::getAllTypes() {
    std::set<std::string> types;
    for ( std::string val:objectConfig | boost::adaptors::map_keys ) {
        types.insert ( val );
    }
    if ( parent.lock() ) {
        for ( std::string val:parent.lock()->getAllTypes() ) {
            types.insert ( val );
        }
    }
    return types;
}

std::shared_ptr<CGameObject> CObjectHandler::getType ( std::string name ) {
    if ( vstd::ctn ( constructors, name ) ) {
        return constructors[name]();
    } else if ( parent.lock() ) {
        return parent.lock()->getType ( name );
    }
    return std::shared_ptr<CGameObject>();
}

void CObjectHandler::registerType ( std::string name, std::function<std::shared_ptr<CGameObject>() > constructor ) {
    constructors.insert ( std::make_pair ( name, constructor ) );
}

std::shared_ptr<CGameObject> CObjectHandler::_createObject ( std::shared_ptr<CMap> map, std::string type ) {
    std::shared_ptr<QJsonObject> config = getConfig ( type );
    if ( ( *config ).isEmpty() ) {
        ( *config ) ["class"] = type;
    }
    return CSerialization::deserialize<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>> ( map, config );
}

std::shared_ptr<CGameObject> CObjectHandler::_clone ( std::shared_ptr<CGameObject> object ) {
    return CSerialization::deserialize<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>> ( object->getMap(),
            CSerialization::serialize<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>> (
                object ) );
}










