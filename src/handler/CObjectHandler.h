/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "core/CUtil.h"

#include "core/CSerialization.h"
#include "object/CGameObject.h"


class CMap;

class CObjectHandler : public CGameObject {
public:
    CObjectHandler();

    template<typename T=CGameObject>
    std::shared_ptr<T> createObject(std::shared_ptr<CGame> game, std::string type) {
        return vstd::cast<T>(_createObject(game, type));
    }

    template<typename T=CGameObject>
    std::shared_ptr<T> createObject(std::shared_ptr<CGame> game) {
        return vstd::cast<T>(_createObject(game, T::static_meta()->name()));
    }

    template<typename T>
    std::shared_ptr<T> clone(std::shared_ptr<T> object) {
        return vstd::cast<T>(_clone(object));
    }

    std::vector<std::string> getAllTypes();

    std::vector<std::string> getAllSubTypes(const std::string &claz);

    void registerConfig(const std::string &path);

    void registerConfig(const std::string &name, std::shared_ptr<json> value);

    void registerConfig(const std::set<std::string> &paths);

    void registerType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor);

    std::shared_ptr<CGameObject> getType(const std::string &name);

    std::shared_ptr<json> getConfig(const std::string &type);

    std::string getClass(const std::string &type);

private:
    std::shared_ptr<CGameObject> _createObject(std::shared_ptr<CGame> map, const std::string &type);

    std::shared_ptr<CGameObject> _clone(const std::shared_ptr<CGameObject> &object);

    std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> constructors;

    std::unordered_map<std::string, std::shared_ptr<json>> objectConfig;
};
