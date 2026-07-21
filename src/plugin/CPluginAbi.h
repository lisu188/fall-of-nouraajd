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

#include <stdbool.h>
#include <stdint.h>

#if defined(_WIN32)
#define GAME_PLUGIN_EXPORT __declspec(dllexport)
#elif defined(__GNUC__) || defined(__clang__)
#define GAME_PLUGIN_EXPORT __attribute__((visibility("default")))
#else
#define GAME_PLUGIN_EXPORT
#endif

#ifdef __cplusplus
extern "C" {
#endif

// The native plugin entry handshake. The host constructs a CPluginHostV2 on the stack, resolves
// the entry symbol (default "game_plugin_load_v2"), and invokes it once. The registrar pointer is
// valid only for the duration of that call.
//
// In-tree native plugins are trusted, engine-linked modules; the real host surface is the C++
// CPluginRegistrar (plugin/CPluginRegistrar.h) reached through game_plugin_registrar() below.
// The handshake stays extern "C" so version mismatches, missing symbols, and load failures remain
// detectable and testable without any C++ ABI assumptions.
//
// Plugins are load-only by design: there is no unload entry. Registration donates factories and
// serializers into process-global tables and per-game closures whose code lives in the plugin
// module, and scripted runtimes retain object instances for the engine's lifetime, so unloading
// a module could never be memory-safe. Loaded libraries stay pinned until process exit.
enum { GAME_PLUGIN_API_VERSION = 2 };

typedef struct CPluginHostV2 {
    uint32_t api_version;
    void *registrar; /* CPluginRegistrar*, valid only during the load call */
} CPluginHostV2;

typedef bool (*CPluginLoadV2)(const CPluginHostV2 *host);

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
class CPluginRegistrar;

inline CPluginRegistrar *game_plugin_registrar(const CPluginHostV2 *host) {
    if (host == nullptr || host->api_version != GAME_PLUGIN_API_VERSION || host->registrar == nullptr) {
        return nullptr;
    }
    return static_cast<CPluginRegistrar *>(host->registrar);
}
#endif
