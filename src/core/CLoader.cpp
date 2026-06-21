/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "core/CLoader.h"
#include "core/CController.h"
#include "core/CGameContext.h"
#include "core/CJsonUtil.h"
#include "core/CSaveFormat.h"
#include "core/CSceneManager.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/object/CMapGraphicsObject.h"
#include "handler/CRngHandler.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "plugin/CPluginAbi.h"
#include <pybind11/eval.h>
#include <rdg.h>

#include <algorithm>
#include <cctype>
#include <optional>
#include <utility>

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

std::set<std::string> getConfigPaths(const std::string &mapName);

std::string getMapPath(std::string mapName);

std::set<std::string> get_saved_map_dependencies(const json &save, const std::string &mapName);

void load_map_resources(const std::shared_ptr<CGame> &game, const std::string &mapName);

namespace {
constexpr const char *PLUGIN_MANIFEST_PATH = "plugins/manifest.json";
constexpr const char *DYNAMIC_PLUGIN_DEFAULT_ENTRY = "game_plugin_load_v1";
constexpr std::size_t MAX_TILESET_ID = 16384;
constexpr int MAX_TMX_LAYER_CELLS = 1'000'000;

struct SaveLoadResult {
    std::shared_ptr<CMap> map;
    std::string sourcePath;
    bool recoveredFromBackup = false;
};

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

