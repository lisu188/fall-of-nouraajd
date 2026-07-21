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
#include "handler/CLuaHandler.h"
#include "handler/CRngHandler.h"
#include "object/CCreature.h"
#include "object/CCreatureRace.h"
#include "object/CPlayer.h"
#include "plugin/CPluginRegistrar.h"
#include "plugin/CPluginRuntime.h"
#include <pybind11/eval.h>
#include <rdg.h>

#include <algorithm>
#include <cctype>
#include <optional>
#include <utility>

std::set<std::string> getConfigPaths(const std::shared_ptr<CResourcesProvider> &resourcesProvider,
                                     const std::string &mapName);

std::string getMapPath(std::string mapName);

std::set<std::string> get_saved_map_dependencies(const std::shared_ptr<CGame> &game, const json &save,
                                                 const std::string &mapName);

void load_map_resources(const std::shared_ptr<CGame> &game, const std::string &mapName);

void activate_map_scope(const std::shared_ptr<CGame> &game, const std::string &mapName);

namespace {
constexpr const char *PLUGIN_MANIFEST_PATH = "plugins/manifest.json";
constexpr std::size_t MAX_TILESET_ID = 16384;
constexpr int MAX_TMX_LAYER_CELLS = 1'000'000;

struct SaveLoadResult {
    std::shared_ptr<CMap> map;
    std::string sourcePath;
    bool recoveredFromBackup = false;
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

bool is_allowed_lua_plugin_path(const std::string &path) {
    const auto normalized = normalize_relative_resource_path(path);
    return normalized && vstd::ends_with(*normalized, ".lua") && normalized->rfind("plugins/", 0) == 0;
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
    // Map xBound/yBound metadata is attacker-authorable; clamp the per-axis extent so downstream
    // consumers (notably minimap rendering) cannot be driven to iterate/allocate over enormous or
    // overflow-prone level dimensions. The cap mirrors the per-layer MAX_TMX_LAYER_CELLS guard.
    constexpr int MAX_LEVEL_BOUND = MAX_TMX_LAYER_CELLS - 1;
    x_bounds[level] = std::clamp(read_int_property(layerProperties, "xBound", 0), 0, MAX_LEVEL_BOUND);
    y_bounds[level] = std::clamp(read_int_property(layerProperties, "yBound", 0), 0, MAX_LEVEL_BOUND);
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

void apply_authored_map_metadata(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                 const std::string &mapName) {
    if (!game || !map) {
        return;
    }
    if (std::shared_ptr<json> mapc = game->getConfigurationProvider()->getConfiguration(getMapPath(mapName))) {
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

    apply_authored_map_metadata(game, map, mapName);

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
        for (const auto &requiredMap : get_saved_map_dependencies(game, *saveDocument.snapshot, saveDocument.mapName)) {
            if (requiredMap != saveDocument.mapName) {
                load_map_resources(game, requiredMap);
            }
        }
        // Activate the primary saved map's scope last so dependency maps loaded above for their
        // config/quest data do not leave their scope active.
        activate_map_scope(game, saveDocument.mapName);
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
    auto raw = game->getResourcesProvider()->loadJson(path);
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

void repair_recovered_backup(const std::shared_ptr<CGame> &game, const SaveLoadResult &loaded,
                             const std::string &slotName) {
    if (!loaded.recoveredFromBackup) {
        return;
    }
    auto resourcesProvider = game->getResourcesProvider();
    const auto backupBytes = resourcesProvider->load(loaded.sourcePath);
    if (backupBytes.empty()) {
        vstd::logger::warning("Recovered backup could not be read for primary repair:", slotName, loaded.sourcePath);
        return;
    }
    const auto primaryPath = CSaveFormat::primaryPath(slotName);
    std::error_code errorCode;
    const auto resolvedPrimaryPath = resourcesProvider->getPath(primaryPath);
    if (!resolvedPrimaryPath.empty()) {
        std::filesystem::remove(resolvedPrimaryPath, errorCode);
    }
    if (!resolvedPrimaryPath.empty() && errorCode) {
        vstd::logger::warning("Recovered backup primary repair could not remove rejected primary:", slotName,
                              primaryPath, "resolved:", resolvedPrimaryPath, "reason:", errorCode.message());
        return;
    }
    if (resourcesProvider->save(primaryPath, backupBytes)) {
        vstd::logger::warning("Repaired save primary from recovered backup:", slotName, primaryPath);
    } else {
        vstd::logger::warning("Failed to repair save primary from recovered backup:", slotName, primaryPath);
    }
}

std::shared_ptr<json> load_plugin_manifest(const std::shared_ptr<CResourcesProvider> &resourcesProvider) {
    if (resourcesProvider->getPath(PLUGIN_MANIFEST_PATH).empty()) {
        return nullptr;
    }
    return resourcesProvider->loadJson(PLUGIN_MANIFEST_PATH);
}

// Kinds whose source is a resource path; their paths join the loadedPluginPaths dedupe set that
// the auto-discovery loops in loadGlobalPlugins/loadMapPlugins consult.
bool is_path_sourced_plugin_kind(const std::string &kind) { return kind == "python" || kind == "lua"; }

std::optional<CPluginDescriptor> parse_plugin_descriptor(const json &entry) {
    if (!entry.is_object()) {
        vstd::logger::warning("Ignoring non-object plugin manifest entry");
        return std::nullopt;
    }

    CPluginDescriptor descriptor;
    descriptor.id = entry.value("id", std::string());
    descriptor.kind = entry.value("kind", std::string());
    if (descriptor.kind == "native") {
        descriptor.source = entry.value("library", std::string());
    } else if (descriptor.kind == "cpp") {
        descriptor.source = entry.value("type", std::string());
    } else {
        descriptor.source = entry.value("path", std::string());
    }
    descriptor.entry = entry.value("entry", std::string());
    if (entry.contains("scope") && entry["scope"].is_object() && entry["scope"].contains("map") &&
        entry["scope"]["map"].is_string()) {
        descriptor.mapScope = entry["scope"]["map"].get<std::string>();
    }

    if (descriptor.kind.empty() || descriptor.id.empty() || descriptor.source.empty()) {
        vstd::logger::warning("Ignoring plugin manifest entry without kind, id, or source:", descriptor.kind,
                              descriptor.id);
        return std::nullopt;
    }
    return descriptor;
}

bool load_plugin_descriptor(const std::shared_ptr<CGame> &game, const CPluginDescriptor &descriptor,
                            std::set<std::string> &loadedPluginIds, std::set<std::string> &loadedPluginPaths) {
    plugin_runtime::registerBuiltinRuntimes();
    auto *runtime = plugin_runtime::find(descriptor.kind);
    if (runtime == nullptr) {
        vstd::logger::warning("Ignoring plugin manifest entry with unknown kind:", descriptor.kind);
        return false;
    }
    if (!loadedPluginIds.insert(descriptor.id).second) {
        return true;
    }
    if (is_path_sourced_plugin_kind(descriptor.kind) && !loadedPluginPaths.insert(descriptor.source).second) {
        return true;
    }
    return runtime->load(game, descriptor);
}

bool load_plugin_entries(const std::shared_ptr<CGame> &game, const json &manifest,
                         const std::optional<std::string> &mapScope, std::set<std::string> &loadedPluginIds,
                         std::set<std::string> &loadedPluginPaths) {
    if (!manifest.contains("plugins")) {
        if (manifest.contains("global") || manifest.contains("maps")) {
            vstd::logger::warning("Ignoring unsupported v1 plugin manifest layout; expected a version 2 plugins array");
            return false;
        }
        return true;
    }
    const auto &entries = manifest["plugins"];
    if (!entries.is_array()) {
        vstd::logger::warning("Ignoring non-array plugin manifest section");
        return false;
    }

    bool loadedAll = true;
    for (const auto &entry : entries) {
        const auto descriptor = parse_plugin_descriptor(entry);
        if (!descriptor) {
            loadedAll = false;
            continue;
        }
        if (descriptor->mapScope != mapScope) {
            continue;
        }
        loadedAll = load_plugin_descriptor(game, *descriptor, loadedPluginIds, loadedPluginPaths) && loadedAll;
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

std::set<std::string> getConfigPaths(const std::shared_ptr<CResourcesProvider> &resourcesProvider,
                                     const std::string &mapName) {
    if (!CSaveFormat::isValidMapName(mapName)) {
        vstd::logger::warning("Rejected invalid map name while loading config:", mapName);
        return {};
    }

    const auto logicalMapPath = "maps/" + mapName;
    const auto resolvedMapPath = resourcesProvider->getPath(logicalMapPath);
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

void collect_saved_quest_refs(const json &root, CSavedQuestRefs &refs) {
    // Iterative traversal with an explicit work stack instead of recursion. The save document has
    // already been structurally bounded by CSaveFormat::validateDocumentStructure (depth, node
    // count, container fan-out) before this runs, but keeping the walk non-recursive removes the
    // stack-exhaustion vector entirely and is defended again here by the same node-count ceiling.
    std::vector<const json *> pending;
    pending.push_back(&root);
    std::size_t visited = 0;

    while (!pending.empty()) {
        const json *node = pending.back();
        pending.pop_back();

        if (++visited > CSaveFormat::MAX_DOCUMENT_NODES) {
            vstd::logger::warning("Aborting saved quest reference traversal: node count exceeded");
            return;
        }

        if (node->is_object()) {
            if (node->contains("properties") && (*node)["properties"].is_object()) {
                const json &properties = (*node)["properties"];
                for (const char *journalProperty : {"quests", "completedQuests"}) {
                    if (!properties.contains(journalProperty) || !properties[journalProperty].is_array()) {
                        continue;
                    }
                    for (const auto &quest : properties[journalProperty]) {
                        collect_saved_quest(quest, refs);
                    }
                }
            }
            for (const auto &[key, value] : node->items()) {
                (void)key;
                pending.push_back(&value);
            }
            continue;
        }

        if (node->is_array()) {
            for (const auto &value : *node) {
                pending.push_back(&value);
            }
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
        for (const char *key : {"typeId", "name"}) {
            if (properties.contains(key) && properties[key].is_string() &&
                refs.typeIds.contains(properties[key].get<std::string>())) {
                return true;
            }
        }
    }
    return false;
}

bool map_defines_saved_quest_refs(const std::shared_ptr<CGame> &game, const std::string &mapName,
                                  const CSavedQuestRefs &refs) {
    for (const auto &configPath : getConfigPaths(game->getResourcesProvider(), mapName)) {
        auto config = game->getConfigurationProvider()->getConfiguration(configPath);
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

std::set<std::string> get_saved_map_dependencies(const std::shared_ptr<CGame> &game, const json &save,
                                                 const std::string &mapName) {
    std::set<std::string> maps = {mapName};
    CSavedQuestRefs questRefs;
    collect_saved_quest_refs(save, questRefs);
    if (questRefs.classes.empty() && questRefs.typeIds.empty()) {
        return maps;
    }

    for (const auto &candidate : game->getResourcesProvider()->getFiles(CResType::MAP)) {
        if (!CSaveFormat::isValidMapName(candidate)) {
            continue;
        }
        if (map_defines_saved_quest_refs(game, candidate, questRefs)) {
            maps.insert(candidate);
        }
    }
    return maps;
}

void load_map_resources(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    game->getObjectHandler()->registerConfig(getConfigPaths(game->getResourcesProvider(), mapName));
    CPluginLoader::loadMapPlugins(game, mapName);
    game->getObjectHandler()->registerConfig(getConfigPaths(game->getResourcesProvider(), mapName));
}

// Register the map's directory as a scoped search root and make it the active scope so that
// map-local assets (animations/textures declared by a bare name) resolve through it. Global
// assets keep their precedence: the base search path is always consulted first, and the scope
// only adds map-local names that are not found globally. Absolute/traversal paths remain rejected
// by the provider's existing safe-path guard. Called for the map that becomes active after a load;
// dependency maps loaded only for config/quest data do not steal the active scope.
void activate_map_scope(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    const auto provider = game->getResourcesProvider();
    if (!provider) {
        return;
    }
    const auto mapRoot = provider->getPath("maps/" + mapName);
    if (mapRoot.empty()) {
        return;
    }
    provider->addScopedRoot(mapName, mapRoot);
    provider->setActiveScope(mapName);
}

std::shared_ptr<CMap> CMapLoader::loadNewMap(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    if (std::shared_ptr<json> mapc = game->getConfigurationProvider()->getConfiguration(getMapPath(mapName))) {
        std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game);
        game->setMap(map);
        load_map_resources(game, mapName);
        activate_map_scope(game, mapName);
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
    return loadNewMapWithPlayer(game, name, std::move(player), std::string());
}

std::shared_ptr<CMap> CMapLoader::loadNewMapWithPlayer(const std::shared_ptr<CGame> &game, const std::string &name,
                                                       std::string player, const std::string &raceId) {
    // Validate the player template and (for a non-empty raceId) the race BEFORE loadNewMap replaces
    // the active map. If the race id cannot be resolved, keep the current map untouched and return it
    // so the caller's setMap re-set is a no-op instead of attaching a partial player onto a new map.
    std::shared_ptr<CPlayer> ptr = createPlayer(game, player, raceId);
    if (!ptr) {
        vstd::logger::warning("Keeping the active map unchanged; player could not be created for:", name);
        return game->getMap();
    }

    std::shared_ptr<CMap> map = loadNewMap(game, name);
    map->setPlayer(ptr);

    return map;
}

// TODO: move to map, set player as well as triggers
std::shared_ptr<CPlayer> CMapLoader::createPlayer(const std::shared_ptr<CGame> &game, std::string &player,
                                                  const std::string &raceId) {
    // Resolve and type-check the requested race BEFORE the caller replaces the active map. An empty
    // raceId means "no override": preserve the template's default race so the existing three-argument
    // loaders behave exactly as before. A non-empty raceId must resolve to a CCreatureRace; if it
    // does not (unknown id or an id that maps to a non-race object), we log the exact id and return
    // null so the caller can abort without switching maps or attaching a partial player.
    std::shared_ptr<CCreatureRace> race;
    if (!raceId.empty()) {
        race = game->createObject<CCreatureRace>(raceId);
        if (!race) {
            vstd::logger::warning("Rejected player creation for unresolved race id:", raceId);
            return nullptr;
        }
    }

    auto ptr = game->createObject<CPlayer>(std::move(player));
    if (ptr && race) {
        ptr->setRaceId(raceId);
        ptr->setRace(std::move(race));
    }

    return ptr;
}

std::shared_ptr<CMap> CMapLoader::loadRandomMapWithPlayer(const std::shared_ptr<CGame> &game, std::string player) {
    return loadRandomMapWithPlayer(game, std::move(player), std::string());
}

std::shared_ptr<CMap> CMapLoader::loadRandomMapWithPlayer(const std::shared_ptr<CGame> &game, std::string player,
                                                          const std::string &raceId) {
    // Validate the player template and (for a non-empty raceId) the race before generating and
    // installing the random map. On an unresolved race id, keep the current map untouched.
    std::shared_ptr<CPlayer> ptr = createPlayer(game, player, raceId);
    if (!ptr) {
        vstd::logger::warning("Keeping the active map unchanged; player could not be created for random map");
        return game->getMap();
    }

    std::shared_ptr<CMap> map = CRandomMapGenerator::loadRandomMap(game);
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

    // Persist through the saved map's per-session resources provider; fall back to the process
    // singleton only when the map has already been detached from its game (compatibility path).
    auto game = map->getGame();
    auto resources = game ? game->getResourcesProvider() : CResourcesProvider::getInstance();
    resources->save(CSaveFormat::primaryPath(name), CJsonUtil::to_string(*envelope, -1));
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
    initConfigurations(game);
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGameWithPlayer(const std::shared_ptr<CGame> &game, const std::string &file, std::string player) {
    startGameWithPlayer(game, file, std::move(player), std::string());
}

void CGameLoader::startGameWithPlayer(const std::shared_ptr<CGame> &game, const std::string &file, std::string player,
                                      const std::string &raceId) {
    game->setMap(CMapLoader::loadNewMapWithPlayer(game, file, std::move(player), raceId));
}

void CGameLoader::startRandomGameWithPlayer(const std::shared_ptr<CGame> &game, std::string player) {
    startRandomGameWithPlayer(game, std::move(player), std::string());
}

void CGameLoader::startRandomGameWithPlayer(const std::shared_ptr<CGame> &game, std::string player,
                                            const std::string &raceId) {
    game->setMap(CMapLoader::loadRandomMapWithPlayer(game, std::move(player), raceId));
}

void CGameLoader::loadSavedGame(const std::shared_ptr<CGame> &game, const std::string &save) {
    if (auto loaded = try_load_saved_map(game, save)) {
        game->setMap(loaded->map);
        repair_recovered_backup(game, *loaded, save);
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

void CGameLoader::initConfigurations(const std::shared_ptr<CGame> &game) {
    for (const std::string &path : game->getResourcesProvider()->getFiles(CResType::CONFIG)) {
        game->getObjectHandler()->registerConfig(path);
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

bool CPluginLoader::isTrustedPluginPath(const std::string &path) { return is_allowed_python_plugin_path(path); }

bool CPluginLoader::isTrustedLuaPluginPath(const std::string &path) { return is_allowed_lua_plugin_path(path); }

bool CPluginLoader::loadLuaPlugin(const std::shared_ptr<CGame> &game, const std::string &path) {
    if (!isTrustedLuaPluginPath(path)) {
        vstd::logger::warning("Rejected Lua plugin outside trusted resource plugin paths:", path);
        return false;
    }
    try {
        std::string code = game->getResourcesProvider()->load(path);
        return game->getLuaHandler()->loadPlugin(game, path, code);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Failed to load Lua plugin:", path, exception.what());
    } catch (...) {
        vstd::logger::warning("Failed to load Lua plugin:", path);
    }
    return false;
}

bool CPluginLoader::loadPlugin(const std::shared_ptr<CGame> &game, const std::string &path) {
    if (!isTrustedPluginPath(path)) {
        vstd::logger::warning("Rejected Python plugin outside trusted resource plugin paths:", path);
        return false;
    }
    try {
        std::string code = game->getResourcesProvider()->load(path);
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
        CPluginRegistrar registrar(game);
        plugin->load(registrar);
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
    return plugin_runtime::loadNativePlugin(game, library, entry);
}

bool CPluginLoader::loadGlobalPlugins(const std::shared_ptr<CGame> &game) {
    bool loadedAll = true;
    std::set<std::string> loadedPluginIds;
    std::set<std::string> loadedPluginPaths;

    if (auto manifest = load_plugin_manifest(game->getResourcesProvider())) {
        loadedAll = load_plugin_entries(game, *manifest, std::nullopt, loadedPluginIds, loadedPluginPaths) && loadedAll;
    }

    for (const std::string &script : game->getResourcesProvider()->getFiles(CResType::PLUGIN)) {
        if (!loadedPluginPaths.contains(script)) {
            loadedAll = loadPlugin(game, script) && loadedAll;
        }
    }

    for (const std::string &script : game->getResourcesProvider()->getFiles(CResType::PLUGIN_LUA)) {
        if (!loadedPluginPaths.contains(script)) {
            loadedAll = loadLuaPlugin(game, script) && loadedAll;
        }
    }

    return loadedAll;
}

bool CPluginLoader::loadMapPlugins(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    if (!CSaveFormat::isValidMapName(mapName)) {
        vstd::logger::warning("Rejected invalid map name while loading plugins:", mapName);
        return false;
    }

    // Mark every class registration performed while this map's script/plugins load as map-scoped, so
    // a transition destination's classes override an earlier map's identically named classes without
    // clobbering core types or explicit overrides. The guard restores the flag even if a plugin
    // throws mid-load.
    struct MapScriptScopeGuard {
        std::shared_ptr<CObjectHandler> handler;
        explicit MapScriptScopeGuard(std::shared_ptr<CObjectHandler> handler) : handler(std::move(handler)) {
            if (this->handler) {
                this->handler->beginMapScriptScope();
            }
        }
        ~MapScriptScopeGuard() {
            if (handler) {
                handler->endMapScriptScope();
            }
        }
    } mapScriptScopeGuard(game->getObjectHandler());

    bool loadedAll = true;
    std::set<std::string> loadedPluginIds;
    std::set<std::string> loadedPluginPaths;

    if (auto manifest = load_plugin_manifest(game->getResourcesProvider())) {
        loadedAll = load_plugin_entries(game, *manifest, std::optional<std::string>(mapName), loadedPluginIds,
                                        loadedPluginPaths) &&
                    loadedAll;
    }

    const auto scriptPath = getScriptPath(mapName);
    if (!loadedPluginPaths.contains(scriptPath)) {
        loadedAll = loadPlugin(game, scriptPath) && loadedAll;
    }
    return loadedAll;
}
