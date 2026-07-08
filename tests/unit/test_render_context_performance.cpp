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
#include "gui/CRenderContext.h"
#include "gui/CSdlResources.h"
#include "gui/object/CGameGraphicsObject.h"
#include "test_harness.h"

#include <cstddef>
#include <memory>

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

} // namespace

void run_render_context_performance_tests() {
    test_render_context_bulk_copy_accounting_is_exact();
    test_render_context_stable_scene_frame_copies_do_not_grow();
}
