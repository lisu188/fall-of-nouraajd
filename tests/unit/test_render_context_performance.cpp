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

#include "core/CAsync.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CStats.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CDetailViewport.h"
#include "gui/CLayout.h"
#include "gui/CMovementAnimation.h"
#include "gui/CRenderContext.h"
#include "gui/CSdlResources.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/object/CGameGraphicsObject.h"
#include "handler/CObjectHandler.h"
#include "object/CInteraction.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <cstddef>
#include <array>
#include <memory>
#include <iostream>
#include <type_traits>

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

class CountingRenderLayout : public CLayout {
  public:
    std::size_t resolutions = 0;

    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject>) override {
        ++resolutions;
        return CUtil::rect(0, 0, SCENE_TILE_SIZE, SCENE_TILE_SIZE);
    }
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

void testBackgroundFreeObjectsResolveLayoutOnlyForDrawing() {
    auto gui = make_headless_gui();
    auto object = std::make_shared<CGameGraphicsObject>();
    auto layout = std::make_shared<CountingRenderLayout>();
    object->setLayout(layout);
    gui->pushChild(object);
    constexpr std::size_t frames = 64;
    for (std::size_t frame = 0; frame < frames; ++frame)
        gui->render(static_cast<int>(frame));
    expect_true(layout->resolutions == frames,
                "background-free map objects must resolve their layout only once per rendered frame");
    const auto emptyBackgroundResolutions = layout->resolutions;
    object->setBackground("images/panel");
    gui->getRenderContext().resetStats();
    gui->render(0);
    expect_true(layout->resolutions == emptyBackgroundResolutions + 2,
                "objects with a background must still resolve both background and foreground layouts");
    expect_true(gui->getRenderContext().getStats().successfulCopies == 1,
                "a configured background must still render exactly once");
    std::cout << "[render layout] background-free frames=" << frames << " resolutions=" << emptyBackgroundResolutions
              << '\n';
}

void testUnchangedLayoutValuesAreParsedOnlyOnce() {
    auto parent = std::make_shared<CGameGraphicsObject>();
    auto parentLayout = std::make_shared<CLayout>();
    parentLayout->setRect(0, 0, 800, 600);
    parent->setLayout(parentLayout);
    auto child = std::make_shared<CGameGraphicsObject>();
    auto layout = std::make_shared<CLayout>();
    layout->setX("25%");
    layout->setY("-10");
    layout->setW("50%");
    layout->setH("33.5%");
    child->setLayout(layout);
    parent->pushChild(child);
    const auto first = layout->getRect(child);
    expect_true(first->x == 200 && first->y == -10 && first->w == 400 && first->h == 201,
                "layout cache must retain legacy percentage resolution and integer truncation");
    const auto warmed = layout->getValueParseCountForTesting();
    expect_true(warmed == 4, "warming a layout must parse at most its four authored values");
    for (int frame = 0; frame < 256; ++frame) {
        parentLayout->setRuntimeRect(frame, 2 * frame, 800 + 4 * frame, 600);
        const auto rect = layout->getRect(child);
        expect_true(rect->x == 200 + 2 * frame && rect->w == 400 + 2 * frame,
                    "cached percentages must resolve against the current parent geometry");
    }
    expect_true(layout->getValueParseCountForTesting() == warmed,
                "repeated frames and parent resizing must not reparse unchanged layout strings");
    layout->setX("25%");
    layout->getRect(child);
    expect_true(layout->getValueParseCountForTesting() == warmed,
                "setting an identical layout value must retain the parsed cache entry");
    layout->setX("40%");
    layout->getRect(child);
    expect_true(layout->getValueParseCountForTesting() == warmed + 1,
                "changing one layout value must parse exactly one new value");
    std::cout << "[layout parse cache] warm parses=" << warmed
              << " repeated-frame parses=0 changed-value parses=" << layout->getValueParseCountForTesting() - warmed
              << '\n';
}