    CPluginLoadV1 loadSymbol(const std::string &symbolName) const {
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
        return reinterpret_cast<CPluginLoadV1>(symbol);
#else
        dlerror();
        auto symbol = dlsym(handle, symbolName.c_str());
        const char *error = dlerror();
        if (error != nullptr) {
            vstd::logger::warning("Failed to find dynamic plugin symbol:", symbolName, "in:", path, "error:", error);
            return nullptr;
        }
        return reinterpret_cast<CPluginLoadV1>(symbol);
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

std::optional<std::string> normalize_relative_resource_path(const std::string &path) {
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

bool is_allowed_python_plugin_path(const std::string &path) {
    const auto normalized = normalize_relative_resource_path(path);
    if (!normalized || !vstd::ends_with(*normalized, ".py")) {
        return false;
    }

    const std::filesystem::path pluginPath(*normalized);
    if (normalized->rfind("plugins/", 0) == 0) {
        return true;
    }

    if (pluginPath.filename() != "script.py") {
        return false;
    }
    auto parent = pluginPath.parent_path();
    if (parent.parent_path() != "maps") {
        return false;
    }
    return CSaveFormat::isValidMapName(parent.filename().string());
}

bool is_safe_proxy_attr(const std::string &name) {
    return name != "__builtins__" && name != "__cached__" && name != "__file__" && name != "__loader__" &&
           name != "__spec__";
}

pybind11::dict build_restricted_plugin_builtins();

PyObject *build_safe_proxy_module(const std::string &name) {
    pybind11::object moduleName = pybind11::str(name);
    PyObject *modulePtr = PyImport_GetModule(moduleName.ptr());
    if (modulePtr == nullptr) {
        PyErr_Format(PyExc_ImportError, "Allowed Python resource plugin module is not initialized: %s", name.c_str());
        return nullptr;
    }

    pybind11::module_ realModule = pybind11::reinterpret_steal<pybind11::module_>(modulePtr);
    pybind11::module_ proxy = pybind11::reinterpret_steal<pybind11::module_>(PyModule_New(name.c_str()));
    pybind11::dict realDict = realModule.attr("__dict__");

    for (const auto &item : realDict) {
        const auto attrName = pybind11::str(item.first).cast<std::string>();
        if (is_safe_proxy_attr(attrName)) {
            proxy.attr(attrName.c_str()) = pybind11::reinterpret_borrow<pybind11::object>(item.second);
        }
    }
    proxy.attr("__name__") = name;
    proxy.attr("__package__") = pybind11::none();
    proxy.attr("__builtins__") = build_restricted_plugin_builtins();
    return proxy.release().ptr();
}

PyObject *restricted_plugin_import(PyObject *, PyObject *args, PyObject *kwargs) {
    const char *name = nullptr;
    PyObject *globals = nullptr;
    PyObject *locals = nullptr;
    PyObject *fromlist = nullptr;
    int level = 0;
    static const char *keywords[] = {"name", "globals", "locals", "fromlist", "level", nullptr};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|OOOi:__import__", const_cast<char **>(keywords), &name, &globals,
                                     &locals, &fromlist, &level)) {
        return nullptr;
    }

    if (level != 0) {
        PyErr_SetString(PyExc_ImportError, "Python resource plugins may not use relative imports");
        return nullptr;
    }

    if (std::string(name) == "game" || std::string(name) == "json") {
        return build_safe_proxy_module(name);
    }

    PyErr_SetString(PyExc_ImportError, "Python resource plugins may only import the game and json modules");
    return nullptr;
}

pybind11::dict build_restricted_plugin_builtins() {
    pybind11::dict safeBuiltins;
    PyObject *builtins = PyEval_GetBuiltins();
    if (builtins == nullptr || !PyDict_Check(builtins)) {
        vstd::logger::warning("Failed to read Python builtins for resource plugin sandbox");
        return safeBuiltins;
    }

    const std::vector<std::string> allowedNames = {"__build_class__",
                                                   "abs",
                                                   "all",
                                                   "any",
                                                   "bool",
                                                   "callable",
                                                   "classmethod",
                                                   "dict",
                                                   "enumerate",
                                                   "Exception",
                                                   "float",
                                                   "getattr",
                                                   "hasattr",
                                                   "int",
                                                   "isinstance",
                                                   "len",
                                                   "list",
                                                   "max",
                                                   "min",
                                                   "print",
                                                   "property",
                                                   "range",
                                                   "RuntimeError",
                                                   "set",
                                                   "setattr",
                                                   "staticmethod",
                                                   "sorted",
                                                   "str",
                                                   "sum",
                                                   "super",
                                                   "tuple",
                                                   "TypeError",
                                                   "ValueError"};

    for (const auto &name : allowedNames) {
        PyObject *value = PyDict_GetItemString(builtins, name.c_str());
        if (value != nullptr) {
            safeBuiltins[pybind11::str(name)] = pybind11::reinterpret_borrow<pybind11::object>(value);
        }
    }
    static PyMethodDef importMethod = {"__import__", reinterpret_cast<PyCFunction>(restricted_plugin_import),
                                       METH_VARARGS | METH_KEYWORDS,
                                       "Import allow-listed modules for Python resource plugins."};
    safeBuiltins["__import__"] = pybind11::reinterpret_steal<pybind11::object>(PyCFunction_New(&importMethod, nullptr));
    return safeBuiltins;
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
    const auto normalized = normalize_relative_resource_path(library);
    return normalized && normalized->rfind("plugins/native/", 0) == 0;
}

std::string resolve_dynamic_library_path(const std::string &library) {
    if (!is_allowed_dynamic_library_path(library)) {
        vstd::logger::warning("Rejected dynamic C++ plugin outside packaged native plugin paths:", library);
        return {};
    }

    auto provider = CResourcesProvider::getInstance();
    for (const auto &candidate : dynamic_library_candidates(library)) {
        if (!is_allowed_dynamic_library_path(candidate)) {
            continue;
        }
        auto resolved = provider->getPath(candidate);
        if (!resolved.empty()) {
            return std::filesystem::absolute(resolved).lexically_normal().string();
        }
    }
    return {};
}

CDynamicLibrary *load_dynamic_library(const std::string &path) {
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

void dynamic_plugin_log(void *, const char *message) {
    vstd::logger::info("Dynamic plugin:", message == nullptr ? "<null>" : message);
}

bool dynamic_plugin_register_config_json(void *opaqueGame, const char *id, const char *jsonText) {
    if (opaqueGame == nullptr || id == nullptr || id[0] == '\0' || jsonText == nullptr) {
        vstd::logger::warning("Dynamic plugin attempted to register config without a game, id, or json text");
        return false;
    }

    auto *game = static_cast<CGame *>(opaqueGame);
    auto parsed = CJsonUtil::parse_expected(jsonText, std::string("dynamic plugin config ") + id);
    if (!parsed) {
        CJsonUtil::log_parse_error(parsed.error());
        return false;
    }
    if (!(*parsed)->is_object()) {
        vstd::logger::warning("Dynamic plugin config is not an object:", id);
        return false;
    }

    game->getObjectHandler()->registerConfig(id, *parsed);
    return true;
}

bool read_bool_property(const json &properties, const std::string &key) {
    if (!properties.count(key)) {
        return false;
    }
    const auto &value = properties[key];
    if (value.is_boolean()) {
        return value.get<bool>();
    }
    if (value.is_number_integer()) {
        return value.get<int>() != 0;
    }
    if (value.is_string()) {
        const auto text = value.get<std::string>();
        return text == "true" || text == "1";
    }
    return false;
}

std::optional<int> parse_int_text(const std::string &text) {
    if (text.empty()) {
        return std::nullopt;
    }
    try {
        size_t parsed = 0;
        int value = std::stoi(text, &parsed);
        if (parsed == text.size()) {
            return value;
        }
    } catch (...) {
    }
    return std::nullopt;
}

int read_int_value(const json &value, int fallback, const std::string &context) {
    if (value.is_number_integer()) {
        return value.get<int>();
    }
    if (value.is_string()) {
        if (auto parsed = parse_int_text(value.get<std::string>())) {
            return *parsed;
        }
    }
    vstd::logger::warning("Invalid integer value for", context, "- using", fallback);
    return fallback;
}

int read_int_property(const json &properties, const std::string &key, int fallback) {
    if (!properties.is_object() || !properties.contains(key)) {
        return fallback;
    }
    return read_int_value(properties[key], fallback, key);
}

std::string read_string_property(const json &properties, const std::string &key, const std::string &fallback = {}) {
    if (!properties.is_object() || !properties.contains(key)) {
        return fallback;
    }
    const auto &value = properties[key];
    return value.is_string() ? value.get<std::string>() : fallback;
}

int read_object_int(const json &object, const std::string &key, int fallback, const std::string &context) {
    if (!object.is_object() || !object.contains(key)) {
        return fallback;
    }
    return read_int_value(object[key], fallback, context);
}

std::string read_object_string(const json &object, const std::string &key, const std::string &fallback = {}) {
    if (!object.is_object() || !object.contains(key) || !object[key].is_string()) {
        return fallback;
    }
    return object[key].get<std::string>();
}

void apply_tile_layer_metadata(const std::shared_ptr<CMap> &map, const json &layer) {
    if (!layer.contains("properties") || !layer["properties"].is_object()) {
        vstd::logger::warning("Ignoring tile layer without object properties");
        return;
    }
    const json &layerProperties = layer["properties"];
    int level = read_int_property(layerProperties, "level", 0);

    auto default_tiles = map->getDefaultTiles();
    auto out_of_bounds_tiles = map->getOutOfBoundsTiles();
    auto x_bounds = map->getXBounds();
    auto y_bounds = map->getYBounds();
    auto wrap_x = map->getWrapX();
    auto wrap_y = map->getWrapY();

    default_tiles[level] = read_string_property(layerProperties, "default", "GrassTile");
    if (layerProperties.count("outOfBounds")) {
        out_of_bounds_tiles[level] = read_string_property(layerProperties, "outOfBounds", "MountainTile");
    }
    x_bounds[level] = std::max(0, read_int_property(layerProperties, "xBound", 0));
    y_bounds[level] = std::max(0, read_int_property(layerProperties, "yBound", 0));
    wrap_x[level] = read_bool_property(layerProperties, "wrapX") ? 1 : 0;
    wrap_y[level] = read_bool_property(layerProperties, "wrapY") ? 1 : 0;

    map->setDefaultTiles(default_tiles);
    map->setOutOfBoundsTiles(out_of_bounds_tiles);
    map->setXBounds(x_bounds);
    map->setYBounds(y_bounds);
    map->setWrapX(wrap_x);
    map->setWrapY(wrap_y);
}

std::vector<std::string> build_tile_types(const json &tileset) {
    std::size_t maxTileId = 0;
    for (const auto &[tileId, tileConfig] : tileset.items()) {
        (void)tileConfig;
        const auto parsedTileId = parse_int_text(tileId);
        if (parsedTileId && *parsedTileId > 0 && static_cast<std::size_t>(*parsedTileId) <= MAX_TILESET_ID) {
            maxTileId = std::max(maxTileId, static_cast<std::size_t>(*parsedTileId));
        } else if (parsedTileId && static_cast<std::size_t>(*parsedTileId) > MAX_TILESET_ID) {
            vstd::logger::warning("Skipping sparse tile id above limit:", tileId);
        }
    }

    std::vector<std::string> tileTypes(maxTileId + 1);
    for (const auto &[tileId, tileConfig] : tileset.items()) {
        const auto parsedTileId = parse_int_text(tileId);
        if (!parsedTileId || *parsedTileId < 0 || static_cast<std::size_t>(*parsedTileId) >= tileTypes.size()) {
            continue;
        }
        if (tileConfig.is_object() && tileConfig.contains("type") && tileConfig["type"].is_string()) {
            tileTypes[*parsedTileId] = tileConfig["type"].get<std::string>();
        }
    }
    return tileTypes;
}

std::expected<std::shared_ptr<json>, std::string> build_save_envelope(const std::shared_ptr<CMap> &map) {
    if (!map) {
        return std::unexpected("map is null");
    }

    auto snapshot = CSerialization::serialize<std::shared_ptr<json>>(map);
    return CSaveFormat::buildEnvelope(snapshot, map->getMapName());
}

void apply_authored_map_metadata(const std::shared_ptr<CMap> &map, const std::string &mapName) {
    if (!map) {
        return;
    }
    if (std::shared_ptr<json> mapc = CConfigurationProvider::getConfig(getMapPath(mapName))) {
        map->setDefaultTiles({});
        map->setOutOfBoundsTiles({});
        map->setXBounds({});
        map->setYBounds({});
        map->setWrapX({});
        map->setWrapY({});
        const json emptyObject = json::object();
        const json emptyArray = json::array();
        const json &mapProperties =
            mapc->contains("properties") && (*mapc)["properties"].is_object() ? (*mapc)["properties"] : emptyObject;
        map->setEntryX(read_int_property(mapProperties, "x", 0));
        map->setEntryY(read_int_property(mapProperties, "y", 0));
        map->setEntryZ(read_int_property(mapProperties, "z", 0));
        const json &layers = mapc->contains("layers") && (*mapc)["layers"].is_array() ? (*mapc)["layers"] : emptyArray;
        for (const auto &layer : layers) {
            if (layer.is_object() && layer.contains("type") && layer["type"].is_string() &&
                vstd::string_equals(layer["type"].get<std::string>(), "tilelayer")) {
                apply_tile_layer_metadata(map, layer);
            }
        }
    }
}

class CScopedGameMap {
  public:
    explicit CScopedGameMap(std::shared_ptr<CGame> game, std::shared_ptr<CMap> replacement = nullptr)
        : game(std::move(game)), previous(this->game ? this->game->getMap() : nullptr) {
        if (this->game) {
            this->game->setMap(std::move(replacement));
        }
    }

    ~CScopedGameMap() {
        if (game) {
            game->setMap(previous);
        }
    }

    CScopedGameMap(const CScopedGameMap &) = delete;
    CScopedGameMap &operator=(const CScopedGameMap &) = delete;

  private:
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> previous;
};

class CScopedObjectConfig {
  public:
    CScopedObjectConfig(std::shared_ptr<CObjectHandler> handler, std::string name, std::shared_ptr<json> value)
        : handler(std::move(handler)), name(std::move(name)) {
        if (this->handler) {
            previous = this->handler->getConfig(this->name);
            this->handler->registerConfig(this->name, std::move(value));
        }
    }

    ~CScopedObjectConfig() {
        if (!handler) {
            return;
        }
        if (previous) {
            handler->registerConfig(name, previous);
        } else {
            handler->unregisterConfig(name);
        }
    }

    CScopedObjectConfig(const CScopedObjectConfig &) = delete;
    CScopedObjectConfig &operator=(const CScopedObjectConfig &) = delete;

  private:
    std::shared_ptr<CObjectHandler> handler;
    std::string name;
    std::shared_ptr<json> previous;
};

bool rehydrate_loaded_map(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                          const std::string &mapName, std::string &error) {
    if (!game || !map) {
        error = "deserialized map is null";
        return false;
    }
    if (map->getMapName() != mapName) {
        error = "deserialized mapName does not match save envelope";
        return false;
    }

    apply_authored_map_metadata(map, mapName);

    return map->restorePlayerAfterLoad(error);
}

std::expected<std::shared_ptr<CMap>, std::string>
restore_save_document(const std::shared_ptr<CGame> &game, const CSaveFormat::DecodedDocument &saveDocument,
                      const std::string &slotName) {
    if (!game) {
        return std::unexpected("cannot restore save without a game");
    }

    {
        CScopedGameMap scopedMap(game);
        load_map_resources(game, saveDocument.mapName);
        for (const auto &requiredMap : get_saved_map_dependencies(*saveDocument.snapshot, saveDocument.mapName)) {
            if (requiredMap != saveDocument.mapName) {
                load_map_resources(game, requiredMap);
            }
        }
    }

    const auto saveConfigKey = CSaveFormat::savedMapConfigKey(slotName);
    CScopedObjectConfig scopedSaveConfig(game->getObjectHandler(), saveConfigKey, saveDocument.snapshot);

    std::shared_ptr<CMap> map;
    try {
        CSerialization::StrictScope strict;
        map = game->getObjectHandler()->createObject<CMap>(game, saveConfigKey);
    } catch (const std::exception &exception) {
        return std::unexpected(std::string("failed to deserialize saved map: ") + exception.what());
    }

    std::string rehydrateError;
    if (!rehydrate_loaded_map(game, map, saveDocument.mapName, rehydrateError)) {
        return std::unexpected(rehydrateError);
    }

    return map;
}

std::expected<std::shared_ptr<CMap>, std::string>
load_save_candidate(const std::shared_ptr<CGame> &game, const std::string &slotName, const std::string &path) {
    auto raw = CResourcesProvider::getInstance()->loadJson(path);
    if (!raw) {
        return std::unexpected("save file could not be read or parsed");
    }
    auto decoded = CSaveFormat::decodeDocument(raw);
    if (!decoded) {
        return std::unexpected(decoded.error());
    }
    if (decoded->encoding == CSaveFormat::Encoding::Legacy) {
        vstd::logger::info("Migrating legacy save in memory:", slotName, path);
    }
    return restore_save_document(game, *decoded, slotName);
}

std::optional<SaveLoadResult> try_load_saved_map(const std::shared_ptr<CGame> &game, const std::string &name) {
    if (!CSaveFormat::isValidSlotName(name)) {
        vstd::logger::warning("Rejected invalid save slot name during load:", name);
        return std::nullopt;
    }

    const auto primaryPath = CSaveFormat::primaryPath(name);
    auto primary = load_save_candidate(game, name, primaryPath);
    if (primary) {
        return SaveLoadResult{*primary, primaryPath, false};
    }

    vstd::logger::warning("Rejected primary save:", primaryPath, "reason:", primary.error());

    const auto backupPath = CSaveFormat::backupPath(name);
    auto backup = load_save_candidate(game, name, backupPath);
    if (backup) {
        vstd::logger::warning("Recovered save slot from backup:", name, backupPath);
        return SaveLoadResult{*backup, backupPath, true};
    }

    vstd::logger::warning("Rejected backup save:", backupPath, "reason:", backup.error());
    return std::nullopt;
}

void repair_recovered_backup(const SaveLoadResult &loaded, const std::string &slotName) {
    if (!loaded.recoveredFromBackup) {
        return;
    }
    const auto backupBytes = CResourcesProvider::getInstance()->load(loaded.sourcePath);
    if (backupBytes.empty()) {
        vstd::logger::warning("Recovered backup could not be read for primary repair:", slotName, loaded.sourcePath);
        return;
    }
    const auto primaryPath = CSaveFormat::primaryPath(slotName);
    std::error_code errorCode;
    const auto resolvedPrimaryPath = CResourcesProvider::getInstance()->getPath(primaryPath);
    if (!resolvedPrimaryPath.empty()) {
        std::filesystem::remove(resolvedPrimaryPath, errorCode);
    }
    if (!resolvedPrimaryPath.empty() && errorCode) {
        vstd::logger::warning("Recovered backup primary repair could not remove rejected primary:", slotName,
                              primaryPath, "resolved:", resolvedPrimaryPath, "reason:", errorCode.message());
        return;
    }
    if (CResourcesProvider::getInstance()->save(primaryPath, backupBytes)) {
        vstd::logger::warning("Repaired save primary from recovered backup:", slotName, primaryPath);
    } else {
        vstd::logger::warning("Failed to repair save primary from recovered backup:", slotName, primaryPath);
    }
}

std::shared_ptr<json> load_plugin_manifest() {
    auto provider = CResourcesProvider::getInstance();
    if (provider->getPath(PLUGIN_MANIFEST_PATH).empty()) {
        return nullptr;
    }
    return provider->loadJson(PLUGIN_MANIFEST_PATH);
}

bool load_plugin_entry(const std::shared_ptr<CGame> &game, const json &entry,
                       std::set<std::string> &loadedPythonPlugins, std::set<std::string> &loadedDynamicPlugins) {
    if (!entry.is_object()) {
        vstd::logger::warning("Ignoring non-object plugin manifest entry");
        return false;
    }

    std::string kind = entry.value("kind", std::string());
    if (kind.empty()) {
        kind = entry.value("type", std::string());
    }

    if (kind == "cpp") {
        const auto id = entry.value("id", std::string());
        return CPluginLoader::loadCppPlugin(game, id);
    }

    if (kind == "dynamic") {
        const auto id = entry.value("id", std::string());
        const auto library = entry.value("library", std::string());
        const auto symbol = entry.value("entry", std::string(DYNAMIC_PLUGIN_DEFAULT_ENTRY));
        if (id.empty() || library.empty()) {
            vstd::logger::warning("Ignoring dynamic plugin manifest entry without id or library");
            return false;
        }
        if (!loadedDynamicPlugins.insert(id).second) {
            return true;
        }
        return CPluginLoader::loadDynamicPlugin(game, library, symbol);
    }

    if (kind == "python") {
        const auto path = entry.value("path", std::string());
        if (path.empty()) {
            vstd::logger::warning("Ignoring Python plugin manifest entry without path");
            return false;
        }
        if (!loadedPythonPlugins.insert(path).second) {
            return true;
        }
        return CPluginLoader::loadPlugin(game, path);
    }

    vstd::logger::warning("Ignoring plugin manifest entry with unknown kind:", kind);
    return false;
}

bool load_plugin_entries(const std::shared_ptr<CGame> &game, const json &entries,
                         std::set<std::string> &loadedPythonPlugins, std::set<std::string> &loadedDynamicPlugins) {
    if (!entries.is_array()) {
        vstd::logger::warning("Ignoring non-array plugin manifest section");
        return false;
    }

    bool loadedAll = true;
    for (const auto &entry : entries) {
        loadedAll = load_plugin_entry(game, entry, loadedPythonPlugins, loadedDynamicPlugins) && loadedAll;
    }
    return loadedAll;
}

bool isLiveGuiSession(const std::shared_ptr<CGame> &game, const std::shared_ptr<CGameContext> &context,
                      const std::shared_ptr<CGui> &gui) {
    return game && context && context->isActive() && gui && gui->isActive() && game->getGui() == gui;
}
} // namespace

void CMapLoader::loadFromTmx(const std::shared_ptr<CMap> &map, const std::shared_ptr<json> &mapc) {
    if (mapc && mapc->is_object()) {
        const json emptyObject = json::object();
        const json emptyArray = json::array();
        const json &mapProperties =
            mapc->contains("properties") && (*mapc)["properties"].is_object() ? (*mapc)["properties"] : emptyObject;
        const json &mapLayers =
            mapc->contains("layers") && (*mapc)["layers"].is_array() ? (*mapc)["layers"] : emptyArray;
        map->setDefaultTiles({});
        map->setOutOfBoundsTiles({});
        map->setXBounds({});
        map->setYBounds({});
        map->setWrapX({});
        map->setWrapY({});
        map->setEntryX(read_int_property(mapProperties, "x", 0));
        map->setEntryY(read_int_property(mapProperties, "y", 0));
        map->setEntryZ(read_int_property(mapProperties, "z", 0));
        std::vector<std::string> tileTypes;
        if (mapc->contains("tilesets") && (*mapc)["tilesets"].is_array() && !(*mapc)["tilesets"].empty() &&
            (*mapc)["tilesets"][0].is_object() && (*mapc)["tilesets"][0].contains("tileproperties") &&
            (*mapc)["tilesets"][0]["tileproperties"].is_object()) {
            tileTypes = build_tile_types((*mapc)["tilesets"][0]["tileproperties"]);
        }
        for (const auto &layer : mapLayers) {
            if (layer.is_object() && layer.contains("type") && layer["type"].is_string() &&
                vstd::string_equals(layer["type"].get<std::string>(), "tilelayer")) {
                apply_tile_layer_metadata(map, layer);
                handleTileLayer(map, tileTypes, layer);
            }
        }
        for (const auto &layer : mapLayers) {
            if (layer.is_object() && layer.contains("type") && layer["type"].is_string() &&
                vstd::string_equals(layer["type"].get<std::string>(), "objectgroup")) {
                handleObjectLayer(map, layer);
            }
        }
    }
}

std::set<std::string> getConfigPaths(const std::string &mapName) {
    if (!CSaveFormat::isValidMapName(mapName)) {
        vstd::logger::warning("Rejected invalid map name while loading config:", mapName);
        return {};
    }

    const auto logicalMapPath = "maps/" + mapName;
    const auto resolvedMapPath = CResourcesProvider::getInstance()->getPath(logicalMapPath);
    std::error_code errorCode;
    if (resolvedMapPath.empty() || !std::filesystem::is_directory(resolvedMapPath, errorCode)) {
        vstd::logger::warning("Map config directory is missing:", logicalMapPath, "resolved:", resolvedMapPath);
        return {};
    }

    std::set<std::string> configPaths;
    for (const auto &entry : std::filesystem::directory_iterator(resolvedMapPath)) {
        if (!entry.is_regular_file(errorCode)) {
            continue;
        }
        const auto filename = entry.path().filename().generic_string();
        if (vstd::ends_with(filename, ".json") && filename != "map.json") {
            configPaths.insert(vstd::join({logicalMapPath, "/", filename}, ""));
        }
    }
    return configPaths;
}

std::string getScriptPath(std::string mapName) {
    if (!CSaveFormat::isValidMapName(mapName)) {
        vstd::logger::warning("Rejected invalid map name while resolving script:", mapName);
        return {};
    }

    std::string path = vstd::join({"maps/", std::move(mapName)}, "");
    return vstd::join({path, "/script.py"}, "");
}

std::string getMapPath(std::string mapName) {
    if (!CSaveFormat::isValidMapName(mapName)) {
        vstd::logger::warning("Rejected invalid map name while resolving map:", mapName);
        return {};
    }

    std::string path = vstd::join({"maps/", std::move(mapName)}, "");
    return vstd::join({path, "/map.json"}, "");
}

struct CSavedQuestRefs {
    std::set<std::string> classes;
    std::set<std::string> typeIds;
};

void collect_saved_quest(const json &quest, CSavedQuestRefs &refs) {
    if (!quest.is_object()) {
        return;
    }

    if (quest.contains("class") && quest["class"].is_string()) {
        refs.classes.insert(quest["class"].get<std::string>());
    }
    if (!quest.contains("properties") || !quest["properties"].is_object()) {
        return;
    }

    const json &properties = quest["properties"];
    for (const char *key : {"typeId", "name"}) {
        if (properties.contains(key) && properties[key].is_string()) {
            refs.typeIds.insert(properties[key].get<std::string>());
        }
    }
}

void collect_saved_quest_refs(const json &node, CSavedQuestRefs &refs) {
    if (node.is_object()) {
        if (node.contains("properties") && node["properties"].is_object()) {
            const json &properties = node["properties"];
            for (const char *journalProperty : {"quests", "completedQuests"}) {
                if (!properties.contains(journalProperty) || !properties[journalProperty].is_array()) {
                    continue;
                }
                for (const auto &quest : properties[journalProperty]) {
                    collect_saved_quest(quest, refs);
                }
            }
        }
        for (const auto &[key, value] : node.items()) {
            (void)key;
            collect_saved_quest_refs(value, refs);
        }
        return;
    }

    if (node.is_array()) {
        for (const auto &value : node) {
            collect_saved_quest_refs(value, refs);
        }
    }
}

bool config_matches_saved_quest_refs(const json &entry, const CSavedQuestRefs &refs) {
    if (!entry.is_object()) {
        return false;
    }
    if (entry.contains("class") && entry["class"].is_string() &&
        refs.classes.contains(entry["class"].get<std::string>())) {
        return true;
    }
    if (entry.contains("properties") && entry["properties"].is_object()) {
        const json &properties = entry["properties"];
        if (properties.contains("typeId") && properties["typeId"].is_string() &&
            refs.typeIds.contains(properties["typeId"].get<std::string>())) {
            return true;
        }
    }
    return false;
}

bool map_defines_saved_quest_refs(const std::string &mapName, const CSavedQuestRefs &refs) {
    for (const auto &configPath : getConfigPaths(mapName)) {
        auto config = CConfigurationProvider::getConfig(configPath);
        if (!config || !config->is_object()) {
            continue;
        }
        for (const auto &[key, entry] : config->items()) {
            if (refs.typeIds.contains(key) || config_matches_saved_quest_refs(entry, refs)) {
                return true;
            }
        }
    }
    return false;
}

std::set<std::string> get_saved_map_dependencies(const json &save, const std::string &mapName) {
    std::set<std::string> maps = {mapName};
    CSavedQuestRefs questRefs;
    collect_saved_quest_refs(save, questRefs);
    if (questRefs.classes.empty() && questRefs.typeIds.empty()) {
        return maps;
    }

    for (const auto &candidate : CResourcesProvider::getInstance()->getFiles(CResType::MAP)) {
        if (!CSaveFormat::isValidMapName(candidate)) {
            continue;
        }
        if (map_defines_saved_quest_refs(candidate, questRefs)) {
            maps.insert(candidate);
        }
    }
    return maps;
}

void load_map_resources(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
    CPluginLoader::loadMapPlugins(game, mapName);
    game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
}

std::shared_ptr<CMap> CMapLoader::loadNewMap(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    if (std::shared_ptr<json> mapc = CConfigurationProvider::getConfig(getMapPath(mapName))) {
        std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game);
        game->setMap(map);
        load_map_resources(game, mapName);
        loadFromTmx(map, mapc);
        map->setMapName(mapName);
        return map;
    }
    return game->getObjectHandler()->createObject<CMap>(game);
}

