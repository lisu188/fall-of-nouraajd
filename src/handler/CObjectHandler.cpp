/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

CObjectHandler::CObjectHandler() {}

void CObjectHandler::registerConfig(const std::string &path) {
  std::shared_ptr<json> config = CConfigurationProvider::getConfig(path);
  for (auto [key, value] : config->items()) {
    objectConfig[key] = CJsonUtil::clone(value);
  }
}

void CObjectHandler::registerConfig(const std::string &name,
                                    std::shared_ptr<json> value) {
  objectConfig[name] = value;
}

std::shared_ptr<json> CObjectHandler::getConfig(const std::string &type) {
  if (vstd::ctn(objectConfig, type)) {
    return objectConfig[type];
  }
  return nullptr;
}

std::vector<std::string> CObjectHandler::getAllTypes() {
  std::vector<std::string> types;
  for (auto val : objectConfig | boost::adaptors::map_keys) {
    types.push_back(val);
  }
  return types;
}

std::shared_ptr<CGameObject> CObjectHandler::getType(const std::string &name) {
  if (vstd::ctn(constructors, name)) {
    return constructors[name]();
  }
  return std::shared_ptr<CGameObject>();
}

void CObjectHandler::registerType(
    std::string name,
    std::function<std::shared_ptr<CGameObject>()> constructor) {
  constructors.insert(std::make_pair(name, constructor));
}

// TODO: add option to provide custom configuration from string
std::shared_ptr<CGameObject>
CObjectHandler::_createObject(std::shared_ptr<CGame> game,
                              const std::string &type) {
  std::shared_ptr<json> config = getConfig(type);
  if (!config) {
    // TODO: vstd::logger::debug("No config found for:", type);
    config =
        CJsonUtil::from_string(vstd::join({R"({"class":")", type, "\"}"}, ""));
  }
  std::shared_ptr<CGameObject> object =
      CSerialization::deserialize<std::shared_ptr<json>,
                                  std::shared_ptr<CGameObject>>(game, config);
  object->setTypeId(type);
  return object;
}

std::shared_ptr<CGameObject>
CObjectHandler::_clone(const std::shared_ptr<CGameObject> &object) {
  auto _object =
      CSerialization::serialize<std::shared_ptr<json>,
                                std::shared_ptr<CGameObject>>(object);
  // vstd::logger::debug("Cloning:", CJsonUtil::to_string(_object));
  std::shared_ptr<CGameObject> shared_ptr =
      CSerialization::deserialize<std::shared_ptr<json>,
                                  std::shared_ptr<CGameObject>>(
          object->getGame(), _object);
  shared_ptr->setName(CSerialization::generateName(shared_ptr));
  return shared_ptr;
}

std::vector<std::string>
CObjectHandler::getAllSubTypes(const std::string &claz) {
  std::vector<std::string> ret;
  for (const auto &type : getAllTypes()) {
    auto conf = getConfig(type);
    if (CJsonUtil::isRef(conf)) {
      conf = getConfig((*conf)["ref"].get<std::string>());
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
  return (*conf)["class"].get<std::string>();
}

void CObjectHandler::registerConfig(const std::set<std::string> &paths) {
  for (const auto &path : paths) {
    registerConfig(path);
  }
}
