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
    auto initial_tree = serialize_gui_tree(gui);
    const json *initial_proxy = find_serialized_drag_proxy(initial_tree, "15", "25");
    expect_true(initial_proxy != nullptr, "drag start should attach a serialized proxy child");
    if (initial_proxy) {
        expect_true(serialized_layout_value(*initial_proxy, "x") == "15" &&
                        serialized_layout_value(*initial_proxy, "y") == "25",
                    "drag proxy should be centered on the start pointer coordinates");
        expect_true(serialized_layout_value(*initial_proxy, "w") == "50" &&
                        serialized_layout_value(*initial_proxy, "h") == "50",
                    "drag proxy should use the GUI tile size for its serialized layout");
    }

    gui->updateDragSession(90, 110);
    auto moved_tree = serialize_gui_tree(gui);
    const json *moved_proxy = find_serialized_drag_proxy(moved_tree, "65", "85");
    expect_true(moved_proxy != nullptr, "drag update should keep one serialized proxy child");
    if (moved_proxy) {
        expect_true(serialized_layout_value(*moved_proxy, "x") == "65" &&
                        serialized_layout_value(*moved_proxy, "y") == "85",
                    "drag proxy serialized layout should follow pointer coordinates");
    }

    gui->acceptDragSession(target);
    auto accepted_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(accepted_tree) == nullptr,
                "accepted drag should remove the serialized proxy child");
    gui->clearDragSession();

    gui->startDragSession(source, drag_payload(game), 5, 60, 70);
    auto restarted_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(restarted_tree, "35", "45") != nullptr,
                "new drag should attach a fresh serialized proxy child");
    gui->cancelDragSession();
    auto canceled_tree = serialize_gui_tree(gui);
    expect_true(find_serialized_drag_proxy(canceled_tree) == nullptr,
                "canceled drag should remove the serialized proxy child");
    gui->clearDragSession();
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_gui_drag_session_serializes_proxy_child_and_removes_it_after_drop_or_cancel();

    return finish_tests();
}