std::shared_ptr<CMap> CMapLoader::loadSavedMap(const std::shared_ptr<CGame> &game, const std::string &name) {
    if (auto loaded = try_load_saved_map(game, name)) {
        return loaded->map;
    }
    return game->getObjectHandler()->createObject<CMap>(game);
}

std::shared_ptr<CMap> CMapLoader::loadNewMapWithPlayer(const std::shared_ptr<CGame> &game, const std::string &name,
                                                       std::string player) {
    std::shared_ptr<CMap> map = loadNewMap(game, name);
    std::shared_ptr<CPlayer> ptr = createPlayer(game, player);
    map->setPlayer(ptr);

    return map;
}

// TODO: move to map, set player as well as triggers
std::shared_ptr<CPlayer> CMapLoader::createPlayer(const std::shared_ptr<CGame> &game, std::string &player) {
    auto ptr = game->createObject<CPlayer>(std::move(player));
    return ptr;
}

std::shared_ptr<CMap> CMapLoader::loadRandomMapWithPlayer(const std::shared_ptr<CGame> &game, std::string player) {
    std::shared_ptr<CMap> map = CRandomMapGenerator::loadRandomMap(game);
    std::shared_ptr<CPlayer> ptr = createPlayer(game, player);
    map->setPlayer(ptr);
    return map;
}

