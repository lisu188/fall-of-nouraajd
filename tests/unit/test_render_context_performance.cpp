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

#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CDetailViewport.h"
#include "gui/CLayout.h"
#include "gui/CRenderContext.h"
#include "gui/CSdlResources.h"
#include "gui/CTextManager.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/object/CGameGraphicsObject.h"
#include "test_harness.h"

#include <cstddef>
#include <memory>
#include <iostream>

namespace {

constexpr int SCENE_COLUMNS = 8;
constexpr int SCENE_ROWS = 6;
constexpr int SCENE_TILE_SIZE = 16;
constexpr std::size_t SCENE_COPIES = static_cast<std::size_t>(SCENE_COLUMNS) * SCENE_ROWS;
constexpr std::size_t BULK_COPY_COUNT = 512;

// Deterministic scene object: exactly one render-context copy per rendered frame.
class TextureBlitObject : public CGameGraphicsObject {
  public:
    TextureBlitObject(SDL_Texture *texture, SDL_Rect target) : texture(texture), target(target) {}

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect>, int) override {
        gui->getRenderContext().copy(texture, nullptr, &target);
    }

  private:
    SDL_Texture *texture;
    SDL_Rect target;
};

std::shared_ptr<CGui> make_headless_gui() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");
    return std::make_shared<CGui>();
}

fn::sdl::TexturePtr make_solid_texture(const std::shared_ptr<CGui> &gui) {
    auto surface = fn::sdl::SurfacePtr(
        SDL_SAFE(SDL_CreateRGBSurfaceWithFormat(0, SCENE_TILE_SIZE, SCENE_TILE_SIZE, 32, SDL_PIXELFORMAT_RGBA32)));
    if (!surface) {
        return nullptr;
    }
    SDL_SAFE(SDL_FillRect(surface.get(), nullptr, SDL_MapRGBA(surface->format, 32, 96, 160, 255)));
    return fn::sdl::TexturePtr(SDL_SAFE(SDL_CreateTextureFromSurface(gui->getRenderer(), surface.get())));
}

// Operation-count guard (no wall-clock timing): every valid copy request must
// translate into exactly one attempted and one successful SDL copy, and every
// invalid request must be skipped before reaching SDL without ever failing.
void test_render_context_bulk_copy_accounting_is_exact() {
    auto gui = make_headless_gui();
    auto texture = make_solid_texture(gui);
    expect_true(texture != nullptr, "render context perf guard should create a scene texture");
    if (!texture) {
        return;
    }

    auto &renderContext = gui->getRenderContext();
    renderContext.resetStats();

    SDL_Rect target = {1, 2, SCENE_TILE_SIZE, SCENE_TILE_SIZE};
    for (std::size_t i = 0; i < BULK_COPY_COUNT; ++i) {
        renderContext.copy(texture.get(), nullptr, &target);
    }

    const auto bulk = renderContext.getStats();
    expect_true(bulk.attemptedCopies == BULK_COPY_COUNT, "bulk copies should attempt exactly one SDL copy each");
    expect_true(bulk.successfulCopies == BULK_COPY_COUNT, "bulk copies of a valid texture should all succeed");
    expect_true(bulk.failedCopies == 0, "bulk copies of a valid texture should never fail");
    expect_true(bulk.skippedCopies == 0, "bulk copies of a valid texture should never be skipped");

    renderContext.resetStats();
    for (std::size_t i = 0; i < BULK_COPY_COUNT; ++i) {
        renderContext.copy(nullptr, nullptr, &target);
    }

    const auto skipped = renderContext.getStats();
    expect_true(skipped.attemptedCopies == BULK_COPY_COUNT, "null-texture copies should still be counted as attempts");
    expect_true(skipped.skippedCopies == BULK_COPY_COUNT, "null-texture copies should be skipped before reaching SDL");
    expect_true(skipped.successfulCopies == 0, "null-texture copies should never succeed");
    expect_true(skipped.failedCopies == 0, "null-texture copies should be skipped, not failed");
}

