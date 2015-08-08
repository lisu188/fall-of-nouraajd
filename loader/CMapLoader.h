#pragma once
#include "CGlobal.h"
#include "CMap.h"

class CMapLoader {
public:
    static std::shared_ptr<CMap> loadNewMap ( std::shared_ptr<CGame> game, QString name );
    static std::shared_ptr<CMap> loadNewMap ( std::shared_ptr<CGame> game, QString name, QString player );
    //static std::shared_ptr<CMap> loadSavedMap ( std::shared_ptr<CGame> game, QString name );//implement
    static void saveMap ( std::shared_ptr<CMap> map,QString file );
    static void loadFromTmx ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> mapc );
    void save ( std::shared_ptr<QJsonObject> data, QString file );
private:
    static void handleTileLayer ( std::shared_ptr<CMap> map, const QJsonObject& tileset, const QJsonObject& layer );
    static void handleObjectLayer ( std::shared_ptr<CMap> map,const QJsonObject &layer );
};

