#include "CHandler.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"

CObjectHandler::CObjectHandler() {

}

void CObjectHandler::registerConfig(std::string path) {
    std::shared_ptr<Value> config = CConfigurationProvider::getConfig(path);
    for (auto key:config->getMemberNames()) {
        objectConfig[key] = CJsonUtil::clone(&(*config)[key]);
    }
}

std::shared_ptr<Value> CObjectHandler::getConfig(std::string type) {
    if (vstd::ctn(objectConfig, type)) {
        return objectConfig[type];
    }
    return nullptr;
}

std::vector<std::string> CObjectHandler::getAllTypes() {
    std::vector<std::string> types;
    for (std::string val:objectConfig | boost::adaptors::map_keys) {
        types.push_back(val);
    }
    return types;
}

std::shared_ptr<CGameObject> CObjectHandler::getType(std::string name) {
    if (vstd::ctn(constructors, name)) {
        return constructors[name]();
    }
    return std::shared_ptr<CGameObject>();
}

void CObjectHandler::registerType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor) {
    constructors.insert(std::make_pair(name, constructor));
}

std::shared_ptr<CGameObject> CObjectHandler::_createObject(std::shared_ptr<CGame> game, std::string type) {
    std::shared_ptr<Value> config = getConfig(type);
    if (!config) {
        vstd::logger::debug("No config found for:", type);
        config = CJsonUtil::from_string(vstd::join({"{\"class\":\"", type, "\"}"}, ""));
    }
    return CSerialization::deserialize<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>(game, config);
}

std::shared_ptr<CGameObject> CObjectHandler::_clone(std::shared_ptr<CGameObject> object) {
    auto _object = CSerialization::serialize<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>(object);
    //vstd::logger::debug("Cloning:", CJsonUtil::to_string(_object));
    return CSerialization::deserialize<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>(object->getGame(),
                                                                                             _object);
}

std::vector<std::string> CObjectHandler::getAllSubTypes(std::string claz) {
    std::vector<std::string> ret;
    for (auto type:getAllTypes()) {
        auto conf = getConfig(type);
        if (CJsonUtil::isRef(conf)) {
            conf = getConfig((*conf)["ref"].asString());
        }
        std::string clas = (*conf)["class"].asString();
        if (getType(clas) && getType(clas)->meta()->inherits(claz)) {
            ret.push_back(type);
        }
    }
    return ret;
}










