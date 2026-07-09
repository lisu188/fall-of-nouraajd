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
#include "core/CGame.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "handler/CObjectHandler.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "object/CDialog.h"
#include "object/CMarket.h"
#include "object/CObject.h"
#include "object/CPlayer.h"

namespace {

CGame *host_game(const NativePluginHostV1 *host) {
    if (host == nullptr || host->api_version != NATIVE_PLUGIN_API_VERSION || host->game == nullptr) {
        return nullptr;
    }
    return static_cast<CGame *>(host->game);
}

void log(const NativePluginHostV1 *host, const char *message) {
    if (host != nullptr && host->log != nullptr && host->game != nullptr) {
        host->log(host->game, message);
    }
}

template <fn::MetaRegisteredGameObject T, fn::GameObjectDerived... Bases> bool register_type(CGame *game) {
    if (game == nullptr) {
        return false;
    }
    CTypes::register_type<T, Bases...>();
    game->getObjectHandler()->registerType(T::static_meta()->name(), []() { return std::make_shared<T>(); });
    return true;
}

} // namespace

namespace native_plugin {

bool register_effects(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    registered = register_type<CEffect, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CEffect>, CEffect, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay effect classes");
    }
    return registered;
}

bool register_interactions(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    registered = register_type<CInteraction, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CInteraction>, CInteraction, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay interaction classes");
    }
    return registered;
}

bool register_items(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    registered = register_type<CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CWeapon, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CSmallWeapon, CWeapon, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CArmor, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CPotion, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CPotion>, CPotion, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CHelmet, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CBoots, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CBelt, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CGloves, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CPants, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CShield, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CScroll, CItem, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CScroll>, CScroll, CItem, CMapObject, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay item classes");
    }
    return registered;
}

bool register_tiles(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    registered = register_type<CTile, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CTile>, CTile, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay tile classes");
    }
    return registered;
}

bool register_map_content(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    registered = register_type<CMapObject, CGameObject>(game) && registered;
    registered = register_type<CBuilding, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CBuilding>, CBuilding, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CEvent, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CEvent>, CEvent, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CMarket, CGameObject>(game) && registered;
    registered = register_type<CDialog, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CDialog>, CDialog, CGameObject>(game) && registered;
    registered = register_type<CDialogOption, CGameObject>(game) && registered;
    registered = register_type<CDialogState, CGameObject>(game) && registered;
    registered = register_type<CTrigger, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CTrigger>, CTrigger, CGameObject>(game) && registered;
    registered = register_type<CQuest, CGameObject>(game) && registered;
    registered = register_type<CWrapper<CQuest>, CQuest, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay map content classes");
    }
    return registered;
}

bool register_controllers(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    registered = register_type<CFightController, CGameObject>(game) && registered;
    registered = register_type<CPlayerFightController, CFightController, CGameObject>(game) && registered;
    registered = register_type<CMonsterFightController, CFightController, CGameObject>(game) && registered;
    registered = register_type<CController, CGameObject>(game) && registered;
    registered = register_type<CTargetController, CController, CGameObject>(game) && registered;
    registered = register_type<CRandomController, CController, CGameObject>(game) && registered;
    registered = register_type<CGroundController, CController, CGameObject>(game) && registered;
    registered = register_type<CRangeController, CController, CGameObject>(game) && registered;
    registered = register_type<CNpcRandomController, CController, CGameObject>(game) && registered;
    registered = register_type<CPlayerController, CController, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay controller classes");
    }
    return registered;
}

bool register_creatures(const NativePluginHostV1 *host) {
    auto *game = host_game(host);
    bool registered = true;
    // Register the race archetype definition before the concrete creatures. It
    // derives from CGameObject (not CCreature), so configured race IDs are
    // constructible while the class stays out of CCreature inheritance and the
    // random-encounter / getAllSubTypes("CCreature") enumeration.
    registered = register_type<CCreatureRace, CGameObject>(game) && registered;
    // The creature class definition is likewise a CGameObject-derived archetype,
    // not a CCreature, so it stays out of the encounter / subtype enumeration.
    registered = register_type<CCreatureClass, CGameObject>(game) && registered;
    // The multiclass class-track record (EPIC_08 future mechanics) pairs a
    // CCreatureClass reference with a per-track level; like the other metadata
    // definitions it is never spawnable and never a CCreature subtype.
    registered = register_type<CCreatureClassTrack, CGameObject>(game) && registered;
    // The template overlay definition (elite/undead/... variants, EPIC_08) is also
    // a CGameObject-derived metadata definition referenced via CCreature.templates;
    // it is never spawnable and never a CCreature subtype.
    registered = register_type<CCreatureTemplate, CGameObject>(game) && registered;
    registered = register_type<CCreature, CMapObject, CGameObject>(game) && registered;
    registered = register_type<CPlayer, CCreature, CMapObject, CGameObject>(game) && registered;
    if (registered) {
        log(host, "registered native gameplay creature classes");
    }
    return registered;
}

} // namespace native_plugin
