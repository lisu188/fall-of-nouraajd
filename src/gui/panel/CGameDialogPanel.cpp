/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2020  Andrzej Lis

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
#include "object/CDialog.h"
#include "gui/object/CWidget.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"


const std::shared_ptr<CDialog> &CGameDialogPanel::getDialog() const {
    return dialog;
}

void CGameDialogPanel::setDialog(const std::shared_ptr<CDialog> &_dialog) {
    dialog = _dialog;
}

//TODO: unify with CGuiHandler
void CGameDialogPanel::reload() {
    auto self = this->ptr<CGameDialogPanel>();
    if (currentStateId != "EXIT") {
        std::shared_ptr<CDialogState> state = dialog->getState(currentStateId);

        std::set<std::shared_ptr<CGameGraphicsObject>> widgets;

        std::shared_ptr<CTextWidget> mainWidget = getGame()->createObject<CTextWidget>("CTextWidget");
        mainWidget->setCentered(false);
        mainWidget->setText(state->getText());

        int percentSize = 5;

        //TODO: make this generic and in vstd
        struct OptionComparator {
            bool operator()(const std::shared_ptr<CDialogOption> &a, const std::shared_ptr<CDialogOption> &b) const {
                return a->getNumber() > b->getNumber();
            }
        };

        auto options = vstd::cast<std::set<std::shared_ptr<CDialogOption>, OptionComparator>>(state->getOptions());

        int totalLines = 0;
        for (const auto &option : options) {
            std::string clickName = vstd::to_hex_hash(option);

            self->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(clickName, self,
                                                                                       [self, option](
                                                                                               CGameGraphicsObject *_self,
                                                                                               std::shared_ptr<CGui> gui) {
                                                                                           self->selectOption(option);
                                                                                       });


            std::shared_ptr<CTextWidget> optionWidget = getGame()->createObject<CTextWidget>("CTextWidget");
            optionWidget->setClick(clickName);
            auto optionText =
                    vstd::str(option->getNumber() + 1) + ": " + option->getText();
            optionWidget->setText(optionText);
            optionWidget->setCentered(false);

            std::shared_ptr<CLayout> optionWidgetLayout = getGame()->createObject<CLayout>("CLayout");

            auto lines = getGame()->getGui()->getTextManager()->countLines(optionText, getLayout()->getRect(self)->w);
            totalLines += lines;

            optionWidgetLayout->setY(vstd::str(100 - (totalLines * percentSize)) + "%");
            optionWidgetLayout->setW(vstd::str(100) + "%");
            optionWidgetLayout->setH(vstd::str(percentSize * lines) + "%");
            optionWidget->setLayout(optionWidgetLayout);

            widgets.insert(optionWidget);
        }

        std::shared_ptr<CLayout> mainWidgetLayout = getGame()->createObject<CLayout>("CLayout");
        mainWidgetLayout->setW(vstd::str(100) + "%");
        int textSize = 100 - totalLines * percentSize;
        mainWidgetLayout->setH(vstd::str(textSize) + "%");
        mainWidget->setLayout(mainWidgetLayout);

        widgets.insert(mainWidget);

        setChildren(widgets);
    } else {
        self->close();
    }
}

std::shared_ptr<CDialogOption> CGameDialogPanel::getOption(int option) {
    return vstd::find_if(getCurrentOptions(), [option](auto op) {
        return op->getNumber() == option;
    });
}

const std::set<std::shared_ptr<CDialogOption>> &
CGameDialogPanel::getCurrentOptions() { return dialog->getState(currentStateId)->getOptions(); }

void CGameDialogPanel::selectOption(int option) {
    selectOption(getOption(option));
}

void CGameDialogPanel::selectOption(const std::shared_ptr<CDialogOption> &option) {
    if (!option->getAction().empty()) {
        dialog->invokeAction(
                option->getAction());
    }
    currentStateId = option->getNextStateId();
    reload();
}

bool CGameDialogPanel::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    //TODO: util function to transalte number keys to int
    if (type == SDL_KEYDOWN) {
        auto opt = CUtil::parseKey(i) - 1;
        if (opt > -1 && opt < getCurrentOptions().size()) {
            selectOption(opt);
            return true;
        }
    }
    return false;
}
