/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CProvider.h"
#include "core/CRuntimeBridge.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"

#include <filesystem>
#include <iostream>
#include <pybind11/embed.h>

int main(int argc, char **argv) {
    const bool unattached = argc == 4 && std::string(argv[3]) == "--unattached-fixture";
    if (argc != 3 && !unattached) {
        std::cerr << "Usage: ui_choice_profile <game res directory> <isolated writable directory> "
                     "[--unattached-fixture]\n";
        return 2;
    }
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    const auto preferences = (std::filesystem::path(argv[2]) / "choice-profile-preferences.json").string();
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferences.c_str(), 1);
    pybind11::scoped_interpreter interpreter;
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    if (!CResourcesProvider::configurePlatformRoots(argv[1], argv[2]))
        return 3;
    auto gui = std::make_shared<CGui>();
    SDL_RendererInfo renderer{};
    if (!SDL_GetCurrentVideoDriver() || std::string(SDL_GetCurrentVideoDriver()) != "dummy" ||
        SDL_GetRendererInfo(gui->getRenderer(), &renderer) != 0 || !renderer.name ||
        std::string(renderer.name) != "software") {
        std::cerr << "Refusing a non-isolated or non-software renderer.\n";
        return 4;
    }
    gui->applyUiPreferences("{}");
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    std::vector<CGameCampaignBrowserPanel::ChoiceOption> choices;
    for (int index = 0; index < 700; ++index)
        choices.push_back({std::to_string(index), "Adventure " + std::to_string(index), "Preview", true});
    browser->configureChoices("Saved adventures", choices, "Load save", "Back");
    auto bounds = std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 1800, 1000});
    if (!unattached) {
        auto layout = std::make_shared<CLayout>();
        layout->setRuntimeRect(bounds);
        browser->setLayout(layout);
    }
    std::cout << "video=dummy renderer=software rows=700 layout=" << (unattached ? "unattached" : "1800x1000") << '\n';
    for (int frame = 0; frame < 5; ++frame) {
        const auto before = gui->getTextManager()->getTextureLoadCount();
        browser->renderObject(gui, bounds, 0);
        std::cout << "frame=" << frame << " textureLoads=" << gui->getTextManager()->getTextureLoadCount() - before
                  << " cached=" << gui->getTextManager()->getCachedTextureCount() << '\n';
    }
    gui->shutdown();
    return 0;
}
