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
#pragma once

#include "core/CGlobal.h"

class CGameObject;

class CGame;

struct CNativePluginInfo {
  std::string name;
  std::string version;
  std::string description;
};

struct CNativeTypeRegistration {
  std::string name;
  std::function<std::shared_ptr<CGameObject>()> constructor;
};

struct CNativeConfigRegistration {
  std::string name;
  std::shared_ptr<json> config;
};

class CNativePluginContext {
public:
  void registerType(std::string name,
                    std::function<std::shared_ptr<CGameObject>()> constructor);

  void registerConfig(std::string name, std::shared_ptr<json> config);

private:
  friend class CNativePluginLoader;

  std::vector<CNativeTypeRegistration> types;
  std::vector<CNativeConfigRegistration> configs;
  std::unordered_set<std::string> usedNames;
};

class CNativePlugin {
public:
  virtual ~CNativePlugin() = default;

  virtual CNativePluginInfo info() const = 0;

  virtual void registerContent(CNativePluginContext &context) = 0;
};

class CNativePluginRegistry {
public:
  using Factory = std::function<std::shared_ptr<CNativePlugin>()>;

  static CNativePluginRegistry &instance();

  void registerPlugin(CNativePluginInfo info, Factory factory);

  std::shared_ptr<CNativePlugin> create(const std::string &name) const;

  std::map<std::string, std::string> getAvailablePlugins() const;

private:
  struct Entry {
    CNativePluginInfo info;
    Factory factory;
  };

  std::map<std::string, Entry> plugins;
};

class CNativePluginRegistrar {
public:
  CNativePluginRegistrar(CNativePluginInfo info,
                         CNativePluginRegistry::Factory factory);
};

class CNativePluginLoader {
public:
  static std::vector<std::string> configuredPluginsFromEnvironment();

  static std::map<std::string, std::string> getAvailablePlugins();

  static void loadConfiguredPlugins(const std::shared_ptr<CGame> &game);

  static void loadPlugin(const std::shared_ptr<CGame> &game,
                         const std::string &name);

private:
  static void applyContext(const std::shared_ptr<CGame> &game,
                           const CNativePluginContext &context);
};

#define REGISTER_NATIVE_PLUGIN(PluginType)                                     \
  namespace {                                                                  \
  const CNativePluginRegistrar PluginType##_registrar(                         \
      PluginType::static_info(),                                               \
      []() -> std::shared_ptr<CNativePlugin> {                                 \
        return std::make_shared<PluginType>();                                 \
      });                                                                      \
  }
