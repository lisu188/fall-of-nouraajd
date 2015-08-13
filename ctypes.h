#pragma once
#include "CGlobal.h"
#include "object/CObject.h"
#include "CSerialization.h"

class CTypes {
public:
    static std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> &registry();
    template<typename T>
    static void register_type() {
        registry() [ T::staticMetaObject.className()]=[]() {return std::make_shared<T>();};
        std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::shared_ptr<T>>>()->reg();
        std::make_shared<CSerializer<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<T>>>>()->reg();
        std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<T>>>>()->reg();
    }
};


