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
#include "test_harness.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
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

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_resource_provider_paths_and_config_loader();
    test_resource_provider_save_uses_provider_root_when_cwd_changes();
    test_load_game_creates_context_owned_providers();

    return finish_tests();
}
