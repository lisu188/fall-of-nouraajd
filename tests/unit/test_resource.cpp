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

#include "core/CProvider.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CSaveFormat.h"
#include "handler/CObjectHandler.h"
#include "object/CItem.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>

namespace {

class ScopedCurrentPath {
  public:
    explicit ScopedCurrentPath(std::filesystem::path replacement)
        : originalPath(std::filesystem::current_path()), replacementPath(std::move(replacement)) {
        std::filesystem::current_path(replacementPath);
    }

    ~ScopedCurrentPath() { std::filesystem::current_path(originalPath); }

  private:
    std::filesystem::path originalPath;
    std::filesystem::path replacementPath;
};

std::string json_string_value(const std::shared_ptr<json> &node, const std::string &key) {
    if (!node || !node->contains(key) || !node->at(key).is_string()) {
        return {};
    }
    return node->at(key).get<std::string>();
}

bool write_text_file(const std::filesystem::path &path, const std::string &text) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        return false;
    }
    stream << text;
    return static_cast<bool>(stream);
}

void test_resource_provider_paths_and_config_loader() {
    auto provider = CResourcesProvider::getInstance();
    expect_true(provider->getPath("").empty(), "empty resource paths should be rejected");
    expect_true(provider->getPath("../config/items.json").empty(), "parent-relative resource paths should be rejected");
    expect_true(provider->getPath("config/../config/items.json").find("items.json") != std::string::npos,
                "normalized safe resource paths should resolve");

    const auto config_files = provider->getFiles(CResType::CONFIG);
    expect_true(std::find(config_files.begin(), config_files.end(), "config/items.json") != config_files.end(),
                "config file listing should include items.json");
    const auto plugin_files = provider->getFiles(CResType::PLUGIN);
    expect_true(std::find(plugin_files.begin(), plugin_files.end(), "plugins/effect.py") != plugin_files.end(),
                "plugin file listing should include effect.py");
    const auto map_files = provider->getFiles(CResType::MAP);
    expect_true(std::find(map_files.begin(), map_files.end(), "test") != map_files.end(),
                "map directory listing should include the test map");
    const auto save_files = provider->getFiles(CResType::SAVE);
    expect_true(save_files.empty() || !save_files.front().empty(),
                "save file listing should tolerate absent optional save directories");

    expect_true(!provider->load("config/items.json").empty(), "load should read existing resources as text");
    expect_true(provider->load("config/missing-resource.json").empty(),
                "load should return empty text for missing files");
    auto parsed_items = provider->loadJson("config/items.json");
    expect_true(parsed_items && parsed_items->is_object(), "loadJson should parse existing JSON resources");

    CConfigResourceLoader loader;
    auto item_resource = std::static_pointer_cast<CTextResource>(loader.load("config/items.json"));
    expect_true(std::filesystem::path(item_resource->getFilePath()).generic_string() == "config/items.json",
                "config loader should avoid double config prefixes");
    expect_true(!item_resource->getText().empty(), "config resources should load text through the provider");
    auto normalized_resource = std::static_pointer_cast<CTextResource>(loader.load("items"));
    expect_true(std::filesystem::path(normalized_resource->getFilePath()).generic_string() == "config/items.json",
                "config loader should append the json suffix for bare names");

    auto cached_config = CConfigurationProvider::getConfig("items.json");
    expect_true(cached_config && cached_config->is_object(), "configuration provider should parse normalized configs");
    expect_true(CConfigurationProvider::getConfig("items.json") == cached_config,
                "configuration provider should cache parsed configs by path");
}

