#include "CJsonUtil.h"

bool CJsonUtil::hasStringProp(std::shared_ptr<QJsonObject> object, QString prop) {
    auto it = object->find(prop);
    return it != object->end() && it.value().isString() && it.value().toString().trimmed() != "";
}

bool CJsonUtil::hasObjectProp(std::shared_ptr<QJsonObject> object, QString prop) {
    auto it = object->find(prop);
    return it != object->end() && it.value().isObject();
}

bool CJsonUtil::isRef(std::shared_ptr<QJsonObject> object) {
    if (object->size() == 1) {
        return hasStringProp(object, "ref");
    } else if (object->size() == 2) {
        return hasObjectProp(object, "properties") && hasStringProp(object, "ref");
    }
    return false;
}

bool CJsonUtil::isType(std::shared_ptr<QJsonObject> object) {
    if (object->size() == 1) {
        return hasStringProp(object, "class");
    } else if (object->size() == 2) {
        return hasObjectProp(object, "properties") && hasStringProp(object, "class");
    }
    return false;
}

bool CJsonUtil::isObject(std::shared_ptr<QJsonObject> object) {
    return isRef(object) || isType(object);
}

bool CJsonUtil::isMap(std::shared_ptr<QJsonObject> object) {
    for (auto it = object->begin(); it != object->end(); it++) {
        if (!it.value().isObject() ||
            !isObject(std::make_shared<QJsonObject>(it.value().toObject()))) {
            return false;
        }
    }
    return true;
}
