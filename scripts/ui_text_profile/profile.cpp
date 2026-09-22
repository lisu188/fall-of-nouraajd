/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CProvider.h"
#include "core/CRuntimeBridge.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"
#include "gui/CRenderContext.h"

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <pybind11/embed.h>

using ProfileClock = std::chrono::steady_clock;

double elapsedMs(ProfileClock::time_point started) {
    return std::chrono::duration<double, std::milli>(ProfileClock::now() - started).count();
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values.at(values.size() / 2);
}

int main(int argc, char **argv) {
    if (argc != 3) {
        std::cerr << "Usage: ui_profile <game res directory> <isolated writable directory>\n";
        return 2;
    }
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    const auto preferences = (std::filesystem::path(argv[2]) / "ui-profile-preferences.json").string();
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferences.c_str(), 1);
    pybind11::scoped_interpreter interpreter;
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    if (!CResourcesProvider::configurePlatformRoots(argv[1], argv[2]))
        return 3;
    auto gui = std::make_shared<CGui>();
    SDL_RendererInfo renderer{};
    if (!SDL_GetCurrentVideoDriver() || std::string(SDL_GetCurrentVideoDriver()) != "dummy" || !gui->getRenderer() ||
        SDL_GetRendererInfo(gui->getRenderer(), &renderer) != 0 || !renderer.name ||
        std::string(renderer.name) != "software") {
        std::cerr << "Refusing a non-isolated or non-software renderer.\n";
        return 4;
    }
    std::vector<std::string> strings;
    for (int i = 0; i < 200; ++i) {
        strings.push_back(
            "Adventure entry " + std::to_string(i) +
            ": Travel through the old forest, recover the lost provisions, and return to the northern gate.");
    }
    std::vector<double> coldSamples, warmSamples, redrawSamples;
    std::uint64_t dimensionsChecksum = 0;
    auto viewport = CUtil::rect(0, 0, 600, 180);
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "video=" << SDL_GetCurrentVideoDriver() << " renderer=" << renderer.name
              << " uniqueStrings=200 width=600 redrawPasses=200 redrawStrings=10 warmups=1 samples=7\n";
    for (int sample = -1; sample < 7; ++sample) {
        auto text = std::make_shared<CTextManager>(gui);
        auto started = ProfileClock::now();
        for (const auto &value : strings) {
            const auto size = text->getWrappedTextureSize(value, 600);
            if (size.first <= 0 || size.second <= 0) {
                std::cerr << "Font or text texture unavailable.\n";
                return 5;
            }
            dimensionsChecksum += size.first + size.second;
        }
        const double cold = elapsedMs(started);
        started = ProfileClock::now();
        for (const auto &value : strings) {
            const auto size = text->getWrappedTextureSize(value, 600);
            dimensionsChecksum += size.first + size.second;
        }
        const double warm = elapsedMs(started);
        gui->getRenderContext().resetStats();
        started = ProfileClock::now();
        for (int frame = 0; frame < 200; ++frame) {
            for (int entry = 0; entry < 10; ++entry) {
                text->drawTextScrolled(strings[entry], viewport, 0);
            }
        }
        const double redraw = elapsedMs(started);
        const auto copies = gui->getRenderContext().getStats();
        if (copies.attemptedCopies != 2000 || copies.successfulCopies != 2000 || copies.failedCopies != 0 ||
            copies.skippedCopies != 0) {
            std::cerr << "Deterministic redraw copy budget failed.\n";
            return 6;
        }
        if (sample >= 0) {
            coldSamples.push_back(cold);
            warmSamples.push_back(warm);
            redrawSamples.push_back(redraw);
            std::cout << "sample=" << sample << " coldMs=" << cold << " warmMs=" << warm << " redrawMs=" << redraw
                      << " copies=" << copies.successfulCopies << " failed=" << copies.failedCopies << '\n';
        }
    }
    std::cout << "median coldMs=" << median(coldSamples) << " warmMs=" << median(warmSamples)
              << " redrawMs=" << median(redrawSamples) << " dimensionsChecksum=" << dimensionsChecksum << '\n';
    gui->shutdown();
    return 0;
}
