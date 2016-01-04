#pragma once

#include "core/CGlobal.h"
#include "core/CMap.h"

class CMapLoader {
public:
    static std::shared_ptr<CMap> loadNewMap ( std::shared_ptr<CGame> game, std::string name );

    static std::shared_ptr<CMap> loadNewMap ( std::shared_ptr<CGame> game, std::string name, std::string player );

    //static std::shared_ptr<CMap> loadSavedMap ( std::shared_ptr<CGame> game, std::string name );//implement
    static void saveMap ( std::shared_ptr<CMap> map, std::string file );

    static void loadFromTmx ( std::shared_ptr<CMap> map, std::shared_ptr<Value> mapc );

    void save ( std::shared_ptr<Value> data, std::string file );

private:
    static void handleTileLayer ( std::shared_ptr<CMap> map, const Value &tileset, const Value &layer );

    static void handleObjectLayer ( std::shared_ptr<CMap> map, const Value &layer );
};

