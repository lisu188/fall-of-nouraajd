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
#include "CSideBar.h"
#include "gui/CGui.h"
#include "core/CList.h"
#include "gui/panel/CGamePanel.h"

void CSideBar::clickInventory(std::shared_ptr<CGui> gui) {
    flipPanel(gui, "inventoryPanel");
}

void CSideBar::clickJournal(std::shared_ptr<CGui> gui) {
    flipPanel(gui, "questPanel");
}

void CSideBar::clickCharacter(std::shared_ptr<CGui> gui) {
    flipPanel(gui, "characterPanel");
}

std::shared_ptr<CMapStringString> CSideBar::getPanelKeys() {
    return panelKeys;
}

void CSideBar::setPanelKeys(std::shared_ptr<CMapStringString> _panelKeys) {
    this->panelKeys = _panelKeys;
}

void CSideBar::flipPanel(std::shared_ptr<CGui> gui, std::string panel) {
    if (auto _panel = gui->getGame()->getGuiHandler()->flipPanel(panel)) {
        for (auto val:panelKeys->getValues()) {
            if (val.second == panel) {
                auto keyPred = [val](std::shared_ptr<CGui> gui, std::shared_ptr<CGameGraphicsObject> self,
                                     SDL_Event *event) {
                    return event->type == SDL_KEYDOWN && event->key.keysym.sym == val.first[0];
                };
                auto _self = this->ptr<CSideBar>();
                _panel->registerEventCallback(keyPred,
                                              [_self, panel](std::shared_ptr<CGui> gui,
                                                             std::shared_ptr<CGameGraphicsObject> self,
                                                             SDL_Event *event) {
                                                  _self->flipPanel(gui, panel);
                                                  return true;
                                              });
            }
        }

    }
}

bool CSideBar::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        for (auto val:panelKeys->getValues()) {
            if (i == val.first[0]) {
                flipPanel(sharedPtr, val.second);
                return true;
            }
        }
    }
    return false;
}