void testTerrainTextureScalingIsReusedAndBounded() {
    auto gui = make_headless_gui();
    auto cache = gui->getTextureCache();
    const SDL_Rect target{32, 32, 32, 32};
    auto texture = cache->getTileTexture("images/tiles/grass", target);
    expect_true(texture != nullptr, "terrain scaling guard must load the shipped opaque grass texture");
    if (!texture)
        return;
    int width = 0;
    int height = 0;
    SDL_QueryTexture(texture, nullptr, nullptr, &width, &height);
    expect_true(width == target.w && height == target.h,
                "eligible software terrain must use a texture at the actual tile size");
    const auto loads = cache->getTextureLoadCountForTesting();
    const auto builds = cache->getTileTextureBuildCountForTesting();
    expect_true(builds == 1, "warming one software terrain extent must perform exactly one scale operation");
    constexpr int lookups = 4096;
    for (int lookup = 0; lookup < lookups; ++lookup)
        expect_true(cache->getTileTexture("images/tiles/grass", target) == texture,
                    "unchanged terrain extents must reuse the warmed renderer texture");
    expect_true(cache->getTextureLoadCountForTesting() == loads &&
                    cache->getTileTextureBuildCountForTesting() == builds,
                "rendering stable terrain must neither decode PNGs nor rescale surfaces on subsequent frames");
    for (const int size : {50, 64, 32})
        cache->getTileTexture("images/tiles/grass", SDL_Rect{32, 32, size, size});
    expect_true(cache->getTileTextureEntryCountForTesting() == 1,
                "tile size changes must replace the single scaled extent retained for each terrain path");
    expect_true(cache->getTileTextureBuildCountForTesting() == builds + 3,
                "each new terrain extent must scale exactly once");
    std::cout << "[terrain texture cache] repeated lookups=" << lookups << " repeated loads=0 repeated scales=0"
              << " retained extents=" << cache->getTileTextureEntryCountForTesting() << " extent budget=1\n";
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

void testCharacterAbilityDetailsReuseTexturesAndRefreshAvailability() {
    auto gui = make_headless_gui();
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->getObjectHandler()->registerType("CPlayerController", []() { return std::make_shared<CPlayerController>(); });
    game->getObjectHandler()->registerType("CPlayerFightController",
                                           []() { return std::make_shared<CPlayerFightController>(); });
    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);

    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    player->setName("player");
    player->setLevel(1);
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("intelligence");
    stats->setIntelligence(10);
    stats->setStamina(10);
    player->setBaseStats(stats);
    player->setHp(17);
    player->setMana(12);
    map->setObjects({player});
    expect_true(map->getPlayer() == player, "ability render guard must use the map's actual player");

    auto action = std::make_shared<CInteraction>();
    action->setGame(game);
    action->setName("guardWard");
    action->setTypeId("guardWard");
    action->setLabel("Watcher's ward");
    action->setManaCost(8);
    action->setSelfTarget(true);
    const std::string description =
        "Raise a ward around the caster, protecting them while they prepare their next move. "
        "The effect follows the selected ability's existing combat rules and ends when its protection expires. "
        "Read the mana requirement and target before choosing an action in combat.";
    action->setDescription(description);
    player->addAction(action);
    auto panel = std::make_shared<CGameCharacterPanel>();
    panel->interactionsCallback(gui, 0, action);
    const auto hp = player->getHp();
    const auto mana = player->getMana();
    const auto turn = map->getTurn();
    const auto viewport = CUtil::rect(0, 0, 320, 240);
    auto textManager = gui->getTextManager();
    expect_true(textManager->measureText(description, viewport->w).second >
                    textManager->measureText("Short description", viewport->w).second,
                "ability render guard must exercise wrapped descriptions");
    textManager->clearCache();
    const auto availableDetails = panel->getAbilityDetails(gui);
    expect_true(availableDetails.find(description) != std::string::npos,
                "selected ability details must include the authored effect description");
    const auto coldLoads = textManager->getTextureLoadCount();
    panel->renderAbilityDetails(gui, viewport, 0);
    const auto initialLoads = textManager->getTextureLoadCount() - coldLoads;
    expect_true(initialLoads > 0 && initialLoads <= 16, "ability details must use a bounded initial texture set");
    const auto warmLoads = textManager->getTextureLoadCount();
    gui->getRenderContext().resetStats();
    for (int frame = 0; frame < 25; ++frame) {
        panel->renderAbilityDetails(gui, viewport, 0);
    }
    const auto redrawLoads = textManager->getTextureLoadCount() - warmLoads;
    expect_true(redrawLoads == 0, "unchanged ability details must load zero new textures across 25 redraws");
    expect_true(player->getHp() == hp && player->getMana() == mana && map->getTurn() == turn,
                "reading available ability details must not change health, mana, or the map turn");

    player->setMana(3);
    const auto unavailableDetails = panel->getAbilityDetails(gui);
    expect_true(unavailableDetails != availableDetails &&
                    unavailableDetails.find("Unavailable: Needs 5 more mana.") != std::string::npos,
                "mana changes must invalidate the displayed ability availability");
    const auto beforeRefresh = textManager->getTextureLoadCount();
    panel->renderAbilityDetails(gui, viewport, 0);
    const auto refreshLoads = textManager->getTextureLoadCount() - beforeRefresh;
    expect_true(refreshLoads > 0 && refreshLoads <= 16, "changed availability must refresh a bounded texture set");
    const auto refreshedLoads = textManager->getTextureLoadCount();
    for (int frame = 0; frame < 25; ++frame) {
        panel->renderAbilityDetails(gui, viewport, 0);
    }
    const auto unavailableRedrawLoads = textManager->getTextureLoadCount() - refreshedLoads;
    const auto copies = gui->getRenderContext().getStats();
    expect_true(unavailableRedrawLoads == 0, "unchanged unavailable ability details must reuse refreshed textures");
    expect_true(copies.successfulCopies > 0 && copies.failedCopies == 0,
                "ability detail redraws must render successfully on the software renderer");
    expect_true(player->getHp() == hp && player->getMana() == 3 && map->getTurn() == turn,
                "reading unavailable ability details must not change health, mana, or the map turn");
    std::cout << "[character ability] redraws=25 initial loads=" << initialLoads
              << " initial budget=16 redraw loads=" << redrawLoads
              << " redraw budget=0 availability refresh loads=" << refreshLoads
              << " refresh budget=16 unavailable redraw loads=" << unavailableRedrawLoads
              << " unavailable redraw budget=0\n";
    game->getContext()->shutdown();
}

