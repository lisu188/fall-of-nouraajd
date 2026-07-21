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
#include "plugin/CPluginRegistrar.h"

extern "C" NATIVE_PLUGIN_EXPORT bool game_plugin_load_v2(const CPluginHostV2 *host) {
    auto *registrar = game_plugin_registrar(host);
    if (registrar == nullptr) {
        return false;
    }
    return native_plugin::register_gameplay_types(*registrar);
}