void CMapLoader::save(const std::shared_ptr<CMap> &map, const std::string &name) {
    if (!CSaveFormat::isValidSlotName(name)) {
        vstd::logger::warning("Rejected invalid save slot name during save:", name);
        return;
    }

    auto envelope = build_save_envelope(map);
    if (!envelope) {
        vstd::logger::warning("Rejected invalid save snapshot:", name, "reason:", envelope.error());
        return;
    }

    CResourcesProvider::getInstance()->save(CSaveFormat::primaryPath(name), CJsonUtil::to_string(*envelope, -1));
}

void CMapLoader::handleTileLayer(const std::shared_ptr<CMap> &map, const std::vector<std::string> &tileTypes,
                                 const json &layer) {
    if (!layer.is_object() || !layer.contains("properties") || !layer["properties"].is_object() ||
        !layer.contains("data") || !layer["data"].is_array()) {
        vstd::logger::warning("Skipping malformed tile layer");
        return;
    }
    const json &layerProperties = layer["properties"];
    const json &layerData = layer["data"];
    const auto game = map->getGame();
    int level = read_int_property(layerProperties, "level", 0);

    int width = read_object_int(layer, "width", 0, "tile layer width");
    int height = read_object_int(layer, "height", 0, "tile layer height");
    if (width <= 0 || height <= 0 || width > MAX_TMX_LAYER_CELLS / std::max(1, height)) {
        vstd::logger::warning("Skipping tile layer with invalid dimensions:", width, height);
        return;
    }
    if (layerData.size() < static_cast<std::size_t>(width * height)) {
        vstd::logger::warning("Skipping tile layer with too little data:", layerData.size(), "expected",
                              width * height);
        return;
    }

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int id = layerData[x + y * width].get<int>();
            if (id == 0) {
                continue;
            }
            id--;
            if (id < 0 || id >= static_cast<int>(tileTypes.size()) || tileTypes[id].empty()) {
                vstd::logger::warning("Skipping invalid tile id", id + 1, "at", x, y, "level", level);
                continue;
            }
            map->addTile(game->createObject<CTile>(tileTypes[id]), x, y, level);
        }
    }
}

