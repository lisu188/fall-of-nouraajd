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
#include <memory>
#include <optional>
#include <string>

class CGame;

// One parsed manifest entry (or auto-discovered plugin), normalized across kinds.
struct CPluginDescriptor {
    std::string id;
    std::string kind;   // "native" | "cpp" | "python" | "lua"
    std::string source; // native: library path; cpp: CPlugin type name; python/lua: resource path
    std::string entry;  // native entry symbol; empty selects the default
    std::optional<std::string> mapScope;
};

// A per-language plugin loading backend. The registry below is the seam new plugin languages
// plug into: implement the interface, register the runtime, and manifest entries of that kind
// load through it.
class IPluginRuntime {
  public:
    virtual ~IPluginRuntime() = default;

    virtual std::string kind() const = 0;

    virtual bool load(const std::shared_ptr<CGame> &game, const CPluginDescriptor &descriptor) = 0;
};

namespace plugin_runtime {

GAME_CORE_EXPORT void registerRuntime(const std::shared_ptr<IPluginRuntime> &runtime);

GAME_CORE_EXPORT IPluginRuntime *find(const std::string &kind);

// Idempotent; called lazily by the plugin loader before dispatching manifest entries, so runtime
// availability never depends on static initialization order.
GAME_CORE_EXPORT void registerBuiltinRuntimes();

// The native (shared library) backend, implemented in CNativePluginRuntime.cpp. Also backs the
// CPluginLoader::loadDynamicPlugin surface exposed to Python and tests.
GAME_CORE_EXPORT bool loadNativePlugin(const std::shared_ptr<CGame> &game, const std::string &library,
                                       const std::string &entry);

} // namespace plugin_runtime