void test_resource_provider_save_uses_provider_root_when_cwd_changes() {
    auto provider = CResourcesProvider::getInstance();
    const auto itemsPath = std::filesystem::path(provider->getPath("config/items.json"));
    expect_true(!itemsPath.empty(), "items config should resolve before provider-root save test");
    if (itemsPath.empty()) {
        return;
    }
    const auto resourceRoot = itemsPath.parent_path().parent_path();
    const std::string logicalSavePath = "save/unit_resource_provider_cwd.json";
    const auto providerSavePath = resourceRoot / logicalSavePath;
    const auto providerBackupPath = std::filesystem::path(providerSavePath.string() + CSaveFormat::BACKUP_SUFFIX);
    std::filesystem::remove(providerSavePath);
    std::filesystem::remove(providerBackupPath);

    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto tempRoot = std::filesystem::temp_directory_path() / ("resource-provider-cwd-" + std::to_string(nonce));
    std::filesystem::create_directories(tempRoot / "save");
    const auto cwdSavePath = tempRoot / logicalSavePath;

    {
        ScopedCurrentPath cwd(tempRoot);
        expect_true(provider->save(logicalSavePath, "{\"providerRoot\":true}"),
                    "provider save should succeed from unrelated cwd");
    }

    expect_true(std::filesystem::exists(providerSavePath), "save should be written under provider resource root");
    expect_true(!std::filesystem::exists(cwdSavePath), "save should not be written under current working directory");
    expect_true(provider->getPath(logicalSavePath) == std::filesystem::weakly_canonical(providerSavePath).string(),
                "new save should resolve through provider search roots");
    expect_true(provider->load(logicalSavePath).find("providerRoot") != std::string::npos,
                "new save should be loadable through provider");

    std::filesystem::remove(providerSavePath);
    std::filesystem::remove(providerBackupPath);
    std::filesystem::remove_all(tempRoot);
}

void test_configuration_provider_instances_do_not_share_config_cache() {
    auto resources = CResourcesProvider::getInstance();
    const auto itemsPath = std::filesystem::path(resources->getPath("config/items.json"));
    expect_true(!itemsPath.empty(), "items config should resolve before configuration provider isolation test");
    if (itemsPath.empty()) {
        return;
    }

    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto logicalConfigName = "unit_provider_isolation_" + std::to_string(nonce) + ".json";
    const auto tempConfigPath = itemsPath.parent_path() / logicalConfigName;
    std::filesystem::remove(tempConfigPath);

    expect_true(write_text_file(tempConfigPath, R"({"marker":"first"})"),
                "configuration provider isolation fixture should be written");
    if (!std::filesystem::exists(tempConfigPath)) {
        return;
    }

    CConfigurationProvider firstProvider(resources);
    CConfigurationProvider secondProvider(resources);

    auto firstConfig = firstProvider.getConfiguration(logicalConfigName);
    expect_true(json_string_value(firstConfig, "marker") == "first",
                "first configuration provider should load initial temp config content");

    expect_true(write_text_file(tempConfigPath, R"({"marker":"second"})"),
                "configuration provider isolation fixture should be rewritable");

    auto firstConfigAgain = firstProvider.getConfiguration(logicalConfigName);
    auto secondConfig = secondProvider.getConfiguration(logicalConfigName);
    expect_true(firstConfigAgain == firstConfig, "one provider instance should cache its own parsed config");
    expect_true(json_string_value(firstConfigAgain, "marker") == "first",
                "one provider instance should keep its cached config after the file changes");
    expect_true(json_string_value(secondConfig, "marker") == "second",
                "a separate provider instance should load fresh config content from the temp file");
    expect_true(secondConfig != firstConfig, "separate configuration providers should not share cache entries");

    std::filesystem::remove(tempConfigPath);
}

