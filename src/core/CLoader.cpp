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
#include "core/CJsonUtil.h"
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

namespace {
constexpr const char *PLUGIN_MANIFEST_PATH = "plugins/manifest.json";
constexpr const char *DYNAMIC_PLUGIN_DEFAULT_ENTRY = "game_plugin_load_v1";

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

bool is_valid_map_name(const std::string &mapName) {
    if (mapName.empty()) {
        return true;
    }

    return std::all_of(mapName.begin(), mapName.end(), [](unsigned char ch) {
        if (std::isalnum(ch)) {
            return true;
        }
        return ch == '_' || ch == '-';
    });
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
    return is_valid_map_name(parent.filename().string());
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
        pybind11::object moduleName = pybind11::str(name);
        return PyImport_ImportModuleLevelObject(moduleName.ptr(), globals == nullptr ? Py_None : globals,
                                                locals == nullptr ? Py_None : locals,
                                                fromlist == nullptr ? Py_None : fromlist, level);
    }

    PyErr_SetString(PyExc_ImportError, "Python resource plugins may only import the game and json modules");
    return nullptr;
}

pybind11::dict build_restricted_plugin_builtins() {
    auto builtins = pybind11::module_::import("builtins");
    pybind11::dict safeBuiltins;
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
        safeBuiltins[pybind11::str(name)] = builtins.attr(name.c_str());
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

std::string resolve_dynamic_library_path(const std::string &library) {
    auto provider = CResourcesProvider::getInstance();
    for (const auto &candidate : dynamic_library_candidates(library)) {
        auto resolved = provider->getPath(candidate);
        if (!resolved.empty()) {
            return std::filesystem::absolute(resolved).lexically_normal().string();
        }
        if (std::filesystem::exists(candidate)) {
            return std::filesystem::absolute(candidate).lexically_normal().string();
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

void apply_tile_layer_metadata(const std::shared_ptr<CMap> &map, const json &layer) {
    const json &layerProperties = layer["properties"];
    int level = vstd::to_int(layerProperties["level"].get<std::string>()).first;

    auto default_tiles = map->getDefaultTiles();
    auto out_of_bounds_tiles = map->getOutOfBoundsTiles();
    auto x_bounds = map->getXBounds();
    auto y_bounds = map->getYBounds();
    auto wrap_x = map->getWrapX();
    auto wrap_y = map->getWrapY();

    default_tiles[level] = layerProperties["default"].get<std::string>();
    if (layerProperties.count("outOfBounds")) {
        out_of_bounds_tiles[level] = layerProperties["outOfBounds"].get<std::string>();
    }
    x_bounds[level] = vstd::to_int(layerProperties["xBound"].get<std::string>()).first;
    y_bounds[level] = vstd::to_int(layerProperties["yBound"].get<std::string>()).first;
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
        const int parsedTileId = vstd::to_int(tileId).first;
        if (parsedTileId > 0) {
            maxTileId = std::max(maxTileId, static_cast<std::size_t>(parsedTileId));
        }
    }

    std::vector<std::string> tileTypes(maxTileId + 1);
    for (const auto &[tileId, tileConfig] : tileset.items()) {
        const int parsedTileId = vstd::to_int(tileId).first;
        if (parsedTileId < 0) {
            continue;
        }
        tileTypes[parsedTileId] = tileConfig["type"].get<std::string>();
    }
    return tileTypes;
}

bool is_valid_slot_name(const std::string &name) {
    if (name.empty() || name.find("..") != std::string::npos) {
        return false;
    }

    return std::all_of(name.begin(), name.end(), [](unsigned char ch) {
        if (std::isalnum(ch)) {
            return true;
        }
        return ch == '.' || ch == '_' || ch == '-';
    });
}

std::string build_saved_map_config_key(const std::string &slotName) { return "__save_slot__/" + slotName; }

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
} // namespace

void CMapLoader::loadFromTmx(const std::shared_ptr<CMap> &map, const std::shared_ptr<json> &mapc) {
    if (mapc) {
        const json &mapProperties = (*mapc)["properties"];
        const json &mapLayers = (*mapc)["layers"];
        map->setDefaultTiles({});
        map->setOutOfBoundsTiles({});
        map->setXBounds({});
        map->setYBounds({});
        map->setWrapX({});
        map->setWrapY({});
        map->setEntryX(vstd::to_int(mapProperties.count("x") ? mapProperties["x"].get<std::string>() : "0").first);
        map->setEntryY(vstd::to_int(mapProperties.count("y") ? mapProperties["y"].get<std::string>() : "0").first);
        map->setEntryZ(vstd::to_int(mapProperties.count("z") ? mapProperties["z"].get<std::string>() : "0").first);
        const auto tileTypes = build_tile_types((*mapc)["tilesets"][0]["tileproperties"]);
        for (const auto &layer : mapLayers) {
            if (vstd::string_equals(layer["type"].get<std::string>(), "tilelayer")) {
                apply_tile_layer_metadata(map, layer);
                handleTileLayer(map, tileTypes, layer);
            }
        }
        for (const auto &layer : mapLayers) {
            if (vstd::string_equals(layer["type"].get<std::string>(), "objectgroup")) {
                handleObjectLayer(map, layer);
            }
        }
    }
}

std::set<std::string> getConfigPaths(const std::string &mapName) {
    if (!is_valid_map_name(mapName)) {
        vstd::logger::warning("Rejected invalid map name while loading config:", mapName);
        return {};
    }

    return CUtil::findFiles("maps/" + mapName, [](auto path) {
        return vstd::ends_with(path, ".json") && !vstd::ends_with(path, "map.json");
    });
}

std::string getScriptPath(std::string mapName) {
    if (!is_valid_map_name(mapName)) {
        vstd::logger::warning("Rejected invalid map name while resolving script:", mapName);
        return {};
    }

    std::string path = vstd::join({"maps/", std::move(mapName)}, "");
    return vstd::join({path, "/script.py"}, "");
}

std::string getMapPath(std::string mapName) {
    if (!is_valid_map_name(mapName)) {
        vstd::logger::warning("Rejected invalid map name while resolving map:", mapName);
        return {};
    }

    std::string path = vstd::join({"maps/", std::move(mapName)}, "");
    return vstd::join({path, "/map.json"}, "");
}

std::shared_ptr<CMap> CMapLoader::loadNewMap(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    if (std::shared_ptr<json> mapc = CConfigurationProvider::getConfig(getMapPath(mapName))) {
        std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game);
        game->setMap(map);
        game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
        CPluginLoader::loadMapPlugins(game, mapName);
        loadFromTmx(map, mapc);
        map->setMapName(mapName);
        return map;
    }
    return game->getObjectHandler()->createObject<CMap>(game);
}

std::shared_ptr<CMap> CMapLoader::loadSavedMap(const std::shared_ptr<CGame> &game, const std::string &name) {
    if (!is_valid_slot_name(name)) {
        vstd::logger::warning("Rejected invalid save slot name during load:", name);
        return game->getObjectHandler()->createObject<CMap>(game);
    }

    const std::string path = "save/" + name + ".json";
    const std::string saveConfigKey = build_saved_map_config_key(name);

    if (std::shared_ptr<json> save = CConfigurationProvider::getConfig(path)) {
        const auto mapName = (*save)["properties"]["mapName"].get<std::string>();

        game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
        CPluginLoader::loadMapPlugins(game, mapName);
        game->getObjectHandler()->registerConfig(getConfigPaths(mapName)); // TODO: duplicate?

        game->getObjectHandler()->registerConfig(saveConfigKey, save);

        auto map = game->getObjectHandler()->createObject<CMap>(game, saveConfigKey);
        if (std::shared_ptr<json> mapc = CConfigurationProvider::getConfig(getMapPath(mapName))) {
            map->setDefaultTiles({});
            map->setOutOfBoundsTiles({});
            map->setXBounds({});
            map->setYBounds({});
            map->setWrapX({});
            map->setWrapY({});
            const json &mapProperties = (*mapc)["properties"];
            map->setEntryX(vstd::to_int(mapProperties.count("x") ? mapProperties["x"].get<std::string>() : "0").first);
            map->setEntryY(vstd::to_int(mapProperties.count("y") ? mapProperties["y"].get<std::string>() : "0").first);
            map->setEntryZ(vstd::to_int(mapProperties.count("z") ? mapProperties["z"].get<std::string>() : "0").first);
            for (const auto &layer : (*mapc)["layers"]) {
                if (vstd::string_equals(layer["type"].get<std::string>(), "tilelayer")) {
                    apply_tile_layer_metadata(map, layer);
                }
            }
        }
        for (const auto &object : map->getObjects()) {
            if (auto player = std::dynamic_pointer_cast<CPlayer>(object)) {
                map->player = player;
                map->registerPlayerTriggers();
                break;
            }
        }
        return map;
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
    if (!is_valid_slot_name(name)) {
        vstd::logger::warning("Rejected invalid save slot name during save:", name);
        return;
    }

    CResourcesProvider::getInstance()->save(vstd::join({"save/", name, ".json"}, ""), JSONIFY_STYLED(map));
}

void CMapLoader::handleTileLayer(const std::shared_ptr<CMap> &map, const std::vector<std::string> &tileTypes,
                                 const json &layer) {
    const json &layerProperties = layer["properties"];
    const json &layerData = layer["data"];
    const auto game = map->getGame();
    int level = vstd::to_int(layerProperties["level"].get<std::string>()).first;

    int width = layer["width"].get<int>();
    int height = layer["height"].get<int>();

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
    int level = vstd::to_int(layer["properties"]["level"].get<std::string>()).first;
    const json &objects = layer["objects"];
    for (const auto &object : objects) {
        auto objectType = object["type"].get<std::string>();
        auto objectName = object["name"].get<std::string>();

        int xPos = object["x"].get<int>() / object["width"].get<int>();
        int yPos = object["y"].get<int>() / object["height"].get<int>();
        auto mapObject = map->getGame()->createObject<CMapObject>(objectType);
        if (mapObject == nullptr) {
            vstd::logger::debug("Failed to load object:", objectType, objectName);
            continue;
        }
        if (!vstd::is_empty(objectName)) {
            mapObject->setName(objectName);
        }
        const json &objectProperties = object.count("properties") ? object["properties"] : json();
        for (auto &[key, value] : objectProperties.items()) {
            CSerialization::setProperty(mapObject, key, CJsonUtil::clone(value));
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
    game->setMap(CMapLoader::loadSavedMap(game, save));
}

void CGameLoader::startGame(const std::shared_ptr<CGame> &game, const std::string &file) {
    game->setMap(CMapLoader::loadNewMap(game, file));
}

void CGameLoader::changeMap(const std::shared_ptr<CGame> &game, const std::string &name) {
    vstd::call_later([game, name]() {
        // TODO: implement stop processing events here
        vstd::call_when([game]() { return !game->getMap()->isMoving(); },
                        [game, name]() {
                            std::shared_ptr<CMap> oldMap = game->getMap();
                            std::shared_ptr<CMap> map = CMapLoader::loadNewMap(game, name);
                            game->setMap(map);
                            std::shared_ptr<CPlayer> player = oldMap->getPlayer();
                            game->getMap()->setPlayer(player);
                            game->getMap()->setTurn(oldMap->getTurn());
                        });
    });
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
    std::shared_ptr<CGui> gui = game->createObject<CGui>("gui");

    game->setGui(gui);

    vstd::event_loop<>::instance()->registerFrameCallback([game](int time) { game->getGui()->render(time); });
    vstd::event_loop<>::instance()->registerEventCallback(
        [game](SDL_Event *event) { return game->getGui()->event(event); });
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
    if (!is_valid_map_name(mapName)) {
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