void CMapLoader::handleObjectLayer(const std::shared_ptr<CMap> &map, const json &layer) {
    if (!layer.is_object() || !layer.contains("objects") || !layer["objects"].is_array()) {
        vstd::logger::warning("Skipping malformed object layer");
        return;
    }
    int level = layer.contains("properties") && layer["properties"].is_object()
                    ? read_int_property(layer["properties"], "level", 0)
                    : 0;
    const json &objects = layer["objects"];
    for (const auto &object : objects) {
        if (!object.is_object()) {
            continue;
        }
        auto objectType = read_object_string(object, "type");
        auto objectName = read_object_string(object, "name");
        const int objectWidth = read_object_int(object, "width", 0, "map object width");
        const int objectHeight = read_object_int(object, "height", 0, "map object height");
        if (objectType.empty() || objectWidth <= 0 || objectHeight <= 0) {
            vstd::logger::warning("Skipping malformed map object:", objectName);
            continue;
        }

        int xPos = read_object_int(object, "x", 0, "map object x") / objectWidth;
        int yPos = read_object_int(object, "y", 0, "map object y") / objectHeight;
        auto mapObject = map->getGame()->createObject<CMapObject>(objectType);
        if (mapObject == nullptr) {
            vstd::logger::debug("Failed to load object:", objectType, objectName);
            continue;
        }
        if (!vstd::is_empty(objectName)) {
            mapObject->setName(objectName);
        }
        if (object.contains("properties") && object["properties"].is_object()) {
            const json &objectProperties = object["properties"];
            CGameObject::PropertyNotificationBatch notificationBatch(*mapObject);
            for (auto &[key, value] : objectProperties.items()) {
                try {
                    CSerialization::setProperty(mapObject, key, CJsonUtil::clone(value));
                } catch (const std::exception &exception) {
                    vstd::logger::warning("Skipping malformed map object property:", key, exception.what());
                }
            }
        }
        mapObject->setPosX(xPos);
        mapObject->setPosY(yPos);
        mapObject->setPosZ(level);
        map->addObject(mapObject);
        vstd::logger::debug("Loaded object:", mapObject->to_string());
    }
}