void testLoadingReaderReusesWarmTextures() {
    auto gui = make_headless_gui();
    auto reader = std::make_shared<CGameTextPanel>();
    reader->setTitle("Please wait");
    reader->setText("Loading saved adventure...");
    reader->setCloseable(false);
    reader->setLayout(std::make_shared<CLayout>());
    reader->getLayout()->setRect(40, 30, 900, 640);
    gui->pushChild(reader);
    auto text = gui->getTextManager();
    text->clearCache();
    const auto before = text->getTextureLoadCount();
    gui->render(0);
    const auto initialLoads = text->getTextureLoadCount() - before;
    expect_true(initialLoads > 0 && initialLoads <= 8, "the waiting reader uses a bounded initial texture set");
    const auto warm = text->getTextureLoadCount();
    gui->getRenderContext().resetStats();
    for (int frame = 0; frame < 25; ++frame)
        gui->render(0);
    const auto redrawLoads = text->getTextureLoadCount() - warm;
    const auto copies = gui->getRenderContext().getStats();
    expect_true(redrawLoads == 0, "an unchanged waiting footer and message load zero textures over 25 redraws");
    expect_true(copies.successfulCopies > 0 && copies.failedCopies == 0 && reader->getParent() == gui,
                "the waiting reader renders successfully and remains attached after redraws");
    std::cout << "[loading reader] redraws=25 initial loads=" << initialLoads
              << " initial budget=8 redraw loads=" << redrawLoads << " redraw budget=0\n";
    reader->close();
}

