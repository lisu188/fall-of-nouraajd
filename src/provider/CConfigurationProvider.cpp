#include "CConfigurationProvider.h"
#include "handler/CHandler.h"

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
    this->insert(std::make_pair( path, CResourcesProvider::getInstance()->load_json(path)));
}
