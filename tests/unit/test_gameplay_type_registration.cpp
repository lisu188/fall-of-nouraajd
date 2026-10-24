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

#include "core/CGame.h"
#include "core/CTypeRegistration.h"
#include "core/CGameplayTypeTable.h"
#include "core/CWrapper.h"
#include "handler/CObjectHandler.h"
#include "object/CPlayer.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <memory>
#include <set>

namespace {

void test_types_are_not_constructible_without_factory_registration() {
    auto game = std::make_shared<CGame>();
    expect_true(game->getObjectHandler()->getType("CPlayer") == nullptr,
                "gameplay metadata alone must not register per-game object factories");
}

void test_gameplay_type_table_registration() {
    auto game = std::make_shared<CGame>();
    type_registration::registerGameplayTypes(game);

    auto handler = game->getObjectHandler();
    std::set<std::string> wrapperNames;
#define FN_CHECK_TYPE(T, ...)                                                                                          \
    expect_true(handler->getType(#T) != nullptr, #T " from the gameplay type table must be constructible");
#define FN_CHECK_WRAPPED(T, ...)                                                                                       \
    FN_CHECK_TYPE(T)                                                                                                   \
    expect_true(wrapperNames.insert(CWrapper<T>::static_meta()->name()).second,                                        \
                "CWrapper<" #T "> must have a unique reflected type name");                                            \
    expect_true(handler->getType(CWrapper<T>::static_meta()->name()) != nullptr,                                       \
                "CWrapper<" #T "> must be registered for the scripted base " #T);
    FN_GAMEPLAY_TYPES(FN_CHECK_TYPE, FN_CHECK_WRAPPED)
#undef FN_CHECK_WRAPPED
#undef FN_CHECK_TYPE

    expect_true(handler->getType("CWrapper<CItem>") == nullptr,
                "plain table rows must not grow scripting trampolines (negative control)");

    auto player = handler->getType("CPlayer");
    expect_true(player != nullptr && player->meta()->inherits("CCreature"),
                "CPlayer metadata must declare its CCreature base chain");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    test_types_are_not_constructible_without_factory_registration();
    test_gameplay_type_table_registration();
    return finish_tests();
}
