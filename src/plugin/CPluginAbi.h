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

enum { GAME_PLUGIN_API_VERSION = 1 };

typedef struct CPluginHostV1 {
    uint32_t api_version;
    void *game;
    void (*log)(void *game, const char *message);
    bool (*register_config_json)(void *game, const char *id, const char *json_text);
} CPluginHostV1;

typedef bool (*CPluginLoadV1)(const CPluginHostV1 *host);

#ifdef __cplusplus
}
#endif
