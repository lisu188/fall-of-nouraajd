#pragma once
#include <QString>

class CMap;
class QJsonObject;

class CMapLoader {
public:
    static  void loadMap ( CMap* map,QString mapPath );
private:
    static void handleTileLayer ( CMap* map,const QJsonObject& tileset,const QJsonObject& layer );
    static void handleObjectLayer ( CMap* map,const QJsonObject &layer );
};

