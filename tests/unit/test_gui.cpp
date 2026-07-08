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

#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CJsonUtil.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CScript.h"
#include "core/CStats.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CRenderContext.h"
#include "gui/CSdlResources.h"
#include "gui/CTextureCache.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/object/CMinimapGraphicsObject.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CGameQuestPanel.h"
#define GAME_UNIT_TESTS
#include "gui/panel/CGameDialogPanel.h"
#undef GAME_UNIT_TESTS
#include "gui/panel/CListView.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CDialog.h"
#include "object/CEffect.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <chrono>
#include <limits>
#include <vector>
#include <utility>

namespace {

class ClosingRenderObject : public CGameGraphicsObject {
  public:
    void renderObject(std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int) override {
        if (auto parent = getParent()) {
            parent->removeChild(this->ptr<CGameGraphicsObject>());
        }
    }
};

class CountingRenderObject : public CGameGraphicsObject {
  public:
    explicit CountingRenderObject(int &render_count) : render_count(render_count) {}

    void renderObject(std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int) override { ++render_count; }

  private:
    int &render_count;
};

class CountingGui : public CGui {
    V_META(CountingGui, CGui, vstd::meta::empty())

  public:
    explicit CountingGui(int &render_count) : render_count(render_count) {}

    void renderObject(std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int) override { ++render_count; }

  private:
    int &render_count;
};

class MouseEventRecorder : public CGameGraphicsObject {
  public:
    bool mouseEvent(std::shared_ptr<CGui>, SDL_EventType type, int button, int x, int y) override {
        ++button_count;
        last_type = type;
        last_button = button;
        last_x = x;
        last_y = y;
        return true;
    }

    bool mouseMotionEvent(std::shared_ptr<CGui>, SDL_EventType type, int x, int y, int xrel, int yrel) override {
        ++motion_count;
        last_type = type;
        last_x = x;
        last_y = y;
        last_xrel = xrel;
        last_yrel = yrel;
        return true;
    }

    bool mouseWheelEvent(std::shared_ptr<CGui>, SDL_EventType type, int x, int y, int wheelX, int wheelY) override {
        ++wheel_count;
        last_type = type;
        last_x = x;
        last_y = y;
        last_wheel_x = wheelX;
        last_wheel_y = wheelY;
        return true;
    }

    bool mouseCancelEvent(std::shared_ptr<CGui>, SDL_EventType type) override {
        ++cancel_count;
        last_type = type;
        return true;
    }

    int button_count = 0;
    int motion_count = 0;
    int wheel_count = 0;
    int cancel_count = 0;
    SDL_EventType last_type = SDL_FIRSTEVENT;
    int last_button = 0;
    int last_x = 0;
    int last_y = 0;
    int last_xrel = 0;
    int last_yrel = 0;
    int last_wheel_x = 0;
    int last_wheel_y = 0;
};

class RefreshCountingListView : public CListView {
    V_META(RefreshCountingListView, CListView, vstd::meta::empty())

  public:
    int getSizeX(std::shared_ptr<CGui>) override { return 1; }

    int getSizeY(std::shared_ptr<CGui>) override { return 1; }

    std::list<std::shared_ptr<CGameGraphicsObject>> getProxiedObjects(std::shared_ptr<CGui>, int, int) override {
        ++refresh_count;
        return {};
    }

    void setResolvedRefreshTarget(std::shared_ptr<CGameObject> refresh_target) {
        resolvedRefreshTarget = std::move(refresh_target);
    }

    int refresh_count = 0;

  protected:
    std::shared_ptr<CGameObject> resolveRefreshTarget() override { return resolvedRefreshTarget; }

  private:
    std::shared_ptr<CGameObject> resolvedRefreshTarget;
};

// Counts quest-journal text rebuilds so the tests can assert the quest panel only
// rebuilds when its underlying quest data actually changed (reactive refresh), never
// per read/frame. Mirrors RefreshCountingListView: the quest source is injected so no
// full map boot is needed.
class QuestTextCountingPanel : public CGameQuestPanel {
    V_META(QuestTextCountingPanel, CGameQuestPanel, vstd::meta::empty())

  public:
    void setResolvedQuestSource(std::shared_ptr<CPlayer> player) { resolvedQuestSource = std::move(player); }

    void setResolvedQuestStateSource(std::shared_ptr<CGameObject> questState) {
        resolvedQuestStateSource = std::move(questState);
    }

    int build_count = 0;

  protected:
    std::shared_ptr<CPlayer> resolveQuestSource(const std::shared_ptr<CGui> &) override { return resolvedQuestSource; }

    std::shared_ptr<CGameObject> resolveQuestStateSource(const std::shared_ptr<CGui> &) override {
        return resolvedQuestStateSource;
    }

    std::string buildText(const std::shared_ptr<CPlayer> &player) override {
        ++build_count;
        return CGameQuestPanel::buildText(player);
    }

  private:
    std::shared_ptr<CPlayer> resolvedQuestSource;

    std::shared_ptr<CGameObject> resolvedQuestStateSource;
};

class DragCallbackPanel : public CGamePanel {
    V_META(DragCallbackPanel, CGamePanel,
           V_METHOD(DragCallbackPanel, sourceCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
           V_METHOD(DragCallbackPanel, targetCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
           V_METHOD(DragCallbackPanel, sourceClick, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
           V_METHOD(DragCallbackPanel, targetClick, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
           V_METHOD(DragCallbackPanel, sourceDragStart, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
           V_METHOD(DragCallbackPanel, targetDragValidate, bool, std::shared_ptr<CGui>, int,
                    std::shared_ptr<CGameObject>),
           V_METHOD(DragCallbackPanel, targetDrop, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
           V_METHOD(DragCallbackPanel, sourceDragCancel, void, std::shared_ptr<CGui>, int,
                    std::shared_ptr<CGameObject>))

  public:
    CListView::collection_pointer sourceCollection(std::shared_ptr<CGui>) {
        auto collection = std::make_shared<CListView::collection_type>();
        collection->insert(sourceItem);
        return collection;
    }

    CListView::collection_pointer targetCollection(std::shared_ptr<CGui>) {
        auto collection = std::make_shared<CListView::collection_type>();
        collection->insert(targetItem);
        return collection;
    }

    void sourceClick(std::shared_ptr<CGui>, int index, std::shared_ptr<CGameObject> object) {
        ++source_clicks;
        last_source_click_index = index;
        last_source_click = object;
    }

    void targetClick(std::shared_ptr<CGui>, int index, std::shared_ptr<CGameObject> object) {
        ++target_clicks;
        last_target_index = index;
        last_target_object = object;
    }

    bool sourceDragStart(std::shared_ptr<CGui>, int index, std::shared_ptr<CGameObject> object) {
        ++drag_starts;
        last_source_index = index;
        last_source_object = object;
        return allow_drag_start;
    }

    bool targetDragValidate(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
        ++drag_validations;
        last_target_index = index;
        last_target_object = object;
        if (gui && gui->hasDragSession()) {
            const auto *session = gui->getDragSession();
            last_source_index = session->sourceIndex;
            last_source_object = session->payload;
        }
        return allow_drop;
    }

    void targetDrop(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object) {
        ++drops;
        last_target_index = index;
        last_target_object = object;
        if (gui && gui->hasDragSession()) {
            const auto *session = gui->getDragSession();
            last_source_index = session->sourceIndex;
            last_source_object = session->payload;
        }
    }

    void sourceDragCancel(std::shared_ptr<CGui>, int index, std::shared_ptr<CGameObject> object) {
        ++drag_cancels;
        last_source_index = index;
        last_source_object = object;
    }

    std::shared_ptr<CGameObject> sourceItem = std::make_shared<CGameObject>();
    std::shared_ptr<CGameObject> targetItem = std::make_shared<CGameObject>();
    std::shared_ptr<CGameObject> last_source_object;
    std::shared_ptr<CGameObject> last_source_click;
    std::shared_ptr<CGameObject> last_target_object;
    int last_source_index = -1;
    int last_source_click_index = -1;
    int last_target_index = -1;
    int source_clicks = 0;
    int target_clicks = 0;
    int drag_starts = 0;
    int drag_validations = 0;
    int drops = 0;
    int drag_cancels = 0;
    bool allow_drag_start = true;
    bool allow_drop = true;
};

// Parent that exposes valid reflective widget callbacks plus a private one, used
// to prove config-driven CWidget render/click dispatch fails closed on bad names.
class WidgetCallbackPanel : public CGamePanel {
    V_META(WidgetCallbackPanel, CGamePanel,
           V_METHOD(WidgetCallbackPanel, renderWidget, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int),
           V_METHOD(WidgetCallbackPanel, clickWidget, void, std::shared_ptr<CGui>))

  public:
    void renderWidget(std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int) { ++renders; }

    void clickWidget(std::shared_ptr<CGui>) { ++clicks; }

    int renders = 0;
    int clicks = 0;
};

void drain_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < 5; ++i) {
        loop->run();
    }
}

std::shared_ptr<MouseEventRecorder> attach_mouse_recorder(const std::shared_ptr<CGui> &gui) {
    auto recorder = std::make_shared<MouseEventRecorder>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(10, 20, 100, 80);
    recorder->setLayout(layout);
    gui->pushChild(recorder);
    return recorder;
}

class DropTargetRecorder : public MouseEventRecorder {
  public:
    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override {
        MouseEventRecorder::mouseEvent(gui, type, button, x, y);
        if (type == SDL_MOUSEBUTTONUP && button == SDL_BUTTON_LEFT && gui && gui->hasDragSession()) {
            gui->acceptDragSession(this->ptr<CGameGraphicsObject>());
        }
        return true;
    }
};

std::shared_ptr<DropTargetRecorder> attach_drop_target_recorder(const std::shared_ptr<CGui> &gui) {
    auto recorder = std::make_shared<DropTargetRecorder>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(200, 20, 100, 80);
    recorder->setLayout(layout);
    gui->pushChild(recorder);
    return recorder;
}

std::shared_ptr<CGame> create_gui_game(const std::shared_ptr<CGui> &gui) {
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    CTypes::register_type_metadata<RefreshCountingListView, CListView, CProxyTargetGraphicsObject, CGameGraphicsObject,
                                   CGameObject>();
    CTypes::register_type_metadata<QuestTextCountingPanel, CGameQuestPanel, CGamePanel, CGameGraphicsObject,
                                   CGameObject>();
    CTypes::register_type_metadata<DragCallbackPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type_metadata<WidgetCallbackPanel, CGamePanel, CGameGraphicsObject, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);
    game->getObjectHandler()->registerType(CProxyGraphicsLayout::static_meta()->name(),
                                           []() { return std::make_shared<CProxyGraphicsLayout>(); });
    return game;
}

std::shared_ptr<CGame> create_loader_gui_game(const std::string &guiClass = "CGui") {
    auto game = std::make_shared<CGame>();
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    auto guiConfig = std::make_shared<json>();
    (*guiConfig)["class"] = guiClass;
    game->getObjectHandler()->registerConfig("gui", guiConfig);
    return game;
}

struct DragListHarness {
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CGame> game;
    std::shared_ptr<DragCallbackPanel> panel;
    std::shared_ptr<CListView> source;
    std::shared_ptr<CListView> target;
};

std::shared_ptr<CLayout> fixed_layout(int x, int y, int w, int h) {
    auto layout = std::make_shared<CLayout>();
    layout->setRect(x, y, w, h);
    return layout;
}

void expect_rect(std::shared_ptr<SDL_Rect> rect, int x, int y, int w, int h, const char *message) {
    expect_true(rect && rect->x == x && rect->y == y && rect->w == w && rect->h == h, message);
}

void test_layout_runtime_overrides_preserve_serialized_percentage_layouts() {
    auto parent = std::make_shared<CGameGraphicsObject>();
    auto parentLayout = std::make_shared<CLayout>();
    parentLayout->setRect(10, 20, 200, 100);
    parent->setLayout(parentLayout);

    auto child = std::make_shared<CGameGraphicsObject>();
    auto childLayout = std::make_shared<CLayout>();
    childLayout->setX("10%");
    childLayout->setY("20%");
    childLayout->setW("50%");
    childLayout->setH("25%");
    child->setLayout(childLayout);
    parent->addChild(child);

    expect_rect(childLayout->getRect(child), 30, 40, 100, 25,
                "percentage child layout should resolve from the serialized parent rectangle");

    parentLayout->setRuntimeRect(15, 25, 400, 200);
    expect_rect(childLayout->getRect(child), 55, 65, 200, 50,
                "percentage child layout should recompute from the runtime parent rectangle");
    expect_true(parentLayout->getX() == "10" && parentLayout->getY() == "20" && parentLayout->getW() == "200" &&
                    parentLayout->getH() == "100",
                "parent runtime rectangle should not rewrite serialized layout values");

    childLayout->setRuntimeW(90);
    childLayout->setRuntimeH(40);
    expect_rect(childLayout->getRect(child), 55, 65, 90, 40,
                "partial runtime size overrides should preserve percentage position");

    childLayout->setRuntimeX(7);
    childLayout->setRuntimeY(8);
    expect_rect(childLayout->getRect(child), 22, 33, 90, 40,
                "partial runtime position overrides should move relative to the current parent rectangle");
    expect_true(childLayout->getX() == "10%" && childLayout->getY() == "20%" && childLayout->getW() == "50%" &&
                    childLayout->getH() == "25%",
                "child runtime rectangle should not rewrite serialized percentage layout values");

    childLayout->clearRuntimeRect();
    expect_rect(childLayout->getRect(child), 55, 65, 200, 50,
                "clearing child runtime overrides should restore percentage resolution against the runtime parent");

    parentLayout->clearRuntimeRect();
    expect_rect(childLayout->getRect(child), 30, 40, 100, 25,
                "clearing parent runtime overrides should restore the serialized parent rectangle");
}

void test_layout_fractional_percentages_resolve_exact_design_pixels() {
    auto parent = std::make_shared<CGameGraphicsObject>();
    auto parentLayout = std::make_shared<CLayout>();
    parentLayout->setRect(0, 0, 1920, 1080);
    parent->setLayout(parentLayout);

    auto child = std::make_shared<CGameGraphicsObject>();
    auto childLayout = std::make_shared<CCenteredLayout>();
    childLayout->setW("41.67%");
    childLayout->setH("55.56%");
    child->setLayout(childLayout);
    parent->addChild(child);

    expect_rect(childLayout->getRect(child), 560, 240, 800, 600,
                "fractional percentages should reproduce the 800x600 design rect at 1920x1080");

    parentLayout->setRuntimeRect(0, 0, 2560, 1440);
    expect_rect(childLayout->getRect(child), 747, 320, 1066, 800,
                "fractional percentages should scale panels with a larger root rectangle");

    childLayout->setW("12.5");
    expect_true(childLayout->getRect(child)->w == 0, "fractional plain pixel values should stay invalid");
    childLayout->setW("nan%");
    expect_true(childLayout->getRect(child)->w == 0, "non-finite percentages should stay invalid");
}

void test_layout_minimum_size_floors_percentage_panels() {
    auto parent = std::make_shared<CGameGraphicsObject>();
    auto parentLayout = std::make_shared<CLayout>();
    parentLayout->setRect(0, 0, 1280, 720);
    parent->setLayout(parentLayout);

    auto child = std::make_shared<CGameGraphicsObject>();
    auto childLayout = std::make_shared<CCenteredLayout>();
    childLayout->setW("41.67%");
    childLayout->setH("55.56%");
    childLayout->setMinW(800);
    childLayout->setMinH(600);
    child->setLayout(childLayout);
    parent->addChild(child);

    expect_rect(childLayout->getRect(child), 240, 60, 800, 600,
                "panels below the minimum size should be floored and stay centered");

    parentLayout->setRuntimeRect(0, 0, 1920, 1080);
    expect_rect(childLayout->getRect(child), 560, 240, 800, 600,
                "the minimum floor should hand off exactly at the design resolution");

    childLayout->setRuntimeW(320);
    childLayout->setRuntimeH(200);
    expect_rect(childLayout->getRect(child), 800, 440, 320, 200,
                "runtime size overrides should bypass the minimum floor");

    childLayout->clearRuntimeRect();
    parentLayout->setRuntimeRect(0, 0, 1280, 720);
    childLayout->setMinW(-50);
    childLayout->setMinH(-50);
    expect_rect(childLayout->getRect(child), 374, 160, 533, 400, "negative minimum sizes should be ignored");
}

void test_gui_window_is_resizable_and_guard_paths_fail_closed() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    SDL_Window *window = SDL_RenderGetWindow(gui->getRenderer());
    expect_true(window != nullptr, "GUI renderer should expose its SDL window");
    if (window) {
        const Uint32 flags = SDL_GetWindowFlags(window);
        expect_true((flags & SDL_WINDOW_RESIZABLE) != 0, "GUI window should be created resizable");

        int minimum_width = 0;
        int minimum_height = 0;
        SDL_GetWindowMinimumSize(window, &minimum_width, &minimum_height);
        expect_true(minimum_width == 320 && minimum_height == 240,
                    "GUI window should enforce the logical minimum size");
    }

    gui->setLayout(fixed_layout(0, 0, 1920, 1080));
    gui->setWidth(100);
    gui->setHeight(100);
    expect_true(gui->getWidth() == 320 && gui->getHeight() == 240, "GUI logical size should clamp to the minimum");
    expect_true(gui->getLayout()->getW() == "1920" && gui->getLayout()->getH() == "1080",
                "GUI runtime resize should not rewrite serialized root layout dimensions");
    gui->setWidth(9000);
    gui->setHeight(5000);
    expect_true(gui->getWidth() == 7680 && gui->getHeight() == 4320, "GUI logical size should clamp to the maximum");

    expect_true(!gui->event(nullptr), "GUI should reject null SDL events");
    expect_true(!gui->isPointerCapturedBy(nullptr), "GUI should reject null pointer capture probes");
    expect_true(gui->getDragSession() == nullptr, "new GUI should not expose a drag session");
    const std::shared_ptr<const CGui> const_gui = gui;
    expect_true(const_gui->getDragSession() == nullptr, "const drag-session accessor should fail closed");

    auto payload = std::make_shared<CGameObject>();
    auto unattached_source = std::make_shared<MouseEventRecorder>();
    gui->startDragSession(unattached_source, payload, 1, 10, 20);
    expect_true(!gui->hasDragSession(), "unattached widgets should not start GUI drag sessions");

    auto captured_source = attach_mouse_recorder(gui);
    gui->capturePointer(captured_source);
    expect_true(gui->isPointerCapturedBy(captured_source), "attached widgets should be eligible for pointer capture");
    captured_source->setParent(nullptr);

    SDL_Event captured_motion{};
    captured_motion.type = SDL_MOUSEMOTION;
    captured_motion.motion.x = 30;
    captured_motion.motion.y = 40;
    captured_motion.motion.xrel = 1;
    captured_motion.motion.yrel = 1;
    expect_true(!gui->event(&captured_motion), "detached pointer capture should be released without dispatch");
    expect_true(!gui->hasPointerCapture(), "stale pointer capture should be cleared");
    gui->removeChild(captured_source);

    auto source = attach_mouse_recorder(gui);
    auto target = attach_drop_target_recorder(gui);
    gui->startDragSession(source, payload, 5, 20, 30);
    expect_true(gui->hasDragSession(), "attached widgets should start GUI drag sessions");
    expect_true(const_gui->getDragSession() != nullptr, "const drag-session accessor should expose active sessions");
    gui->acceptDragSession(target);
    gui->updateDragSession(80, 90);
    gui->cancelDragSession();
    expect_true(gui->getDragSession() && gui->getDragSession()->canceled, "canceling a drag session should mark it");
    gui->clearDragSession();

    gui->startDragSession(source, payload, 6, 20, 30);
    SDL_Event release{};
    release.type = SDL_MOUSEBUTTONUP;
    release.button.button = SDL_BUTTON_LEFT;
    release.button.x = 900;
    release.button.y = 900;
    gui->event(&release);
    expect_true(!gui->hasDragSession(), "button release without an accepted target should clear the drag session");

    if (window) {
        const int previous_width = gui->getWidth();
        const int previous_height = gui->getHeight();
        SDL_Event wrong_window_resize{};
        wrong_window_resize.type = SDL_WINDOWEVENT;
        wrong_window_resize.window.event = SDL_WINDOWEVENT_SIZE_CHANGED;
        wrong_window_resize.window.windowID = SDL_GetWindowID(window) + 1;
        wrong_window_resize.window.data1 = 800;
        wrong_window_resize.window.data2 = 600;
        gui->event(&wrong_window_resize);
        expect_true(gui->getWidth() == previous_width && gui->getHeight() == previous_height,
                    "resize events for another SDL window should be ignored");
    }
}

DragListHarness create_drag_list_harness() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    DragListHarness harness;
    harness.gui = std::make_shared<CGui>();
    harness.game = create_gui_game(harness.gui);
    harness.panel = std::make_shared<DragCallbackPanel>();
    harness.source = std::make_shared<CListView>();
    harness.target = std::make_shared<CListView>();

    harness.panel->sourceItem->setGame(harness.game);
    harness.panel->sourceItem->setName("sourceItem");
    harness.panel->targetItem->setGame(harness.game);
    harness.panel->targetItem->setName("targetItem");

    harness.panel->setLayout(fixed_layout(0, 0, 200, 100));
    harness.source->setLayout(fixed_layout(0, 0, 50, 50));
    harness.source->setCollection("sourceCollection");
    harness.source->setCallback("sourceClick");
    harness.source->setTileSize(50);
    harness.source->setXPrefferedSize(1);
    harness.source->setYPrefferedSize(1);

    harness.target->setLayout(fixed_layout(100, 0, 50, 50));
    harness.target->setCollection("targetCollection");
    harness.target->setCallback("targetClick");
    harness.target->setTileSize(50);
    harness.target->setXPrefferedSize(1);
    harness.target->setYPrefferedSize(1);

    harness.panel->addChild(harness.source);
    harness.panel->addChild(harness.target);
    harness.gui->pushChild(harness.panel);
    return harness;
}

void test_widget_ignores_unarmed_non_left_clicks() {
    auto widget = std::make_shared<CWidget>();

    expect_true(!widget->mouseEvent(nullptr, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 0, 0),
                "plain widget should ignore right clicks when no click callback is armed");
}

void test_list_view_refreshes_from_generic_property_notifications() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    gui->pushChild(list);
    list->setResolvedRefreshTarget(refresh_target);
    list->setRefreshOnPropertyChanged(true);

