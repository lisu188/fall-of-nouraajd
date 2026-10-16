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
#include "plugin/NativeMarkerPlugin.h"

#if !defined(GAME_PLUGIN_TEST_MISSING_VERSION)
extern "C" GAME_PLUGIN_EXPORT uint32_t game_plugin_api_version() {
#if defined(GAME_PLUGIN_TEST_LEGACY_VERSION)
    return 2;
#else
    return GAME_PLUGIN_API_VERSION;
#endif
}
#endif

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_v3(const CPluginHostV3 *host) {
    auto *registrar = game_plugin_registrar(host);
    return registrar != nullptr && native_plugin::register_dynamic_marker(*registrar);
}

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_direct_v3(const CPluginHostV3 *host) {
    auto *registrar = game_plugin_registrar(host);
    return registrar != nullptr && native_plugin::register_direct_dynamic_marker(*registrar);
}

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_bad_api_v3(const CPluginHostV3 *host) {
    return host != nullptr && host->api_version == GAME_PLUGIN_API_VERSION + 1;
}

extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_false_v3(const CPluginHostV3 *) { return false; }

// A legacy entry that would succeed if invoked: rejection tests must stop before calling it.
extern "C" GAME_PLUGIN_EXPORT bool game_plugin_load_v2(const void *) { return true; }
