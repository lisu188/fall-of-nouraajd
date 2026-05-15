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
#include "plugin/FonPluginAbi.h"

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

bool register_marker(const FonPluginHostV1 *host, const char *id, const char *config) {
    if (host == nullptr || host->api_version != FON_PLUGIN_API_VERSION || host->game == nullptr ||
        host->register_config_json == nullptr) {
        return false;
    }
    if (host->log != nullptr) {
        host->log(host->game, "registering dynamic native marker content");
    }
    return host->register_config_json(host->game, id, config);
}

} // namespace

extern "C" FON_PLUGIN_EXPORT bool fon_plugin_load_v1(const FonPluginHostV1 *host) {
    return register_marker(host, "dynamicNativePluginMarker", DYNAMIC_MARKER_CONFIG);
}

extern "C" FON_PLUGIN_EXPORT bool fon_plugin_load_direct_v1(const FonPluginHostV1 *host) {
    return register_marker(host, "directDynamicPluginMarker", DIRECT_MARKER_CONFIG);
}

extern "C" FON_PLUGIN_EXPORT bool fon_plugin_load_bad_api_v1(const FonPluginHostV1 *host) {
    return host != nullptr && host->api_version == FON_PLUGIN_API_VERSION + 1;
}

extern "C" FON_PLUGIN_EXPORT bool fon_plugin_load_false_v1(const FonPluginHostV1 *) { return false; }
