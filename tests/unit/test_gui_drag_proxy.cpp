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
#include "core/CSerialization.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/object/CGameGraphicsObject.h"
#include "object/CGameObject.h"
#include "test_harness.h"

#include <pybind11/embed.h>

namespace {

class MouseEventRecorder : public CGameGraphicsObject {
  public:
    bool mouseEvent(std::shared_ptr<CGui>, SDL_EventType, int, int, int) override { return true; }
};

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

std::shared_ptr<MouseEventRecorder> attach_mouse_recorder(const std::shared_ptr<CGui> &gui) {
    auto recorder = std::make_shared<MouseEventRecorder>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(10, 20, 100, 80);
    recorder->setLayout(layout);
    gui->pushChild(recorder);
    return recorder;
}

std::shared_ptr<DropTargetRecorder> attach_drop_target_recorder(const std::shared_ptr<CGui> &gui) {
    auto recorder = std::make_shared<DropTargetRecorder>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(200, 20, 100, 80);
    recorder->setLayout(layout);
    gui->pushChild(recorder);
    return recorder;
}

std::shared_ptr<json> serialize_gui_tree(const std::shared_ptr<CGui> &gui) {
    return CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(gui);
}

std::string serialized_layout_value(const json &node, const std::string &key) {
    if (!node.contains("properties")) {
        return "";
    }
    const auto &properties = node["properties"];
    if (!properties.contains("layout") || !properties["layout"].contains("properties")) {
        return "";
    }
    const auto &layout = properties["layout"]["properties"];
    return layout.contains(key) && layout[key].is_string() ? layout[key].get<std::string>() : "";
}

const json *find_serialized_drag_proxy(const std::shared_ptr<json> &gui_tree, const std::string &x = "",
                                       const std::string &y = "") {
    if (!gui_tree || !gui_tree->contains("properties")) {
        return nullptr;
    }
    const auto &properties = (*gui_tree)["properties"];
    if (!properties.contains("children") || !properties["children"].is_array()) {
        return nullptr;
    }

    const json *proxy = nullptr;
    for (const auto &child : properties["children"]) {
        if (serialized_layout_value(child, "w") != "50" || serialized_layout_value(child, "h") != "50") {
            continue;
        }
        if ((!x.empty() && serialized_layout_value(child, "x") != x) ||
            (!y.empty() && serialized_layout_value(child, "y") != y)) {
            continue;
        }
        if (proxy) {
            return nullptr;
        }
        proxy = &child;
    }
    return proxy;
}

std::shared_ptr<CGameObject> drag_payload(const std::shared_ptr<CGame> &game) {
    auto payload = std::make_shared<CGameObject>();
    payload->setGame(game);
    payload->setAnimation("images/item");
    return payload;
}

std::shared_ptr<CGame> create_gui_game(const std::shared_ptr<CGui> &gui) {
    type_registration::registerGuiTypes();
    type_registration::registerGuiAnimationTypes();

    auto game = std::make_shared<CGame>();
    game->setGui(gui);
    gui->setGame(game);
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    return game;
}

void test_gui_drag_session_serializes_proxy_child_and_removes_it_after_drop_or_cancel() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);

    auto source = attach_mouse_recorder(gui);
    auto target = attach_drop_target_recorder(gui);

    gui->startDragSession(source, drag_payload(game), 4, 40, 50);
    // A drag start is only a *candidate*: below-threshold motion (here zero motion at
    // the start point) must NOT attach a proxy widget, because the interaction is still
    // a potential click.
    auto candidate_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(candidate_tree) == nullptr,
                "candidate drag (no threshold-crossing motion) should not attach a proxy child");

    // Motion that stays within the Chebyshev threshold (<= 4 px on both axes) keeps the
    // session a candidate and still shows no proxy.
    gui->updateDragSession(44, 54);
    auto below_threshold_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(below_threshold_tree) == nullptr,
                "below-threshold motion should not attach a drag proxy child");

    // Crossing the threshold (Chebyshev distance > 4) promotes the session to an active
    // drag and attaches the proxy centered on the current pointer coordinates.
    gui->updateDragSession(90, 110);
    auto moved_tree = serialize_gui_tree(gui);
    const json *moved_proxy = find_serialized_drag_proxy(moved_tree, "65", "85");
    expect_true(moved_proxy != nullptr, "crossing the movement threshold should attach one serialized proxy child");
    if (moved_proxy) {
        expect_true(serialized_layout_value(*moved_proxy, "x") == "65" &&
                        serialized_layout_value(*moved_proxy, "y") == "85",
                    "drag proxy serialized layout should follow pointer coordinates");
        expect_true(serialized_layout_value(*moved_proxy, "w") == "50" &&
                        serialized_layout_value(*moved_proxy, "h") == "50",
                    "drag proxy should use the GUI tile size for its serialized layout");
    }

    gui->acceptDragSession(target);
    auto accepted_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(accepted_tree) == nullptr,
                "accepted drag should remove the serialized proxy child");
    gui->clearDragSession();

    gui->startDragSession(source, drag_payload(game), 5, 60, 70);
    // Fresh candidate session: no proxy until motion crosses the threshold.
    auto restarted_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(restarted_tree) == nullptr,
                "a fresh candidate drag should not attach a proxy child before threshold-crossing motion");
    gui->updateDragSession(120, 130);
    auto restarted_active_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(restarted_active_tree, "95", "105") != nullptr,
                "crossing the threshold on the new drag should attach a fresh serialized proxy child");
    gui->cancelDragSession();
    auto canceled_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(canceled_tree) == nullptr,
                "canceled drag should remove the serialized proxy child");
    gui->clearDragSession();
}

