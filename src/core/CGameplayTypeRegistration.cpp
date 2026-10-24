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
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "core/CGame.h"
#include "core/CController.h"
#include "core/CWrapper.h"
#include "handler/CEventHandler.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "object/CDialog.h"
#include "object/CMarket.h"
#include "object/CObject.h"
#include "object/CPlayer.h"
#include "core/CGameplayTypeTable.h"
#include "handler/CObjectHandler.h"

namespace {

template <fn::MetaRegisteredGameObject T, fn::GameObjectDerived... Bases>
void registerGameplayType(const std::shared_ptr<CObjectHandler> &handler) {
    CTypes::register_type<T, Bases...>();
    handler->registerNativeType(T::static_meta()->name(), [] { return std::make_shared<T>(); });
}

} // namespace

namespace type_registration {

void registerGameplayTypeMetadata() {
#define FN_TYPE(T, ...) CTypes::register_type_metadata<T, __VA_ARGS__>();
#define FN_WRAPPED(T, ...)                                                                                             \
    CTypes::register_type_metadata<T, __VA_ARGS__>();                                                                  \
    CTypes::register_type_metadata<CWrapper<T>, T, __VA_ARGS__>();
    FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)
#undef FN_WRAPPED
#undef FN_TYPE
}

void registerGameplayTypes(const std::shared_ptr<CGame> &game) {
    const auto handler = game->getObjectHandler();
#define FN_TYPE(T, ...) registerGameplayType<T, __VA_ARGS__>(handler);
#define FN_WRAPPED(T, ...)                                                                                             \
    registerGameplayType<T, __VA_ARGS__>(handler);                                                                      \
    registerGameplayType<CWrapper<T>, T, __VA_ARGS__>(handler);
    FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)
#undef FN_WRAPPED
#undef FN_TYPE
}

} // namespace type_registration