    list->refresh();
    const int after_initial_refresh = list->refresh_count;

    refresh_target->setNumericProperty("threat", 1);
    drain_event_loop();

    expect_true(list->refresh_count == after_initial_refresh + 1,
                "generic propertyChanged subscription should refresh the list for any changed property");
}

void test_list_view_coalesces_property_refreshes_per_event_loop_tick() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    gui->pushChild(list);
    list->setResolvedRefreshTarget(refresh_target);
    list->setRefreshOnPropertyChanged(true);

    list->refresh();
    const int after_initial_refresh = list->refresh_count;

    refresh_target->setNumericProperty("threat", 1);
    refresh_target->setStringProperty("label", "first");
    refresh_target->setBoolProperty("enabled", true);
    expect_true(list->refresh_count == after_initial_refresh,
                "property notifications should queue refresh work instead of refreshing synchronously");

    drain_event_loop();

    expect_true(list->refresh_count == after_initial_refresh + 1,
                "multiple property notifications in one event-loop turn should coalesce to one list refresh");
}

void test_list_view_skips_queued_property_refresh_after_detach() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    gui->pushChild(list);
    list->setResolvedRefreshTarget(refresh_target);
    list->setRefreshOnPropertyChanged(true);

    list->refresh();
    const int after_initial_refresh = list->refresh_count;

    refresh_target->setNumericProperty("threat", 1);
    gui->removeChild(list);
    drain_event_loop();

    expect_true(list->refresh_count == after_initial_refresh, "detached list views should ignore queued refresh work");
}

void test_list_view_refresh_event_compatibility() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    gui->pushChild(list);
    list->setResolvedRefreshTarget(refresh_target);
    list->setRefreshEvent("legacyRefresh");

    list->refresh();
    const int after_initial_refresh = list->refresh_count;

    refresh_target->signal("legacyRefresh");
    drain_event_loop();

    expect_true(list->refresh_count == after_initial_refresh + 1,
                "legacy no-argument refreshEvent subscription should still refresh the list");
}

void test_list_view_property_subscriptions_follow_resolved_target_and_null() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto first_target = std::make_shared<CGameObject>();
    auto second_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    gui->pushChild(list);
    list->setResolvedRefreshTarget(first_target);
    list->setRefreshProperties({"label"});

    list->refresh();
    const int after_initial_refresh = list->refresh_count;

    first_target->setStringProperty("label", "first");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 1,
                "property-specific subscription should refresh for the selected property");

    first_target->setNumericProperty("threat", 1);
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 1,
                "property-specific subscription should ignore unrelated property notifications");

    list->setResolvedRefreshTarget(second_target);
    list->refresh();
    expect_true(list->refresh_count == after_initial_refresh + 2,
                "subscription refresh should reconnect when the resolved refresh target changes");

    first_target->setStringProperty("label", "stale");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 2,
                "old refresh target should be disconnected after reconnecting to a new target");

    second_target->setStringProperty("label", "second");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 3,
                "new refresh target should drive later property-specific refreshes");

    list->setResolvedRefreshTarget(nullptr);
    list->refresh();
    expect_true(list->refresh_count == after_initial_refresh + 4,
                "subscription refresh should handle the refresh script resolving to null");

    second_target->setStringProperty("label", "after-null");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 4,
                "previous refresh target should be disconnected when the refresh script resolves to null");
}

void test_list_view_refresh_property_collision_fails_closed() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    gui->pushChild(list);
    list->setResolvedRefreshTarget(refresh_target);

    // "inventory" derives the "inventoryChanged" channel, which collides with the
    // typed engine signal CCreature emits. Configuring it as a refreshProperty must
    // fail closed: the list must NOT wire a property-specific reflective subscription
    // on the typed channel (no spoofing in either direction) while a valid configured
    // property ("label") still refreshes normally.
    list->setRefreshProperties({"inventory", "label"});

    list->refresh();
    const int after_initial_refresh = list->refresh_count;

    // A direct typed-engine emission on the colliding channel must NOT refresh the list
    // (the colliding property was never subscribed) and must not crash.
    refresh_target->signal("inventoryChanged");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh,
                "a refreshProperty colliding with a typed engine signal must not be subscribed (fail closed)");

    // A dynamic property literally named "inventory" must not refresh the list either:
    // its per-property notification is dropped fail-closed and the name is rejected.
    refresh_target->setStringProperty("inventory", "spoofed");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh,
                "a colliding dynamic property change must not drive a fail-closed refreshProperty");

    // The valid configured property still refreshes.
    refresh_target->setStringProperty("label", "ok");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 1,
                "a non-colliding configured refreshProperty must still refresh the list");
}

void test_quest_panel_rebuilds_text_only_when_quest_data_changes() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto player = std::make_shared<CPlayer>();
    auto panel = std::make_shared<QuestTextCountingPanel>();
    panel->setLayout(fixed_layout(0, 0, 200, 100));
    panel->setResolvedQuestSource(player);
    gui->pushChild(panel);

    auto active = std::make_shared<CQuest>();
    active->setName("reactiveQuest");
    active->setDescription("Recover the sunken sigil");
    player->setQuests({active});
    drain_event_loop();

    const auto initial = panel->getText(gui);
    expect_true(initial.find("[Active] Recover the sunken sigil") != std::string::npos,
                "quest panel should render the active quest description");
    expect_true(panel->build_count == 1, "the first quest journal read should build the text exactly once");

    expect_true(panel->getText(gui) == initial, "repeated reads should serve the cached quest text");
    drain_event_loop();
    expect_true(panel->getText(gui) == initial, "cached quest text should survive idle event-loop turns");
    expect_true(panel->build_count == 1, "quest text must not be rebuilt while the quest log is unchanged");

    player->setNumericProperty("threat", 7);
    drain_event_loop();
    panel->getText(gui);
    expect_true(panel->build_count == 1, "unrelated player property changes must not rebuild the quest text");

    auto completed = std::make_shared<CQuest>();
    completed->setName("finishedQuest");
    completed->setDescription("Silence the bell tower");
    player->setCompletedQuests({completed});
    drain_event_loop();
    const auto updated = panel->getText(gui);
    expect_true(updated.find("[Completed] Silence the bell tower") != std::string::npos,
                "quest panel should render newly completed quests after the change notification");
    expect_true(updated.find("[Active] Recover the sunken sigil") != std::string::npos,
                "quest panel should keep rendering still-active quests after a rebuild");
    expect_true(panel->build_count == 2, "a quest-log change should trigger exactly one coalesced rebuild");
}

void test_quest_panel_resubscribes_when_quest_source_changes() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto first_player = std::make_shared<CPlayer>();
    auto second_player = std::make_shared<CPlayer>();
    auto panel = std::make_shared<QuestTextCountingPanel>();
    panel->setLayout(fixed_layout(0, 0, 200, 100));
    panel->setResolvedQuestSource(first_player);
    gui->pushChild(panel);

    auto first_quest = std::make_shared<CQuest>();
    first_quest->setName("firstQuest");
    first_quest->setDescription("Chart the first road");
    first_player->setQuests({first_quest});

    expect_true(panel->getText(gui).find("Chart the first road") != std::string::npos,
                "quest panel should render the first player's quest log");
    expect_true(panel->build_count == 1, "the first player's journal should build once");

    auto second_quest = std::make_shared<CQuest>();
    second_quest->setName("secondQuest");
    second_quest->setDescription("Chart the second road");
    second_player->setQuests({second_quest});
    panel->setResolvedQuestSource(second_player);

    const auto swapped = panel->getText(gui);
    expect_true(swapped.find("Chart the second road") != std::string::npos &&
                    swapped.find("Chart the first road") == std::string::npos,
                "quest panel should rebuild from the new player after the quest source changes");
    expect_true(panel->build_count == 2, "swapping the quest source should rebuild the journal once");

    first_quest->setDescription("Chart the forgotten road");
    first_player->setQuests({first_quest});
    drain_event_loop();
    panel->getText(gui);
    expect_true(panel->build_count == 2,
                "quest changes on the disconnected previous player must not rebuild the journal");

    auto second_completed = std::make_shared<CQuest>();
    second_completed->setName("secondCompletedQuest");
    second_completed->setDescription("Seal the second gate");
    second_player->setCompletedQuests({second_completed});
    drain_event_loop();
    expect_true(panel->getText(gui).find("[Completed] Seal the second gate") != std::string::npos,
                "quest panel should follow completed-quest changes on the new player");
    expect_true(panel->build_count == 3, "the new player's quest changes should drive rebuilds");
}

void test_quest_panel_rebuilds_when_quest_state_properties_change() {
    // Quest objective/reward/hint text is derived by map scripts from quest-state
    // properties (QuestStateStore.set_state writes "quest_state_*" on the map) and
    // from map object/turn state — the quest set membership never changes in those
    // transitions. The journal cache must invalidate through the map's propertyChanged
    // / turnPassed / objectChanged channels, not only through quest membership.
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto player = std::make_shared<CPlayer>();
    auto quest_state = std::make_shared<CGameObject>();
    auto panel = std::make_shared<QuestTextCountingPanel>();
    panel->setLayout(fixed_layout(0, 0, 200, 100));
    panel->setResolvedQuestSource(player);
    panel->setResolvedQuestStateSource(quest_state);
    gui->pushChild(panel);

    auto quest = std::make_shared<CQuest>();
    quest->setName("victorQuest");
    quest->setDescription("Find Victor's missing daughter.");
    quest->setObjective("Find Victor's missing daughter.");
    player->setQuests({quest});
    drain_event_loop();

    const auto initial = panel->getText(gui);
    expect_true(initial.find("Objective: Find Victor's missing daughter.") != std::string::npos,
                "quest panel should render the initial state-derived objective");
    expect_true(panel->build_count == 1, "the first read should build the journal once");

    panel->getText(gui);
    drain_event_loop();
    panel->getText(gui);
    expect_true(panel->build_count == 1, "the journal must stay cached while quest state is unchanged");

    // Quest-state transition: the same quest object stays active (no membership
    // change), only a state property on the quest-state source flips and the script
    // would now derive different objective text.
    quest->setObjective("Defeat the cultists in the courtyard.");
    quest_state->setStringProperty("quest_state_victor", "encounter_active");
    drain_event_loop();
    const auto transitioned = panel->getText(gui);
    expect_true(transitioned.find("Objective: Defeat the cultists in the courtyard.") != std::string::npos &&
                    transitioned.find("Objective: Find Victor's missing daughter.") == std::string::npos,
                "a quest-state property change must refresh state-derived journal text");
    expect_true(panel->build_count == 2, "a quest-state property change should trigger exactly one rebuild");

    // Turn-driven quest text (typed no-argument map signal).
    quest->setHint("The cultists began their rite; hurry.");
    quest_state->signal("turnPassed");
    drain_event_loop();
    expect_true(panel->getText(gui).find("Hint: The cultists began their rite; hurry.") != std::string::npos,
                "a passed turn must refresh turn-derived journal text");
    expect_true(panel->build_count == 3, "turnPassed should trigger exactly one rebuild");

    // Object-driven quest text (typed map signal carrying coordinates).
    quest->setObjective("Seal every siege gate (1/4 sealed).");
    quest_state->signal("objectChanged", Coords(1, 2, 0));
    drain_event_loop();
    expect_true(panel->getText(gui).find("Objective: Seal every siege gate (1/4 sealed).") != std::string::npos,
                "a map object change must refresh object-derived journal text");
    expect_true(panel->build_count == 4, "objectChanged should trigger exactly one rebuild");
}

