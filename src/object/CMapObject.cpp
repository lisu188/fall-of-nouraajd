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
#include "CMapObject.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "handler/CEventHandler.h"

CMapObject::CMapObject() {}

CMapObject::~CMapObject() {}

void CMapObject::move(int x, int y, int z) {
  Coords target(posx + x, posy + y, posz + z);
  auto map = getMap();
  if (map) {
    target = map->normalizeCoords(target);
  }

  if (dynamic_cast<Moveable *>(this) && map) {
    auto current = map->normalizeCoords(Coords(posx, posy, posz));
    auto delta = map->getShortestDelta(current, target);
    bool is_registered = map->getObjectByName(getName()) == this->ptr<CMapObject>();
    bool is_step_move = delta.z == 0 && std::abs(delta.x) + std::abs(delta.y) == 1;
    if (is_registered && is_step_move && !map->canStep(target)) {
      vstd::logger::debug(getName(), "cannot step on:", target.x, target.y,
                          target.z);
      return;
    }
    dynamic_cast<Moveable *>(this)->beforeMove();
  }

  Coords oldCoords(posx, posy, posz);
  posx = target.x;
  posy = target.y;
  posz = target.z;
  Coords newCoords(posx, posy, posz);

  if (map) {
    map->objectMoved(this->ptr<CMapObject>(), oldCoords, newCoords);
  }

  if (dynamic_cast<Moveable *>(this) && map) {
    dynamic_cast<Moveable *>(this)->afterMove();
  }
}

void CMapObject::move(Coords coords) {
  this->move(coords.x, coords.y, coords.z);
}

void CMapObject::moveTo(int x, int y, int z) {
  move(x - posx, y - posy, z - posz);
}

void CMapObject::moveTo(Coords coords) {
  this->moveTo(coords.x, coords.y, coords.z);
}

int CMapObject::getPosY() const { return posy; }

int CMapObject::getPosZ() const { return posz; }

int CMapObject::getPosX() const { return posx; }

void CMapObject::onTurn(std::shared_ptr<CGameEvent> event) {
  pybind11::gil_scoped_acquire gil;
  if (auto override = CPythonOverrides::find_override(this, "onTurn");
      !override.is_none()) {
    PY_SAFE(override(event); return;)
  }
}

void CMapObject::onCreate(std::shared_ptr<CGameEvent> event) {
  pybind11::gil_scoped_acquire gil;
  if (auto override = CPythonOverrides::find_override(this, "onCreate");
      !override.is_none()) {
    PY_SAFE(override(event); return;)
  }
}

void CMapObject::onDestroy(std::shared_ptr<CGameEvent> event) {
  pybind11::gil_scoped_acquire gil;
  if (auto override = CPythonOverrides::find_override(this, "onDestroy");
      !override.is_none()) {
    PY_SAFE(override(event); return;)
  }
}

Coords CMapObject::getCoords() { return Coords(posx, posy, posz); }

void CMapObject::setCoords(Coords coords) {
  this->moveTo(coords.x, coords.y, coords.z);
}

bool CMapObject::isAffiliatedWith(std::shared_ptr<CMapObject> object) {
  return !vstd::is_empty(this->getAffiliation()) &&
         !vstd::is_empty(object->getAffiliation()) &&
         this->getAffiliation() == object->getAffiliation();
}

void CMapObject::setPosX(int posx) { this->posx = posx; }

std::string CMapObject::getAffiliation() { return affiliation; }

void CMapObject::setAffiliation(const std::string &affiliation) {
  CMapObject::affiliation = affiliation;
}

void CMapObject::setPosY(int posy) { this->posy = posy; }

void CMapObject::setPosZ(int posz) { this->posz = posz; }

bool CMapObject::getCanStep() { return canStep; }

void CMapObject::setCanStep(bool step) { canStep = step; }
