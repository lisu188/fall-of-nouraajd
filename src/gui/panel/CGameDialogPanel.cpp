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

#include "CGameDialogPanel.h"
#include "core/CPlaytestTrace.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/object/CWidget.h"
#include "object/CDialog.h"

#include <algorithm>
#include <tuple>
#include <vector>

const std::shared_ptr<CDialog> &CGameDialogPanel::getDialog() const { return dialog; }

void CGameDialogPanel::setDialog(const std::shared_ptr<CDialog> &_dialog) { dialog = _dialog; }

// TODO: unify with CGuiHandler
void CGameDialogPanel::reload() {
    auto self = this->ptr<CGameDialogPanel>();
    if (!dialog) {
        self->close();
        return;
    }
    if (currentStateId != "EXIT") {
        std::shared_ptr<CDialogState> state = dialog->getState(currentStateId);
        if (!state) {
            vstd::logger::warning("Closing dialog with missing state:", currentStateId);
            self->close();
            return;
        }

        std::set<std::shared_ptr<CGameGraphicsObject>> widgets;

        std::shared_ptr<CTextWidget> mainWidget = getGame()->createObject<CTextWidget>("CTextWidget");
        mainWidget->setCentered(false);
        mainWidget->setText(state->getText());

        auto currentOptions = getCurrentOptions();
        const auto panelRect = getLayout()->getRect(self);
        const auto width = std::max(1, panelRect ? panelRect->w : 1);
        const int minimumMainPercent = 20;

        std::vector<std::tuple<int, std::shared_ptr<CDialogOption>, int>> optionLayouts;
        int totalLines = 0;
        for (const auto &[index, option] : currentOptions) {
            auto optionText = vstd::str(index + 1) + ": " + option->getText();
            int lines = std::max(1, getGame()->getGui()->getTextManager()->countLines(optionText, width));
            optionLayouts.emplace_back(index, option, lines);
            totalLines += lines;
        }

        const int optionAreaPercent = std::max(0, 100 - minimumMainPercent);
        int consumedLines = 0;
        for (const auto &[index, option, lines] : optionLayouts) {
            std::string clickName = vstd::to_hex_hash(option);

            auto _option = option;
            self->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(
                clickName, self, [self, _option](CGameGraphicsObject *_self, std::shared_ptr<CGui> gui) {
                    self->selectOption(_option);
                });

            std::shared_ptr<CTextWidget> optionWidget = getGame()->createObject<CTextWidget>("CTextWidget");
            optionWidget->setClick(clickName);
            auto optionText = vstd::str(index + 1) + ": " + option->getText();
            optionWidget->setText(optionText);
            optionWidget->setCentered(false);

            std::shared_ptr<CLayout> optionWidgetLayout = getGame()->createObject<CLayout>("CLayout");

            const int y0 = optionAreaPercent * consumedLines / std::max(1, totalLines);
            consumedLines += lines;
            const int y1 = optionAreaPercent * consumedLines / std::max(1, totalLines);
            const int height = std::max(1, y1 - y0);
            optionWidgetLayout->setY(vstd::str(minimumMainPercent + y0) + "%");
            optionWidgetLayout->setW(vstd::str(100) + "%");
            optionWidgetLayout->setH(vstd::str(height) + "%");
            optionWidget->setLayout(optionWidgetLayout);

            widgets.insert(optionWidget);
        }

        std::shared_ptr<CLayout> mainWidgetLayout = getGame()->createObject<CLayout>("CLayout");
        mainWidgetLayout->setW(vstd::str(100) + "%");
        int textSize = optionLayouts.empty() ? 100 : minimumMainPercent;
        mainWidgetLayout->setH(vstd::str(textSize) + "%");
        mainWidget->setLayout(mainWidgetLayout);

        widgets.insert(mainWidget);

        setChildren(widgets);
    } else {
        self->close();
    }
}

std::shared_ptr<CDialogOption> CGameDialogPanel::getOption(int option) { return getCurrentOptions()[option]; }

std::map<int, std::shared_ptr<CDialogOption>> CGameDialogPanel::getCurrentOptions() {
    // TODO: make this generic and in vstd
    struct OptionComparator {
        bool operator()(const std::shared_ptr<CDialogOption> &a, const std::shared_ptr<CDialogOption> &b) const {
            return a->getNumber() < b->getNumber();
        }
    };

    std::set<std::shared_ptr<CDialogOption>, OptionComparator> options;
    if (!dialog) {
        return {};
    }
    auto state = dialog->getState(currentStateId);
    if (!state) {
        return {};
    }
    for (const auto &option : state->getOptions()) {
        if (!option) {
            continue;
        }
        if (option->getCondition().empty() || dialog->invokeCondition(option->getCondition())) {
            options.insert(option);
        }
    }

    std::map<int, std::shared_ptr<CDialogOption>> return_value;
    int index = 0;
    for (const auto &option : options) {
        return_value[index++] = option;
    }
    return return_value;
}

void CGameDialogPanel::selectOption(int option) { selectOption(getOption(option)); }

void CGameDialogPanel::selectOption(const std::shared_ptr<CDialogOption> &option) {
    if (!option || !dialog) {
        return;
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"action", option->getAction()},
            {"dialog", CPlaytestTrace::objectRef(dialog)},
            {"nextStateId", option->getNextStateId()},
            {"optionNumber", option->getNumber()},
            {"stateId", currentStateId},
        };
        CPlaytestTrace::addMapContext(fields, getGame() ? getGame()->getMap() : nullptr);
        CPlaytestTrace::record("dialog_option_selected", fields);
    }
    if (!option->getAction().empty()) {
        dialog->invokeAction(option->getAction());
    }
    currentStateId = option->getNextStateId().empty() ? "EXIT" : option->getNextStateId();
    reload();
}

bool CGameDialogPanel::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    // TODO: util function to transalte number keys to int
    if (type == SDL_KEYDOWN) {
        if (const auto opt = CUtil::parseKey(i) - 1;
            opt > -1 && static_cast<size_t>(opt) < getCurrentOptions().size()) {
            selectOption(opt);
            return true;
        }
    }
    return false;
}