std::shared_ptr<CStats> player_stats() {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    return stats;
}

// Refresh-count coverage for every list view migrated to the reactive mechanism:
// inventory, equipped, and effects lists subscribe exactly as res/config/panels.json
// wires them (refreshEvent inventoryChanged/equippedChanged/effectsChanged with the
// refreshObject script resolving to the player creature, injected directly here like
// the other subscription tests) and real model mutations must drive exactly one
// coalesced rebuild per affected view — never a rebuild of an unaffected view, never
// a rebuild from an idle rendered frame.
void test_reactive_list_views_refresh_counts_match_model_changes_exactly() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    // equipItem validates slots through the game's slot configuration, so register the
    // same single-weapon-slot setup the drag-drop harness uses.
    game->getObjectHandler()->registerConfig("slotConfiguration", CJsonUtil::from_string(R"({
            "class": "CSlotConfig",
            "properties": {
                "configuration": {
                    "0": {"class": "CSlot", "properties": {"slotName": "RightHand", "types": ["CWeapon"]}}
                }
            }
        })",
                                                                                         "slotConfiguration"));

    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    player->setBaseStats(player_stats());
    player->setHp(player->getHpMax());
    game->getMap()->setPlayer(player);

    auto inventory_list = std::make_shared<RefreshCountingListView>();
    auto equipped_list = std::make_shared<RefreshCountingListView>();
    auto effects_list = std::make_shared<RefreshCountingListView>();
    auto attach_counting_list = [&gui, &player](const std::shared_ptr<RefreshCountingListView> &list,
                                                const std::string &refreshEvent) {
        gui->pushChild(list);
        list->setResolvedRefreshTarget(player);
        list->setRefreshEvent(refreshEvent);
        list->refresh();
    };
    attach_counting_list(inventory_list, "inventoryChanged");
    attach_counting_list(equipped_list, "equippedChanged");
    attach_counting_list(effects_list, "effectsChanged");

    auto make_weapon = [&game](const std::string &name) {
        auto weapon = std::make_shared<CWeapon>();
        weapon->setGame(game);
        weapon->setName(name);
        weapon->setTypeId(name + "Type");
        // Stat composition folds equipped item bonuses without a null guard, so every
        // equippable test item carries an (empty) bonus block like configured items do.
        weapon->setBonus(std::make_shared<CStats>());
        return weapon;
    };

    const int inventory_base = inventory_list->refresh_count;
    const int equipped_base = equipped_list->refresh_count;
    const int effects_base = effects_list->refresh_count;

    // One model change rebuilds only the affected view, exactly once, and only after
    // the queued refresh work is flushed by the event loop.
    auto sword = make_weapon("refreshCountSword");
    player->addItem(sword);
    expect_true(inventory_list->refresh_count == inventory_base,
                "an inventory change must queue the list rebuild instead of rebuilding synchronously");
    drain_event_loop();
    expect_true(inventory_list->refresh_count == inventory_base + 1,
                "one inventory change should rebuild the inventory list exactly once");
    expect_true(equipped_list->refresh_count == equipped_base && effects_list->refresh_count == effects_base,
                "an inventory change must not rebuild the equipped or effects lists");

    // Equipping moves the item between the two lists: each affected view rebuilds
    // exactly once (equippedChanged plus the removeItem-driven inventoryChanged).
    player->equipItem("0", sword);
    drain_event_loop();
    expect_true(equipped_list->refresh_count == equipped_base + 1,
                "equipping an item should rebuild the equipped list exactly once");
    expect_true(inventory_list->refresh_count == inventory_base + 2,
                "equipping an item leaves the inventory, rebuilding the inventory list exactly once");
    expect_true(effects_list->refresh_count == effects_base, "equipment changes must not rebuild the effects list");

    auto effect = std::make_shared<CEffect>();
    effect->setGame(game);
    effect->setName("refreshCountEffect");
    effect->setTypeId("refreshCountEffectType");
    player->addEffect(effect);
    drain_event_loop();
    expect_true(effects_list->refresh_count == effects_base + 1,
                "adding an effect should rebuild the effects list exactly once");
    expect_true(inventory_list->refresh_count == inventory_base + 2 &&
                    equipped_list->refresh_count == equipped_base + 1,
                "effect changes must not rebuild the inventory or equipped lists");

    // N rapid model changes in one event-loop turn coalesce into exactly one rebuild.
    auto axe = make_weapon("refreshCountAxe");
    auto dagger = make_weapon("refreshCountDagger");
    player->addItem(axe);
    player->addItem(dagger);
    player->removeItem(dagger);
    drain_event_loop();
    expect_true(inventory_list->refresh_count == inventory_base + 3,
                "three inventory changes in one event-loop turn must coalesce into exactly one rebuild");

    // Unrelated model changes rebuild nothing (no over-refresh). The names must be
    // dynamic-only properties: a name owned by a typed V_META property (e.g. "gold" on
    // CCreature) would route setProperty through the typed reflective setter, which
    // needs object-type any-cast registrations this GUI suite does not perform.
    player->setNumericProperty("threat", 42);
    player->setStringProperty("warCry", "warden");
    drain_event_loop();
    expect_true(inventory_list->refresh_count == inventory_base + 3 &&
                    equipped_list->refresh_count == equipped_base + 1 &&
                    effects_list->refresh_count == effects_base + 1,
                "unrelated player property changes must not rebuild any reactive list view");

    // Idle frames render from the cached proxy children: zero rebuilds per frame.
    for (int frame = 0; frame < 3; ++frame) {
        gui->render(0);
    }
    drain_event_loop();
    expect_true(inventory_list->refresh_count == inventory_base + 3 &&
                    equipped_list->refresh_count == equipped_base + 1 &&
                    effects_list->refresh_count == effects_base + 1,
                "rendering idle frames must not rebuild any reactive list view");
}

// Refresh-count coverage for the migrated quest panel: rapid invalidations across
// every subscribed channel (quest membership on the player plus the map's quest-state
// property / turnPassed / objectChanged channels) coalesce into exactly one rebuild,
// each map-channel invalidation on its own counts exactly one rebuild, and reads
// without a pending invalidation always serve the cache (the render path is a read).
void test_quest_panel_refresh_count_coalesces_rapid_invalidations() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto player = std::make_shared<CPlayer>();
    auto quest_state = std::make_shared<CGameObject>();
    auto panel = std::make_shared<QuestTextCountingPanel>();
    panel->setLayout(fixed_layout(0, 0, 200, 100));
    panel->setResolvedQuestSource(player);
    panel->setResolvedQuestStateSource(quest_state);
    gui->pushChild(panel);

    auto quest = std::make_shared<CQuest>();
    quest->setName("countedQuest");
    quest->setDescription("Recover the ledger of debts");
    quest->setObjective("Search the counting house.");
    player->setQuests({quest});
    drain_event_loop();

    expect_true(panel->getText(gui).find("[Active] Recover the ledger of debts") != std::string::npos,
                "quest panel should render the active quest before counting rebuilds");
    expect_true(panel->build_count == 1, "the first quest journal read should count exactly one rebuild");

    // Rapid invalidations across every subscribed channel in one event-loop turn.
    auto completed = std::make_shared<CQuest>();
    completed->setName("countedCompletedQuest");
    completed->setDescription("Bar the western gate");
    quest->setObjective("Confront the ledger keeper.");
    player->setQuests({quest});
    player->setCompletedQuests({completed});
    quest_state->setStringProperty("quest_state_ledger", "keeper_revealed");
    quest_state->signal("turnPassed");
    quest_state->signal("objectChanged", Coords(3, 4, 0));
    expect_true(panel->build_count == 1, "invalidations must mark the cache stale without rebuilding synchronously");
    drain_event_loop();
    expect_true(panel->build_count == 1, "invalidations alone must not rebuild the journal before the next read");

    const auto rebuilt = panel->getText(gui);
    expect_true(rebuilt.find("[Completed] Bar the western gate") != std::string::npos &&
                    rebuilt.find("Objective: Confront the ledger keeper.") != std::string::npos,
                "the coalesced rebuild should reflect every change from the rapid turn");
    expect_true(panel->build_count == 2,
                "five invalidation signals in one event-loop turn must coalesce into exactly one rebuild");

    panel->getText(gui);
    drain_event_loop();
    panel->getText(gui);
    expect_true(panel->build_count == 2, "reads after the coalesced rebuild must serve the cache with zero rebuilds");

    // Each map-channel invalidation counts exactly one rebuild across repeated reads.
    quest_state->setStringProperty("quest_state_ledger", "keeper_defeated");
    drain_event_loop();
    panel->getText(gui);
    panel->getText(gui);
    expect_true(panel->build_count == 3, "a quest-state property change must count exactly one rebuild");

    quest_state->signal("turnPassed");
    drain_event_loop();
    panel->getText(gui);
    panel->getText(gui);
    expect_true(panel->build_count == 4, "turnPassed must count exactly one rebuild");

    quest_state->signal("objectChanged", Coords(5, 6, 0));
    drain_event_loop();
    panel->getText(gui);
    panel->getText(gui);
    expect_true(panel->build_count == 5, "objectChanged must count exactly one rebuild");

    // Unrelated changes on the unsubscribed channels count zero rebuilds.
    player->setNumericProperty("threat", 3);
    drain_event_loop();
    panel->getText(gui);
    expect_true(panel->build_count == 5, "unrelated player property changes must not count a quest journal rebuild");
}

struct MinimapHarness {
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CPlayer> player;
};

MinimapHarness make_minimap_harness() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    MinimapHarness harness;
    harness.game = std::make_shared<CGame>();
    harness.map = std::make_shared<CMap>();
    harness.gui = std::make_shared<CGui>();
    harness.player = std::make_shared<CPlayer>();

    harness.game->setMap(harness.map);
    harness.game->setGui(harness.gui);
    harness.map->setGame(harness.game);
    harness.gui->setGame(harness.game);

    harness.player->setGame(harness.game);
    harness.player->setBaseStats(player_stats());
    harness.player->setHp(harness.player->getHpMax());
    harness.map->setPlayer(harness.player);
    return harness;
}

// Renders the minimap once and asserts the call returns (the pre-fix bug could iterate/scale over
// attacker-extreme or overflow-prone level extents). Returns elapsed milliseconds for liveness checks.
double render_minimap_once(const MinimapHarness &harness) {
    auto minimap = std::make_shared<CMinimapGraphicsObject>();
    auto rect = CUtil::rect(0, 0, 128, 128);
    const auto start = std::chrono::steady_clock::now();
    minimap->renderObject(harness.gui, rect, 0);
    const auto end = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::milli>(end - start).count();
}

// Liveness budget: a bounded/fail-closed minimap render must complete near-instantly. The unbounded
// path would iterate billions of cells, so a generous wall-clock cap reliably catches a regression
// without flaking on slow CI.
constexpr double MINIMAP_RENDER_BUDGET_MS = 2000.0;

void test_minimap_bounds_extreme_metadata_fails_closed() {
    auto harness = make_minimap_harness();
    // Attacker-extreme xBound/yBound metadata (post-loader clamp these would already be smaller, but the
    // minimap must defend independently of the loader).
    harness.map->setXBounds({{0, std::numeric_limits<int>::max()}});
    harness.map->setYBounds({{0, std::numeric_limits<int>::max()}});

    const double elapsed = render_minimap_once(harness);
    expect_true(elapsed < MINIMAP_RENDER_BUDGET_MS,
                "minimap should fail closed on extreme metadata bounds instead of iterating to INT_MAX");
}

void test_minimap_bounds_overflow_prone_extents_fail_closed() {
    auto harness = make_minimap_harness();
    // maxX = INT_MAX combined with a negative-spanning min would overflow int extent arithmetic.
    harness.map->setEntryX(-1000);
    harness.map->setEntryY(-1000);
    harness.player->moveTo(-1000, -1000, 0);
    harness.map->setXBounds({{0, std::numeric_limits<int>::max()}});
    harness.map->setYBounds({{0, std::numeric_limits<int>::max()}});

    const double elapsed = render_minimap_once(harness);
    expect_true(elapsed < MINIMAP_RENDER_BUDGET_MS,
                "minimap should fail closed on overflow-prone level extents without signed-overflow UB");
}

void test_minimap_bounds_sparse_coordinates_fail_closed() {
    auto harness = make_minimap_harness();
    // No metadata bounds -> bounds are derived from sparse coordinates. A single far-flung tile must not
    // expand iteration/scaling over the enormous empty span between the player and that tile.
    harness.map->setXBounds({});
    harness.map->setYBounds({});
    harness.map->addTile(std::make_shared<CTile>(), 50'000'000, 50'000'000, 0);

    const double elapsed = render_minimap_once(harness);
    expect_true(elapsed < MINIMAP_RENDER_BUDGET_MS,
                "minimap should fail closed on sparse far-flung coordinates instead of iterating empty space");
}

void test_minimap_bounds_negative_sparse_coordinates_render() {
    auto harness = make_minimap_harness();
    harness.map->setXBounds({});
    harness.map->setYBounds({});
    // A compact cluster including negative coordinates must still render (regression: clamping must not
    // reject legitimately small negative-origin levels).
    harness.map->addTile(std::make_shared<CTile>(), -5, -5, 0);
    harness.map->addTile(std::make_shared<CTile>(), -3, -2, 0);

    const double elapsed = render_minimap_once(harness);
    expect_true(elapsed < MINIMAP_RENDER_BUDGET_MS,
                "minimap should render a small negative-origin level without failing closed");
}

void test_minimap_bounds_normal_map_renders() {
    auto harness = make_minimap_harness();
    harness.map->setXBounds({{0, 32}});
    harness.map->setYBounds({{0, 32}});
    harness.map->setDefaultTiles({{0, "GrassTile"}});
    harness.map->addTile(std::make_shared<CTile>(), 4, 4, 0);
    harness.map->addTile(std::make_shared<CTile>(), 10, 12, 0);
    auto creature = std::make_shared<CCreature>();
    harness.map->addObject(creature, Coords(6, 6, 0));

    const double elapsed = render_minimap_once(harness);
    expect_true(elapsed < MINIMAP_RENDER_BUDGET_MS, "minimap should render a normal bounded map (regression)");
}

// Builds a GUI where a map-layer recorder and an overlapping minimap overlay share the same parent. The
// minimap is pushed last so it has the higher priority and is visited first by CGameGraphicsObject::event(),
// exactly like the live layer ordering. Synthetic SDL events dispatched through gui->event() then let us
// count whether the underlying map layer was reached.
struct MinimapClickHarness {
    std::shared_ptr<CGui> gui;
    std::shared_ptr<MouseEventRecorder> map;
    std::shared_ptr<CMinimapGraphicsObject> minimap;
};

MinimapClickHarness make_minimap_click_harness() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    MinimapClickHarness harness;
    harness.gui = std::make_shared<CGui>();

    harness.map = std::make_shared<MouseEventRecorder>();
    harness.map->setLayout(fixed_layout(0, 0, 200, 200));
    harness.gui->pushChild(harness.map); // lower priority -> underlying layer

    harness.minimap = std::make_shared<CMinimapGraphicsObject>();
    harness.minimap->setLayout(fixed_layout(10, 10, 50, 50));
    harness.gui->pushChild(harness.minimap); // higher priority -> overlay on top
    return harness;
}

