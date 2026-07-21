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
#include "core/CGlobal.h"
#include "core/CProvider.h"
#include "plugin/CPluginAbi.h"
#include "plugin/CPluginRegistrar.h"
#include "plugin/CPluginRuntime.h"

#include <filesystem>
#include <map>
#include <optional>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {

constexpr const char *NATIVE_PLUGIN_DEFAULT_ENTRY = "game_plugin_load_v2";

class CDynamicLibrary {
  public:
    explicit CDynamicLibrary(std::string path) : path(std::move(path)) {
#if defined(_WIN32)
        handle = LoadLibraryW(std::filesystem::path(this->path).wstring().c_str());
#else
        handle = dlopen(this->path.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
    }

    ~CDynamicLibrary() {
        if (!handle) {
            return;
        }
#if defined(_WIN32)
        FreeLibrary(handle);
#else
        dlclose(handle);
#endif
    }

    CDynamicLibrary(const CDynamicLibrary &) = delete;
    CDynamicLibrary &operator=(const CDynamicLibrary &) = delete;

    bool isLoaded() const { return handle != nullptr; }

    CPluginLoadV2 loadSymbol(const std::string &symbolName) const {
        if (!handle) {
            return nullptr;
        }

#if defined(_WIN32)
        auto symbol = GetProcAddress(handle, symbolName.c_str());
        if (!symbol) {
            vstd::logger::warning("Failed to find dynamic plugin symbol:", symbolName, "in:", path,
                                  "error code:", static_cast<int>(GetLastError()));
            return nullptr;
        }
        return reinterpret_cast<CPluginLoadV2>(symbol);
#else
        dlerror();
        auto symbol = dlsym(handle, symbolName.c_str());
        const char *error = dlerror();
        if (error != nullptr) {
            vstd::logger::warning("Failed to find dynamic plugin symbol:", symbolName, "in:", path, "error:", error);
            return nullptr;
        }
        return reinterpret_cast<CPluginLoadV2>(symbol);
#endif
    }

    const std::string &getPath() const { return path; }

  private:
    std::string path;
#if defined(_WIN32)
    HMODULE handle = nullptr;
#else
    void *handle = nullptr;
#endif
};

std::optional<std::string> normalize_relative_library_path(const std::string &path) {
    const std::filesystem::path resourcePath(path);
    if (path.empty() || resourcePath.is_absolute() || resourcePath.has_root_name()) {
        return std::nullopt;
    }

    const auto normalized = resourcePath.lexically_normal().generic_string();
    if (normalized.empty() || normalized == "." || normalized == ".." || normalized.rfind("../", 0) == 0 ||
        normalized.find("/../") != std::string::npos) {
        return std::nullopt;
    }
    return normalized;
}

std::string dynamic_library_suffix() {
#if defined(_WIN32)
    return ".dll";
#elif defined(__APPLE__)
    return ".dylib";
#else
    return ".so";
#endif
}

std::vector<std::string> dynamic_library_candidates(const std::string &library) {
    std::vector<std::string> candidates{library};
    if (std::filesystem::path(library).extension().empty()) {
        candidates.push_back(library + dynamic_library_suffix());
    }
    return candidates;
}

bool is_allowed_dynamic_library_path(const std::string &library) {
    const auto normalized = normalize_relative_library_path(library);
    return normalized && normalized->rfind("plugins/native/", 0) == 0;
}

std::string resolve_dynamic_library_path(const std::shared_ptr<CResourcesProvider> &resourcesProvider,
                                         const std::string &library) {
    if (!is_allowed_dynamic_library_path(library)) {
        vstd::logger::warning("Rejected dynamic C++ plugin outside packaged native plugin paths:", library);
        return {};
    }

    for (const auto &candidate : dynamic_library_candidates(library)) {
        if (!is_allowed_dynamic_library_path(candidate)) {
            continue;
        }
        auto resolved = resourcesProvider->getPath(candidate);
        if (!resolved.empty()) {
            return std::filesystem::absolute(resolved).lexically_normal().string();
        }
    }
    return {};
}

CDynamicLibrary *load_dynamic_library(const std::string &path) {
    // Loaded libraries stay pinned for the process lifetime by design: registered factories and
    // serializers reference code inside the module, so unloading could never be memory-safe.
    static std::map<std::string, std::unique_ptr<CDynamicLibrary>> libraries;

    auto existing = libraries.find(path);
    if (existing != libraries.end()) {
        return existing->second.get();
    }

    auto library = std::make_unique<CDynamicLibrary>(path);
    if (!library->isLoaded()) {
#if defined(_WIN32)
        vstd::logger::warning("Failed to load dynamic plugin library:", path,
                              "error code:", static_cast<int>(GetLastError()));
#else
        const char *error = dlerror();
        vstd::logger::warning("Failed to load dynamic plugin library:", path,
                              "error:", error == nullptr ? "<unknown>" : error);
#endif
        return nullptr;
    }

    auto inserted = libraries.emplace(path, std::move(library));
    return inserted.first->second.get();
}

} // namespace

namespace plugin_runtime {

bool loadNativePlugin(const std::shared_ptr<CGame> &game, const std::string &library, const std::string &entry) {
    if (!game || library.empty()) {
        vstd::logger::warning("Cannot load dynamic C++ plugin without a game and library path");
        return false;
    }

    const auto symbolName = entry.empty() ? std::string(NATIVE_PLUGIN_DEFAULT_ENTRY) : entry;
    const auto resolvedPath = resolve_dynamic_library_path(game->getResourcesProvider(), library);
    if (resolvedPath.empty()) {
        vstd::logger::warning("Failed to resolve dynamic C++ plugin library:", library);
        return false;
    }

    auto *dynamicLibrary = load_dynamic_library(resolvedPath);
    if (!dynamicLibrary) {
        return false;
    }

    auto entrypoint = dynamicLibrary->loadSymbol(symbolName);
    if (!entrypoint) {
        return false;
    }

    CPluginRegistrar registrar(game);
    CPluginHostV2 host{GAME_PLUGIN_API_VERSION, &registrar};
    try {
        if (!entrypoint(&host)) {
            vstd::logger::warning("Dynamic C++ plugin entrypoint returned false:", library, symbolName);
            return false;
        }
        return true;
    } catch (const std::exception &exception) {
        vstd::logger::warning("Failed to load dynamic C++ plugin:", library, symbolName, exception.what());
    } catch (...) {
        vstd::logger::warning("Failed to load dynamic C++ plugin:", library, symbolName);
    }
    return false;
}

} // namespace plugin_runtime