// Frame-stability guard: rendering the same unchanged scene twice must produce
// identical per-frame copy counts (no per-frame growth or hidden amplification),
// with zero failed copies on the software renderer.
void test_render_context_stable_scene_frame_copies_do_not_grow() {
    auto gui = make_headless_gui();
    auto texture = make_solid_texture(gui);
    expect_true(texture != nullptr, "render context frame guard should create a scene texture");
    if (!texture) {
        return;
    }

    auto &renderContext = gui->getRenderContext();

    renderContext.resetStats();
    gui->render(0);
    const auto baseline = renderContext.getStats();
    expect_true(baseline.failedCopies == 0, "an empty gui frame should not fail any copies");

    for (int row = 0; row < SCENE_ROWS; ++row) {
        for (int column = 0; column < SCENE_COLUMNS; ++column) {
            SDL_Rect target = {column * SCENE_TILE_SIZE, row * SCENE_TILE_SIZE, SCENE_TILE_SIZE, SCENE_TILE_SIZE};
            gui->pushChild(std::make_shared<TextureBlitObject>(texture.get(), target));
        }
    }

    renderContext.resetStats();
    gui->render(0);
    const auto first = renderContext.getStats();

    renderContext.resetStats();
    gui->render(0);
    const auto second = renderContext.getStats();

    expect_true(first.attemptedCopies == baseline.attemptedCopies + SCENE_COPIES,
                "a stable scene frame should attempt exactly one copy per scene object");
    expect_true(first.successfulCopies == first.attemptedCopies - first.skippedCopies,
                "every non-skipped copy of a stable scene frame should succeed");
    expect_true(first.failedCopies == 0, "a stable scene frame should not fail any copies");
    expect_true(second.attemptedCopies == first.attemptedCopies,
                "re-rendering an unchanged scene must not grow per-frame attempted copies");
    expect_true(second.successfulCopies == first.successfulCopies,
                "re-rendering an unchanged scene must not change per-frame successful copies");
    expect_true(second.skippedCopies == first.skippedCopies,
                "re-rendering an unchanged scene must not change per-frame skipped copies");
    expect_true(second.failedCopies == 0, "re-rendering an unchanged scene must not fail any copies");
}

void test_styled_text_reuses_bounded_cache() {
    auto gui = make_headless_gui();
    auto text = gui->getTextManager();
    auto rect = CUtil::rect(0, 0, 600, 120);
    constexpr int entries = 200;
    constexpr int passes = 10;
    for (int index = 0; index < entries; ++index) {
        const auto measured = text->measureText("Inventory entry " + std::to_string(index), rect->w);
        expect_true(measured.first > 0 && measured.second > 0, "bundled fonts must load in performance guards");
    }
    const auto loads = text->getTextureLoadCount();
    gui->getRenderContext().resetStats();
    for (int pass = 0; pass < passes; ++pass) {
        for (int index = 0; index < entries; ++index) {
            text->drawTextStyled("Inventory entry " + std::to_string(index), rect);
        }
    }
    const auto copies = gui->getRenderContext().getStats();
    expect_true(text->getTextureLoadCount() == loads, "unchanged text must not rasterize again on subsequent frames");
    expect_true(text->getCachedTextureCount() == entries, "repeated text must retain exactly the warmed entries");
    expect_true(copies.successfulCopies == entries * passes && copies.failedCopies == 0,
                "cached text must issue exactly one successful copy per draw");
    for (int index = 0; index < 800; ++index)
        text->measureText("History entry " + std::to_string(index), rect->w);
    expect_true(text->getCachedTextureCount() <= 512, "long sessions must respect the text texture budget");
    expect_true(text->getCachedFontCount() <= 24, "font glyph caches must remain bounded");
    text->clearCache();
    const auto beforeInvalidation = text->getTextureLoadCount();
    text->measureText("Inventory entry 0", rect->w);
    expect_true(text->getTextureLoadCount() == beforeInvalidation + 1,
                "explicit invalidation must rebuild obsolete font textures exactly once");
    std::cout << "[text cache] warm entries=" << entries << " redraw copies=" << copies.successfulCopies
              << " redraw loads=" << text->getTextureLoadCount() - beforeInvalidation - 1
              << " texture budget=512 font budget=24\n";
}

void test_choice_layout_does_not_rasterize_hidden_rows_on_redraw() {
    auto gui = make_headless_gui();
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    std::vector<CGameCampaignBrowserPanel::ChoiceOption> choices;
    for (int index = 0; index < 700; ++index)
        choices.push_back({std::to_string(index), "Adventure " + std::to_string(index), "Preview", true});
    browser->configureChoices("Saved adventures", choices, "Load save", "Back");
    const auto bounds = CUtil::rect(0, 0, 1800, 1000);
    auto layout = std::make_shared<CLayout>();
    layout->setRuntimeRect(bounds);
    browser->setLayout(layout);
    browser->renderObject(gui, bounds, 0);
    browser->renderObject(gui, bounds, 0);
    const auto loads = gui->getTextManager()->getTextureLoadCount();
    for (int frame = 0; frame < 4; ++frame)
        browser->renderObject(gui, bounds, 0);
    const auto redrawLoads = gui->getTextManager()->getTextureLoadCount() - loads;
    expect_true(redrawLoads == 0, "unchanged long choice lists reuse row metrics without churning the text cache");
    expect_true(browser->getChoiceViewport().h >= 400,
                "the long-list render guard measures a usable viewport with valid panel geometry");
    browser->configureChoices("Changed choices", {{"long", "A newly wrapped label for a different choice", "", true}},
                              "Choose", "Back");
    const auto changedBounds = CUtil::rect(0, 0, 600, 676);
    layout->setRuntimeRect(changedBounds);
    browser->renderObject(gui, changedBounds, 0);
    expect_true(gui->getTextManager()->getTextureLoadCount() > loads,
                "reconfigured choices and viewport changes must rebuild their text metrics");
    std::cout << "[choice layout] rows=700 redraws=4 redraw texture loads=" << redrawLoads << " budget=0\n";
}

