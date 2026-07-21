/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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
#include "plugin/CPluginAbi.h"
#include "plugin/CPluginRegistrar.h"

namespace {

constexpr const char *DYNAMIC_MARKER_CONFIG = R"json({
  "class": "CGameObject",
  "properties": {
    "label": "Dynamic native plugin marker",
    "description": "Registered by a dynamic C++ plugin.",
    "nativePluginLoaded": true,
    "dynamicPluginLoaded": true
  }
})json";

constexpr const char *DIRECT_MARKER_CONFIG = R"json({
  "class": "CGameObject",
  "properties": {
    "label": "Direct dynamic plugin marker",
    "description": "Registered by an explicit dynamic C++ plugin load.",
    "nativePluginLoaded": true,
    "dynamicPluginLoaded": true,
    "directDynamicPluginLoaded": true
  }
})json";

bool register_marker(const CPluginHostV2 *host, const char *id, const char *config) {
    auto *registrar = game_plugin_registrar(host);
    if (registrar == nullptr) {
        return false;
    }
    registrar->log("registering dynamic native marker content");
    return registrar->registerConfigJson(id, config);
}

} // namespace

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_v2(const CPluginHostV2 *host) {
    return register_marker(host, "dynamicNativePluginMarker", DYNAMIC_MARKER_CONFIG);
}

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_direct_v2(const CPluginHostV2 *host) {
    return register_marker(host, "directDynamicPluginMarker", DIRECT_MARKER_CONFIG);
}

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_bad_api_v2(const CPluginHostV2 *host) {
    return host != nullptr && host->api_version == GAME_PLUGIN_API_VERSION + 1;
}

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_false_v2(const CPluginHostV2 *) { return false; }
