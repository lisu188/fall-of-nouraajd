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
#include "core/CNativePlugin.h"
#include "core/CGame.h"
#include "handler/CObjectHandler.h"

#include <cstdlib>
#include <stdexcept>

void CNativePluginContext::registerType(
    std::string name,
    std::function<std::shared_ptr<CGameObject>()> constructor) {
  name = vstd::trim(name);
  if (name.empty()) {
    throw std::runtime_error("Native plugin type registration requires a name.");
  }
  if (!constructor) {
    throw std::runtime_error("Native plugin type '" + name +
                             "' registration requires a constructor.");
  }
  if (usedNames.count(name)) {
    throw std::runtime_error("Native plugin attempted to register '" + name +
                             "' more than once.");
  }
  usedNames.insert(name);
  types.push_back({std::move(name), std::move(constructor)});
}

void CNativePluginContext::registerConfig(std::string name,
                                          std::shared_ptr<json> config) {
  name = vstd::trim(name);
  if (name.empty()) {
    throw std::runtime_error(
        "Native plugin config registration requires a name.");
  }
  if (!config || !config->is_object()) {
    throw std::runtime_error("Native plugin config '" + name +
                             "' must be a JSON object.");
  }
  if (usedNames.count(name)) {
    throw std::runtime_error("Native plugin attempted to register '" + name +
                             "' more than once.");
  }
  usedNames.insert(name);
  configs.push_back({std::move(name), std::move(config)});
}

CNativePluginRegistry &CNativePluginRegistry::instance() {
  static CNativePluginRegistry registry;
  return registry;
}

void CNativePluginRegistry::registerPlugin(CNativePluginInfo info,
                                           Factory factory) {
  auto name = vstd::trim(info.name);
  if (name.empty()) {
    throw std::runtime_error("Native plugin registration requires a name.");
  }
  if (vstd::trim(info.version).empty()) {
    throw std::runtime_error("Native plugin '" + name +
                             "' registration requires a version.");
  }
  if (plugins.count(name)) {
    throw std::runtime_error("Duplicate native plugin registration: " + name);
  }
  info.name = name;
  plugins.emplace(name, Entry{std::move(info), std::move(factory)});
}

std::shared_ptr<CNativePlugin>
CNativePluginRegistry::create(const std::string &name) const {
  auto plugin = plugins.find(name);
  if (plugin == plugins.end()) {
    return nullptr;
  }
  return plugin->second.factory();
}

std::map<std::string, std::string>
CNativePluginRegistry::getAvailablePlugins() const {
  std::map<std::string, std::string> available;
  for (const auto &[name, entry] : plugins) {
    available[name] = entry.info.version;
  }
  return available;
}

CNativePluginRegistrar::CNativePluginRegistrar(
    CNativePluginInfo info, CNativePluginRegistry::Factory factory) {
  CNativePluginRegistry::instance().registerPlugin(std::move(info),
                                                   std::move(factory));
}

std::vector<std::string>
CNativePluginLoader::configuredPluginsFromEnvironment() {
  const char *raw = std::getenv("FON_NATIVE_PLUGINS");
  if (!raw) {
    return {};
  }

  std::unordered_set<std::string> seen;
  std::vector<std::string> configured;
  for (auto name : vstd::split(std::string(raw), ',')) {
    auto trimmed = vstd::trim(name);
    if (!trimmed.empty() && !vstd::ctn(seen, trimmed)) {
      configured.push_back(trimmed);
      seen.insert(trimmed);
    }
  }
  return configured;
}

std::map<std::string, std::string> CNativePluginLoader::getAvailablePlugins() {
  return CNativePluginRegistry::instance().getAvailablePlugins();
}

void CNativePluginLoader::loadConfiguredPlugins(
    const std::shared_ptr<CGame> &game) {
  for (const auto &name : configuredPluginsFromEnvironment()) {
    loadPlugin(game, name);
  }
}

void CNativePluginLoader::applyContext(const std::shared_ptr<CGame> &game,
                                       const CNativePluginContext &context) {
  auto handler = game->getObjectHandler();

  for (const auto &type : context.types) {
    if (handler->getType(type.name)) {
      throw std::runtime_error("Native plugin type '" + type.name +
                               "' is already registered.");
    }
  }
  for (const auto &config : context.configs) {
    if (handler->getConfig(config.name)) {
      throw std::runtime_error("Native plugin config '" + config.name +
                               "' is already registered.");
    }
  }

  for (const auto &type : context.types) {
    handler->registerType(type.name, type.constructor);
  }
  for (const auto &config : context.configs) {
    handler->registerConfig(config.name, config.config);
  }
}

void CNativePluginLoader::loadPlugin(const std::shared_ptr<CGame> &game,
                                     const std::string &name) {
  auto plugin_name = vstd::trim(name);
  if (plugin_name.empty()) {
    game->registerNativePluginError("<empty>",
                                    "Native plugin name cannot be empty.");
    return;
  }
  if (game->hasLoadedNativePlugin(plugin_name)) {
    return;
  }

  auto plugin = CNativePluginRegistry::instance().create(plugin_name);
  if (!plugin) {
    auto available = getAvailablePlugins();
    std::stringstream stream;
    stream << "Native plugin '" << plugin_name << "' is not registered.";
    if (!available.empty()) {
      stream << " Available plugins:";
      bool first = true;
      for (const auto &[available_name, version] : available) {
        stream << (first ? " " : ", ") << available_name << "@" << version;
        first = false;
      }
    }
    auto error = stream.str();
    game->registerNativePluginError(plugin_name, error);
    vstd::logger::error(error);
    return;
  }

  auto info = plugin->info();
  if (info.name != plugin_name) {
    auto error = "Native plugin registry entry '" + plugin_name +
                 "' returned mismatched metadata '" + info.name + "'.";
    game->registerNativePluginError(plugin_name, error);
    vstd::logger::error(error);
    return;
  }

  try {
    CNativePluginContext context;
    plugin->registerContent(context);
    applyContext(game, context);
    game->registerLoadedNativePlugin(info.name, info.version);
    vstd::logger::info("Loaded native plugin:", info.name, info.version);
  } catch (const std::exception &exception) {
    auto error = "Failed to load native plugin '" + info.name + "' (" +
                 info.version + "): " + exception.what();
    game->registerNativePluginError(info.name, error);
    vstd::logger::error(error);
  }
}
