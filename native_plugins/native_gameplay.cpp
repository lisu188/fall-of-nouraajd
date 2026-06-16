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
#include "plugin/NativePlugin.h"

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_effects_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_effects(host);
}

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_interactions_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_interactions(host);
}

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_items_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_items(host);
}

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_tiles_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_tiles(host);
}

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_map_content_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_map_content(host);
}

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_controllers_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_controllers(host);
}

extern "C" NATIVE_PLUGIN_EXPORT bool native_gameplay_creatures_load_v1(const NativePluginHostV1 *host) {
    return native_plugin::register_creatures(host);
}