void test_detail_layout_draws_only_visible_cached_paragraphs() {
    auto gui = make_headless_gui();
    auto textManager = gui->getTextManager();
    std::string text;
    for (int index = 0; index < 700; ++index) {
        text += "Journal entry " + std::to_string(index) + ": a discovered clue and its reward.\n";
    }
    DetailViewport::Layout layout;
    const auto viewport = CUtil::rect(0, 0, 600, 180);
    layout.update(gui, text, viewport->w);
    const int bottom = std::max(0, layout.getContentHeight() - viewport->h);
    textManager->clearCache();
    const auto coldLoads = textManager->getTextureLoadCount();
    layout.draw(gui, viewport, bottom);
    const auto visibleLoads = textManager->getTextureLoadCount() - coldLoads;
    expect_true(visibleLoads > 0 && visibleLoads <= 16,
                "scrolling to a long detail ending must load only the visible paragraphs");
    const auto warmLoads = textManager->getTextureLoadCount();
    gui->getRenderContext().resetStats();
    for (int frame = 0; frame < 25; ++frame) {
        expect_true(!layout.update(gui, text, viewport->w), "warm detail frames must not remeasure hidden paragraphs");
        layout.draw(gui, viewport, bottom);
    }
    const auto redrawLoads = textManager->getTextureLoadCount() - warmLoads;
    const auto copies = gui->getRenderContext().getStats();
    expect_true(redrawLoads == 0, "warm long-detail frames must load zero text textures");
    expect_true(copies.successfulCopies == visibleLoads * 25 && copies.failedCopies == 0,
                "long details must copy only their visible paragraphs on every redraw");
    expect_true(textManager->getCachedTextureCount() <= 16,
                "drawing long-detail endings must not repopulate the cache with hidden text");
    std::cout << "[detail layout] paragraphs=700 redraws=25 visible loads=" << visibleLoads
              << " visible budget=16 redraw texture loads=" << redrawLoads << " redraw budget=0\n";
}

void test_reward_receipt_draws_only_visible_cached_rows() {
    auto gui = make_headless_gui();
    auto textManager = gui->getTextManager();
    auto rewards = std::make_shared<CGameLootPanel>();
    std::set<std::shared_ptr<CItem>> items;
    for (int index = 0; index < 700; ++index) {
        auto item = std::make_shared<CItem>();
        item->setLabel("Recovered relic " + std::to_string(1000 + index) + " from the forgotten archive");
        items.insert(item);
    }
    rewards->setItems(items);
    const auto viewport = CUtil::rect(0, 0, 600, 180);
    rewards->renderRewards(gui, viewport, 0);
    rewards->mouseWheelEvent(gui, SDL_MOUSEWHEEL, 1, 1, 0, -1000000);
    textManager->clearCache();
    const auto coldLoads = textManager->getTextureLoadCount();
    rewards->renderRewards(gui, viewport, 0);
    const auto visibleLoads = textManager->getTextureLoadCount() - coldLoads;
    expect_true(visibleLoads > 0 && visibleLoads <= 16,
                "long reward receipts must rasterize only a bounded visible set after scrolling");
    const auto warmLoads = textManager->getTextureLoadCount();
    gui->getRenderContext().resetStats();
    for (int frame = 0; frame < 25; ++frame) {
        rewards->renderRewards(gui, viewport, 0);
    }
    const auto redrawLoads = textManager->getTextureLoadCount() - warmLoads;
    const auto copies = gui->getRenderContext().getStats();
    expect_true(redrawLoads == 0, "warm long-receipt frames must load zero additional text textures");
    expect_true(copies.successfulCopies > 0 && copies.successfulCopies <= 16 * 25 && copies.failedCopies == 0,
                "long reward receipts must copy only visible rows on each warm frame");
    expect_true(textManager->getCachedTextureCount() <= 16,
                "warm receipt redraws must not repopulate the texture cache with hidden rows");
    std::cout << "[reward receipt] rows=700 redraws=25 visible loads=" << visibleLoads
              << " visible budget=16 redraw texture loads=" << redrawLoads
              << " redraw budget=0 copies=" << copies.successfulCopies << " copy budget=400\n";
}

} // namespace

void run_render_context_performance_tests() {
    test_render_context_bulk_copy_accounting_is_exact();
    test_render_context_stable_scene_frame_copies_do_not_grow();
    test_styled_text_reuses_bounded_cache();
    test_choice_layout_does_not_rasterize_hidden_rows_on_redraw();
    test_detail_layout_draws_only_visible_cached_paragraphs();
    test_reward_receipt_draws_only_visible_cached_rows();
}