void test_load_game_creates_context_owned_providers() {
    auto first_game = CGameLoader::loadGame();
    auto second_game = CGameLoader::loadGame();

    auto first_context = first_game->getContext();
    auto second_context = second_game->getContext();

    auto first_resources = first_context->getResourcesProvider();
    auto first_resources_from_game = first_game->getResourcesProvider();
    auto second_resources = second_game->getResourcesProvider();
    expect_true(first_resources == first_resources_from_game,
                "CGame should delegate resource provider access to CGameContext");
    expect_true(first_resources != CResourcesProvider::getInstance(),
                "context-owned resource providers should be distinct from the legacy singleton");
    expect_true(first_resources != second_resources,
                "CGameLoader::loadGame should create one resource provider instance per game context");

    auto first_configuration = first_context->getConfigurationProvider();
    auto first_configuration_from_game = first_game->getConfigurationProvider();
    auto second_configuration = second_context->getConfigurationProvider();
    expect_true(first_configuration == first_configuration_from_game,
                "CGame should delegate configuration provider access to CGameContext");
    expect_true(first_configuration != second_configuration,
                "CGameLoader::loadGame should create one configuration provider instance per game context");

    auto first_items = first_configuration->getConfiguration("items.json");
    auto second_items = second_configuration->getConfiguration("items.json");
    expect_true(first_items && second_items, "context-owned configuration providers should load config resources");
    expect_true(first_items == first_configuration->getConfiguration("items.json"),
                "context-owned configuration providers should cache configs per provider instance");
    expect_true(first_items != second_items, "separate game contexts should not share configuration provider caches");
}

void test_map_load_resolves_through_context_owned_providers() {
    auto singletonResources = CResourcesProvider::getInstance();
    const auto itemsPath = std::filesystem::path(singletonResources->getPath("config/items.json"));
    expect_true(!itemsPath.empty(), "items config should resolve before context-owned map load test");
    if (itemsPath.empty()) {
        return;
    }
    const auto resourceRoot = itemsPath.parent_path().parent_path();

    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::string mapName = "unit_ctx_map_" + std::to_string(nonce);
    const auto mapDir = resourceRoot / "maps" / mapName;
    std::filesystem::create_directories(mapDir);
    const auto mapConfigPath = mapDir / "map.json";
    const std::string logicalMapConfig = "maps/" + mapName + "/map.json";

    expect_true(write_text_file(mapConfigPath, R"({"marker":"first","properties":{"x":0,"y":0,"z":0},"layers":[]})"),
                "temporary map fixture should be written");
    if (!std::filesystem::exists(mapConfigPath)) {
        std::filesystem::remove_all(mapDir);
        return;
    }

    auto game = CGameLoader::loadGame();
    expect_true(game->getResourcesProvider() != singletonResources,
                "map load test should run against a context-owned resource provider");

    auto map = CMapLoader::loadNewMap(game, mapName);
    expect_true(map && map->getMapName() == mapName,
                "loadNewMap should load the authored map through the game's provider instances");

    // Rewrite the fixture: only a cache primed while loadNewMap ran keeps the original content, so
    // the assertions below can tell exactly which provider instance the load path went through.
    expect_true(write_text_file(mapConfigPath, R"({"marker":"second","properties":{"x":0,"y":0,"z":0},"layers":[]})"),
                "temporary map fixture should be rewritable");

    auto cachedConfig = game->getConfigurationProvider()->getConfiguration(logicalMapConfig);
    expect_true(json_string_value(cachedConfig, "marker") == "first",
                "loadNewMap should prime the game's own configuration provider cache");

    CConfigurationProvider explicitProvider(game->getResourcesProvider());
    auto freshConfig = explicitProvider.getConfiguration(logicalMapConfig);
    expect_true(json_string_value(freshConfig, "marker") == "second",
                "an explicitly-passed provider instance should load the map config independently");

    auto legacyConfig = CConfigurationProvider::getConfig(logicalMapConfig);
    expect_true(json_string_value(legacyConfig, "marker") == "second",
                "map load must not populate the process-wide configuration provider cache");

    std::filesystem::remove_all(mapDir);
}