void test_minimap_consumes_inside_pointer_events_and_preserves_outside_and_wheel() {
    // 1. A left button press strictly inside the minimap rectangle must be consumed by the overlay and must
    //    NOT reach the underlying map layer.
    {
        auto harness = make_minimap_click_harness();
        SDL_Event down{};
        down.type = SDL_MOUSEBUTTONDOWN;
        down.button.button = SDL_BUTTON_LEFT;
        down.button.x = 30;
        down.button.y = 30;
        expect_true(harness.gui->event(&down), "left click inside the minimap should be handled by the overlay");
        expect_true(harness.map->button_count == 0,
                    "left click inside the minimap should not reach the underlying map layer");
    }

    // 2. A right button press inside the minimap must be consumed the same way.
    {
        auto harness = make_minimap_click_harness();
        SDL_Event down{};
        down.type = SDL_MOUSEBUTTONDOWN;
        down.button.button = SDL_BUTTON_RIGHT;
        down.button.x = 30;
        down.button.y = 30;
        expect_true(harness.gui->event(&down), "right click inside the minimap should be handled by the overlay");
        expect_true(harness.map->button_count == 0,
                    "right click inside the minimap should not reach the underlying map layer");
    }

    // 3. Mouse motion inside the minimap must be consumed so hovering/dragging does not interact with the world.
    {
        auto harness = make_minimap_click_harness();
        SDL_Event motion{};
        motion.type = SDL_MOUSEMOTION;
        motion.motion.x = 30;
        motion.motion.y = 30;
        motion.motion.xrel = 2;
        motion.motion.yrel = 2;
        expect_true(harness.gui->event(&motion), "motion inside the minimap should be handled by the overlay");
        expect_true(harness.map->motion_count == 0,
                    "motion inside the minimap should not reach the underlying map layer");
    }

    // 4. A click one pixel outside the minimap rectangle must still fall through to the map. CUtil::isIn uses
    //    inclusive bounds, so the minimap rect (10,10,50,50) covers x/y in [10,60]; x = 61 is the first column
    //    outside it.
    {
        auto harness = make_minimap_click_harness();
        SDL_Event down{};
        down.type = SDL_MOUSEBUTTONDOWN;
        down.button.button = SDL_BUTTON_LEFT;
        down.button.x = 61;
        down.button.y = 30;
        expect_true(harness.gui->event(&down), "click outside the minimap should be handled by the map layer");
        expect_true(harness.map->button_count == 1,
                    "click one pixel outside the minimap should still reach the underlying map layer");
    }

    // 5. Wheel decision is explicit: the minimap deliberately does NOT override mouseWheelEvent, so a wheel
    //    event over the minimap falls through to the map (map zoom keeps working under the cursor).
    {
        auto harness = make_minimap_click_harness();
        SDL_Event wheel{};
        wheel.type = SDL_MOUSEWHEEL;
        wheel.wheel.x = 0;
        wheel.wheel.y = 1;
#if SDL_VERSION_ATLEAST(2, 26, 0)
        wheel.wheel.mouseX = 30;
        wheel.wheel.mouseY = 30;
        expect_true(harness.gui->event(&wheel), "wheel over the minimap should be handled by the map layer");
        expect_true(harness.map->wheel_count == 1,
                    "wheel over the minimap should fall through to the underlying map layer (no wheel override)");
#endif
    }

    // 6. A hidden minimap must consume nothing: a visible script that fails to resolve makes isVisible() false,
    //    so event() short-circuits before any minimap hook and the click reaches the map.
    {
        auto harness = make_minimap_click_harness();
        harness.minimap->setVisible(std::make_shared<CScript>());
        SDL_Event down{};
        down.type = SDL_MOUSEBUTTONDOWN;
        down.button.button = SDL_BUTTON_LEFT;
        down.button.x = 30;
        down.button.y = 30;
        expect_true(harness.gui->event(&down), "click under a hidden minimap should be handled by the map layer");
        expect_true(harness.map->button_count == 1, "a hidden minimap should consume nothing");
    }

    // 7. A modal panel still takes precedence: a higher-priority modal recorder pushed above the minimap
    //    receives even out-of-its-bounds clicks before the minimap, so the minimap does not override modal
    //    dispatch.
    {
        auto harness = make_minimap_click_harness();
        auto modalPanel = std::make_shared<MouseEventRecorder>();
        modalPanel->setLayout(fixed_layout(120, 120, 40, 40));
        modalPanel->setModal(true);
        harness.gui->pushChild(modalPanel); // highest priority

        SDL_Event down{};
        down.type = SDL_MOUSEBUTTONDOWN;
        down.button.button = SDL_BUTTON_LEFT;
        down.button.x = 30; // inside the minimap rect, outside the modal panel rect
        down.button.y = 30;
        expect_true(harness.gui->event(&down), "modal panel should consume the click");
        expect_true(modalPanel->button_count == 1, "a modal panel should take precedence over the minimap overlay");
        expect_true(harness.minimap->mouseEvent(nullptr, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 0, 0),
                    "minimap mouseEvent should still report handled for in-bounds dispatch");
        expect_true(harness.map->button_count == 0,
                    "a modal panel should also stop the click before the underlying map layer");
    }
}

void test_inventory_double_select_uses_selected_item_and_clears_selection() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    auto gui = std::make_shared<CGui>();
    auto player = std::make_shared<CPlayer>();
    auto potion = std::make_shared<CPotion>();
    auto same_type_potion = std::make_shared<CPotion>();
    auto panel = std::make_shared<CGameInventoryPanel>();

    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);

    player->setGame(game);
    player->setBaseStats(player_stats());
    player->setHp(player->getHpMax());
    map->setPlayer(player);

    potion->setGame(game);
    potion->setName("coveredFullHealthPotion");
    potion->setTypeId("coveredFullHealthPotionType");
    potion->addTag(CTag::Heal);
    same_type_potion->setTypeId(potion->getTypeId());
    player->addItem(potion);

    const auto inventory_size = player->getItems().size();
    panel->inventoryCallback(gui, 0, potion);
    expect_true(panel->inventorySelect(gui, 0, potion), "first inventory click should select a usable item");
    expect_true(!panel->inventorySelect(gui, 0, same_type_potion),
                "inventory selection should not select a different item instance with the same configured id");

    panel->inventoryCallback(gui, 0, potion);
    expect_true(player->getItems().size() == inventory_size,
                "full-health potion double-select should call useItem without consuming the item");
    expect_true(!panel->inventorySelect(gui, 0, potion), "second inventory click should clear the used selection");
}

struct InventoryRightClickHarness {
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CPlayer> player;
    std::shared_ptr<CGameInventoryPanel> panel;
};

InventoryRightClickHarness make_inventory_right_click_harness() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    InventoryRightClickHarness harness;
    harness.game = std::make_shared<CGame>();
    harness.map = std::make_shared<CMap>();
    harness.gui = std::make_shared<CGui>();
    harness.player = std::make_shared<CPlayer>();
    harness.panel = std::make_shared<CGameInventoryPanel>();

    harness.game->setMap(harness.map);
    harness.game->setGui(harness.gui);
    harness.map->setGame(harness.game);
    harness.gui->setGame(harness.game);

    harness.player->setGame(harness.game);
    harness.player->setBaseStats(player_stats());
    harness.player->setHp(harness.player->getHpMax());
    harness.map->setPlayer(harness.player);
    return harness;
}

void test_inventory_right_click_uses_usable_item_once_and_consumes_it() {
    auto harness = make_inventory_right_click_harness();
    auto potion = std::make_shared<CPotion>();
    potion->setGame(harness.game);
    potion->setName("healingPotion");
    potion->setTypeId("healingPotionType");
    potion->addTag(CTag::Heal);
    harness.player->addItem(potion);

    // Wound the player so the heal potion actually has something to restore, which lets
    // CCreature::useItem() fire onUse and consume the disposable potion.
    harness.player->setHp(harness.player->getHpMax() - 1);
    const auto inventory_size = harness.player->getItems().size();

    const bool consumed = harness.panel->inventoryRightClickCallback(harness.gui, 0, potion);
    expect_true(consumed, "right-clicking a usable item should return true so parents stop processing the click");
    expect_true(harness.player->getItems().size() == inventory_size - 1,
                "right-clicking a usable disposable potion should use and consume it exactly once");
    expect_true(!harness.player->hasInInventory(potion),
                "the used disposable potion should no longer belong to the player");
}

void test_inventory_right_click_full_resource_item_not_consumed() {
    auto harness = make_inventory_right_click_harness();
    auto potion = std::make_shared<CPotion>();
    potion->setGame(harness.game);
    potion->setName("fullHealthPotion");
    potion->setTypeId("fullHealthPotionType");
    potion->addTag(CTag::Heal);
    harness.player->addItem(potion);

    // Player is already at full HP, so the engine reports no use and must not consume it.
    harness.player->setHp(harness.player->getHpMax());
    const auto inventory_size = harness.player->getItems().size();

    const bool consumed = harness.panel->inventoryRightClickCallback(harness.gui, 0, potion);
    expect_true(consumed, "right-clicking a full-resource item still handles the click (delegates to useItem)");
    expect_true(harness.player->getItems().size() == inventory_size,
                "a full-health potion must not be consumed when the engine reports no use");
    expect_true(harness.player->hasInInventory(potion),
                "a full-health potion must remain in the inventory after a no-op use");
}

void test_inventory_right_click_quest_item_is_protected() {
    auto harness = make_inventory_right_click_harness();
    auto quest_item = std::make_shared<CPotion>();
    quest_item->setGame(harness.game);
    quest_item->setName("questElixir");
    quest_item->setTypeId("questElixirType");
    quest_item->addTag(CTag::Heal);
    quest_item->addTag(CTag::Quest);
    harness.player->addItem(quest_item);

    harness.player->setHp(harness.player->getHpMax() - 1);
    const auto inventory_size = harness.player->getItems().size();

    const bool consumed = harness.panel->inventoryRightClickCallback(harness.gui, 0, quest_item);
    expect_true(!consumed, "right-clicking a quest item must not be handled as a use");
    expect_true(harness.player->getItems().size() == inventory_size,
                "quest items must never be consumed by a right-click use");
    expect_true(harness.player->hasInInventory(quest_item),
                "quest items must remain in the inventory after a right-click");
}

void test_inventory_right_click_invalid_and_empty_are_safe() {
    auto harness = make_inventory_right_click_harness();
    auto potion = std::make_shared<CPotion>();
    potion->setGame(harness.game);
    potion->setName("looseHealingPotion");
    potion->setTypeId("looseHealingPotionType");
    potion->addTag(CTag::Heal);
    // Intentionally NOT added to the inventory: an item the player does not own must not be used.
    harness.player->setHp(harness.player->getHpMax() - 1);

    const bool not_owned = harness.panel->inventoryRightClickCallback(harness.gui, 0, potion);
    expect_true(!not_owned, "right-clicking an item not in the inventory must not be handled as a use");
    expect_true(!harness.player->hasInInventory(potion), "an unowned item is never added or altered by a right-click");

    // A non-item payload (e.g. a bare creature) must be rejected safely.
    auto non_item = std::make_shared<CCreature>();
    const bool non_item_handled = harness.panel->inventoryRightClickCallback(harness.gui, 0, non_item);
    expect_true(!non_item_handled, "right-clicking a non-item payload must be safely ignored");

    // An empty cell (null payload) must be safe and unhandled.
    const bool empty_handled = harness.panel->inventoryRightClickCallback(harness.gui, 0, nullptr);
    expect_true(!empty_handled, "right-clicking an empty inventory cell must be safely ignored");
}

void test_inventory_left_click_drag_still_starts_for_owned_item() {
    auto harness = make_inventory_right_click_harness();
    auto potion = std::make_shared<CPotion>();
    potion->setGame(harness.game);
    potion->setName("draggableHealingPotion");
    potion->setTypeId("draggableHealingPotionType");
    potion->addTag(CTag::Heal);
    harness.player->addItem(potion);

    // The inventory list is draggable (dragEnabled defaults true, #625): a left-click on an
    // owned, non-quest item still authorizes a drag start. A quest item never does.
    expect_true(harness.panel->inventoryDragStart(harness.gui, 0, potion),
                "left-click drag on an owned non-quest inventory item should still start");

    auto quest_item = std::make_shared<CPotion>();
    quest_item->setGame(harness.game);
    quest_item->setName("questBoundPotion");
    quest_item->setTypeId("questBoundPotionType");
    quest_item->addTag(CTag::Quest);
    harness.player->addItem(quest_item);
    expect_true(!harness.panel->inventoryDragStart(harness.gui, 1, quest_item),
                "left-click drag must never start for a quest item");
}

void test_fight_panel_right_click_item_use_still_works() {
    auto harness = make_inventory_right_click_harness();
    auto fight_panel = std::make_shared<CGameFightPanel>();
    auto potion = std::make_shared<CPotion>();
    potion->setGame(harness.game);
    potion->setName("fightHealingPotion");
    potion->setTypeId("fightHealingPotionType");
    potion->addTag(CTag::Heal);
    harness.player->addItem(potion);

    harness.player->setHp(harness.player->getHpMax() - 1);
    const auto inventory_size = harness.player->getItems().size();

    const bool consumed = fight_panel->itemsRightClickCallback(harness.gui, 0, potion);
    expect_true(consumed, "fight-panel right-click item use should remain unchanged and consume the click");
    expect_true(harness.player->getItems().size() == inventory_size - 1,
                "fight-panel right-click should still use and consume a usable disposable potion");
}

void test_fight_panel_enemy_selection_uses_exact_instance() {
    auto panel = std::make_shared<CGameFightPanel>();
    auto enemy = std::make_shared<CCreature>();
    auto same_type_enemy = std::make_shared<CCreature>();

    enemy->setName("unitSelectedEnemy");
    enemy->setTypeId("unitSelectedEnemyType");
    enemy->setHp(1);
    same_type_enemy->setName(enemy->getName());
    same_type_enemy->setTypeId(enemy->getTypeId());
    same_type_enemy->setHp(1);

    panel->setEnemy(enemy);

    expect_true(panel->enemiesSelect(nullptr, 0, enemy), "fight enemy selection should match the selected instance");
    expect_true(!panel->enemiesSelect(nullptr, 0, same_type_enemy),
                "fight enemy selection should not match a different creature with the same configured id");
}

void test_list_view_drag_callbacks_validate_and_drop_without_click_fallback() {
    auto harness = create_drag_list_harness();
    harness.source->setDragStart("sourceDragStart");
    harness.source->setDragCancel("sourceDragCancel");
    harness.target->setDragValidate("targetDragValidate");
    harness.target->setDrop("targetDrop");

    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25),
                "source drag start should consume the click");
    expect_true(harness.gui->hasDragSession(), "source drag start should create a GUI drag session");
    expect_true(harness.panel->drag_starts == 1, "source drag-start callback should run once");
    expect_true(harness.panel->source_clicks == 0, "drag-start should defer normal click fallback");
    expect_true(harness.panel->last_source_index == 0, "drag-start callback should receive the source index");
    expect_true(harness.panel->last_source_object == harness.panel->sourceItem,
                "drag-start callback should receive the source object");

    harness.gui->updateDragSession(125, 25);
    expect_true(harness.target->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25),
                "target drop should consume the release");
    expect_true(harness.panel->drag_validations == 1, "target drag-validate callback should run once");
    expect_true(harness.panel->drops == 1, "target drop callback should run once");
    expect_true(harness.panel->target_clicks == 0, "target drop should not fall back to the click callback");
    expect_true(harness.panel->drag_cancels == 0, "accepted drop should not cancel the source drag");
    expect_true(harness.panel->last_source_index == 0, "target callbacks should receive the source index");
    expect_true(harness.panel->last_source_object == harness.panel->sourceItem,
                "target callbacks should receive the source object");
    expect_true(harness.panel->last_target_index == 0, "target callbacks should receive the target index");
    expect_true(harness.panel->last_target_object == harness.panel->targetItem,
                "target callbacks should receive the target object");
}

void test_list_view_drag_callbacks_cancel_and_preserve_unmoved_clicks() {
    auto harness = create_drag_list_harness();
    harness.source->setDragStart("sourceDragStart");
    harness.source->setDragCancel("sourceDragCancel");

    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession(), "drag-start callback should create a drag session");
    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.panel->source_clicks == 1, "unmoved source release should preserve normal click behavior");
    expect_true(harness.panel->drag_cancels == 0, "unmoved click should not be reported as drag cancel");
    harness.gui->clearDragSession();

    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    harness.gui->updateDragSession(180, 25);
    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 180, 25);
    expect_true(harness.panel->drag_cancels == 1, "moved release without a target should call drag-cancel");
    expect_true(harness.panel->source_clicks == 1, "canceled drag should not add another click callback");
    expect_true(harness.panel->last_source_index == 0, "drag-cancel should receive the source index");
    expect_true(harness.panel->last_source_object == harness.panel->sourceItem,
                "drag-cancel should receive the source object");
}

void test_list_view_legacy_click_callback_still_fires_without_drag_callbacks() {
    auto harness = create_drag_list_harness();

    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25),
                "legacy source click should be consumed");
    expect_true(harness.panel->source_clicks == 1, "legacy source click should still call the click callback");
    expect_true(harness.panel->drag_starts == 0, "legacy source click should not call drag-start");
    expect_true(harness.gui->hasDragSession(), "legacy source click should still create the existing drag session");
    expect_true(harness.panel->last_source_click_index == 0, "legacy click should keep the clicked item index");
    expect_true(harness.panel->last_source_click == harness.panel->sourceItem,
                "legacy click should keep the clicked item object");
}

