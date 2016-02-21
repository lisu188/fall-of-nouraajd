#pragma once

#include "core/CGlobal.h"

namespace CJsonUtil {
    template<typename T>
    bool hasStringProp(T object, std::string prop) {
        return object->isMember(prop) && (*object)[prop].isString();
    }

    template<typename T>
    bool hasObjectProp(T object, std::string prop) {
        return object->isMember(prop) && (*object)[prop].isObject();
    }

    template<typename T>
    bool isRef(T object) {
        if (object->size() == 1) {
            return hasStringProp(object, "ref");
        } else if (object->size() == 2) {
            return hasObjectProp(object, "properties") && hasStringProp(object, "ref");
        }
        return false;
    }

    template<typename T>
    bool isType(T object) {
        if (object->size() == 1) {
            return hasStringProp(object, "class");
        } else if (object->size() == 2) {
            return hasObjectProp(object, "properties") && hasStringProp(object, "class");
        }
        return false;
    }

    template<typename T>
    bool isObject(T object) {
        return isRef(object) || isType(object);
    }

    template<typename T>
    bool isMap(T object) {
        for (auto it :object->getMemberNames()) {
            if (!(*object)[it].isObject() ||
                !isObject(&(*object)[it])) {
                return false;
            }
        }
        return true;
    }

    template<typename T=void>
    std::shared_ptr<Value> from_string(std::string json) {
        auto d = std::make_shared<Value>();
        Reader reader;
        if (reader.parse(json, *d)) {
            return d;
        }
        //vstd::logger::debug(reader.getFormatedErrorMessages());
        return nullptr;
    }

    template<typename T, typename Writer=FastWriter>
    std::string to_string(T value) {
        return std::make_shared<Writer>()->write(*value);
    }

    template<typename T>
    std::shared_ptr<Value> clone(T value) {
        std::string json = to_string(value);
        return from_string(json);
    }
}