void test_resource_plugin_trust_boundary_rejects_escapes() {
    auto provider = CResourcesProvider::getInstance();
    const auto itemsPath = std::filesystem::path(provider->getPath("config/items.json"));
    expect_true(!itemsPath.empty(), "items config should resolve before trust-boundary test");
    if (itemsPath.empty()) {
        return;
    }
    const auto resourceRoot = itemsPath.parent_path().parent_path();

    // Untrusted: absolute and parent-traversal resource reads must be rejected by the boundary.
    expect_true(provider->getPath("/etc/passwd").empty(), "absolute resource paths must be rejected");
    expect_true(provider->getPath("../config/items.json").empty(), "parent-traversal resource paths must be rejected");

    // Untrusted: a symlink inside the resource root that points outside it must be rejected even
    // though it lexically lives under the root, because getPath canonicalizes (follows symlinks)
    // before checking containment.
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto outsideDir =
        std::filesystem::temp_directory_path() / ("trust-boundary-outside-" + std::to_string(nonce));
    std::error_code errorCode;
    std::filesystem::create_directories(outsideDir, errorCode);
    const auto outsideFile = outsideDir / "secret.json";
    expect_true(write_text_file(outsideFile, R"({"secret":true})"), "out-of-root fixture should be written");

    const std::string logicalLink = "config/trust_boundary_escape_" + std::to_string(nonce) + ".json";
    const auto linkPath = resourceRoot / logicalLink;
    std::filesystem::create_symlink(outsideFile, linkPath, errorCode);
    if (!errorCode) {
        expect_true(provider->getPath(logicalLink).empty(),
                    "symlink escaping the resource root must be rejected by getPath");
        expect_true(provider->load(logicalLink).empty(),
                    "symlink escaping the resource root must not be readable through load");
    }
    std::filesystem::remove(linkPath, errorCode);
    std::filesystem::remove_all(outsideDir, errorCode);

    // Untrusted: Python plugin/script loads outside the trusted plugin/map roots must be refused
    // before any code is executed. The trust-boundary decision (isTrustedPluginPath) is the
    // security-relevant behavior, so assert it directly -- loadPlugin executing plugin code needs
    // the _game pybind bindings, which this game_core unit-test binary does not link, so its return
    // value cannot distinguish a boundary rejection from a runtime failure here.
    auto game = CGameLoader::loadGame();
    for (const std::string &untrusted : {std::string("../evil.py"), std::string("/tmp/evil.py"),
                                         std::string("config/items.json"), std::string("plugins/../../escape.py")}) {
        expect_true(!CPluginLoader::isTrustedPluginPath(untrusted),
                    "paths outside the trusted plugin roots must not be trusted");
        expect_true(!CPluginLoader::loadPlugin(game, untrusted),
                    "untrusted plugin paths must be rejected before execution");
    }

    // Trusted: an in-root plugin path under plugins/ is accepted by the boundary. Its actual
    // execution is exercised by the gameplay suites that run with the real _game module.
    const std::string trustedPluginLogical = "plugins/trust_boundary_ok_" + std::to_string(nonce) + ".py";
    expect_true(CPluginLoader::isTrustedPluginPath(trustedPluginLogical),
                "an in-root plugin path under plugins/ must be trusted by the boundary");
}

