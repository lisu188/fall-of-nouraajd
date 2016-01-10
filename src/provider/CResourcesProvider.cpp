#include "core/CJsonUtil.h"
#include "CResourcesProvider.h"
#include "core/CUtil.h"


std::list<std::string> CResourcesProvider::searchPath = {"", ":/"};

CResourcesProvider *CResourcesProvider::getInstance() {
    static CResourcesProvider instance;
    return &instance;
}

std::string CResourcesProvider::load(std::string path) {
    std::string data;
    std::ifstream f(path);
    f >> data;
    return data;
}

std::shared_ptr<Value> CResourcesProvider::load_json(std::string path) {
    return CJsonUtil::from_string(load(path));
}

std::string CResourcesProvider::getPath(std::string path) {
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
    switch (type) {
        case CONFIG:
            folderName = "config";
            break;
        case SCRIPT:
            folderName = "scripts";
            break;
        case IMAGE:
            folderName = "images";
            break;
        case MAP:
            folderName = "maps";
            break;
        case SAVE:
            folderName = "save";
            break;
    }
    boost::filesystem::recursive_directory_iterator dir(folderName), end;
    while (dir != end) {
        retValue.insert(dir->path().string());
        dir++;
    }
    return retValue;
}

void CResourcesProvider::save(std::string file, std::string data) {
    std::ofstream f(file);
    f << data;
}

void CResourcesProvider::save(std::string file, std::shared_ptr<Value> data) {
    save(file, CJsonUtil::to_string(data));
}

CResourcesProvider::CResourcesProvider() {

}
