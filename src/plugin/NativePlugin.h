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
#pragma once

#include "core/CExport.h"
#include "plugin/FonPluginAbi.h"

using NativePluginHostV1 = FonPluginHostV1;

constexpr int NATIVE_PLUGIN_API_VERSION = FON_PLUGIN_API_VERSION;

#define NATIVE_PLUGIN_EXPORT FON_PLUGIN_EXPORT

namespace native_plugin {

FON_CORE_EXPORT bool register_effects(const NativePluginHostV1 *host);

FON_CORE_EXPORT bool register_interactions(const NativePluginHostV1 *host);

FON_CORE_EXPORT bool register_items(const NativePluginHostV1 *host);

FON_CORE_EXPORT bool register_tiles(const NativePluginHostV1 *host);

FON_CORE_EXPORT bool register_map_content(const NativePluginHostV1 *host);

FON_CORE_EXPORT bool register_controllers(const NativePluginHostV1 *host);

FON_CORE_EXPORT bool register_creatures(const NativePluginHostV1 *host);

} // namespace native_plugin