void test_two_game_contexts_isolate_provider_cache_and_object_config() {
    // Two independent game sessions. SUBSTORY_01/02/03 moved the resources/configuration providers
    // onto CGameContext, so each game must resolve content through its OWN provider and cache rather
    // than through the process-wide compatibility singletons.
    auto firstGame = CGameLoader::loadGame();
    auto secondGame = CGameLoader::loadGame();

    auto firstResources = firstGame->getResourcesProvider();
    auto secondResources = secondGame->getResourcesProvider();
    expect_true(firstResources && secondResources, "both game contexts should expose resources providers");
    expect_true(firstResources != secondResources,
                "each game context should own a distinct resources provider instance");
    expect_true(firstResources != CResourcesProvider::getInstance(),
                "context-owned resources providers must not be the process-wide singleton");
    expect_true(secondResources != CResourcesProvider::getInstance(),
                "context-owned resources providers must not be the process-wide singleton");

    auto firstConfiguration = firstGame->getConfigurationProvider();
    auto secondConfiguration = secondGame->getConfigurationProvider();
    expect_true(firstConfiguration != secondConfiguration,
                "each game context should own a distinct configuration provider instance");

    // Register the SAME logical config id with DIFFERENT temp-file content, one value per game. The
    // fixture lives directly under config/ so getConfiguration routes it through CConfigResourceLoader.
    const auto itemsPath = std::filesystem::path(firstResources->getPath("config/items.json"));
    expect_true(!itemsPath.empty(), "items config should resolve before game-scoped provider isolation test");
    if (itemsPath.empty()) {
        return;
    }
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto logicalConfigName = "unit_game_scoped_provider_" + std::to_string(nonce) + ".json";
    const auto tempConfigPath = itemsPath.parent_path() / logicalConfigName;
    std::filesystem::remove(tempConfigPath);

    expect_true(write_text_file(tempConfigPath, R"({"marker":"first"})"),
                "game-scoped provider isolation fixture should be written");
    if (!std::filesystem::exists(tempConfigPath)) {
        return;
    }

    auto firstConfig = firstConfiguration->getConfiguration(logicalConfigName);
    expect_true(json_string_value(firstConfig, "marker") == "first",
                "the first game provider should cache the initial temp config content");

    // Rewrite the fixture: only the game whose provider already cached it keeps the original value, so
    // each assertion pins down exactly which game-scoped cache served the request.
    expect_true(write_text_file(tempConfigPath, R"({"marker":"second"})"),
                "game-scoped provider isolation fixture should be rewritable");

    auto secondConfig = secondConfiguration->getConfiguration(logicalConfigName);
    auto firstConfigAgain = firstConfiguration->getConfiguration(logicalConfigName);
    expect_true(firstConfigAgain == firstConfig, "a game provider should return its own cached config entry");
    expect_true(json_string_value(firstConfigAgain, "marker") == "first",
                "the first game provider should keep its own cached value after the file changes");
    expect_true(json_string_value(secondConfig, "marker") == "second",
                "the second game provider should load its own fresh value from the temp file");
    expect_true(secondConfig != firstConfig, "separate game providers must not share configuration cache entries");

    // The process-wide compatibility singleton must not have been populated by either game session:
    // asking it now reads the current on-disk value ("second"), never the first game's cached "first".
    auto singletonConfig = CConfigurationProvider::getConfig(logicalConfigName);
    expect_true(json_string_value(singletonConfig, "marker") == "second",
                "the process-wide configuration singleton must load independently of the game caches");
    expect_true(singletonConfig != firstConfig,
                "game providers must not populate the process-wide configuration singleton");

    std::filesystem::remove(tempConfigPath);

    // Object-construction path: register the SAME logical object id in each game's own object handler
    // with a DIFFERENT value, then build it from each game and assert each resolves its own config.
    const auto objectTypeId = "unit_game_scoped_item_" + std::to_string(nonce);
    auto firstItemConfig = std::make_shared<json>();
    (*firstItemConfig)["class"] = "CItem";
    (*firstItemConfig)["properties"]["power"] = 11;
    firstGame->getObjectHandler()->registerConfig(objectTypeId, firstItemConfig);

    auto secondItemConfig = std::make_shared<json>();
    (*secondItemConfig)["class"] = "CItem";
    (*secondItemConfig)["properties"]["power"] = 22;
    secondGame->getObjectHandler()->registerConfig(objectTypeId, secondItemConfig);

    expect_true(firstGame->getObjectHandler() != secondGame->getObjectHandler(),
                "each game context should own a distinct object handler instance");
    expect_true(firstGame->getObjectHandler()->getConfig(objectTypeId) == firstItemConfig,
                "the first game object handler should return only its own registered config");
    expect_true(secondGame->getObjectHandler()->getConfig(objectTypeId) == secondItemConfig,
                "the second game object handler should return only its own registered config");

    auto firstItem = firstGame->createObject<CItem>(objectTypeId);
    auto secondItem = secondGame->createObject<CItem>(objectTypeId);
    expect_true(firstItem && secondItem, "both games should build the configured object through their own handler");
    expect_true(firstItem && firstItem->getPower() == 11,
                "the first game should build the object from its own game-scoped config");
    expect_true(secondItem && secondItem->getPower() == 22,
                "the second game should build the object from its own game-scoped config");

    // Unsafe-path rejection is unchanged for context-owned providers.
    expect_true(firstResources->getPath("").empty(), "context-owned providers must reject empty resource paths");
    expect_true(firstResources->getPath("../config/items.json").empty(),
                "context-owned providers must reject parent-traversal resource paths");
    expect_true(firstResources->getPath("/etc/passwd").empty(),
                "context-owned providers must reject absolute resource paths");
}

