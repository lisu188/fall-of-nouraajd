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

    if (dynamic_cast<CMoveable *>(this) && map) {
        auto current = map->normalizeCoords(Coords(posx, posy, posz));
        auto delta = map->getShortestDelta(current, target);
        bool is_registered = map->getObjectByName(getName()) == this->ptr<CMapObject>();
        bool is_step_move = delta.z == 0 && std::abs(delta.x) + std::abs(delta.y) == 1;
        if (is_registered && is_step_move && !map->canStep(target)) {
            vstd::logger::debug(getName(), "cannot step on:", target.x, target.y, target.z);
            return;
        }
        dynamic_cast<CMoveable *>(this)->beforeMove();
    }

    Coords oldCoords(posx, posy, posz);
    posx = target.x;
    posy = target.y;
    posz = target.z;
    Coords newCoords(posx, posy, posz);

    if (map && map->getObjectByName(getName()) == this->ptr<CMapObject>()) {
        map->objectMoved(this->ptr<CMapObject>(), oldCoords, newCoords);
    }

    if (dynamic_cast<CMoveable *>(this) && map) {
        dynamic_cast<CMoveable *>(this)->afterMove();
    }
}

void CMapObject::move(Coords coords) { this->move(coords.x, coords.y, coords.z); }

void CMapObject::moveTo(int x, int y, int z) { move(x - posx, y - posy, z - posz); }

void CMapObject::moveTo(Coords coords) { this->moveTo(coords.x, coords.y, coords.z); }

void CMapObject::relocateWithoutMoveHooks(Coords coords) {
    auto map = getMap();
    if (map) {
        coords = map->normalizeCoords(coords);
    }

    Coords oldCoords(posx, posy, posz);
    posx = coords.x;
    posy = coords.y;
    posz = coords.z;

    if (map && map->getObjectByName(getName()) == this->ptr<CMapObject>()) {
        map->objectMoved(this->ptr<CMapObject>(), oldCoords, coords);
    }
}

int CMapObject::getPosY() const { return posy; }

int CMapObject::getPosZ() const { return posz; }

int CMapObject::getPosX() const { return posx; }

void CMapObject::onTurn(std::shared_ptr<CGameEvent> event) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "onTurn"); !override.is_none()) {
        PY_SAFE(override(event); return;)
    }
}

void CMapObject::onCreate(std::shared_ptr<CGameEvent> event) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "onCreate"); !override.is_none()) {
        PY_SAFE(override(event); return;)
    }
}

void CMapObject::onDestroy(std::shared_ptr<CGameEvent> event) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "onDestroy"); !override.is_none()) {
        PY_SAFE(override(event); return;)
    }
}

Coords CMapObject::getCoords() { return Coords(posx, posy, posz); }

void CMapObject::setCoords(Coords coords) { this->moveTo(coords.x, coords.y, coords.z); }

bool CMapObject::isAffiliatedWith(std::shared_ptr<CMapObject> object) {
    return object && !vstd::is_empty(this->getAffiliation()) && !vstd::is_empty(object->getAffiliation()) &&
           this->getAffiliation() == object->getAffiliation();
}

void CMapObject::setPosX(int posx) { this->posx = posx; }

std::string CMapObject::getAffiliation() { return affiliation; }

void CMapObject::setAffiliation(const std::string &affiliation) { CMapObject::affiliation = affiliation; }

void CMapObject::setPosY(int posy) { this->posy = posy; }

void CMapObject::setPosZ(int posz) { this->posz = posz; }

bool CMapObject::getCanStep() { return canStep; }

void CMapObject::setCanStep(bool step) { canStep = step; }