void test_list_view_non_draggable_does_click_only_press_motion_release() {
    auto harness = create_drag_list_harness();
    harness.source->setDragEnabled(false);

    // Mouse-down on a non-draggable command list must run the click callback and never
    // start a drag session or capture the pointer.
    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25),
                "non-draggable list should consume the left click");
    expect_true(harness.panel->source_clicks == 1, "non-draggable list should fire the click callback once on press");
    expect_true(harness.panel->drag_starts == 0, "non-draggable list should never call drag-start");
    expect_true(!harness.gui->hasDragSession(), "non-draggable list must not create a drag session");
    expect_true(!harness.gui->hasPointerCapture(), "non-draggable list must not capture the pointer");

    // Pointer motion and release must not suppress or duplicate the click callback, and must
    // not retroactively spawn a session/proxy.
    harness.gui->updateDragSession(180, 25);
    expect_true(!harness.gui->hasDragSession(), "motion without a session must not create one");
    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 180, 25),
                "non-draggable list should consume the release");
    expect_true(harness.panel->source_clicks == 1, "motion/release must not suppress or duplicate the click callback");
    expect_true(harness.panel->drag_cancels == 0, "non-draggable list release must not report a drag cancel");
    expect_true(!harness.gui->hasDragSession(), "non-draggable list must leave no drag session after release");
    expect_true(!harness.gui->hasPointerCapture(), "non-draggable list must leave no pointer capture after release");
}

void test_list_view_non_draggable_repeated_click_preserves_first_select_second_confirm() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    auto gui = std::make_shared<CGui>();
    auto player = std::make_shared<CPlayer>();
    auto interaction = std::make_shared<CInteraction>();
    auto panel = std::make_shared<CGameFightPanel>();

    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);

    player->setGame(game);
    player->setBaseStats(player_stats());
    player->setMana(player->getManaMax());
    map->setPlayer(player);

    interaction->setGame(game);
    interaction->setName("nonDraggableInteraction");
    interaction->setTypeId("nonDraggableInteractionType");
    interaction->setManaCost(0);
    player->addAction(interaction);

    // First combat click selects (highlights) the affordable interaction.
    panel->interactionsCallback(gui, 0, interaction);
    expect_true(panel->interactionsSelect(gui, 0, interaction),
                "first combat interaction click should select the interaction");

    // Second click on the same interaction confirms it; selection is preserved until the
    // blocking select loop consumes finalSelected, so the highlight remains.
    panel->interactionsCallback(gui, 0, interaction);
    expect_true(panel->interactionsSelect(gui, 0, interaction),
                "second combat interaction click should confirm without losing the selection");
}

void test_list_view_draggable_default_still_drags_after_non_draggable_change() {
    auto harness = create_drag_list_harness();
    // Default (unset dragEnabled) preserves legacy draggable behavior: a populated item
    // still starts the generic drag session on press (inventory/equipment regression).
    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25),
                "default draggable list should consume the click");
    expect_true(harness.gui->hasDragSession(), "default draggable list should still create the existing drag session");
    expect_true(harness.panel->source_clicks == 1, "default draggable list should still fire the click callback");
    harness.gui->clearDragSession();
    harness.gui->releasePointerCapture();

    // Explicitly enabling drag keeps the same behavior.
    harness.source->setDragEnabled(true);
    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25),
                "explicitly draggable list should consume the click");
    expect_true(harness.gui->hasDragSession(), "explicitly draggable list should still create a drag session");
    harness.gui->clearDragSession();
    harness.gui->releasePointerCapture();
}

void test_list_view_non_draggable_panel_removal_during_input_leaves_no_session_or_capture() {
    auto harness = create_drag_list_harness();
    harness.source->setDragEnabled(false);

    // Press on the non-draggable list (no session/capture is created), then remove the
    // owning panel mid-interaction. Nothing dangling should remain.
    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(!harness.gui->hasDragSession(), "non-draggable press should not create a session before removal");
    expect_true(!harness.gui->hasPointerCapture(), "non-draggable press should not capture the pointer before removal");

    harness.gui->removeChild(harness.panel);
    expect_true(!harness.gui->hasDragSession(), "panel removal during input must leave no dangling drag session");
    expect_true(!harness.gui->hasPointerCapture(), "panel removal during input must leave no dangling pointer capture");
}

void test_list_view_below_threshold_motion_stays_a_click_no_proxy_no_drop() {
    // Deferred source callback path (select returns true) so the click is decided at
    // release: below-threshold motion must fire the click callback exactly once and
    // never spawn a proxy, drop, or drag-cancel.
    auto harness = create_drag_list_harness();
    harness.source->setSelect("");
    harness.source->setDragStart("sourceDragStart");
    harness.source->setDragCancel("sourceDragCancel");

    // Press starts a candidate drag session (drag-start deferred the click).
    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25),
                "source press should be consumed");
    expect_true(harness.gui->hasDragSession(), "press should create a candidate drag session");
    expect_true(harness.gui->getDragSession() && !harness.gui->getDragSession()->dragActive,
                "a fresh session must be a candidate, not an active drag");
    expect_true(harness.panel->source_clicks == 0, "drag-start should defer the click until release");

    // Below-threshold motion (Chebyshev distance 4 <= threshold) keeps it a candidate.
    harness.gui->updateDragSession(29, 29);
    expect_true(harness.gui->getDragSession() && !harness.gui->getDragSession()->dragActive,
                "below-threshold motion must not promote the session to an active drag");

    // Release below threshold: this is a click. The click callback fires exactly once,
    // and no drag-cancel is reported.
    expect_true(harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 29, 29),
                "below-threshold release should be consumed");
    expect_true(harness.panel->source_clicks == 1, "below-threshold release must fire the click callback exactly once");
    expect_true(harness.panel->drag_cancels == 0, "below-threshold click must not report a drag cancel");
    expect_true(harness.panel->drops == 0, "below-threshold click must not perform a drop");
}

void test_list_view_exact_boundary_is_a_click_above_boundary_is_a_drag() {
    // Exact boundary (Chebyshev distance == threshold) is a click (exclusive boundary).
    {
        auto harness = create_drag_list_harness();
        harness.source->setDragStart("sourceDragStart");
        harness.source->setDragCancel("sourceDragCancel");

        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
        harness.gui->updateDragSession(29, 29); // dx = dy = 4 (exact boundary)
        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 29, 29);
        expect_true(harness.panel->source_clicks == 1, "exact-boundary motion must stay a click and fire once");
        expect_true(harness.panel->drag_cancels == 0, "exact-boundary click must not report a drag cancel");
    }

    // One pixel past the boundary is a drag; with no target the source drag is canceled
    // and the click callback does not fire.
    {
        auto harness = create_drag_list_harness();
        harness.source->setDragStart("sourceDragStart");
        harness.source->setDragCancel("sourceDragCancel");

        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
        harness.gui->updateDragSession(30, 25); // dx = 5 (above boundary)
        expect_true(harness.gui->getDragSession() && harness.gui->getDragSession()->dragActive,
                    "above-boundary motion must promote the session to an active drag");
        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 30, 25);
        expect_true(harness.panel->drag_cancels == 1, "above-boundary release without a target must call drag-cancel");
        expect_true(harness.panel->source_clicks == 0, "an active drag must not fire the click callback");
    }
}

void test_list_view_negative_and_diagonal_motion_follow_the_rule() {
    // Negative-axis motion above threshold is a drag.
    {
        auto harness = create_drag_list_harness();
        harness.source->setDragStart("sourceDragStart");
        harness.source->setDragCancel("sourceDragCancel");
        // Start away from the edge so a negative offset stays inside the widget.
        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 40, 40);
        harness.gui->updateDragSession(35, 40); // dx = -5
        expect_true(harness.gui->getDragSession() && harness.gui->getDragSession()->dragActive,
                    "negative-axis motion above threshold must become a drag");
    }

    // Diagonal 4/4 stays a click; diagonal 5/5 is a drag.
    {
        auto harness = create_drag_list_harness();
        harness.source->setDragStart("sourceDragStart");
        harness.source->setDragCancel("sourceDragCancel");
        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 20, 20);
        harness.gui->updateDragSession(24, 24); // diagonal 4/4
        expect_true(harness.gui->getDragSession() && !harness.gui->getDragSession()->dragActive,
                    "diagonal 4/4 motion must stay a click");
        harness.gui->updateDragSession(25, 25); // diagonal 5/5
        expect_true(harness.gui->getDragSession() && harness.gui->getDragSession()->dragActive,
                    "diagonal 5/5 motion must become a drag");
    }
}

void test_list_view_above_threshold_drop_is_accepted_below_threshold_is_not() {
    // Above-threshold motion onto a valid target performs the drop.
    {
        auto harness = create_drag_list_harness();
        harness.source->setDragStart("sourceDragStart");
        harness.source->setDragCancel("sourceDragCancel");
        harness.target->setDragValidate("targetDragValidate");
        harness.target->setDrop("targetDrop");

        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
        harness.gui->updateDragSession(125, 25); // well past the threshold, over the target
        expect_true(harness.target->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25),
                    "above-threshold drop should be consumed by the target");
        expect_true(harness.panel->drops == 1, "above-threshold motion onto a target must drop exactly once");
        expect_true(harness.panel->drag_cancels == 0, "an accepted drop must not cancel the source drag");
    }

    // Below-threshold motion must NOT be treated as a drop even if the release lands on
    // the target rectangle: it is a click on the source.
    {
        auto harness = create_drag_list_harness();
        harness.source->setDragStart("sourceDragStart");
        harness.source->setDragCancel("sourceDragCancel");
        harness.target->setDragValidate("targetDragValidate");
        harness.target->setDrop("targetDrop");

        harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
        harness.gui->updateDragSession(27, 25); // dx = 2, below threshold
        expect_true(harness.target->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25),
                    "below-threshold release should still be consumed");
        expect_true(harness.panel->drops == 0, "below-threshold motion must not perform a drop");
        expect_true(harness.panel->drag_validations == 0, "below-threshold motion must not validate a drop target");
    }
}

void test_list_view_moved_drop_without_target_callbacks_cancels_instead_of_clicking() {
    // Drop contract (#627): a moved cross-list release is only ever a drop. A list that
    // does not define target drop callbacks is not a drop target, so the gesture must
    // cancel the source drag. It must NOT fall back to the target's ordinary click
    // callback with the target-cell object (the pre-fix behavior), because that
    // re-enters selection-state click flows and can mutate a different object than the
    // dragged payload.
    auto harness = create_drag_list_harness();
    harness.source->setDragStart("sourceDragStart");
    harness.source->setDragCancel("sourceDragCancel");
    // The target list intentionally has no dragValidate/drop callbacks.

    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession(), "source drag start should create a GUI drag session");
    harness.gui->updateDragSession(125, 25); // above threshold, over the target list

    expect_true(harness.target->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25),
                "a moved release over a drop-incapable list should still be consumed");
    expect_true(harness.panel->target_clicks == 0,
                "a moved drop must never invoke the target's ordinary click callback");
    expect_true(harness.panel->drops == 0, "a drop-incapable list must not report a drop");
    expect_true(harness.panel->drag_cancels == 1,
                "a moved drop on a drop-incapable list must cancel the source drag once");
    expect_true(harness.gui->hasDragSession() && !harness.gui->getDragSession()->acceptedTarget.lock(),
                "a drop-incapable list must never accept the drag session");
}

struct InventoryDragDropHarness {
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CPlayer> player;
    std::shared_ptr<CGameInventoryPanel> panel;
    std::shared_ptr<CListView> inventory;
    std::shared_ptr<CListView> equipped;
};

// Builds a real CGameInventoryPanel with its two CListViews wired exactly like
// res/config/panels.json (collections, drag callbacks, grouping) plus a two-slot
// configuration: slot "0" accepts CWeapon and slot "1" accepts CHelmet only. Drag
// gestures are then driven through the same CListView::mouseEvent entry points the
// live GUI uses, so the tests exercise payload resolution, validation, and drop
// dispatch end to end.
InventoryDragDropHarness create_inventory_drag_drop_harness() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    InventoryDragDropHarness harness;
    harness.gui = std::make_shared<CGui>();
    harness.game = create_gui_game(harness.gui);
    harness.map = harness.game->getMap();
    for (const auto &[name, builder] : *CTypes::builders()) {
        harness.game->getObjectHandler()->registerType(name, builder);
    }
    harness.game->getObjectHandler()->registerConfig("slotConfiguration", CJsonUtil::from_string(R"({
            "class": "CSlotConfig",
            "properties": {
                "configuration": {
                    "0": {"class": "CSlot", "properties": {"slotName": "RightHand", "types": ["CWeapon"]}},
                    "1": {"class": "CSlot", "properties": {"slotName": "Head", "types": ["CHelmet"]}}
                }
            }
        })",
                                                                                                 "slotConfiguration"));

    harness.player = std::make_shared<CPlayer>();
    harness.player->setGame(harness.game);
    harness.player->setBaseStats(player_stats());
    harness.player->setHp(harness.player->getHpMax());
    harness.map->setPlayer(harness.player);

    harness.panel = std::make_shared<CGameInventoryPanel>();
    harness.panel->setLayout(fixed_layout(0, 0, 400, 100));

    harness.inventory = std::make_shared<CListView>();
    harness.inventory->setLayout(fixed_layout(0, 0, 100, 50));
    harness.inventory->setCollection("inventoryCollection");
    harness.inventory->setCallback("inventoryCallback");
    harness.inventory->setSelect("inventorySelect");
    harness.inventory->setRightClickCallback("inventoryRightClickCallback");
    harness.inventory->setDragStart("inventoryDragStart");
    harness.inventory->setDragCancel("inventoryDragCancel");
    harness.inventory->setDragValidate("inventoryDropValidate");
    harness.inventory->setDrop("inventoryDrop");
    harness.inventory->setGrouping(true);
    harness.inventory->setTileSize(50);
    harness.inventory->setXPrefferedSize(2);
    harness.inventory->setYPrefferedSize(1);

    harness.equipped = std::make_shared<CListView>();
    harness.equipped->setLayout(fixed_layout(200, 0, 100, 50));
    harness.equipped->setCollection("equippedCollection");
    harness.equipped->setCallback("equippedCallback");
    harness.equipped->setSelect("equippedSelect");
    harness.equipped->setDragStart("equippedDragStart");
    harness.equipped->setDragCancel("equippedDragCancel");
    harness.equipped->setDragValidate("equippedDropValidate");
    harness.equipped->setDrop("equippedDrop");
    harness.equipped->setTileSize(50);
    harness.equipped->setXPrefferedSize(2);
    harness.equipped->setYPrefferedSize(1);

    harness.panel->addChild(harness.inventory);
    harness.panel->addChild(harness.equipped);
    harness.gui->pushChild(harness.panel);
    return harness;
}

std::shared_ptr<CWeapon> make_inventory_weapon(const InventoryDragDropHarness &harness, const std::string &name) {
    auto weapon = std::make_shared<CWeapon>();
    weapon->setGame(harness.game);
    weapon->setName(name);
    weapon->setTypeId(name + "Type");
    // Stat composition folds equipped item bonuses without a null guard, so every
    // equippable test item carries an (empty) bonus block like configured items do.
    weapon->setBonus(std::make_shared<CStats>());
    harness.player->addItem(weapon);
    return weapon;
}

void test_inventory_drag_drop_equips_exact_dragged_item_and_unequips_it_back() {
    auto harness = create_inventory_drag_drop_harness();
    auto sword = make_inventory_weapon(harness, "identityDragSword");
    auto spare = make_inventory_weapon(harness, "identityDragSpare");

    // Press on the first inventory cell; the session payload is the exact item shown
    // in that cell (grouping order is not asserted, identity is read from the session).
    harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession(), "inventory press on an owned item should start a drag session");
    auto payload = vstd::cast<CItem>(harness.gui->getDragSession() ? harness.gui->getDragSession()->payload : nullptr);
    expect_true(payload && (CGameObject::sameInstance(payload, sword) || CGameObject::sameInstance(payload, spare)),
                "the drag payload must be one of the player's exact inventory items");
    if (!payload) {
        return;
    }
    auto other = CGameObject::sameInstance(payload, sword) ? spare : sword;

    // Select the OTHER item via the ordinary click flow: the drop must equip the
    // dragged payload, never the current selection.
    harness.panel->inventoryCallback(harness.gui, 0, other);

    harness.gui->updateDragSession(225, 25); // above threshold, over equipped slot "0"
    expect_true(harness.equipped->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25),
                "drop on a compatible equipment slot should be consumed");
    expect_true(CGameObject::sameInstance(harness.player->getItemAtSlot("0"), payload),
                "the exact dragged item must be the one equipped in the compatible slot");
    expect_true(!harness.player->hasInInventory(payload),
                "the equipped dragged item must leave the inventory exactly once");
    expect_true(harness.player->hasInInventory(other),
                "the selected-but-not-dragged item must stay in the inventory untouched");
    expect_true(harness.player->getItemAtSlot("1") == nullptr, "no other slot may be touched by the drop");
    expect_true(harness.gui->getDragSession() &&
                    harness.gui->getDragSession()->acceptedTarget.lock() == harness.equipped,
                "a successful drop must accept the drag session on the target list");

    // Round trip: drag the equipped item back onto the inventory list; the exact item
    // must be unequipped and returned to the inventory once.
    harness.gui->clearDragSession();
    harness.gui->releasePointerCapture();
    harness.equipped->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession() && harness.gui->getDragSession() &&
                    CGameObject::sameInstance(harness.gui->getDragSession()->payload, payload),
                "dragging the equipped slot should carry the exact equipped item as payload");
    harness.gui->updateDragSession(25, 25); // above threshold, over the inventory list
    expect_true(harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25),
                "drop of an equipped item on the inventory list should be consumed");
    expect_true(harness.player->getItemAtSlot("0") == nullptr,
                "dropping an equipped item on the inventory must unequip its slot");
    expect_true(harness.player->hasInInventory(payload), "the exact unequipped item must return to the inventory");
    expect_true(harness.player->hasInInventory(other), "the untouched item must survive the round trip");
}

