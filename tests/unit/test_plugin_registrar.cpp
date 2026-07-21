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

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CPlugin.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "handler/CEventHandler.h"
#include "handler/CObjectHandler.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "object/CDialog.h"
#include "object/CMarket.h"
#include "object/CObject.h"
#include "object/CPlayer.h"
#include "plugin/CGameplayTypeTable.h"
#include "plugin/CPluginAbi.h"
#include "plugin/CPluginRegistrar.h"
#include "plugin/NativePlugin.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <memory>
#include <string>

namespace {

// The registrar performs the engine's canonical double registration: process-global CTypes
// tables plus the per-game CObjectHandler factory that JSON {"class": name} construction reads.
void test_registrar_registers_types_and_factories() {
    auto game = std::make_shared<CGame>();
    CPluginRegistrar registrar(game);

    expect_true(registrar.registerType<CEffect, CGameObject>(),
                "registerType must succeed for a reflected gameplay type");
    auto handler = game->getObjectHandler();
    auto effect = handler->getType("CEffect");
    expect_true(effect != nullptr, "a registered type name must construct an instance");
    expect_true(effect->meta()->name() == "CEffect", "the constructed instance reports its meta name");
    expect_true(handler->getType("CDefinitelyMissingType") == nullptr,
                "an unregistered type name must construct nothing (negative control)");
}

void test_registrar_rejects_invalid_arguments() {
    auto game = std::make_shared<CGame>();
    CPluginRegistrar registrar(game);

    expect_true(!registrar.registerFactory("", []() { return std::make_shared<CGameObject>(); }),
                "registerFactory must reject an empty type name");
    expect_true(!registrar.registerFactory("CProbe", nullptr), "registerFactory must reject a missing factory");
    expect_true(!registrar.registerConfigJson("", "{}"), "registerConfigJson must reject an empty id");
    expect_true(!registrar.registerConfigJson("probe", ""), "registerConfigJson must reject empty json text");
    expect_true(!registrar.registerConfigJson("probe", "definitely { not json"),
                "registerConfigJson must reject unparseable json");
    expect_true(!registrar.registerConfigJson("probe", "[1, 2]"),
                "registerConfigJson must reject json that is not an object");

    CPluginRegistrar orphan(nullptr);
    expect_true(!orphan.registerFactory("CProbe", []() { return std::make_shared<CGameObject>(); }),
                "a registrar without a game must reject factory registration");
    expect_true(!orphan.registerConfigJson("probe", "{}"),
                "a registrar without a game must reject config registration");
    orphan.log("logging without a game must not crash");
}

void test_registrar_registers_config_json() {
    auto game = std::make_shared<CGame>();
    CPluginRegistrar registrar(game);
    // A bare CGame skips CGameLoader::initObjectHandler, so install the base factory the
    // config's {"class": "CGameObject"} construction needs.
    registrar.registerFactory("CGameObject", []() { return std::make_shared<CGameObject>(); });

    expect_true(
        registrar.registerConfigJson("registrarProbeConfig",
                                     R"json({"class": "CGameObject", "properties": {"registrarProbe": true}})json"),
        "registerConfigJson must accept a valid object config");
    auto probe = game->createObject<CGameObject>("registrarProbeConfig");
    expect_true(probe != nullptr, "a registered config id must be constructible");
    expect_true(probe != nullptr && probe->getBoolProperty("registrarProbe"),
                "config properties must round-trip through construction");
}

// Every row of plugin/CGameplayTypeTable.h must be constructible after
// register_gameplay_types, and exactly the FN_WRAPPED rows must also register their
// CWrapper<T> scripting trampolines.
void test_gameplay_type_table_registration() {
    auto game = std::make_shared<CGame>();
    CPluginRegistrar registrar(game);
    expect_true(native_plugin::register_gameplay_types(registrar),
                "register_gameplay_types must register the whole table");

    auto handler = game->getObjectHandler();
    // The generic CWrapper<T> template reflects under the literal meta name "CWrapper<T>" (only
    // explicit specializations carry their instantiated name), so wrapper registration is
    // asserted through static_meta() rather than a spelled-out string.
#define FN_CHECK_TYPE(T, ...)                                                                                          \
    expect_true(handler->getType(#T) != nullptr, #T " from the gameplay type table must be constructible");
#define FN_CHECK_WRAPPED(T, ...)                                                                                       \
    FN_CHECK_TYPE(T)                                                                                                   \
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

void test_plugin_host_v2_handshake() {
    auto game = std::make_shared<CGame>();
    CPluginRegistrar registrar(game);

    CPluginHostV2 host{GAME_PLUGIN_API_VERSION, &registrar};
    expect_true(game_plugin_registrar(&host) == &registrar, "a matching api version must hand back the registrar");

    CPluginHostV2 badVersion{GAME_PLUGIN_API_VERSION + 1, &registrar};
    expect_true(game_plugin_registrar(&badVersion) == nullptr, "a version mismatch must be rejected");

    CPluginHostV2 nullRegistrar{GAME_PLUGIN_API_VERSION, nullptr};
    expect_true(game_plugin_registrar(&nullRegistrar) == nullptr, "a null registrar must be rejected");
    expect_true(game_plugin_registrar(nullptr) == nullptr, "a null host must be rejected");
}

void test_cpp_plugin_loads_through_registrar() {
    auto game = std::make_shared<CGame>();
    CPluginRegistrar registrar(game);

    registrar.registerFactory("CGameObject", []() { return std::make_shared<CGameObject>(); });
    CNativeContentPlugin plugin;
    plugin.load(registrar);
    auto marker = game->createObject<CGameObject>("nativePluginMarker");
    expect_true(marker != nullptr, "CNativeContentPlugin must register its marker config via the registrar");
    expect_true(marker != nullptr && marker->getStringProperty("label") == "Native plugin marker",
                "the marker keeps its label through the registrar path");
    expect_true(marker != nullptr && marker->getBoolProperty("nativePluginLoaded"),
                "the marker keeps its bool property");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_registrar_registers_types_and_factories();
    test_registrar_rejects_invalid_arguments();
    test_registrar_registers_config_json();
    test_gameplay_type_table_registration();
    test_plugin_host_v2_handshake();
    test_cpp_plugin_loads_through_registrar();

    return finish_tests();
}
