/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include "gui/CLayout.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "core/CController.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "core/CLoader.h"
#include "CWidget.h"

CMapGraphicsObject::CMapGraphicsObject() {

}


std::list<std::shared_ptr<CGameGraphicsObject>>
CMapGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    return vstd::with<std::list<std::shared_ptr<CGameGraphicsObject>>>(
            gui->getGame()->getMap(), [&](auto map) {
                std::list<std::shared_ptr<CGameGraphicsObject>> return_val;

                std::shared_ptr<CPlayer> player = gui->getGame()->getMap()->getPlayer();
                auto actualCoords = guiToMap(gui, Coords(x, y, player->getCoords().z));

                std::shared_ptr<CTile> tile = map->getTile(actualCoords.x, actualCoords.y, actualCoords.z);

                return_val.push_back(tile->getGraphicsObject()->withCallback(
                        [actualCoords](std::shared_ptr<CGui> gui, SDL_EventType type, int button, int, int) {
                            if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
                                auto controller = vstd::cast<CPlayerController>(
                                        gui->getGame()->getMap()->getPlayer()->getController());
                                if (!controller) {
                                    return false;
                                }
                                auto player = gui->getGame()->getMap()->getPlayer();
                                controller->setTarget(player, actualCoords);

                                if (!gui->getMap()->isMoving()) {
                                    //move this code
                                    while (!controller->isCompleted(player)) {
                                        gui->getGame()->getMap()->move();
                                    }
                                }

                                return true;
                            }
                            return false;
                        }));


                for (const auto &ob: map->getObjectsAtCoords(actualCoords)) {
                    return_val.push_back(ob->getGraphicsObject());
                }

                //TODO: make list of such properties in config
                if (map->getBoolProperty("showCoordinates")) {
                    showCoordinates(gui, return_val, actualCoords);
                }


                auto playerController = vstd::cast<CPlayerController>(player->getController());
                auto path = playerController ?
                        playerController->isOnPath(player, actualCoords) : std::make_pair(false, Coords::UNDEFINED);
                if (path.first) {
                    showFootprint(gui,
                                  path.second,
                                  return_val);
                }

                return return_val;
            }

    );
}

//TODO: fix text display, smaller font
void CMapGraphicsObject::showCoordinates(std::shared_ptr<CGui> &gui,
                                         std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                                         const Coords &actualCoords) const {
    auto countBox = gui->getGame()->getObjectHandler()->createObject<CTextWidget>(gui->getGame());
    countBox->setText(vstd::str(actualCoords.x, ",", actualCoords.y));
    auto layout = gui->getGame()->getObjectHandler()->createObject<CLayout>(gui->getGame());
    layout->setHorizontal("RIGHT");
    layout->setVertical("DOWN");
    layout->setW("100%");
    layout->setH("25%");
    countBox->setLayout(layout);
    countBox->setPriority(4);
    return_val.push_back(countBox);
}

void CMapGraphicsObject::showFootprint(std::shared_ptr<CGui> &gui,
                                       Coords::Direction dir,
                                       std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    auto footprint = vstd::cast<CStaticAnimation>(CAnimationProvider::getAnimation(gui->getGame(), "images/footprint"));
    switch (dir) {
        case Coords::UNDEFINED:
        case Coords::ZERO:
        case Coords::NORTH:
        case Coords::UP:
        case Coords::DOWN:
            break;
        case Coords::EAST:
            footprint->setRotation(90);
            break;
        case Coords::SOUTH:
            footprint->setRotation(180);
            break;
        case Coords::WEST:
            footprint->setRotation(270);
            break;
    }
    auto layout = gui->getGame()->getObjectHandler()->createObject<CLayout>(gui->getGame());
    layout->setHorizontal("CENTER");
    layout->setVertical("CENTER");
    layout->setW("50%");
    layout->setH("50%");
    footprint->setLayout(layout);
    footprint->setPriority(4);
    return_val.push_back(footprint);
}

void CMapGraphicsObject::initialize() {
    auto self = this->ptr<CMapGraphicsObject>();
    vstd::call_when([self]() {
                        return self->getGui() != nullptr
                               && self->getGui()->getGame() != nullptr
                               && self->getGui()->getGame()->getMap() != nullptr;
                    }, [self]() {
                        self->getGui()->getGame()->getMap()->connect(
                                "turnPassed", self, "refreshAll");
                        self->getGui()->getGame()->getMap()->connect(
                                "tileChanged", self,
                                "refreshObject"); // TODO: current lazy tile loading may cause event spam
                        self->getGui()->getGame()->getMap()->connect(
                                "objectChanged", self,
                                "refreshObject"); // TODO: current lazy tile loading may cause event spam
                        self->refresh();
                    }
    );
}


int CMapGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) {
    return gui->getTileCountY();
}

int CMapGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) {
    return gui->getTileCountX();
}

bool CMapGraphicsObject::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        if (gui->getGame()->getMap()->isMoving()) {
            return true; //TODO: rethink this
        }
        std::shared_ptr<CPlayer> player = gui->getGame()->getMap()->getPlayer();
        switch (i) {
            case SDLK_UP:
                vstd::cast<CPlayerController>(player->getController())->setTarget(player,
                                                                                  player->getCoords() +
                                                                                  NORTH);
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_DOWN:
                vstd::cast<CPlayerController>(player->getController())->setTarget(player,
                                                                                  player->getCoords() +
                                                                                  SOUTH);
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_LEFT:
                vstd::cast<CPlayerController>(player->getController())->setTarget(player,
                                                                                  player->getCoords() +
                                                                                  WEST);
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_RIGHT:
                vstd::cast<CPlayerController>(player->getController())->setTarget(player,
                                                                                  player->getCoords() +
                                                                                  EAST);
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_SPACE:
                vstd::cast<CPlayerController>(player->getController())->setTarget(player,
                                                                                  player->getCoords() +
                                                                                  ZERO);
                gui->getGame()->getMap()->move();
                return true;
            case SDLK_s:
                CMapLoader::save(gui->getGame()->getMap(), gui->getGame()->getMap()->getName());
                return true;
        }
    }
    return false;
}

Coords CMapGraphicsObject::mapToGui(std::shared_ptr<CGui> gui, Coords coords) {
    auto playerCoords = gui->getGame()->getMap()->getPlayer()->getCoords();

    return Coords(coords.x - playerCoords.x + gui->getTileCountX() / 2,
                  coords.y - playerCoords.y + gui->getTileCountY() / 2,
                  coords.z);
}

Coords CMapGraphicsObject::guiToMap(std::shared_ptr<CGui> gui, Coords coords) {
    auto playerCoords = gui->getGame()->getMap()->getPlayer()->getCoords();

    return Coords(playerCoords.x - gui->getTileCountX() / 2 + coords.x,
                  playerCoords.y - gui->getTileCountY() / 2 + coords.y,
                  playerCoords.z);
}

void CMapGraphicsObject::refreshObject(Coords coords) {
    auto translated = mapToGui(getGui(), coords);
    CProxyTargetGraphicsObject::refreshObject(translated.x, translated.y);
}