// Drives updateDragSession from a fixed start point to (start + dx, start + dy) and
// reports whether the session became an active drag. A fresh session is started each
// time so latching from a previous sample does not leak in.
bool drag_active_after_offset(const std::shared_ptr<CGui> &gui, const std::shared_ptr<CGameGraphicsObject> &source,
                              const std::shared_ptr<CGameObject> &payload, int start_x, int start_y, int dx, int dy) {
    gui->startDragSession(source, payload, 0, start_x, start_y);
    gui->updateDragSession(start_x + dx, start_y + dy);
    const bool active = gui->getDragSession() && gui->getDragSession()->dragActive;
    gui->clearDragSession();
    return active;
}

void test_gui_drag_movement_threshold_is_deterministic_chebyshev_boundary() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto source = attach_mouse_recorder(gui);
    auto payload = drag_payload(game);

    const int start_x = 100;
    const int start_y = 100;

    // Zero movement stays a click.
    expect_true(!drag_active_after_offset(gui, source, payload, start_x, start_y, 0, 0),
                "zero movement must not promote the session to a drag");

    // Below threshold on each single axis stays a click (positive and negative).
    expect_true(!drag_active_after_offset(gui, source, payload, start_x, start_y, 1, 0),
                "1px x motion must stay a click");
    expect_true(!drag_active_after_offset(gui, source, payload, start_x, start_y, 0, 3),
                "3px y motion must stay a click");
    expect_true(!drag_active_after_offset(gui, source, payload, start_x, start_y, -4, 0),
                "-4px x motion (exact boundary) must stay a click");
    expect_true(!drag_active_after_offset(gui, source, payload, start_x, start_y, 0, -4),
                "-4px y motion (exact boundary) must stay a click");

    // Exact boundary (Chebyshev distance == threshold) is EXCLUSIVE -> still a click,
    // including the diagonal 4/4 case.
    expect_true(!drag_active_after_offset(gui, source, payload, start_x, start_y, 4, 4),
                "diagonal 4/4 motion at the exact boundary must stay a click (exclusive boundary)");

    // Above threshold on either axis becomes a drag (positive, negative, diagonal).
    expect_true(drag_active_after_offset(gui, source, payload, start_x, start_y, 5, 0),
                "5px x motion must become a drag");
    expect_true(drag_active_after_offset(gui, source, payload, start_x, start_y, 0, 5),
                "5px y motion must become a drag");
    expect_true(drag_active_after_offset(gui, source, payload, start_x, start_y, -5, 0),
                "-5px x motion must become a drag (negative axis)");
    expect_true(drag_active_after_offset(gui, source, payload, start_x, start_y, 0, -5),
                "-5px y motion must become a drag (negative axis)");
    expect_true(drag_active_after_offset(gui, source, payload, start_x, start_y, 5, 5),
                "diagonal 5/5 motion must become a drag");
    expect_true(drag_active_after_offset(gui, source, payload, start_x, start_y, -6, 3),
                "diagonal motion is governed by the larger axis (|-6| > 4)");
}

void test_gui_drag_active_latches_and_survives_below_threshold_return() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto gui = std::make_shared<CGui>();
    auto game = create_gui_game(gui);
    auto source = attach_mouse_recorder(gui);

    gui->startDragSession(source, drag_payload(game), 0, 100, 100);
    expect_true(gui->getDragSession() && !gui->getDragSession()->dragActive,
                "a fresh session starts as a candidate (not an active drag)");

    gui->updateDragSession(110, 100); // dx = 10 -> crosses threshold
    expect_true(gui->getDragSession() && gui->getDragSession()->dragActive,
                "crossing the threshold must latch the session as an active drag");

    gui->updateDragSession(100, 100); // back to start (below threshold again)
    expect_true(gui->getDragSession() && gui->getDragSession()->dragActive,
                "an active drag must not demote back to a click when motion returns below the threshold");
    gui->clearDragSession();
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_gui_drag_session_serializes_proxy_child_and_removes_it_after_drop_or_cancel();
    test_gui_drag_movement_threshold_is_deterministic_chebyshev_boundary();
    test_gui_drag_active_latches_and_survives_below_threshold_return();

    return finish_tests();
}
