/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "CGamePanel.h"
#include "gui/CGui.h"
#include "gui/object/CWidget.h"
#include "gui/CTextureCache.h"


bool CGamePanel::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return true;
}

bool CGamePanel::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    return true;
}

void CGamePanel::refreshViews() {
    for (auto child : getChildren()) {
        if (child->meta()->inherits(CListView::static_meta()->name())) {
            vstd::cast<CListView>(child)->refreshAll();
        }
    }
}

CGamePanel::CGamePanel() {
    //TODO: extract to json
    setBackground("images/panel");
    setModal(true);
}

void CGamePanel::awaitClosing() {
    auto self = this->ptr<CGamePanel>();
    vstd::wait_until([self]() {
        return !self->getGui() || self->getGui()->findChild(self) == nullptr;
    });
}
