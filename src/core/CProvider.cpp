#include "core/CProvider.h"
#include "handler/CHandler.h"
#include "core/CJsonUtil.h"

std::shared_ptr<Value> CConfigurationProvider::getConfig(std::string path) {
    static CConfigurationProvider instance;
    return instance.getConfiguration(path);
}

CConfigurationProvider::CConfigurationProvider() {

}

CConfigurationProvider::~CConfigurationProvider() {
    clear();
}

std::shared_ptr<Value> CConfigurationProvider::getConfiguration(std::string path) {
    if (this->find(path) != this->end()) {
        return this->at(path);
    }
    loadConfig(path);
    return getConfiguration(path);
}

void CConfigurationProvider::loadConfig(std::string path) {
    this->insert(std::make_pair(path, CResourcesProvider::getInstance()->load_json(path)));
}

std::list<std::string> CResourcesProvider::searchPath = {""};

CResourcesProvider *CResourcesProvider::getInstance() {
    static CResourcesProvider instance;
    return &instance;
}

std::string CResourcesProvider::load(std::string path) {
    std::ifstream t(get_path(path));
    return std::string(std::istreambuf_iterator<char>(t),
                       std::istreambuf_iterator<char>());
}

std::shared_ptr<Value> CResourcesProvider::load_json(std::string path) {
    return CJsonUtil::from_string(load(path));
}

std::string CResourcesProvider::get_path(std::string path) {
    for (auto it:searchPath) {
        if (boost::filesystem::exists(it / boost::filesystem::path(path))) {
            boost::filesystem::path p = it / boost::filesystem::path(path);
            return p.string();
        }
    }
    return std::string();
}

std::set<std::string> CResourcesProvider::getFiles(CResType type) {
    std::set<std::string> retValue;
    std::string folderName;
    std::string suffix;
    //TODO: do not traverse for .py files and return directories for maps
    switch (type) {
        case CONFIG:
            folderName = "config";
            suffix = "json";
            break;
        case PLUGIN:
            folderName = "plugins";
            suffix = "py";
            break;
        case MAP:
            folderName = "maps";
            suffix = "map";
            break;
        case SAVE:
            folderName = "save";
            suffix = "sav";
            break;
    }
    boost::filesystem::recursive_directory_iterator dir(folderName), end;
    while (dir != end) {
        if (!boost::filesystem::is_directory(dir->path())) {
            auto pt = dir->path().string();
            if (vstd::ends_with(pt, vstd::join({".", suffix}, ""))) {
                retValue.insert(pt);
            }
        }
        dir++;
    }

    return retValue;
}

void CResourcesProvider::save(std::string file, std::string data) {
    boost::filesystem::path path(file);
    boost::filesystem::path dir = path.parent_path();
    if (!boost::filesystem::exists(dir)) {
        boost::filesystem::create_directory(dir);
    }
    std::ofstream f(file);
    f << data;
}

void CResourcesProvider::save(std::string file, std::shared_ptr<Value> data) {
    save(file, CJsonUtil::to_string(data));
}

CResourcesProvider::CResourcesProvider() {

}