void test_inventory_drag_drop_incompatible_slot_rejects_without_ownership_change() {
    auto harness = create_inventory_drag_drop_harness();
    auto sword = make_inventory_weapon(harness, "incompatibleDropSword");

    harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession(), "inventory press should start the drag session");
    harness.gui->updateDragSession(275, 25); // above threshold, over equipped slot "1" (helmet-only)

    harness.equipped->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 75, 25);
    expect_true(harness.player->hasInInventory(sword),
                "a weapon dropped on an incompatible slot must stay in the inventory");
    expect_true(harness.player->getItemAtSlot("1") == nullptr, "an incompatible slot must stay empty after the drop");
    expect_true(harness.player->getItemAtSlot("0") == nullptr,
                "an incompatible drop must not equip the item anywhere else");
    expect_true(harness.gui->getDragSession() && !harness.gui->getDragSession()->acceptedTarget.lock(),
                "an incompatible drop must not accept the drag session");
}

void test_inventory_drag_drop_quest_item_is_protected() {
    auto harness = create_inventory_drag_drop_harness();
    auto relic = make_inventory_weapon(harness, "questBoundRelicSword");
    relic->addTag(CTag::Quest);

    // A quest item never authorizes a drag start.
    harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(!harness.gui->hasDragSession(), "a quest item must never start an inventory drag session");

    // Even a forced session carrying a quest payload must be rejected by the drop
    // validation, leaving ownership unchanged.
    harness.gui->startDragSession(harness.inventory, relic, 0, 25, 25, true);
    harness.gui->updateDragSession(225, 25);
    harness.equipped->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.player->hasInInventory(relic),
                "a quest item must stay in the inventory after any drop attempt");
    expect_true(harness.player->getItemAtSlot("0") == nullptr, "a quest item must never be equipped through a drop");
    expect_true(harness.gui->getDragSession() && !harness.gui->getDragSession()->acceptedTarget.lock(),
                "a quest-item drop must not accept the drag session");
}

void test_inventory_drag_drop_same_list_release_is_a_no_op() {
    auto harness = create_inventory_drag_drop_harness();
    auto sword = make_inventory_weapon(harness, "sameListDropSword");

    harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession(), "inventory press should start the drag session");
    harness.gui->updateDragSession(75, 25); // above threshold, still over the inventory list

    harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 75, 25);
    expect_true(harness.player->hasInInventory(sword), "a same-list drop must leave the item in the inventory");
    expect_true(harness.player->getItemAtSlot("0") == nullptr && harness.player->getItemAtSlot("1") == nullptr,
                "a same-list drop must not equip anything");
    expect_true(harness.gui->getDragSession() && !harness.gui->getDragSession()->acceptedTarget.lock(),
                "a same-list drop must not accept the drag session");
}

void test_inventory_drag_drop_cancel_outside_targets_keeps_ownership() {
    auto harness = create_inventory_drag_drop_harness();
    auto sword = make_inventory_weapon(harness, "cancelPathDragSword");

    harness.inventory->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    expect_true(harness.gui->hasDragSession(), "inventory press should start the drag session");
    harness.gui->updateDragSession(350, 75); // above threshold, outside both lists

    // Release through the full GUI pipeline so cancel, capture, and session cleanup run.
    SDL_Event release{};
    release.type = SDL_MOUSEBUTTONUP;
    release.button.button = SDL_BUTTON_LEFT;
    release.button.x = 350;
    release.button.y = 75;
    harness.gui->event(&release);

    expect_true(!harness.gui->hasDragSession(), "a cancelled drag must clear the drag session");
    expect_true(!harness.gui->hasPointerCapture(), "a cancelled drag must clear pointer capture");
    expect_true(harness.player->hasInInventory(sword), "a cancelled drag must leave the item in the inventory");
    expect_true(harness.player->getItemAtSlot("0") == nullptr && harness.player->getItemAtSlot("1") == nullptr,
                "a cancelled drag must not equip anything");
    expect_true(harness.panel->inventorySelect(harness.gui, 0, sword),
                "a cancelled drag should restore the dragged item as the inventory selection");
}

void test_list_view_below_threshold_candidate_panel_removal_leaves_no_session() {
    // A candidate (below-threshold) session must be cleared correctly when the owning
    // panel is removed before the threshold is ever crossed.
    auto harness = create_drag_list_harness();
    harness.source->setDragStart("sourceDragStart");

    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    harness.gui->updateDragSession(26, 26); // below threshold: still a candidate
    expect_true(harness.gui->hasDragSession() && !harness.gui->getDragSession()->dragActive,
                "press + jitter should leave a candidate session before removal");

    harness.gui->removeChild(harness.panel);
    expect_true(!harness.gui->hasDragSession(), "panel removal must clear a below-threshold candidate drag session");
    expect_true(!harness.gui->hasPointerCapture(), "panel removal must clear pointer capture for a candidate session");
}

void test_list_view_active_drag_panel_removal_leaves_no_session() {
    // An active (above-threshold) drag session must also be cleared on panel removal.
    auto harness = create_drag_list_harness();
    harness.source->setDragStart("sourceDragStart");

    harness.source->mouseEvent(harness.gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 25, 25);
    harness.gui->updateDragSession(120, 25); // above threshold: active drag
    expect_true(harness.gui->hasDragSession() && harness.gui->getDragSession()->dragActive,
                "press + threshold-crossing motion should leave an active drag session");

    harness.gui->removeChild(harness.panel);
    expect_true(!harness.gui->hasDragSession(), "panel removal must clear an active drag session");
    expect_true(!harness.gui->hasPointerCapture(), "panel removal must clear pointer capture for an active session");
}

void test_panel_event_callbacks_stop_after_close() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto panel = std::make_shared<CGamePanel>();
    gui->pushChild(panel);

    int first_callback_count = 0;
    int second_callback_count = 0;
    auto always = [](std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *) { return true; };

    panel->registerEventCallback(
        always, [&first_callback_count](std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject> self, SDL_Event *) {
            ++first_callback_count;
            if (auto panel = vstd::cast<CGamePanel>(self)) {
                panel->close();
            }
            return false;
        });
    panel->registerEventCallback(
        always, [&second_callback_count](std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *) {
            ++second_callback_count;
            return false;
        });

    SDL_Event event{};
    event.type = SDL_MOUSEBUTTONDOWN;
    event.button.button = SDL_BUTTON_LEFT;
    gui->event(&event);

    expect_true(first_callback_count == 1, "first callback should close the panel during event dispatch");
    expect_true(second_callback_count == 0, "detached panel should not receive later event callbacks");
    expect_true(!gui->findChild(panel), "closed panel should be detached from the GUI");
}

void test_loader_gui_sessions_shutdown_stale_callbacks() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto firstGame = create_loader_gui_game();
    CGameLoader::loadGui(firstGame);
    auto firstGui = firstGame->getGui();
    auto firstContext = firstGame->getContext();
    expect_true(firstGui != nullptr, "first loader GUI session should create a GUI");

    auto firstRecorder = attach_mouse_recorder(firstGui);
    int firstRenderCount = 0;
    firstGui->pushChild(std::make_shared<CountingRenderObject>(firstRenderCount));

    firstContext->shutdown();
    expect_true(!firstContext->isActive(), "first context should be inactive after explicit shutdown");
    expect_true(firstGame->getGui() == nullptr, "first shutdown should detach the game GUI");
    expect_true(firstGui->getChildren().empty(), "first shutdown should clear GUI children");
    drain_event_loop();
    expect_true(firstRecorder->button_count == 0, "first shutdown should prevent stale event dispatch");
    expect_true(firstRenderCount == 0, "first shutdown should prevent stale frame rendering");

    auto secondGame = create_loader_gui_game();
    CGameLoader::loadGui(secondGame);
    auto secondGui = secondGame->getGui();
    auto secondContext = secondGame->getContext();
    expect_true(secondGui != nullptr, "second loader GUI session should create a GUI");

    auto secondRecorder = attach_mouse_recorder(secondGui);
    int secondRenderCount = 0;
    secondGui->pushChild(std::make_shared<CountingRenderObject>(secondRenderCount));

    SDL_Event event{};
    event.type = SDL_MOUSEBUTTONDOWN;
    event.button.button = SDL_BUTTON_LEFT;
    event.button.x = 35;
    event.button.y = 55;
    SDL_PushEvent(&event);
    drain_event_loop();

    expect_true(firstRecorder->button_count == 0, "second session events should not reach the first GUI");
    expect_true(secondRecorder->button_count == 1, "second session should receive one event-loop dispatch");
    expect_true(secondRenderCount > 0, "second active GUI should render through its event-loop callback");

    secondContext->shutdown();
    expect_true(!secondContext->isActive(), "second context should be inactive after explicit shutdown");
    const int renderCountAfterShutdown = secondRenderCount;
    drain_event_loop();
    expect_true(secondRecorder->button_count == 1, "second shutdown should stop later event dispatch");
    expect_true(secondRenderCount == renderCountAfterShutdown, "second shutdown should stop later frame rendering");

    int directRenderCount = 0;
    int directEventCount = 0;
    CTypes::register_type_metadata<CountingGui, CGui, CGameGraphicsObject, CGameObject>();
    auto directShutdownGame = create_loader_gui_game("CountingGui");
    directShutdownGame->getObjectHandler()->registerType(
        "CountingGui", [&directRenderCount]() { return std::make_shared<CountingGui>(directRenderCount); });
    CGameLoader::loadGui(directShutdownGame);
    auto directShutdownGui = vstd::cast<CountingGui>(directShutdownGame->getGui());
    expect_true(directShutdownGui != nullptr, "direct shutdown test should load a counting GUI");
    expect_true(directShutdownGame->getContext()->isActive(),
                "direct GUI shutdown should leave the game context active before the shutdown");

    directShutdownGui->registerEventCallback(
        [](std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *) { return true; },
        [&directEventCount](std::shared_ptr<CGui>, std::shared_ptr<CGameGraphicsObject>, SDL_Event *) {
            ++directEventCount;
            return true;
        });
    directShutdownGui->shutdown();
    expect_true(!directShutdownGui->isActive(), "direct GUI shutdown should mark the GUI inactive");
    expect_true(directShutdownGame->getGui() == directShutdownGui,
                "direct GUI shutdown should leave the game GUI pointer intact for stale callback coverage");

    SDL_Event staleEvent{};
    staleEvent.type = SDL_MOUSEBUTTONDOWN;
    staleEvent.button.button = SDL_BUTTON_LEFT;
    staleEvent.button.x = 35;
    staleEvent.button.y = 55;
    SDL_PushEvent(&staleEvent);
    drain_event_loop();

    expect_true(directRenderCount == 0, "direct GUI shutdown should prevent stale frame rendering");
    expect_true(directEventCount == 0, "direct GUI shutdown should prevent stale root event dispatch");
}

void test_gui_routes_mouse_motion_to_target_child() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto recorder = attach_mouse_recorder(gui);

    SDL_Event event{};
    event.type = SDL_MOUSEMOTION;
    event.motion.x = 35;
    event.motion.y = 55;
    event.motion.xrel = 4;
    event.motion.yrel = -3;

    expect_true(gui->event(&event), "mouse motion over a child should be consumed by that child");
    expect_true(recorder->motion_count == 1, "mouse motion should be routed to the child handler");
    expect_true(recorder->last_type == SDL_MOUSEMOTION, "mouse motion handler should receive the SDL event type");
    expect_true(recorder->last_x == 25 && recorder->last_y == 35,
                "mouse motion coordinates should be relative to the child layout");
    expect_true(recorder->last_xrel == 4 && recorder->last_yrel == -3,
                "mouse motion relative deltas should be preserved");
}

void test_gui_routes_mouse_button_up_without_drag_to_target_child() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto recorder = attach_mouse_recorder(gui);

    SDL_Event event{};
    event.type = SDL_MOUSEBUTTONUP;
    event.button.button = SDL_BUTTON_LEFT;
    event.button.x = 35;
    event.button.y = 55;

    expect_true(gui->event(&event), "mouse button up without a drag should use normal hit testing");
    expect_true(recorder->button_count == 1, "mouse button up should be routed to the target child");
    expect_true(recorder->last_type == SDL_MOUSEBUTTONUP, "mouse button handler should receive the SDL event type");
    expect_true(recorder->last_button == SDL_BUTTON_LEFT, "mouse button handler should receive the SDL button");
    expect_true(recorder->last_x == 25 && recorder->last_y == 35,
                "mouse button coordinates should be relative to the child layout");
}

void test_gui_routes_mouse_wheel_to_target_child() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto recorder = attach_mouse_recorder(gui);

    SDL_Event event{};
    event.type = SDL_MOUSEWHEEL;
    event.wheel.x = -1;
    event.wheel.y = 2;
#if SDL_VERSION_ATLEAST(2, 26, 0)
    event.wheel.mouseX = 40;
    event.wheel.mouseY = 70;
#else
    recorder->setModal(true);
#endif

    expect_true(gui->event(&event), "mouse wheel over a child should be consumed by that child");
    expect_true(recorder->wheel_count == 1, "mouse wheel should be routed to the child handler");
    expect_true(recorder->last_type == SDL_MOUSEWHEEL, "mouse wheel handler should receive the SDL event type");
    expect_true(recorder->last_wheel_x == -1 && recorder->last_wheel_y == 2, "mouse wheel deltas should be preserved");
#if SDL_VERSION_ATLEAST(2, 26, 0)
    expect_true(recorder->last_x == 30 && recorder->last_y == 50,
                "mouse wheel coordinates should be relative to the child layout");
#endif
}

void test_gui_routes_window_leave_as_mouse_cancel() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto recorder = attach_mouse_recorder(gui);

    SDL_Event event{};
    event.type = SDL_WINDOWEVENT;
    event.window.event = SDL_WINDOWEVENT_LEAVE;

    expect_true(gui->event(&event), "window leave should be consumed by a child cancel handler");
    expect_true(recorder->cancel_count == 1, "window leave should be routed as mouse cancellation");
    expect_true(recorder->last_type == SDL_WINDOWEVENT, "mouse cancel handler should receive the SDL event type");
}

void test_gui_pointer_capture_routes_drag_release_and_clears_session() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto source = attach_mouse_recorder(gui);
    auto target = attach_drop_target_recorder(gui);
    auto payload = std::make_shared<CGameObject>();

    gui->startDragSession(source, payload, 7, 20, 30);
    gui->capturePointer(source);

    SDL_Event motion{};
    motion.type = SDL_MOUSEMOTION;
    motion.motion.x = 220;
    motion.motion.y = 55;
    motion.motion.xrel = 200;
    motion.motion.yrel = 25;

    expect_true(gui->event(&motion), "captured mouse motion outside the source should be consumed");
    expect_true(source->motion_count == 1, "captured source should receive motion outside its rectangle");
    expect_true(target->motion_count == 0, "motion should not be rerouted to the hovered target during capture");
    expect_true(gui->hasDragSession(), "drag session should remain active during captured motion");
    expect_true(gui->hasPointerCapture(), "pointer capture should remain active during captured motion");

    SDL_Event button_up{};
    button_up.type = SDL_MOUSEBUTTONUP;
    button_up.button.button = SDL_BUTTON_LEFT;
    button_up.button.x = 220;
    button_up.button.y = 55;

    expect_true(gui->event(&button_up), "drop over target should be consumed");
    expect_true(target->button_count == 1, "drop target should receive the release under the pointer");
    expect_true(source->button_count == 1, "captured source should also receive the release");
    expect_true(!gui->hasDragSession(), "drop should clear the drag session");
    expect_true(!gui->hasPointerCapture(), "drop should clear pointer capture");
}

