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
#include "plugin/CPluginAbi.h"

class CPluginRegistrar;

#define NATIVE_PLUGIN_EXPORT GAME_PLUGIN_EXPORT

namespace native_plugin {

// Registers every content-constructible gameplay type from plugin/CGameplayTypeTable.h.
// Invoked by the native_gameplay plugin's game_plugin_load_v2 entry point.
GAME_CORE_EXPORT bool register_gameplay_types(CPluginRegistrar &registrar);

} // namespace native_plugin
