/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "CHandler.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"

#include <algorithm>

CObjectHandler::CObjectHandler() {}

void CObjectHandler::registerConfig(const std::string &path) {
    std::shared_ptr<json> config = CConfigurationProvider::getConfig(path);
    if (!config) {
        vstd::logger::warning("Failed to load config:", path);
        return;
    }
    for (auto &[key, value] : config->items()) {
        if (value.is_object() && !value.count("class") && !value.count("ref")) {
            continue;
        }
        objectConfig[key] = CJsonUtil::alias(config, value);
    }
}

void CObjectHandler::registerConfig(const std::string &name, std::shared_ptr<json> value) {
    objectConfig[name] = value;
}

void CObjectHandler::unregisterConfig(const std::string &name) { objectConfig.erase(name); }

std::shared_ptr<json> CObjectHandler::getConfig(const std::string &type) {
    if (vstd::ctn(objectConfig, type)) {
        return objectConfig[type];
    }
    return nullptr;
}

std::vector<std::string> CObjectHandler::getAllTypes() {
    std::vector<std::string> types;
    for (auto val : constructors | std::views::keys) {
        types.push_back(val);
    }
    for (auto val : objectConfig | std::views::keys) {
        types.push_back(val);
    }
    std::ranges::sort(types);
    auto duplicates = std::ranges::unique(types);
    types.erase(duplicates.begin(), duplicates.end());
    return types;
}

std::shared_ptr<CGameObject> CObjectHandler::getType(const std::string &name) {
    if (vstd::ctn(constructors, name)) {
        return constructors[name]();
    }
    return std::shared_ptr<CGameObject>();
}

void CObjectHandler::registerType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor) {
    // A map's script.py is loaded (registering its classes) immediately before that map's objects
    // are constructed from TMX, so a class name shared across maps -- e.g. every campaign map
    // defines its own "StartEvent" -- must resolve to the map currently being loaded. The previous
    // std::unordered_map::insert kept the first binding and silently dropped later ones, so the
    // first map loaded in a session (the campaign start) owned a shared class name for every
    // subsequent map: entering a later map constructed its start markers from the wrong map's class
    // and skipped that map's arrival initialization.
    //
    // Registrations made while a map script is loading are therefore last-wins *among map scripts*,
    // but must not clobber an authoritative binding registered outside map-script loading (native /
    // config / global plugin, or an explicit tooling/test registration): those keep first priority
    // so a globally injected class still overrides a map's same-named declaration.
    if (loadingMapScript) {
        if (externalConstructors.contains(name)) {
            return;
        }
    } else {
        externalConstructors.insert(name);
    }
    constructors.insert_or_assign(std::move(name), std::move(constructor));
}

void CObjectHandler::beginMapScriptScope() { loadingMapScript = true; }

void CObjectHandler::endMapScriptScope() { loadingMapScript = false; }

// TODO: add option to provide custom configuration from string
std::shared_ptr<CGameObject> CObjectHandler::_createObject(std::shared_ptr<CGame> game, const std::string &type) {
    std::shared_ptr<json> config = getConfig(type);
    if (!config) {
        vstd::logger::debug("No config found for:", type, "falling back to class-name construction");
        config = std::make_shared<json>();
        (*config)["class"] = type;
    }
    std::shared_ptr<CGameObject> object =
        CSerialization::deserialize<std::shared_ptr<json>, std::shared_ptr<CGameObject>>(game, config);
    if (!object) {
        return object;
    }
    object->setTypeId(type);
    return object;
}

std::shared_ptr<CGameObject> CObjectHandler::_clone(const std::shared_ptr<CGameObject> &object) {
    auto _object = CSerialization::serialize<std::shared_ptr<json>, std::shared_ptr<CGameObject>>(object);
    std::shared_ptr<CGameObject> shared_ptr =
        CSerialization::deserialize<std::shared_ptr<json>, std::shared_ptr<CGameObject>>(object->getGame(), _object);
    shared_ptr->setName(CSerialization::generateName(shared_ptr));
    return shared_ptr;
}

std::vector<std::string> CObjectHandler::getAllSubTypes(const std::string &claz) {
    std::vector<std::string> ret;
    for (const auto &type : getAllTypes()) {
        auto conf = getConfig(type);
        if (CJsonUtil::isRef(conf)) {
            conf = getConfig((*conf)["ref"].get<std::string>());
        }
        if (!conf || !conf->is_object() || !conf->contains("class") || !(*conf)["class"].is_string()) {
            continue;
        }
        auto clas = (*conf)["class"].get<std::string>();
        if (getType(clas) && getType(clas)->meta()->inherits(claz)) {
            ret.push_back(type);
        }
    }
    return ret;
}

std::string CObjectHandler::getClass(const std::string &type) {
    auto conf = getConfig(type);
    if (CJsonUtil::isRef(conf)) {
        conf = getConfig((*conf)["ref"].get<std::string>());
    }
    if (!conf || !conf->is_object() || !conf->contains("class") || !(*conf)["class"].is_string()) {
        return "";
    }
    return (*conf)["class"].get<std::string>();
}

void CObjectHandler::registerConfig(const std::set<std::string> &paths) {
    for (const auto &path : paths) {
        registerConfig(path);
    }
}
