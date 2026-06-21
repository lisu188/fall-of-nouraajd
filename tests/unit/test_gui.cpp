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
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CRenderContext.h"
#include "gui/CSdlResources.h"
#include "gui/CTextureCache.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CListView.h"
#include "handler/CObjectHandler.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "test_harness.h"

#include <pybind11/embed.h>

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
    CTypes::register_type_metadata<DragCallbackPanel, CGamePanel, CGameGraphicsObject, CGameObject>();

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
    first_target->setStringProperty("label", "handoff");
    drain_event_loop();
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
    second_target->setStringProperty("label", "to-null");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 4,
                "subscription refresh should handle the refresh script resolving to null");

    second_target->setStringProperty("label", "after-null");
    drain_event_loop();
    expect_true(list->refresh_count == after_initial_refresh + 4,
                "previous refresh target should be disconnected when the refresh script resolves to null");
}

std::shared_ptr<CStats> player_stats() {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    return stats;
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

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_layout_runtime_overrides_preserve_serialized_percentage_layouts();
    test_widget_ignores_unarmed_non_left_clicks();
    test_list_view_refreshes_from_generic_property_notifications();
    test_list_view_refresh_event_compatibility();
    test_list_view_property_subscriptions_follow_resolved_target_and_null();
    test_inventory_double_select_uses_selected_item_and_clears_selection();
    test_fight_panel_enemy_selection_uses_exact_instance();
    test_gui_window_is_resizable_and_guard_paths_fail_closed();
    test_list_view_drag_callbacks_validate_and_drop_without_click_fallback();
    test_list_view_drag_callbacks_cancel_and_preserve_unmoved_clicks();
    test_list_view_legacy_click_callback_still_fires_without_drag_callbacks();
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

    return finish_tests();
}