void testMovementSamplingReusesOneBoundedRecord() {
    static_assert(std::is_trivially_copyable_v<CMovementAnimation>,
                  "movement interpolation must retain scalar state without an allocated history");
    constexpr std::size_t moves = 512;
    constexpr std::size_t samplesPerMove = 16;
    constexpr int tileSize = 64;
    constexpr std::array<Coords, 4> directions = {NORTH, EAST, SOUTH, WEST};
    CMovementAnimation animation;
    std::size_t samples = 0;
    std::size_t completedMoves = 0;
    std::size_t movingActorSamples = 0;
    std::size_t movingCameraSamples = 0;
    bool offsetsBounded = true;
    bool cameraConsistent = true;
    bool reducedMotionSnaps = true;
    bool completedOffsetsClear = true;

    performance_guard::resetMapCoordinateLookupProbe();
    for (std::size_t move = 0; move < moves; ++move) {
        const Uint32 startedAt = 1000 + static_cast<Uint32>(move) * 200;
        const bool reducedMotion = move % 5 == 0;
        const bool movesCamera = move % 3 == 0;
        animation.begin(directions[move % directions.size()], startedAt, reducedMotion, movesCamera);
        for (std::size_t sample = 0; sample < samplesPerMove; ++sample) {
            animation.advance(startedAt + static_cast<Uint32>(sample) * 10);
            const auto actor = animation.actorOffset(tileSize);
            const auto camera = animation.cameraOffset(tileSize);
            offsetsBounded &= std::abs(actor.x) <= tileSize && std::abs(actor.y) <= tileSize &&
                              std::abs(camera.x) <= tileSize && std::abs(camera.y) <= tileSize;
            cameraConsistent &=
                movesCamera ? actor.x + camera.x == 0 && actor.y + camera.y == 0 : camera.x == 0 && camera.y == 0;
            reducedMotionSnaps &= !reducedMotion || (actor.x == 0 && actor.y == 0 && camera.x == 0 && camera.y == 0);
            movingActorSamples += actor.x != 0 || actor.y != 0;
            movingCameraSamples += camera.x != 0 || camera.y != 0;
            ++samples;
        }
        completedMoves += animation.isCompleted();
        animation.advance(startedAt + 10000);
        const auto actor = animation.actorOffset(tileSize);
        const auto camera = animation.cameraOffset(tileSize);
        completedOffsetsClear &=
            animation.isCompleted() && actor.x == 0 && actor.y == 0 && camera.x == 0 && camera.y == 0;
    }
    const auto coordinateLookups = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();

    expect_true(sizeof(animation) <= 64, "one movement interpolation record must fit its 64-byte state budget");
    expect_true(samples == moves * samplesPerMove && completedMoves == moves,
                "fixed movement samples must complete every reused record without a growing queue");
    expect_true(offsetsBounded && cameraConsistent && reducedMotionSnaps && completedOffsetsClear,
                "movement sampling must keep bounded offsets and clear completed or reduced-motion translations");
    expect_true(movingActorSamples > 0 && movingCameraSamples > 0,
                "the movement guard must exercise both sprite and camera interpolation");
    expect_true(coordinateLookups == 0, "pure movement frame sampling must perform zero map coordinate lookups");
    std::cout << "[movement sampling] moves=" << moves << " samples=" << samples
              << " sample budget=" << moves * samplesPerMove << " reused records=1 state bytes=" << sizeof(animation)
              << " state budget=64 coordinate lookups=" << coordinateLookups << " lookup budget=0\n";
}

struct ActiveTurnOverlayGate {
    bool entered = false;
    bool released = false;
};

vstd::task<void> waitForActiveTurnOverlay(std::shared_ptr<ActiveTurnOverlayGate> gate) {
    gate->entered = true;
    co_await vstd::until(vstd::event_loop<>::instance(), [gate] { return gate->released; });
}

