#pragma once
#include "CGlobal.h"
#include "CMap.h"

class CMapLoader {
public:
    static std::shared_ptr<CMap> loadMap ( std::shared_ptr<CGame> game, QString name );
    static std::shared_ptr<CMap> loadMap ( std::shared_ptr<CGame> game, QString name, QString player );
    static void saveMap ( std::shared_ptr<CMap> map,QString file );
private:
    static void handleTileLayer ( std::shared_ptr<CMap> map, const QJsonObject& tileset, const QJsonObject& layer );
    static void handleObjectLayer ( std::shared_ptr<CMap> map,const QJsonObject &layer );
};