std::shared_ptr<CMap> CRandomMapGenerator::loadRandomMap(const std::shared_ptr<CGame> &game) {
    auto map = CMapLoader::loadNewMap(game, "");

    // TODO: this should be passed
    auto options = rdg::Options();

    options.n_rows = 555;
    options.n_cols = 555;
    options.corridor_layout = rdg::CorridorLayout::BENT;

    auto dungeon = rdg::create_dungeon(options);
    const auto &container = dungeon.getStairs();
    auto stairs = vstd::any(container);

    if (stairs != container.end()) {
        map->setEntryX(stairs->row);
        map->setEntryY(stairs->col);
        map->setEntryZ(0);
    }

    generateTiles(map, dungeon);

    const auto &rooms = dungeon.getRooms();

    generateEncounters(game, map, rooms);

    return map;
}

void CRandomMapGenerator::generateEncounters(const std::shared_ptr<CGame> &game, std::shared_ptr<CMap> &map,
                                             const std::vector<rdg::Room> &rooms) {
    for (const auto &room : rooms) {
        auto roomCoords = Coords(room.row + room.width / 2, room.col + room.height / 2, 0);
        if (roomCoords.getDist(map->getEntry()) > 5) {
            for (const auto &creature : game->getRngHandler()->getRandomEncounter(5)) {
                map->addObject(creature, roomCoords);
            }
        }
    }
}

