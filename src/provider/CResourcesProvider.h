#pragma once

#include "core/CGlobal.h"

enum CResType {
    CONFIG, MAP, PLUGIN, IMAGE, SAVE
};

class CResourcesProvider {
public:
    static CResourcesProvider *getInstance();

    std::string load(std::string path);

    std::shared_ptr<Value> load_json(std::string path);

    std::string get_path(std::string path);

    std::set<std::string> getFiles(CResType type);

    void save(std::string file, std::string data);

    void save(std::string file, std::shared_ptr<Value> data);

private:
    static std::list<std::string> searchPath;

    CResourcesProvider();
};