void test_scoped_search_roots_resolve_active_map_assets() {
    // Two maps register the SAME logical filename under DIFFERENT scoped roots; the active scope must
    // decide which physical file resolves. A bare scoped filename must never resolve through the base
    // (process-wide) search path, so nothing here can collide with the real resource tree.
    const auto nonce = std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    const std::string assetName = "scoped_asset_" + nonce + ".txt";

    const auto tempRootA = std::filesystem::temp_directory_path() / ("scoped-root-a-" + nonce);
    const auto tempRootB = std::filesystem::temp_directory_path() / ("scoped-root-b-" + nonce);
    std::error_code errorCode;
    std::filesystem::create_directories(tempRootA, errorCode);
    std::filesystem::create_directories(tempRootB, errorCode);
    expect_true(write_text_file(tempRootA / assetName, "A"), "scoped root A fixture should be written");
    expect_true(write_text_file(tempRootB / assetName, "B"), "scoped root B fixture should be written");

    const auto canonicalRootA = std::filesystem::weakly_canonical(tempRootA, errorCode).string();
    const auto canonicalRootB = std::filesystem::weakly_canonical(tempRootB, errorCode).string();

    auto provider = std::make_shared<CResourcesProvider>();

    // Nothing is active yet, so a bare scoped filename must not resolve at the base search path.
    expect_true(provider->getPath(assetName).empty(), "scoped asset must not resolve at base search path");

    provider->addScopedRoot("mapA", tempRootA.string());
    provider->addScopedRoot("mapB", tempRootB.string());
    auto roots = provider->getScopedRoots();
    expect_true(std::find(roots.begin(), roots.end(), canonicalRootA) != roots.end(),
                "getScopedRoots should list the canonical root of mapA");
    expect_true(std::find(roots.begin(), roots.end(), canonicalRootB) != roots.end(),
                "getScopedRoots should list the canonical root of mapB");

    // Registered but inactive scopes must not change base resolution.
    expect_true(provider->getPath(assetName).empty(), "scoped asset must not resolve while no scope is active");

    provider->setActiveScope("mapA");
    const auto resolvedA = provider->getPath(assetName);
    expect_true(!resolvedA.empty(), "active scope mapA should resolve the scoped asset");
    expect_true(std::filesystem::weakly_canonical(std::filesystem::path(resolvedA).parent_path(), errorCode).string() ==
                    canonicalRootA,
                "active scope mapA should resolve the asset inside tempRootA");
    {
        std::ifstream stream(resolvedA);
        std::string contents((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
        expect_true(contents == "A", "active scope mapA should read the tempRootA copy of the asset");
    }

    provider->setActiveScope("mapB");
    const auto resolvedB = provider->getPath(assetName);
    expect_true(!resolvedB.empty(), "active scope mapB should resolve the scoped asset");
    expect_true(std::filesystem::weakly_canonical(std::filesystem::path(resolvedB).parent_path(), errorCode).string() ==
                    canonicalRootB,
                "active scope mapB should resolve the asset inside tempRootB");
    {
        std::ifstream stream(resolvedB);
        std::string contents((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
        expect_true(contents == "B", "active scope mapB should read the tempRootB copy of the asset");
    }

    // Security: an active scope must never relax the traversal/absolute guards.
    expect_true(provider->getPath("../escape.txt").empty(),
                "parent-traversal paths must be rejected even with an active scope");
    expect_true(provider->getPath("/etc/passwd").empty(), "absolute paths must be rejected even with an active scope");

    // Ref-counting: a second add keeps the root alive across one release.
    provider->addScopedRoot("mapA", tempRootA.string());
    provider->releaseScopedRoot("mapA");
    provider->setActiveScope("mapA");
    expect_true(!provider->getPath(assetName).empty(), "mapA should still resolve while its refcount is positive");

    provider->releaseScopedRoot("mapA");
    auto rootsAfterRelease = provider->getScopedRoots();
    expect_true(std::find(rootsAfterRelease.begin(), rootsAfterRelease.end(), canonicalRootA) ==
                    rootsAfterRelease.end(),
                "mapA root should be dropped once its refcount reaches zero");
    expect_true(provider->getActiveScope().empty(), "releasing the active scope to zero should clear the active scope");
    expect_true(provider->getPath(assetName).empty(), "mapA asset must not resolve after its scope is dropped");

    std::filesystem::remove_all(tempRootA, errorCode);
    std::filesystem::remove_all(tempRootB, errorCode);
}

void test_map_load_activates_scope_for_map_local_assets() {
    // Loading a map must register and activate that map's directory as a scoped search root, so a
    // map-local asset (e.g. an animation frame declared by a bare name) resolves through the active
    // scope while global assets keep resolving through the base search path. This is what the
    // animation/texture cache relies on, since both resolve through the game's resources provider.
    auto singletonResources = CResourcesProvider::getInstance();
    const auto itemsPath = std::filesystem::path(singletonResources->getPath("config/items.json"));
    expect_true(!itemsPath.empty(), "items config should resolve before the map-local asset scope test");
    if (itemsPath.empty()) {
        return;
    }
    const auto resourceRoot = itemsPath.parent_path().parent_path();

    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::string mapName = "unit_scope_map_" + std::to_string(nonce);
    const auto mapDir = resourceRoot / "maps" / mapName;
    std::filesystem::create_directories(mapDir);
    const auto mapConfigPath = mapDir / "map.json";
    const std::string localAssetName = "unit_scope_sprite_" + std::to_string(nonce) + ".png";
    const auto localAssetPath = mapDir / localAssetName;

    const bool fixtureWritten =
        write_text_file(mapConfigPath, R"({"marker":"scope","properties":{"x":0,"y":0,"z":0},"layers":[]})") &&
        write_text_file(localAssetPath, "png");
    expect_true(fixtureWritten, "temporary map fixture and map-local asset should be written");
    if (!std::filesystem::exists(mapConfigPath) || !std::filesystem::exists(localAssetPath)) {
        std::filesystem::remove_all(mapDir);
        return;
    }

    auto game = CGameLoader::loadGame();
    auto provider = game->getResourcesProvider();

    // Before the map loads, the map-local asset must NOT resolve by its bare name (no active scope).
    expect_true(provider->getPath(localAssetName).empty(),
                "a map-local asset must not resolve by bare name before its map is loaded");

    auto map = CMapLoader::loadNewMap(game, mapName);
    expect_true(map && map->getMapName() == mapName, "loadNewMap should load the authored map");

    expect_true(provider->getActiveScope() == mapName, "loadNewMap should activate the loaded map's scope");

    // The map-local asset now resolves by its bare name, inside the map directory.
    const auto resolvedLocal = provider->getPath(localAssetName);
    expect_true(!resolvedLocal.empty(), "the map-local asset should resolve through the active map scope");
    std::error_code errorCode;
    expect_true(std::filesystem::weakly_canonical(std::filesystem::path(resolvedLocal).parent_path(), errorCode) ==
                    std::filesystem::weakly_canonical(mapDir, errorCode),
                "the map-local asset should resolve inside the loaded map's directory");

    // Global assets keep their precedence: a base-path asset still resolves after a scope is active.
    expect_true(!provider->getPath("config/items.json").empty(),
                "global assets must still resolve through the base search path with a map scope active");

    std::filesystem::remove_all(mapDir);
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_resource_provider_paths_and_config_loader();
    test_resource_provider_save_uses_provider_root_when_cwd_changes();
    test_configuration_provider_instances_do_not_share_config_cache();
    test_load_game_creates_context_owned_providers();
    test_map_load_resolves_through_context_owned_providers();
    test_two_game_contexts_isolate_provider_cache_and_object_config();
    test_resource_plugin_trust_boundary_rejects_escapes();
    test_scoped_search_roots_resolve_active_map_assets();
    test_map_load_activates_scope_for_map_local_assets();

    return finish_tests();
}
