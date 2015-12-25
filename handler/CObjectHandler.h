#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "templates/cast.h"
#include "core/CSerialization.h"

class ATypeHandler;

class CGameObject;

class CMap;

class CObjectHandler {
public:
    CObjectHandler(std::shared_ptr<CObjectHandler> parent = std::shared_ptr<CObjectHandler>());

    template<typename T=CGameObject>
    std::shared_ptr<T> createObject(std::shared_ptr<CMap> map, QString type) {
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

    std::set<QString> getAllTypes();

    void registerConfig(QString path);

    void registerType(QString name, std::function<std::shared_ptr<CGameObject>()> constructor);

    std::shared_ptr<CGameObject> getType(QString name);

    std::shared_ptr<QJsonObject> getConfig(QString type);

private:
    std::shared_ptr<CGameObject> _createObject(std::shared_ptr<CMap> map, QString type);

    std::shared_ptr<CGameObject> _clone(std::shared_ptr<CGameObject> object);

    std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> constructors;

    std::unordered_map<QString, std::shared_ptr<QJsonObject>> objectConfig;

    std::weak_ptr<CObjectHandler> parent;

};
