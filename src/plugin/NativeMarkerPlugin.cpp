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
#include "plugin/NativeMarkerPlugin.h"
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

bool register_marker(CPluginRegistrar &registrar, const char *id, const char *config) {
    registrar.log("registering dynamic native marker content");
    return registrar.registerConfigJson(id, config);
}

} // namespace

namespace native_plugin {

bool register_dynamic_marker(CPluginRegistrar &registrar) {
    return register_marker(registrar, "dynamicNativePluginMarker", DYNAMIC_MARKER_CONFIG);
}

bool register_direct_dynamic_marker(CPluginRegistrar &registrar) {
    return register_marker(registrar, "directDynamicPluginMarker", DIRECT_MARKER_CONFIG);
}

} // namespace native_plugin
