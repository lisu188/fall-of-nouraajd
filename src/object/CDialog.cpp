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
#include "CDialog.h"
#include "core/CPythonOverrides.h"
#include "core/CGame.h"
#include "handler/CGuiHandler.h"
#include "handler/CScriptHandler.h"

const std::set<std::shared_ptr<CDialogState>> &CDialog::getStates() const { return states; }

void CDialog::setStates(const std::set<std::shared_ptr<CDialogState>> &states) { CDialog::states = states; }

std::shared_ptr<CDialogState> CDialog::getState(std::string stateId) {
    auto state = vstd::find_if(states, [stateId](auto _state) { return _state->getStateId() == stateId; });
    return state != states.end() ? *state : nullptr;
}

void CDialog::invokeAction(std::string action) { invokeActionChecked(action); }

bool CDialog::invokeActionChecked(std::string action) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "invokeAction"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override(action).cast<bool>();, false)
    }
    return false;
}

vstd::task<bool> CDialog::invokeActionCheckedAsync(std::string action) {
    return [](std::shared_ptr<CDialog> self, std::string action) -> vstd::task<bool> {
        auto loop = vstd::event_loop<>::instance();
        if (!loop->isMainThread()) {
            co_await vstd::post(loop);
        }
        try {
            std::unique_ptr<CScriptFlow> flow;
            std::shared_ptr<CGuiHandler> gui;
            {
                pybind11::gil_scoped_acquire acquire;
                auto getter = CPythonOverrides::find_override(self.get(), "getActionFlow");
                if (getter.is_none()) {
                    co_return self->invokeActionChecked(std::move(action));
                }
                auto callback = getter(action);
                if (callback.is_none()) {
                    co_return self->invokeActionChecked(std::move(action));
                }
                auto game = self->getGame();
                if (!game) {
                    co_return false;
                }
                gui = game->getGuiHandler();
                flow = game->getScriptHandler()->createCallbackFlow(callback.cast<pybind11::function>(), game);
            }
            co_await gui->runScriptFlowAsync(std::move(flow));
            co_return true;
        } catch (const vstd::task_cancelled &) {
            throw;
        } catch (const vstd::scheduler_rejected &) {
            throw;
        } catch (...) {
            PYTHON_LOG;
            co_return false;
        }
    }(this->ptr<CDialog>(), std::move(action));
}

bool CDialog::invokeCondition(std::string condition) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "invokeCondition"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override(condition).cast<bool>();, false)
    }
    return false;
}

const std::string &CDialogState::getText() const { return text; }

void CDialogState::setText(const std::string &text) { CDialogState::text = text; }

const std::set<std::shared_ptr<CDialogOption>> &CDialogState::getOptions() const { return options; }

void CDialogState::setOptions(const std::set<std::shared_ptr<CDialogOption>> &options) {
    CDialogState::options = options;
}

int CDialogOption::getNumber() const { return number; }

void CDialogOption::setNumber(int number) { CDialogOption::number = number; }

const std::string &CDialogOption::getText() const { return text; }

void CDialogOption::setText(const std::string &text) { CDialogOption::text = text; }

const std::string &CDialogOption::getAction() const { return action; }

void CDialogOption::setAction(const std::string &action) { CDialogOption::action = action; }

const std::string &CDialogState::getStateId() const { return stateId; }

void CDialogState::setStateId(const std::string &stateId) { CDialogState::stateId = stateId; }

const std::string &CDialogOption::getNextStateId() const { return nextStateId; }

void CDialogOption::setNextStateId(const std::string &nextStateId) { CDialogOption::nextStateId = nextStateId; }

const std::string &CDialogOption::getCondition() const { return condition; }

void CDialogOption::setCondition(const std::string &condition) { CDialogOption::condition = condition; }
