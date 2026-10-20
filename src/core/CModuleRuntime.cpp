/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "bindings/CModuleBindings.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CRuntimeBridge.h"

namespace py = pybind11;

namespace nouraajd::bindings {
namespace {
vstd::task<void> runPostedScriptFlow(std::weak_ptr<CGuiHandler> gui, std::unique_ptr<CScriptFlow> flow) {
    try {
        co_await vstd::post(CRuntimeBridge::event_loop_instance());
        if (auto owner = gui.lock()) {
            co_await owner->runScriptFlowAsync(std::move(flow));
        }
    } catch (const vstd::task_cancelled &) {
        throw;
    } catch (const vstd::scheduler_rejected &) {
        throw;
    } catch (const std::exception &error) {
        vstd::logger::error("Session script callback failed: " + std::string(error.what()));
    }
}
} // namespace

int randint(int i, int j) { return vstd::rand(i, j); }

void seedModuleRandomForTests(std::uint32_t seed) {
    CRuntimeBridge::seedRandomForTests(seed);
    // Linux extensions keep a local RNG; embedded interpreters use the executable's stream.
    vstd::rng().seed(seed);
}

void postScriptFlow(const std::shared_ptr<CGame> &game, py::function callback) {
    auto context = game->getContext();
    if (!context->isActive()) {
        throw std::runtime_error("Cannot post script work to a closed game session.");
    }
    auto flow = game->getScriptHandler()->createCallbackFlow(std::move(callback), game);
    context->spawnTask(runPostedScriptFlow(game->getGuiHandler(), std::move(flow)));
}
} // namespace nouraajd::bindings