void test_gui_pointer_capture_does_not_duplicate_same_source_release() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto source = attach_mouse_recorder(gui);

    gui->startDragSession(source, std::make_shared<CGameObject>(), 7, 20, 30);
    gui->capturePointer(source);

    SDL_Event motion{};
    motion.type = SDL_MOUSEMOTION;
    motion.motion.x = 36;
    motion.motion.y = 56;
    motion.motion.xrel = 1;
    motion.motion.yrel = 1;

    expect_true(gui->event(&motion), "same-source jitter motion should be captured");

    SDL_Event button_up{};
    button_up.type = SDL_MOUSEBUTTONUP;
    button_up.button.button = SDL_BUTTON_LEFT;
    button_up.button.x = 36;
    button_up.button.y = 56;

    expect_true(gui->event(&button_up), "same-source release should be handled");
    expect_true(source->button_count == 1, "same-source release should not be dispatched twice");
    expect_true(!gui->hasDragSession(), "same-source release should clear the drag session");
    expect_true(!gui->hasPointerCapture(), "same-source release should clear pointer capture");
}

void test_gui_pointer_capture_clears_when_captured_widget_is_removed() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto source = attach_mouse_recorder(gui);

    gui->startDragSession(source, std::make_shared<CGameObject>(), 3, 20, 30);
    gui->capturePointer(source);
    gui->removeChild(source);

    expect_true(!gui->hasDragSession(), "removing the captured widget should clear the drag session");
    expect_true(!gui->hasPointerCapture(), "removing the captured widget should clear pointer capture");
}

void test_render_traversal_stops_after_detach() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto parent = std::make_shared<ClosingRenderObject>();
    int child_render_count = 0;
    auto child = std::make_shared<CountingRenderObject>(child_render_count);

    parent->addChild(child);
    gui->pushChild(parent);
    gui->render(0);

    expect_true(!gui->findChild(parent), "rendering parent should detach itself from the GUI");
    expect_true(child_render_count == 0, "children of a detached render object should fail closed");
}

void test_texture_cache_without_gui_fails_closed() {
    auto cache = std::make_shared<CTextureCache>();
    expect_true(cache->getTexture("images/panel") == nullptr, "texture cache without GUI should return null");
}

void test_render_context_rejects_null_texture_and_copies_valid_texture() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto &renderContext = gui->getRenderContext();
    renderContext.resetStats();

    SDL_Rect target = {2, 3, 4, 5};
    expect_true(!renderContext.copy(nullptr, nullptr, &target), "render context should reject null textures");

    const auto normalized = CRenderContext::normalizeTargetRect(SDL_Rect{10, 12, -3, -4});
    expect_true(normalized.x == 7 && normalized.y == 8 && normalized.w == 3 && normalized.h == 4,
                "render context should normalize negative target extents");

    auto surface = fn::sdl::SurfacePtr(SDL_SAFE(SDL_CreateRGBSurfaceWithFormat(0, 2, 2, 32, SDL_PIXELFORMAT_RGBA32)));
    expect_true(surface != nullptr, "render context smoke test should create an SDL surface");
    if (!surface) {
        return;
    }
    SDL_SAFE(SDL_FillRect(surface.get(), nullptr, SDL_MapRGBA(surface->format, 255, 0, 0, 255)));
    auto texture = fn::sdl::TexturePtr(SDL_SAFE(SDL_CreateTextureFromSurface(gui->getRenderer(), surface.get())));
    expect_true(texture != nullptr, "render context smoke test should create an SDL texture");
    if (!texture) {
        return;
    }

    SDL_Rect source = {0, 0, 2, 2};
    SDL_Rect clip = {0, 0, 8, 8};
    expect_true(renderContext.copy(texture.get(), &source, target, &clip), "render context should copy valid textures");

    const auto &stats = renderContext.getStats();
    expect_true(stats.attemptedCopies == 2, "render context should count attempted copies");
    expect_true(stats.successfulCopies == 1, "render context should count successful copies");
    expect_true(stats.skippedCopies == 1, "render context should count skipped copies");
    expect_true(stats.failedCopies == 0, "render context should not count failed copies for valid smoke path");
}

void test_render_context_copy_ex_rotates_and_tracks_stats() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto &renderContext = gui->getRenderContext();
    renderContext.resetStats();

    // copyEx must fail closed on missing texture, exactly like copy().
    SDL_Rect target = {2, 3, 4, 5};
    expect_true(!renderContext.copyEx(nullptr, nullptr, &target, 90.0, nullptr, SDL_FLIP_NONE),
                "render context copyEx should reject null textures");

    auto surface = fn::sdl::SurfacePtr(SDL_SAFE(SDL_CreateRGBSurfaceWithFormat(0, 2, 2, 32, SDL_PIXELFORMAT_RGBA32)));
    expect_true(surface != nullptr, "render context copyEx smoke test should create an SDL surface");
    if (!surface) {
        return;
    }
    SDL_SAFE(SDL_FillRect(surface.get(), nullptr, SDL_MapRGBA(surface->format, 0, 255, 0, 255)));
    auto texture = fn::sdl::TexturePtr(SDL_SAFE(SDL_CreateTextureFromSurface(gui->getRenderer(), surface.get())));
    expect_true(texture != nullptr, "render context copyEx smoke test should create an SDL texture");
    if (!texture) {
        return;
    }

    // Negative extents must be normalized before reaching SDL, mirroring copy().
    SDL_Rect flippedTarget = {10, 12, -4, -5};
    SDL_Rect clip = {0, 0, 8, 8};
    expect_true(renderContext.copyEx(texture.get(), nullptr, &flippedTarget, 45.0, nullptr, SDL_FLIP_HORIZONTAL, &clip),
                "render context copyEx should rotate and copy valid textures");

    const auto &stats = renderContext.getStats();
    expect_true(stats.attemptedCopies == 2, "render context copyEx should count attempted copies");
    expect_true(stats.successfulCopies == 1, "render context copyEx should count successful copies");
    expect_true(stats.skippedCopies == 1, "render context copyEx should count skipped copies for null texture");
    expect_true(stats.failedCopies == 0, "render context copyEx should not count failed copies for valid smoke path");
}

void test_widget_reflective_callbacks_fail_closed_on_bad_config() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto panel = std::make_shared<WidgetCallbackPanel>();
    panel->setLayout(fixed_layout(0, 0, 200, 100));
    gui->pushChild(panel);

    auto widget = std::make_shared<CWidget>();
    widget->setLayout(fixed_layout(0, 0, 100, 80));
    panel->addChild(widget);

    auto rect = std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 100, 80});

    auto left_click = [&](const std::shared_ptr<CWidget> &w) {
        w->mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1);
        w->mouseEvent(gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 1, 1);
    };

    // Missing reflective method: render must no-op without crashing.
    widget->setRender("missingRenderCallback");
    widget->renderObject(gui, rect, 0);
    expect_true(panel->renders == 0, "missing widget render callback should no-op and fail closed");

    // Missing reflective method on a click action: must no-op without crashing.
    widget->setClick("missingClickCallback");
    left_click(widget);
    expect_true(panel->clicks == 0, "missing widget click callback should no-op and fail closed");

    // Empty names are skipped entirely before dispatch.
    widget->setRender("");
    widget->setClick("");
    widget->renderObject(gui, rect, 0);
    left_click(widget);
    expect_true(panel->renders == 0 && panel->clicks == 0, "empty widget callback names should be skipped");

    // The dispatch entry point / unregistered private names are not valid
    // reflective targets and must also fail closed rather than crash.
    widget->setRender("_privateRender");
    widget->setClick("invokeAction");
    widget->renderObject(gui, rect, 0);
    left_click(widget);
    expect_true(panel->renders == 0 && panel->clicks == 0,
                "private / meta widget callback names should fail closed and never dispatch");

    // Valid config-driven callbacks must keep working unchanged.
    widget->setRender("renderWidget");
    widget->renderObject(gui, rect, 0);
    expect_true(panel->renders == 1, "valid widget render callback should still fire");

    widget->setClick("clickWidget");
    left_click(widget);
    expect_true(panel->clicks == 1, "valid widget click callback should still fire");
}

void test_character_panel_sheet_lines_build_without_rendering_and_fail_closed() {
    auto panel = std::make_shared<CGameCharacterPanel>();
    auto player = std::make_shared<CPlayer>();
    player->setBaseStats(player_stats());
    player->setLevel(4);
    player->setGold(123);
    player->setRaceId("harpy");

    // No configured charSheet: the builder must fail closed with no rows.
    expect_true(panel->buildCharacterSheetLines(player).empty(),
                "character sheet builder should return no rows without a configured charSheet");

    auto charSheet = std::make_shared<CMapStringString>();
    charSheet->setValues({{"Gold", "getGold"},
                          {"Level", "getLevel"},
                          {"Race", "getRaceId"},
                          {"Broken", "notARealAccessor"},
                          {"Empty", ""}});
    panel->setCharSheet(charSheet);

    // The builder resolves the reflective accessors without any GUI/SDL rendering,
    // keeps the configured (map-ordered) rows, and skips bad or empty accessor
    // names fail-closed instead of throwing out of the panel.
    const auto lines = panel->buildCharacterSheetLines(player);
    expect_true(lines.size() == 3,
                "character sheet builder should keep resolvable rows and skip bad / empty accessors");
    if (lines.size() == 3) {
        expect_true(lines[0].first == "Gold" && lines[0].second == "123",
                    "character sheet builder should resolve numeric accessors without rendering");
        expect_true(lines[1].first == "Level" && lines[1].second == "4",
                    "character sheet builder should preserve the charSheet row ordering");
        expect_true(lines[2].first == "Race" && lines[2].second == "harpy",
                    "character sheet builder should fall back to string accessors for identity rows");
    }

    expect_true(panel->buildCharacterSheetLines(nullptr).empty(),
                "character sheet builder should return no rows for a missing player");
}

void test_character_panel_sheet_lines_render_race_and_class_labels() {
    auto panel = std::make_shared<CGameCharacterPanel>();
    auto charSheet = std::make_shared<CMapStringString>();
    charSheet->setValues({{"Gold", "getGold"}});
    panel->setCharSheet(charSheet);

    auto player = std::make_shared<CPlayer>();
    player->setBaseStats(player_stats());
    player->setGold(50);
    player->setTypeId("Harpy");
    player->setLabel("Harpy Windcaller");

    // The builder appends the archetype race / class identity rows after the
    // configured rows, resolving them from the human-readable *Label accessors
    // without any GUI/SDL rendering.
    const auto lines = panel->buildCharacterSheetLines(player);
    auto find_row = [&](const std::string &label) -> std::string {
        for (const auto &[key, value] : lines) {
            if (key == label) {
                return value;
            }
        }
        return "";
    };
    expect_true(lines.size() == 3, "builder should append the Race and Class rows after the configured rows");
    expect_true(!lines.empty() && lines.front().first == "Gold",
                "configured rows should still precede the appended identity rows");
    expect_true(find_row("Race") == "Harpy Windcaller",
                "character sheet builder should render the archetype race label");
    expect_true(find_row("Class") == "Harpy Windcaller",
                "character sheet builder should render the archetype class label");

    // Fail-closed: with no label / type id / name the identity labels resolve
    // empty and are skipped rather than emitting blank Race / Class rows.
    auto anonymous = std::make_shared<CPlayer>();
    anonymous->setBaseStats(player_stats());
    anonymous->setGold(0);
    const auto anonymousLines = panel->buildCharacterSheetLines(anonymous);
    bool hasIdentityRow = false;
    for (const auto &[key, value] : anonymousLines) {
        if (key == "Race" || key == "Class") {
            hasIdentityRow = true;
        }
    }
    expect_true(!hasIdentityRow, "character sheet builder should skip empty race / class labels fail-closed");
}

void test_dialog_panel_current_options_preserve_numeric_display_order() {
    auto make_option = [](int number, const std::string &text) {
        auto option = std::make_shared<CDialogOption>();
        option->setNumber(number);
        option->setText(text);
        return option;
    };

    auto state = std::make_shared<CDialogState>();
    state->setStateId("ENTRY");
    state->setOptions({
        make_option(2, "third"),
        make_option(0, "first"),
        make_option(1, "second"),
    });

    auto dialog = std::make_shared<CDialog>();
    dialog->setStates({state});

    auto panel = std::make_shared<CGameDialogPanel>();
    panel->setDialog(dialog);

    std::vector<std::string> displayedOptions;
    for (const auto &[index, option] : panel->getCurrentOptionsForTest()) {
        displayedOptions.push_back(std::to_string(index + 1) + ": " + option->getText());
    }

    expect_true(displayedOptions == std::vector<std::string>({"1: first", "2: second", "3: third"}),
                "dialog panel should display options from lowest dialog number to highest");
}

// Exercises the opt-in resize handle purely through geometry/state: no renderer, no real SDL input.
// A default panel must ignore the handle entirely; an opted-in panel must resize from a bottom-right
// handle drag and clamp within [min, parent] bounds without rewriting its serialized layout.
void test_panel_opt_in_resize_handle_drag_resizes_within_bounds() {
    auto parent = std::make_shared<CGameGraphicsObject>();
    parent->setLayout(fixed_layout(0, 0, 800, 600));

    auto panel = std::make_shared<CGamePanel>();
    auto layout = fixed_layout(0, 0, 200, 150);
    panel->setLayout(layout);
    parent->addChild(panel);

    // Default (not opted in): the corner is not a handle and a click there must not start a resize.
    expect_true(!panel->isResizable(), "panels should not be resizable by default (opt-in only)");
    expect_true(!panel->isInResizeHandle(195, 145),
                "a non-resizable panel must not treat its bottom-right corner as a handle");
    expect_true(!panel->beginResize(195, 145), "a non-resizable panel must not start a resize drag");
    expect_true(!panel->isResizing(), "a non-resizable panel must never enter the resizing state");
    // A left press on the corner is still consumed (modal) but changes no size.
    expect_true(panel->mouseEvent(nullptr, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 195, 145),
                "a modal panel still consumes clicks even when resizing is disabled");
    expect_rect(layout->getRect(panel), 0, 0, 200, 150,
                "a non-resizable panel must keep its size after a corner click");

    // Opt in and drive a handle drag directly (pointer coordinates are panel-local; top-left is fixed).
    panel->setResizable(true);
    expect_true(panel->isInResizeHandle(195, 145),
                "an opted-in panel's bottom-right corner should hit-test as the resize handle");
    expect_true(!panel->isInResizeHandle(10, 10), "the panel interior is not part of the resize handle");
    expect_true(panel->beginResize(195, 145), "an opted-in panel should start a resize from the handle");
    expect_true(panel->isResizing(), "beginResize should latch the resizing state");

    // Grab offset was (200-195, 150-145) = (5, 5); dragging to (255, 195) => 260x200.
    panel->updateResize(255, 195);
    expect_rect(layout->getRect(panel), 0, 0, 260, 200, "dragging the handle should grow the panel jump-free");
    expect_true(layout->getW() == "200" && layout->getH() == "150",
                "runtime resize must not rewrite the serialized layout width/height");

    // Shrinking past the minimum clamps to the floor (RESIZE_MIN_SIZE = 32).
    panel->updateResize(0, 0);
    expect_rect(layout->getRect(panel), 0, 0, 32, 32, "shrinking past the minimum should clamp to the size floor");

    // Growing past the parent clamps to the room inside the parent rectangle (800x600 from origin).
    panel->updateResize(5000, 5000);
    expect_rect(layout->getRect(panel), 0, 0, 800, 600, "growing past the parent should clamp to the parent bounds");

    panel->endResize();
    expect_true(!panel->isResizing(), "endResize should clear the resizing state");
    // After the drag ends, further motion must not keep resizing.
    panel->updateResize(100, 100);
    expect_rect(layout->getRect(panel), 0, 0, 800, 600, "motion after endResize must not change the size");

    // A configured layout minimum raises the size floor above RESIZE_MIN_SIZE.
    layout->setMinW(120);
    layout->setMinH(90);
    panel->beginResize(int(layout->getRect(panel)->w) - 1, int(layout->getRect(panel)->h) - 1);
    panel->updateResize(0, 0);
    expect_rect(layout->getRect(panel), 0, 0, 120, 90, "the layout minimum should raise the resize floor");
    panel->endResize();
}

