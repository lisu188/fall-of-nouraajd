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
#include "core/CScript.h"


std::shared_ptr<CScript> CCreatureView::getCreatureScript() {
    return creatureScript;
}

void CCreatureView::setCreatureScript(std::shared_ptr<CScript> _creatureScript) {
    creatureScript = _creatureScript;
}

std::set<std::shared_ptr<CGameGraphicsObject>>
CCreatureView::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    auto graphicsObject = getCreature()->getGraphicsObject();
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
    auto self = this->ptr<CCreatureView>();
    vstd::call_when([self]() {
                        return self->getGui() != nullptr
                               && self->getGui()->getGame() != nullptr
                               && self->getGui()->getGame()->getMap() != nullptr;
                    }, [self]() {
                        self->refresh();
                    }
    );
}

CListView::collection_pointer CCreatureView::getEffects() {
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(
            getCreature()->getEffects()));
}

std::shared_ptr<CCreature> CCreatureView::getCreature() {
    return creatureScript->invoke<CCreature>(getGui()->getGame(), this->ptr());
}
