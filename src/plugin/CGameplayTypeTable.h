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

// The single source of truth for content-constructible gameplay types.
//
// Every consumer expands this table instead of maintaining its own list:
//   - native_plugin::register_gameplay_types (src/plugin/NativePlugin.cpp): builders + factories
//   - register_python_binding_type_metadata (src/core/CModule.cpp): serializer/cast metadata
//   - cast_registered_python_object (src/core/CModule.cpp): Python downcast dispatch
//   - scripts/validate_content.py: parses the rows textually to cross-check config class refs
//
// Row format (one row per line, parsed by scripts/validate_content.py — do not wrap or inline):
//   FN_TYPE(T, Bases...)    content-constructible gameplay type; Bases... is the full base chain
//                           up to CGameObject, most-derived first
//   FN_WRAPPED(T, Bases...) same, and T additionally gets a CWrapper<T> scripting trampoline
//                           registered as CWrapper<T> -> T -> Bases... plus Python downcast dispatch
//
// Order invariant: no FN_WRAPPED type derives from another FN_WRAPPED type, so downcast dispatch
// generated from this table is order-independent. Types intentionally NOT constructible from
// content are listed in type_registration_exclusions.json instead of here.
//
// This header defines macros only; consumers must include the object headers themselves.

// clang-format off
#define FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)                                                     \
    FN_WRAPPED(CEffect, CGameObject)                                                               \
    FN_WRAPPED(CInteraction, CGameObject)                                                          \
    FN_TYPE(CItem, CMapObject, CGameObject)                                                        \
    FN_TYPE(CWeapon, CItem, CMapObject, CGameObject)                                               \
    FN_TYPE(CSmallWeapon, CWeapon, CItem, CMapObject, CGameObject)                                 \
    FN_TYPE(CArmor, CItem, CMapObject, CGameObject)                                                \
    FN_WRAPPED(CPotion, CItem, CMapObject, CGameObject)                                            \
    FN_TYPE(CHelmet, CItem, CMapObject, CGameObject)                                               \
    FN_TYPE(CBoots, CItem, CMapObject, CGameObject)                                                \
    FN_TYPE(CBelt, CItem, CMapObject, CGameObject)                                                 \
    FN_TYPE(CGloves, CItem, CMapObject, CGameObject)                                               \
    FN_TYPE(CPants, CItem, CMapObject, CGameObject)                                                \
    FN_TYPE(CShield, CItem, CMapObject, CGameObject)                                               \
    FN_WRAPPED(CScroll, CItem, CMapObject, CGameObject)                                            \
    FN_WRAPPED(CTile, CGameObject)                                                                 \
    FN_TYPE(CMapObject, CGameObject)                                                               \
    FN_WRAPPED(CBuilding, CMapObject, CGameObject)                                                 \
    FN_WRAPPED(CEvent, CMapObject, CGameObject)                                                    \
    FN_TYPE(CMarket, CGameObject)                                                                  \
    FN_WRAPPED(CDialog, CGameObject)                                                               \
    FN_TYPE(CDialogOption, CGameObject)                                                            \
    FN_TYPE(CDialogState, CGameObject)                                                             \
    FN_WRAPPED(CTrigger, CGameObject)                                                              \
    FN_WRAPPED(CQuest, CGameObject)                                                                \
    FN_TYPE(CFightController, CGameObject)                                                         \
    FN_TYPE(CPlayerFightController, CFightController, CGameObject)                                 \
    FN_TYPE(CMonsterFightController, CFightController, CGameObject)                                \
    FN_TYPE(CController, CGameObject)                                                              \
    FN_TYPE(CTargetController, CController, CGameObject)                                           \
    FN_TYPE(CRandomController, CController, CGameObject)                                           \
    FN_TYPE(CGroundController, CController, CGameObject)                                           \
    FN_TYPE(CRangeController, CController, CGameObject)                                            \
    FN_TYPE(CNpcRandomController, CController, CGameObject)                                        \
    FN_TYPE(CPlayerController, CController, CGameObject)                                           \
    /* CCreatureRace/CCreatureClass/CCreatureClassTrack/CCreatureTemplate are CGameObject-derived archetype        */  \
    /* definitions, not CCreature subtypes, so configured IDs stay constructible while the     */  \
    /* classes stay out of random-encounter / getAllSubTypes("CCreature") enumeration.         */  \
    /* CCreatureTemplate is the elite/undead/... overlay referenced via CCreature.templates.   */  \
    FN_TYPE(CCreatureRace, CGameObject)                                                            \
    FN_TYPE(CCreatureClass, CGameObject)                                                           \
    FN_TYPE(CCreatureClassTrack, CGameObject)                                                      \
    FN_TYPE(CCreatureTemplate, CGameObject)                                                        \
    FN_TYPE(CCreature, CMapObject, CGameObject)                                                    \
    FN_TYPE(CPlayer, CCreature, CMapObject, CGameObject)
// clang-format on
