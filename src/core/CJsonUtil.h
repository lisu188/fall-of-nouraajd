#pragma once

#include "core/CGlobal.h"

namespace CJsonUtil {
    template<typename T>
    bool hasStringProp(T object, std::string prop) {
        Value::ConstMemberIterator it = object->FindMember(prop.c_str());
        return it != object->MemberEnd() && it->value.IsString() && vstd::trim(vstd::str(it->value.GetString())) != "";
    }

    template<typename T>
    bool hasObjectProp(T object, std::string prop) {
        auto it = object->FindMember(prop.c_str());
        return it != object->MemberEnd() && it->value.IsObject();
    }

    template<typename T>
    bool isRef(T object) {
        if (object->Size() == 1) {
            return hasStringProp(object, "ref");
        } else if (object->Size() == 2) {
            return hasObjectProp(object, "properties") && hasStringProp(object, "ref");
        }
        return false;
    }

    template<typename T>
    bool isType(T object) {
        if (object->Size() == 1) {
            return hasStringProp(object, "class");
        } else if (object->Size() == 2) {
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
        for (auto it = object->MemberBegin(); it != object->MemberEnd(); it++) {
            if (!it->value.IsObject() ||
                !isObject(&it->value)) {
                return false;
            }
        }
        return true;
    }
}
