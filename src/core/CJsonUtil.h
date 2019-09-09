//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
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
//        vstd::logger::debug(json,reader.getFormatedErrorMessages());
        return nullptr;
    }

    template<typename Writer=FastWriter, typename T>
    std::string to_string(T value) {
        return std::make_shared<Writer>()->write(*value);
    }

    template<typename T>
    std::shared_ptr<Value> clone(T value) {
        std::string json = to_string(value);
//        vstd::logger::debug(json);
        return from_string(json);
    }
}