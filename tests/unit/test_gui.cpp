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
#include "core/CMap.h"
#include "core/CStats.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextureCache.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CListView.h"
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
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);
    return game;
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
    create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    list->setResolvedRefreshTarget(refresh_target);
    list->setRefreshOnPropertyChanged(true);
    gui->pushChild(list);

    list->initialize();
    drain_event_loop();
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
    create_gui_game(gui);
    auto refresh_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    list->setResolvedRefreshTarget(refresh_target);
    list->setRefreshEvent("legacyRefresh");
    gui->pushChild(list);

    list->initialize();
    drain_event_loop();
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
    create_gui_game(gui);
    auto first_target = std::make_shared<CGameObject>();
    auto second_target = std::make_shared<CGameObject>();
    auto list = std::make_shared<RefreshCountingListView>();
    list->setResolvedRefreshTarget(first_target);
    list->setRefreshProperties({"label"});
    gui->pushChild(list);

    list->initialize();
    drain_event_loop();
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
    potion->addTag(CTag::Heal);
    player->addItem(potion);

    const auto inventory_size = player->getItems().size();
    panel->inventoryCallback(gui, 0, potion);
    expect_true(panel->inventorySelect(gui, 0, potion), "first inventory click should select a usable item");

    panel->inventoryCallback(gui, 0, potion);
    expect_true(player->getItems().size() == inventory_size,
                "full-health potion double-select should call useItem without consuming the item");
    expect_true(!panel->inventorySelect(gui, 0, potion), "second inventory click should clear the used selection");
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

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_widget_ignores_unarmed_non_left_clicks();
    test_list_view_refreshes_from_generic_property_notifications();
    test_list_view_refresh_event_compatibility();
    test_list_view_property_subscriptions_follow_resolved_target_and_null();
    test_inventory_double_select_uses_selected_item_and_clears_selection();
    test_panel_event_callbacks_stop_after_close();
    test_gui_routes_mouse_motion_to_target_child();
    test_gui_routes_mouse_button_up_without_drag_to_target_child();
    test_gui_routes_mouse_wheel_to_target_child();
    test_gui_routes_window_leave_as_mouse_cancel();
    test_gui_pointer_capture_routes_drag_release_and_clears_session();
    test_gui_pointer_capture_does_not_duplicate_same_source_release();
    test_gui_pointer_capture_clears_when_captured_widget_is_removed();
    test_render_traversal_stops_after_detach();
    test_texture_cache_without_gui_fails_closed();

    return finish_tests();
}
