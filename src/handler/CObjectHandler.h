#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"

#include "core/CSerialization.h"
#include "object/CGameObject.h"

class ATypeHandler;


class CMap;

class CObjectHandler : public CGameObject {
public:
    CObjectHandler(std::shared_ptr<CObjectHandler> parent = std::shared_ptr<CObjectHandler>());

    template<typename T=CGameObject>
    std::shared_ptr<T> createObject(std::shared_ptr<CMap> map, std::string type) {
        std::shared_ptr<T> object = vstd::cast<T>(_createObject(map, type));
        if (object) {
            return object;
        } else if (parent.lock()) {
            return parent.lock()->createObject<T>(map, type);
        }
        return object;
    }

    template<typename T>
    std::shared_ptr<T> clone(std::shared_ptr<T> object) {
        return vstd::cast<T>(_clone(object));
    }

    std::set<std::string> getAllTypes();

    void registerConfig(std::string path);

    void registerType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor);

    std::shared_ptr<CGameObject> getType(std::string name);

    std::shared_ptr<Value> getConfig(std::string type);

private:
    std::shared_ptr<CGameObject> _createObject(std::shared_ptr<CMap> map, std::string type);

    std::shared_ptr<CGameObject> _clone(std::shared_ptr<CGameObject> object);

    std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> constructors;

    std::unordered_map<std::string, std::shared_ptr<Value>> objectConfig;

    std::weak_ptr<CObjectHandler> parent;

};