// Drives the resize handle through real CGui event dispatch with a child covering the whole panel
// (list views consume left button-downs even on empty cells, so before the panel-level interception
// a covering child would swallow the grab). Also proves the resize state cannot go stale: a release
// over the child still ends the resize, and a resize whose pointer capture ends externally is
// dropped by the next motion instead of resizing with no button held.
void test_panel_resize_handle_press_beats_covering_child_and_release_ends_capture() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    gui->setLayout(fixed_layout(0, 0, 800, 600));

    auto panel = std::make_shared<CGamePanel>();
    auto layout = fixed_layout(0, 0, 200, 150);
    panel->setLayout(layout);
    panel->setResizable(true);
    gui->pushChild(panel);

    auto child = std::make_shared<MouseEventRecorder>();
    child->setLayout(fixed_layout(0, 0, 200, 150)); // covers the panel, including the handle corner
    panel->pushChild(child);

    // Press on the handle must start the resize instead of being consumed by the covering child.
    SDL_Event down{};
    down.type = SDL_MOUSEBUTTONDOWN;
    down.button.button = SDL_BUTTON_LEFT;
    down.button.x = 195;
    down.button.y = 145;
    expect_true(gui->event(&down), "a handle press should be handled by the panel");
    expect_true(panel->isResizing(), "a handle press must start the resize even under a covering child");
    expect_true(child->button_count == 0, "a handle press must not reach the covering child");
    expect_true(gui->isPointerCapturedBy(panel), "a handle press should capture the pointer for the panel");

    // Captured motion resizes the panel (grab offset was 5,5 so (255,195) => 260x200).
    SDL_Event motion{};
    motion.type = SDL_MOUSEMOTION;
    motion.motion.x = 255;
    motion.motion.y = 195;
    gui->event(&motion);
    expect_rect(layout->getRect(panel), 0, 0, 260, 200, "captured motion should resize the panel");
    expect_true(child->motion_count == 0, "captured resize motion must not reach the covering child");

    // Releasing inside the panel over the covering child must still end the resize and the capture.
    SDL_Event up{};
    up.type = SDL_MOUSEBUTTONUP;
    up.button.button = SDL_BUTTON_LEFT;
    up.button.x = 100;
    up.button.y = 100;
    gui->event(&up);
    expect_true(!panel->isResizing(), "a release over a covering child must still end the resize");
    expect_true(!gui->hasPointerCapture(), "a release over a covering child must still release the capture");
    expect_rect(layout->getRect(panel), 0, 0, 260, 200, "the release must keep the resized rectangle");

    // If the capture ends without the panel seeing the release, the next motion drops the stale
    // resize instead of applying it.
    down.button.x = 255;
    down.button.y = 195;
    gui->event(&down);
    expect_true(panel->isResizing(), "a second handle press should start another resize");
    gui->releasePointerCapture();
    motion.motion.x = 230; // inside the panel, outside the covering child
    motion.motion.y = 180;
    gui->event(&motion);
    expect_true(!panel->isResizing(), "losing the pointer capture must clear the resize state");
    expect_rect(layout->getRect(panel), 0, 0, 260, 200, "a stale resize must not change the panel size");
}

// A centered layout recomputes x/y from the current size, so runtime W/H alone would move the
// panel's origin (and its panel-local pointer space) on every drag update. The resize must pin the
// top-left corner for the whole drag and keep it pinned after the drag ends.
void test_panel_resize_centered_layout_keeps_origin_pinned() {
    auto parent = std::make_shared<CGameGraphicsObject>();
    parent->setLayout(fixed_layout(0, 0, 800, 600));

    auto panel = std::make_shared<CGamePanel>();
    auto layout = std::make_shared<CCenteredLayout>();
    layout->setW("200");
    layout->setH("150");
    panel->setLayout(layout);
    panel->setResizable(true);
    parent->addChild(panel);

    expect_rect(layout->getRect(panel), 300, 225, 200, 150, "the centered panel should start centered");

    expect_true(panel->beginResize(195, 145), "the centered panel should start a resize from its handle");
    panel->updateResize(255, 195);
    expect_rect(layout->getRect(panel), 300, 225, 260, 200,
                "growing a centered panel must keep its top-left corner pinned");
    panel->updateResize(155, 120);
    expect_rect(layout->getRect(panel), 300, 225, 160, 125,
                "shrinking a centered panel must keep its top-left corner pinned");
    panel->endResize();
    expect_rect(layout->getRect(panel), 300, 225, 160, 125,
                "the origin must stay pinned after the drag ends instead of re-centering");
    expect_true(layout->getW() == "200" && layout->getH() == "150",
                "pinning the origin must not rewrite the serialized centered layout");
}

// Session-only geometry persistence: finishing a resize records the panel's runtime geometry in the
// CGui session store (keyed by the panel's stable typeId), and a NEW panel instance with the same
// identity gets it re-applied when it joins the GUI. Serialized layout values stay untouched, other
// identities are unaffected, non-resizable panels never apply, and identity-less panels never record.
void test_panel_session_geometry_restores_reopened_panel_same_identity_only() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    gui->setLayout(fixed_layout(0, 0, 800, 600));

    auto panel = std::make_shared<CGamePanel>();
    panel->setTypeId("questPanel");
    panel->setResizable(true);
    auto layout = fixed_layout(0, 0, 200, 150);
    panel->setLayout(layout);
    gui->pushChild(panel);
    expect_rect(layout->getRect(panel), 0, 0, 200, 150, "attaching with an empty store must change nothing");

    // Resize to 260x200 (grab offset 5,5) and finish the drag: endResize records the geometry.
    panel->beginResize(195, 145);
    panel->updateResize(255, 195);
    panel->endResize();
    expect_rect(layout->getRect(panel), 0, 0, 260, 200, "the drag should resize the live panel");

    // Close the panel and reopen a brand-new instance with the same identity: geometry is restored.
    panel->close();
    expect_true(gui->findChild(panel) == nullptr, "close should detach the panel from the gui");
    auto reopened = std::make_shared<CGamePanel>();
    reopened->setTypeId("questPanel");
    reopened->setResizable(true);
    auto reopenedLayout = fixed_layout(0, 0, 200, 150);
    reopened->setLayout(reopenedLayout);
    gui->pushChild(reopened);
    expect_rect(reopenedLayout->getRect(reopened), 0, 0, 260, 200,
                "a reopened panel with the same identity should restore its session geometry");
    expect_true(reopenedLayout->getX() == "0" && reopenedLayout->getY() == "0" && reopenedLayout->getW() == "200" &&
                    reopenedLayout->getH() == "150",
                "restoring session geometry must not rewrite any serialized layout value");
    reopened->close();

    // A different identity must not inherit the recorded geometry.
    auto other = std::make_shared<CGamePanel>();
    other->setTypeId("inventoryPanel");
    other->setResizable(true);
    auto otherLayout = fixed_layout(0, 0, 200, 150);
    other->setLayout(otherLayout);
    gui->pushChild(other);
    expect_rect(otherLayout->getRect(other), 0, 0, 200, 150,
                "a different panel identity must not receive another panel's geometry");
    other->close();

    // A panel without the resize opt-in must never have geometry applied, even for a known identity.
    auto locked = std::make_shared<CGamePanel>();
    locked->setTypeId("questPanel");
    auto lockedLayout = fixed_layout(0, 0, 200, 150);
    locked->setLayout(lockedLayout);
    gui->pushChild(locked);
    expect_rect(lockedLayout->getRect(locked), 0, 0, 200, 150,
                "a non-resizable panel must not have session geometry applied");
    locked->close();

    // A panel with no stable identity records nothing when resized.
    auto anonymous = std::make_shared<CGamePanel>();
    anonymous->setResizable(true);
    anonymous->setLayout(fixed_layout(0, 0, 200, 150));
    gui->pushChild(anonymous);
    anonymous->beginResize(195, 145);
    anonymous->updateResize(255, 195);
    anonymous->endResize();
    anonymous->close();
    expect_true(!gui->getSessionPanelGeometry(""), "a panel without a typeId must not record session geometry");
}

// Re-applied session geometry must clamp against the CURRENT parent bounds: if the window shrank
// (window scaling rewrites the gui layout's runtime size) between the resize and the reopen, the
// restored panel must land fully inside the new bounds instead of keeping an out-of-range rectangle.
void test_panel_session_geometry_reapply_clamps_to_new_parent_bounds() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    gui->setLayout(fixed_layout(0, 0, 800, 600));

    // A centered panel resized once records its pinned origin (300, 225) with the new 260x200 size.
    auto panel = std::make_shared<CGamePanel>();
    panel->setTypeId("questPanel");
    panel->setResizable(true);
    auto layout = std::make_shared<CCenteredLayout>();
    layout->setW("200");
    layout->setH("150");
    panel->setLayout(layout);
    gui->pushChild(panel);
    panel->beginResize(195, 145);
    panel->updateResize(255, 195);
    panel->endResize();
    expect_rect(layout->getRect(panel), 300, 225, 260, 200, "the resized centered panel keeps its pinned origin");
    panel->close();

    // Shrink the gui (the same runtime-override mechanism window scaling uses) and reopen the panel:
    // the origin (300, 225) still fits, but the size clamps to the room left inside 400x300.
    gui->setWidth(400);
    gui->setHeight(300);
    auto reopened = std::make_shared<CGamePanel>();
    reopened->setTypeId("questPanel");
    reopened->setResizable(true);
    auto reopenedLayout = std::make_shared<CCenteredLayout>();
    reopenedLayout->setW("200");
    reopenedLayout->setH("150");
    reopened->setLayout(reopenedLayout);
    gui->pushChild(reopened);
    expect_rect(reopenedLayout->getRect(reopened), 300, 225, 100, 75,
                "restored geometry must clamp its size to the room left in the smaller parent");
    reopened->close();

    // Shrink further so even the recorded origin no longer fits: it clamps to leave the minimum
    // 32x32 of room, and the size clamps to that remaining room.
    gui->setWidth(320);
    gui->setHeight(240);
    auto cramped = std::make_shared<CGamePanel>();
    cramped->setTypeId("questPanel");
    cramped->setResizable(true);
    auto crampedLayout = std::make_shared<CCenteredLayout>();
    crampedLayout->setW("200");
    crampedLayout->setH("150");
    cramped->setLayout(crampedLayout);
    gui->pushChild(cramped);
    expect_rect(crampedLayout->getRect(cramped), 288, 208, 32, 32,
                "a restored origin outside the new parent must clamp back inside with minimum room");
    expect_true(crampedLayout->getW() == "200" && crampedLayout->getH() == "150",
                "clamped re-apply must not rewrite the serialized centered layout");
}

// The geometry store is session-only: it lives on the CGui instance (one per game session) and is
// cleared by CGui::shutdown(), the session boundary CGameContext drives when a game session ends.
// A fresh CGui starts empty, so user-adjusted geometry can never leak across sessions (and, being a
// plain non-reflective member, it can never be serialized to disk at all).
void test_panel_session_geometry_clears_at_session_shutdown() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    gui->setLayout(fixed_layout(0, 0, 800, 600));

    auto panel = std::make_shared<CGamePanel>();
    panel->setTypeId("questPanel");
    panel->setResizable(true);
    panel->setLayout(fixed_layout(0, 0, 200, 150));
    gui->pushChild(panel);
    panel->beginResize(195, 145);
    panel->updateResize(255, 195);
    panel->endResize();

    auto stored = gui->getSessionPanelGeometry("questPanel");
    expect_true(stored.has_value(), "finishing a resize should record geometry in the session store");
    expect_true(stored && stored->x == 0 && stored->y == 0 && stored->w == 260 && stored->h == 200,
                "the recorded geometry should match the resized rectangle");

    gui->shutdown();
    expect_true(!gui->getSessionPanelGeometry("questPanel"),
                "shutdown (the session boundary) must clear the session geometry store");

    auto nextSession = std::make_shared<CGui>();
    expect_true(!nextSession->getSessionPanelGeometry("questPanel"),
                "a new session's GUI must not inherit geometry from a previous session");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_layout_runtime_overrides_preserve_serialized_percentage_layouts();
    test_layout_fractional_percentages_resolve_exact_design_pixels();
    test_layout_minimum_size_floors_percentage_panels();
    test_widget_ignores_unarmed_non_left_clicks();
    test_widget_reflective_callbacks_fail_closed_on_bad_config();
    test_character_panel_sheet_lines_build_without_rendering_and_fail_closed();
    test_character_panel_sheet_lines_render_race_and_class_labels();
    test_dialog_panel_current_options_preserve_numeric_display_order();
    test_panel_opt_in_resize_handle_drag_resizes_within_bounds();
    test_panel_resize_handle_press_beats_covering_child_and_release_ends_capture();
    test_panel_resize_centered_layout_keeps_origin_pinned();
    test_panel_session_geometry_restores_reopened_panel_same_identity_only();
    test_panel_session_geometry_reapply_clamps_to_new_parent_bounds();
    test_panel_session_geometry_clears_at_session_shutdown();
    test_list_view_refreshes_from_generic_property_notifications();
    test_list_view_coalesces_property_refreshes_per_event_loop_tick();
    test_list_view_skips_queued_property_refresh_after_detach();
    test_list_view_refresh_event_compatibility();
    test_list_view_property_subscriptions_follow_resolved_target_and_null();
    test_list_view_refresh_property_collision_fails_closed();
    test_quest_panel_rebuilds_text_only_when_quest_data_changes();
    test_quest_panel_resubscribes_when_quest_source_changes();
    test_quest_panel_rebuilds_when_quest_state_properties_change();
    test_reactive_list_views_refresh_counts_match_model_changes_exactly();
    test_quest_panel_refresh_count_coalesces_rapid_invalidations();
    test_inventory_double_select_uses_selected_item_and_clears_selection();
    test_inventory_right_click_uses_usable_item_once_and_consumes_it();
    test_inventory_right_click_full_resource_item_not_consumed();
    test_inventory_right_click_quest_item_is_protected();
    test_inventory_right_click_invalid_and_empty_are_safe();
    test_inventory_left_click_drag_still_starts_for_owned_item();
    test_fight_panel_right_click_item_use_still_works();
    test_fight_panel_enemy_selection_uses_exact_instance();
    test_gui_window_is_resizable_and_guard_paths_fail_closed();
    test_list_view_drag_callbacks_validate_and_drop_without_click_fallback();
    test_list_view_drag_callbacks_cancel_and_preserve_unmoved_clicks();
    test_list_view_legacy_click_callback_still_fires_without_drag_callbacks();
    test_list_view_non_draggable_does_click_only_press_motion_release();
    test_list_view_non_draggable_repeated_click_preserves_first_select_second_confirm();
    test_list_view_draggable_default_still_drags_after_non_draggable_change();
    test_list_view_non_draggable_panel_removal_during_input_leaves_no_session_or_capture();
    test_list_view_below_threshold_motion_stays_a_click_no_proxy_no_drop();
    test_list_view_exact_boundary_is_a_click_above_boundary_is_a_drag();
    test_list_view_negative_and_diagonal_motion_follow_the_rule();
    test_list_view_above_threshold_drop_is_accepted_below_threshold_is_not();
    test_list_view_moved_drop_without_target_callbacks_cancels_instead_of_clicking();
    test_inventory_drag_drop_equips_exact_dragged_item_and_unequips_it_back();
    test_inventory_drag_drop_incompatible_slot_rejects_without_ownership_change();
    test_inventory_drag_drop_quest_item_is_protected();
    test_inventory_drag_drop_same_list_release_is_a_no_op();
    test_inventory_drag_drop_cancel_outside_targets_keeps_ownership();
    test_list_view_below_threshold_candidate_panel_removal_leaves_no_session();
    test_list_view_active_drag_panel_removal_leaves_no_session();
    test_panel_event_callbacks_stop_after_close();
    test_gui_routes_mouse_motion_to_target_child();
    test_loader_gui_sessions_shutdown_stale_callbacks();
    test_gui_routes_mouse_button_up_without_drag_to_target_child();
    test_gui_routes_mouse_wheel_to_target_child();
    test_gui_routes_window_leave_as_mouse_cancel();
    test_gui_pointer_capture_routes_drag_release_and_clears_session();
    test_gui_pointer_capture_does_not_duplicate_same_source_release();
    test_gui_pointer_capture_clears_when_captured_widget_is_removed();
    test_render_traversal_stops_after_detach();
    test_texture_cache_without_gui_fails_closed();
    test_render_context_rejects_null_texture_and_copies_valid_texture();
    test_render_context_copy_ex_rotates_and_tracks_stats();
    test_minimap_bounds_extreme_metadata_fails_closed();
    test_minimap_bounds_overflow_prone_extents_fail_closed();
    test_minimap_bounds_sparse_coordinates_fail_closed();
    test_minimap_bounds_negative_sparse_coordinates_render();
    test_minimap_bounds_normal_map_renders();
    test_minimap_consumes_inside_pointer_events_and_preserves_outside_and_wheel();

    return finish_tests();
}
