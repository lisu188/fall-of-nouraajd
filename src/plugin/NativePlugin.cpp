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
#include "core/CController.h"
#include "core/CWrapper.h"
#include "handler/CEventHandler.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "object/CDialog.h"
#include "object/CMarket.h"
#include "object/CObject.h"
#include "object/CPlayer.h"
#include "plugin/CGameplayTypeTable.h"
#include "plugin/CPluginRegistrar.h"

namespace native_plugin {

bool register_gameplay_types(CPluginRegistrar &registrar) {
    bool registered = true;
#define FN_TYPE(T, ...) registered = registrar.registerType<T, __VA_ARGS__>() && registered;
#define FN_WRAPPED(T, ...)                                                                                             \
    registered = registrar.registerType<T, __VA_ARGS__>() && registered;                                               \
    registered = registrar.registerType<CWrapper<T>, T, __VA_ARGS__>() && registered;
    FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)
#undef FN_WRAPPED
#undef FN_TYPE
    if (registered) {
        registrar.log("registered native gameplay classes");
    }
    return registered;
}

} // namespace native_plugin
