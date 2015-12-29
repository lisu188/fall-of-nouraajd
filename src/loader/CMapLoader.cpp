#include "loader/CLoader.h"

void CMapLoader::loadFromTmx ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> mapc ) {
    const QJsonObject &mapProperties = ( *mapc ) ["properties"].toObject();
    const QJsonArray &mapLayers = ( *mapc ) ["layers"].toArray();
    map->entryx = mapProperties["x"].toString().toInt();
    map->entryy = mapProperties["y"].toString().toInt();
    map->entryz = mapProperties["z"].toString().toInt();
    const QJsonObject &tileset = ( *mapc ) ["tilesets"].toArray() [0].toObject() ["tileproperties"].toObject();
    for ( auto it = mapLayers.begin(); it != mapLayers.end(); it++ ) {
        const QJsonObject &layer = ( *it ).toObject();
        if ( layer["type"].toString() == "tilelayer" ) {
            handleTileLayer ( map, tileset, layer );
        }
    }
    for ( auto it = mapLayers.begin(); it != mapLayers.end(); it++ ) {
        const QJsonObject &layer = ( *it ).toObject();
        if ( layer["type"].toString() == "objectgroup" ) {
            handleObjectLayer ( map, layer );
        }
    }
}

std::shared_ptr<CMap> CMapLoader::loadNewMap ( std::shared_ptr<CGame> game, QString name ) {
    std::shared_ptr<CMap> map = std::make_shared<CMap> ( game );
    QString path = "maps/" + name;
    map->getObjectHandler()->registerConfig ( path + "/config.json" );
    map->getGame()->getScriptHandler()->addModule ( name, path + "/script.py" );
    map->getGame()->getScriptHandler()->callFunction ( name + ".load", map );
    std::shared_ptr<QJsonObject> mapc = CConfigurationProvider::getConfig ( path + "/map.json" );
    loadFromTmx ( map, mapc );
    return map;
}

//std::shared_ptr<CMap> CMapLoader::loadSavedMap ( std::shared_ptr<CGame> game,QString name ) {
//  std::shared_ptr<CMap> map=std::make_shared<CMap> ( game );
//  QString path="save/"+name+".sav";
//  map->getObjectHandler()->registerConfig ( path+"/config.json" );
//  map->getGame()->getScriptHandler()->addModule ( name,path+"/script.py" );
//  map->getGame()->getScriptHandler()->callFunction ( name+".load",map );
//  std::shared_ptr<QJsonObject> mapc=CConfigurationProvider::getConfig ( path+"/map.json" );
//  loadFromTmx ( map, mapc );
//  return map;
//}

std::shared_ptr<CMap> CMapLoader::loadNewMap ( std::shared_ptr<CGame> game, QString name, QString player ) {
    std::shared_ptr<CMap> map = loadNewMap ( game, name );
    map->setPlayer ( map->createObject<CPlayer> ( player ) );
    return map;
}

void CMapLoader::saveMap ( std::shared_ptr<CMap> map, QString file ) {
    std::shared_ptr<QJsonObject> data = std::make_shared<QJsonObject>();

    std::shared_ptr<QJsonObject> objects = std::make_shared<QJsonObject>();
    std::shared_ptr<QJsonObject> tiles = std::make_shared<QJsonObject>();
    std::shared_ptr<QJsonObject> triggers = std::make_shared<QJsonObject>();

    map->forObjects ( [objects] ( std::shared_ptr<CMapObject> object ) {
        ( *objects ) [object->objectName()] = * ( CSerialization::serialize<std::shared_ptr<QJsonObject >> ( object ) );
    } );

    map->forTiles ( [tiles] ( std::shared_ptr<CTile> tile ) {
        ( *tiles ) [tile->objectName()] = * ( CSerialization::serialize<std::shared_ptr<QJsonObject >> ( tile ) );
    } );

    ( *data ) ["objects"] = *objects;
    ( *data ) ["tiles"] = *tiles;
    ( *data ) ["triggers"] = *triggers;

    CResourcesProvider::getInstance()->saveZip ( "save/" + file, data );
}

void CMapLoader::handleTileLayer ( std::shared_ptr<CMap> map, const QJsonObject &tileset, const QJsonObject &layer ) {
    const QJsonObject &layerProperties = layer["properties"].toObject();
    int level = layerProperties["level"].toString().toInt();
    map->defaultTiles[level] = layerProperties["default"].toString();
    map->boundaries[level] =
        std::make_pair ( layerProperties["xBound"].toString().toInt(),
                         layerProperties["yBound"].toString().toInt() );

    int yLayer = layer["width"].toInt();
    int xLayer = layer["height"].toInt();

    for ( int y = 0; y < yLayer; ++y ) {
        for ( int x = 0; x < xLayer; ++x ) {
            int id = layer["data"].toArray() [x + y * xLayer].toInt();
            if ( id == 0 ) {
                continue;
            }
            id--;
            QString tileId = QString::number ( id );
            QString tileType = tileset[tileId].toObject() ["type"].toString();
            map->addTile ( map->createObject<CTile> ( tileType ), x,
                           y, level );
        }
    }
}

void CMapLoader::handleObjectLayer ( std::shared_ptr<CMap> map, const QJsonObject &layer ) {
    int level = layer["properties"].toObject() ["level"].toString().toInt();
    const QJsonArray &objects = layer["objects"].toArray();
    for ( auto it = objects.begin(); it != objects.end(); it++ ) {
        const QJsonObject &object = ( *it ).toObject();
        QString objectType = object["type"].toString();
        QString objectName = object["name"].toString();

        int xPos = object["x"].toInt() / object["width"].toInt();
        int yPos = object["y"].toInt() / object["height"].toInt();
        auto mapObject = map->createObject<CMapObject> ( objectType );
        if ( mapObject == nullptr ) {
            qDebug() << "Failed to load object:" << objectType
                     << objectName << "\n";
            continue;
        }
        if ( objectName != "" ) {
            mapObject->setObjectName ( objectName );
        }
        map->addObject ( mapObject );
        const QJsonObject &objectProperties = object["properties"].toObject();
        for ( auto it = objectProperties.begin(); it != objectProperties.end(); it++ ) {
            CSerialization::setProperty ( mapObject, it.key(), it.value() );
        }
        mapObject->moveTo ( xPos,
                            yPos, level );
        qDebug() << "Loaded object:" << objectType
                 << objectName << "\n";
    }
}
