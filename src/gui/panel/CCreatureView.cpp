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
#include "gui/CLayout.h"
#include "CCreatureView.h"
#include "object/CCreature.h"
#include "gui/CGui.h"


std::shared_ptr<CScript> CCreatureView::getCreature() {
    return creature;
}

void CCreatureView::setCreature(std::shared_ptr<CScript> _creature) {
    creature = _creature;
}

std::set<std::shared_ptr<CGameGraphicsObject>>
CCreatureView::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    auto graphicsObject = creature->invoke<CCreature>(gui->getGame(), this->ptr())->getGraphicsObject();
    graphicsObject->setLayout(std::make_shared<CParentLayout>());
    return vstd::set(
            graphicsObject);
}

int CCreatureView::getSizeX(std::shared_ptr<CGui> gui) {
    return 1;
}

int CCreatureView::getSizeY(std::shared_ptr<CGui> gui) {
    return 1;
}

void CCreatureView::initialize() {
    vstd::call_when([=]() {
                        return getGui() != nullptr
                               && getGui()->getGame() != nullptr
                               && getGui()->getGame()->getMap() != nullptr;
                    }, [=]() {
                        refresh();
                    }
    );
}
