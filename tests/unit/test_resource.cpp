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
#include "test_harness.h"

#include <algorithm>
#include <filesystem>
#include <memory>
#include <string>

namespace {

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

} // namespace

int main() {
    test_resource_provider_paths_and_config_loader();

    return finish_tests();
}
