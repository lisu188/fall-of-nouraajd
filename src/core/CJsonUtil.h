/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include "core/CGlobal.h"

namespace CJsonUtil {
    template<typename T>
    bool hasStringProp(T object, std::string prop) {
        return object->count(prop) && (*object)[prop].is_string();
    }

    template<typename T>
    bool hasObjectProp(T object, std::string prop) {
        return object->count(prop) && (*object)[prop].is_object();
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
        for (auto[key, value] :object->items()) {
            (void) key;//to silence compiler
            if (!value.is_object() ||
                !isObject(&value)) {
                return false;
            }
        }
        return true;
    }

    template<typename T=void>
    std::shared_ptr<json> from_string(std::string json_string) {
        try {
            return std::make_shared<json>(json::parse(json_string));
        } catch (...) {
            return nullptr;//TODO: handle
        }
//        vstd::logger::debug(json,reader.getFormatedErrorMessages());
    }

    template<typename T>
    std::string to_string(T value, int indent = -1) {
        return value->dump(indent);
    }

    template<typename T>
    std::shared_ptr<json> clone(T value) {
        std::string json = to_string(value);
//        vstd::logger::debug(json);
        return from_string(json);
    }
}