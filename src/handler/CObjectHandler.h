#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"

#include "core/CSerialization.h"
#include "object/CGameObject.h"

class ATypeHandler;


class CMap;

class CObjectHandler : public CGameObject {
public:
    CObjectHandler();

    template<typename T=CGameObject>
    std::shared_ptr<T> createObject(std::shared_ptr<CGame> game, std::string type) {
        return vstd::cast<T>(_createObject(game, type));
    }

    template<typename T>
    std::shared_ptr<T> clone(std::shared_ptr<T> object) {
        return vstd::cast<T>(_clone(object));
    }

    std::vector<std::string> getAllTypes();

    std::vector<std::string> getAllSubTypes(std::string claz);

    void registerConfig(std::string path);

    void registerConfig(std::string name, std::shared_ptr<Value> value);

    void registerType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor);

    std::shared_ptr<CGameObject> getType(std::string name);

    std::shared_ptr<Value> getConfig(std::string type);

private:
    std::shared_ptr<CGameObject> _createObject(std::shared_ptr<CGame> map, std::string type);

    std::shared_ptr<CGameObject> _clone(std::shared_ptr<CGameObject> object);

    std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> constructors;

    std::unordered_map<std::string, std::shared_ptr<Value>> objectConfig;
};
