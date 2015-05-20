#include "CConfigHandler.h"
#include "CUtil.h"
#include "provider/CProvider.h"

CConfigHandler::CConfigHandler ( std::set<QString> paths, CConfigHandler *parent ) :parent ( parent ) {
    for ( QString path:paths ) {
        QJsonObject config=CConfigurationProvider::getConfig ( path ).toObject();
        for ( auto it=config.begin(); it!=config.end(); it++ ) {
            objectConfig[it.key()]=it.value();
        }
    }
}

QJsonObject CConfigHandler::getConfig ( QString type ) {
    QJsonObject config=objectConfig[type].toObject();
    if ( config.isEmpty() &&parent ) {
        return parent->getConfig ( type );
    }
    return config;
}

std::set<QString> CConfigHandler::getAllTypes() {
    return convert<std::set<QString>> ( objectConfig.keys() );
}

bool CConfigHandler::isFlagSet ( QString type, QString property ) {
    return getConfig ( type ) [property].toBool();
}