void testActiveTurnOverlayReadsReuseTheCommittedPlayerRoute() {
    constexpr int routeLength = 32;
    constexpr int queries = 20'000;
    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType("CPlayerController", [] { return std::make_shared<CPlayerController>(); });
    game->getObjectHandler()->registerType("CPlayerFightController",
                                           [] { return std::make_shared<CPlayerFightController>(); });
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    map->setGame(game);
    map->setXBounds({{0, routeLength}});
    map->setYBounds({{0, 0}});
    for (int x = 0; x <= routeLength; ++x) {
        auto tile = std::make_shared<CTile>();
        tile->setGame(game);
        tile->setCanStep(true);
        map->addTile(tile, x, 0, 0);
    }
    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    player->setBaseStats(stats);
    map->setPlayer(player);
    auto controller = std::dynamic_pointer_cast<CPlayerController>(player->getController());
    controller->setTarget(player, Coords(routeLength, 0, 0));
    auto gate = std::make_shared<ActiveTurnOverlayGate>();
    auto loop = vstd::event_loop<>::instance();
    const int turn = map->getTurn();
    auto movement = game->getContext()->spawnTask(
        map->moveAsync([gate](std::shared_ptr<CMapObject>, Coords, Coords) { return waitForActiveTurnOverlay(gate); }));
    loop->runUntilIdle();
    expect_true(gate->entered && !movement.finished() && map->isMoving() && player->getCoords() == Coords(1, 0, 0),
                "the route-overlay guard must hold a real turn after coordinate commitment and before cursor advance");
    const auto navigation = map->getNavigationService();
    const auto budget = navigation->budget();
    const auto retainedBefore = budget->used();
    const auto searchesBefore = navigation->searchCount();
    const auto requestBefore = controller->getRequestSerial();
    const auto probesBefore = controller->getOverlayLookupCount();
    performance_guard::resetMapCoordinateLookupProbe();
    bool allRouteCellsVisible = true;
    for (int index = 0; index < queries; ++index) {
        const auto result = controller->isOnPath(player, Coords(2 + (index * 17) % (routeLength - 1), 0, 0));
        allRouteCellsVisible &= result.first && result.second == Coords::EAST;
    }
    const auto coordinateLookups = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();
    const auto indexProbes = controller->getOverlayLookupCount() - probesBefore;
    const auto retainedAfter = budget->used();
    const auto searchesAfter = navigation->searchCount();
    const auto requestAfter = controller->getRequestSerial();
    expect_true(allRouteCellsVisible && indexProbes == queries,
                "active-turn overlay queries must each perform one indexed probe and preserve every future route cell");
    expect_true(requestAfter == requestBefore && searchesAfter == searchesBefore && retainedBefore > 0 &&
                    retainedAfter == retainedBefore,
                "active-turn rendering must neither cancel or replan the route nor change its retained allocation");
    expect_true(coordinateLookups == 0,
                "cached active-turn overlay queries must perform zero map coordinate lookups or movement validation");
    expect_true(!movement.finished() && map->isMoving() && map->getTurn() == turn &&
                    player->getCoords() == Coords(1, 0, 0),
                "twenty thousand overlay reads must not resume presentation or advance the pending map turn");
    gate->released = true;
    loop->runUntilIdle();
    expect_true(movement.finished() && !map->isMoving() && map->getTurn() == turn + 1 &&
                    player->getCoords() == Coords(1, 0, 0),
                "releasing the fixed presentation gate must finish exactly the original map turn");
    if (movement.finished()) {
        movement.get();
        expect_true(game_async::run(controller->controlAsync(player), game_async::WaitMode::PostedWork) ==
                        Coords(2, 0, 0),
                    "the real player route must continue at its next step after the measured overlay reads");
    }
    std::cout << "[active-turn route overlay] route=" << routeLength << " queries=" << queries
              << " index probes=" << indexProbes << " index budget=" << queries
              << " coordinate lookups=" << coordinateLookups
              << " coordinate budget=0 retained before=" << retainedBefore << " retained after=" << retainedAfter
              << " request changes=" << requestAfter - requestBefore
              << " additional searches=" << searchesAfter - searchesBefore << '\n';
    game->getContext()->shutdown();
}

} // namespace

void run_render_context_performance_tests() {
    testBackgroundFreeObjectsResolveLayoutOnlyForDrawing();
    testUnchangedLayoutValuesAreParsedOnlyOnce();
    testTerrainTextureScalingIsReusedAndBounded();
    test_render_context_bulk_copy_accounting_is_exact();
    test_render_context_stable_scene_frame_copies_do_not_grow();
    test_styled_text_reuses_bounded_cache();
    test_choice_layout_does_not_rasterize_hidden_rows_on_redraw();
    test_detail_layout_draws_only_visible_cached_paragraphs();
    test_reward_receipt_draws_only_visible_cached_rows();
    testCharacterAbilityDetailsReuseTexturesAndRefreshAvailability();
    testLoadingReaderReusesWarmTextures();
    testMovementSamplingReusesOneBoundedRecord();
    testActiveTurnOverlayReadsReuseTheCommittedPlayerRoute();
}