void CRandomMapGenerator::generateTiles(std::shared_ptr<CMap> &map, const rdg::Dungeon &dungeon) {
    for (int row = 0; row < dungeon.rowCount(); row++) {
        for (int col = 0; col < dungeon.colCount(); col++) {
            if (dungeon.cellAt(row, col).isOpenspace()) {
                map->addTile(map->getGame()->createObject<CTile>("GroundTile"), row, col, 0);
            } else {
                map->addTile(map->getGame()->createObject<CTile>("MountainTile"), row, col, 0);
            }
        }
    }
}

std::shared_ptr<CGame> CGameLoader::loadGame() {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    game->getResourcesProvider();
    game->getConfigurationProvider();
    initObjectHandler(game->getObjectHandler());
    initConfigurations(game->getObjectHandler());
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGameWithPlayer(const std::shared_ptr<CGame> &game, const std::string &file, std::string player) {
    game->setMap(CMapLoader::loadNewMapWithPlayer(game, file, std::move(player)));
}

void CGameLoader::startRandomGameWithPlayer(const std::shared_ptr<CGame> &game, std::string player) {
    game->setMap(CMapLoader::loadRandomMapWithPlayer(game, std::move(player)));
}

void CGameLoader::loadSavedGame(const std::shared_ptr<CGame> &game, const std::string &save) {
    if (auto loaded = try_load_saved_map(game, save)) {
        game->setMap(loaded->map);
        repair_recovered_backup(*loaded, save);
        return;
    }
    vstd::logger::warning("Saved game was not loaded; keeping the active map unchanged:", save);
}

void CGameLoader::startGame(const std::shared_ptr<CGame> &game, const std::string &file) {
    game->setMap(CMapLoader::loadNewMap(game, file));
}

void CGameLoader::changeMap(const std::shared_ptr<CGame> &game, const std::string &name) {
    if (!game) {
        vstd::logger::warning("Rejected map transition without a game:", name);
        return;
    }
    game->getSceneManager()->requestMapChange(game, name);
}

void CGameLoader::initConfigurations(const std::shared_ptr<CObjectHandler> &handler) {
    for (const std::string &path : CResourcesProvider::getInstance()->getFiles(CResType::CONFIG)) {
        handler->registerConfig(path);
    }
}

void CGameLoader::initObjectHandler(const std::shared_ptr<CObjectHandler> &handler) {
    for (const auto &it : *CTypes::builders()) {
        handler->registerType(it.first, it.second);
    }
}

void CGameLoader::initScriptHandler(const std::shared_ptr<CScriptHandler> &, const std::shared_ptr<CGame> &game) {
    CPluginLoader::loadGlobalPlugins(game);
}

void CGameLoader::loadGui(const std::shared_ptr<CGame> &game) {
    if (!game) {
        vstd::logger::warning("Failed to load GUI without a game");
        return;
    }
    auto context = game->getContext();
    if (!context->isActive()) {
        vstd::logger::warning("Failed to load GUI after game context shutdown");
        return;
    }

    std::shared_ptr<CGui> gui = game->createObject<CGui>("gui");
    if (!gui) {
        vstd::logger::warning("Failed to create GUI");
        return;
    }

    game->setGui(gui);

    std::weak_ptr<CGame> weakGame = game;
    std::weak_ptr<CGameContext> weakContext = context;
    std::weak_ptr<CGui> weakGui = gui;
    vstd::event_loop<>::instance()->registerFrameCallback([weakGame, weakContext, weakGui](int time) {
        auto game = weakGame.lock();
        auto context = weakContext.lock();
        auto gui = weakGui.lock();
        if (isLiveGuiSession(game, context, gui)) {
            gui->render(time);
        }
    });
    vstd::event_loop<>::instance()->registerEventCallback([weakGame, weakContext, weakGui](SDL_Event *event) {
        auto game = weakGame.lock();
        auto context = weakContext.lock();
        auto gui = weakGui.lock();
        return isLiveGuiSession(game, context, gui) && gui->event(event);
    });
}

bool CPluginLoader::loadPlugin(const std::shared_ptr<CGame> &game, const std::string &path) {
    if (!is_allowed_python_plugin_path(path)) {
        vstd::logger::warning("Rejected Python plugin outside trusted resource plugin paths:", path);
        return false;
    }
    try {
        std::string code = CResourcesProvider::getInstance()->load(path);
        pybind11::dict plugin_namespace;
        plugin_namespace["__builtins__"] = build_restricted_plugin_builtins();
        plugin_namespace["__file__"] = path;
        plugin_namespace["__name__"] = vstd::join({"plugin_", vstd::to_hex_hash(path)}, "");
        pybind11::exec(code + "\n", plugin_namespace, plugin_namespace);
        plugin_namespace["load"](pybind11::none(), pybind11::cast(game));
        return true;
    } catch (const pybind11::error_already_set &exception) {
        vstd::logger::warning("Failed to load Python plugin:", path, exception.what());
    } catch (const std::exception &exception) {
        vstd::logger::warning("Failed to load Python plugin:", path, exception.what());
    } catch (...) {
        vstd::logger::warning("Failed to load Python plugin:", path);
    }
    PyErr_Clear();
    return false;
}

bool CPluginLoader::loadCppPlugin(const std::shared_ptr<CGame> &game, const std::string &type) {
    if (!game || type.empty()) {
        vstd::logger::warning("Cannot load C++ plugin without a game and type id");
        return false;
    }

    auto plugin = game->createObject<CPlugin>(type);
    if (!plugin) {
        vstd::logger::warning("Failed to create C++ plugin:", type);
        return false;
    }

    try {
        plugin->load(game);
        return true;
    } catch (const std::exception &exception) {
        vstd::logger::warning("Failed to load C++ plugin:", type, exception.what());
    } catch (...) {
        vstd::logger::warning("Failed to load C++ plugin:", type);
    }
    return false;
}

bool CPluginLoader::loadDynamicPlugin(const std::shared_ptr<CGame> &game, const std::string &library,
                                      const std::string &entry) {
    if (!game || library.empty()) {
        vstd::logger::warning("Cannot load dynamic C++ plugin without a game and library path");
        return false;
    }

    const auto symbolName = entry.empty() ? std::string(DYNAMIC_PLUGIN_DEFAULT_ENTRY) : entry;
    const auto resolvedPath = resolve_dynamic_library_path(library);
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

    CPluginHostV1 host{GAME_PLUGIN_API_VERSION, game.get(), dynamic_plugin_log, dynamic_plugin_register_config_json};
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

bool CPluginLoader::loadGlobalPlugins(const std::shared_ptr<CGame> &game) {
    bool loadedAll = true;
    std::set<std::string> loadedPythonPlugins;
    std::set<std::string> loadedDynamicPlugins;

    if (auto manifest = load_plugin_manifest()) {
        if (manifest->contains("global")) {
            loadedAll = load_plugin_entries(game, (*manifest)["global"], loadedPythonPlugins, loadedDynamicPlugins) &&
                        loadedAll;
        }
    }

    for (const std::string &script : CResourcesProvider::getInstance()->getFiles(CResType::PLUGIN)) {
        if (!loadedPythonPlugins.contains(script)) {
            loadedAll = loadPlugin(game, script) && loadedAll;
        }
    }

    return loadedAll;
}

bool CPluginLoader::loadMapPlugins(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    if (!CSaveFormat::isValidMapName(mapName)) {
        vstd::logger::warning("Rejected invalid map name while loading plugins:", mapName);
        return false;
    }

    bool loadedAll = true;
    std::set<std::string> loadedPythonPlugins;
    std::set<std::string> loadedDynamicPlugins;

    if (auto manifest = load_plugin_manifest()) {
        if (manifest->contains("maps")) {
            const auto &mapEntries = (*manifest)["maps"];
            if (mapEntries.is_object() && mapEntries.contains(mapName)) {
                loadedAll = load_plugin_entries(game, mapEntries[mapName], loadedPythonPlugins, loadedDynamicPlugins) &&
                            loadedAll;
            } else if (!mapEntries.is_object()) {
                vstd::logger::warning("Ignoring non-object map plugin manifest section");
                loadedAll = false;
            }
        }
    }

    const auto scriptPath = getScriptPath(mapName);
    if (!loadedPythonPlugins.contains(scriptPath)) {
        loadedAll = loadPlugin(game, scriptPath) && loadedAll;
    }
    return loadedAll;
}
