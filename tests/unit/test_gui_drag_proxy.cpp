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
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/object/CGameGraphicsObject.h"
#include "object/CGameObject.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <limits>
#include <vector>

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

std::vector<std::shared_ptr<CGameGraphicsObject>> drag_proxy_children(const std::shared_ptr<CGui> &gui) {
    std::vector<std::shared_ptr<CGameGraphicsObject>> proxies;
    if (!gui) {
        return proxies;
    }
    for (const auto &child : gui->getChildren()) {
        if (child && child->getPriority() == std::numeric_limits<int>::max()) {
            proxies.push_back(child);
        }
    }
    return proxies;
}

std::shared_ptr<CGameGraphicsObject> expect_one_drag_proxy_child(const std::shared_ptr<CGui> &gui,
                                                                 const char *message) {
    auto proxies = drag_proxy_children(gui);
    expect_true(proxies.size() == 1, message);
    return proxies.empty() ? nullptr : proxies.front();
}

void expect_no_drag_proxy_child(const std::shared_ptr<CGui> &gui, const char *message) {
    expect_true(drag_proxy_children(gui).empty(), message);
}

void expect_proxy_rect(const std::shared_ptr<CGameGraphicsObject> &proxy, int x, int y, int w, int h,
                       const char *message) {
    if (!proxy || !proxy->getLayout()) {
        expect_true(false, message);
        return;
    }
    auto rect = proxy->getLayout()->getRect(proxy);
    expect_true(rect && rect->x == x && rect->y == y && rect->w == w && rect->h == h, message);
}

std::shared_ptr<CGameObject> drag_payload(const std::shared_ptr<CGame> &game) {
    auto payload = std::make_shared<CGameObject>();
    payload->setGame(game);
    payload->setAnimation("images/item");
    return payload;
}

void test_gui_drag_session_attaches_proxy_child_and_removes_it_after_drop_or_cancel() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = std::make_shared<CGame>();
    auto gui = std::make_shared<CGui>();
    game->setGui(gui);
    gui->setGame(game);

    auto source = attach_mouse_recorder(gui);
    auto target = attach_drop_target_recorder(gui);

    gui->startDragSession(source, drag_payload(game), 4, 40, 50);
    auto initial_proxy = expect_one_drag_proxy_child(gui, "drag start should attach one high-priority proxy child");
    expect_proxy_rect(initial_proxy, 15, 25, 50, 50, "drag proxy should be centered on the start pointer coordinates");

    gui->updateDragSession(90, 110);
    auto moved_proxy = expect_one_drag_proxy_child(gui, "drag update should keep one high-priority proxy child");
    expect_true(moved_proxy == initial_proxy, "drag update should reuse the existing proxy child");
    expect_proxy_rect(moved_proxy, 65, 85, 50, 50, "drag proxy layout should follow pointer coordinates");

    gui->acceptDragSession(target);
    expect_no_drag_proxy_child(gui, "accepted drag should remove the proxy child");
    gui->clearDragSession();

    gui->startDragSession(source, drag_payload(game), 5, 60, 70);
    expect_one_drag_proxy_child(gui, "new drag should attach a fresh proxy child");
    gui->cancelDragSession();
    expect_no_drag_proxy_child(gui, "canceled drag should remove the proxy child");
    gui->clearDragSession();
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_gui_drag_session_attaches_proxy_child_and_removes_it_after_drop_or_cancel();

    return finish_tests();
}
