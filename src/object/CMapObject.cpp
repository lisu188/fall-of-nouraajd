#include "CMapObject.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "handler/CEventHandler.h"

CMapObject::CMapObject() {}

CMapObject::~CMapObject() {}

void CMapObject::move(int x, int y, int z) {
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    auto map = getMap();
    std::unique_lock<std::recursive_mutex> navigationLock;
    if (map)
        navigationLock = std::unique_lock(map->getNavigationMutex());
    Coords target(posx + x, posy + y, posz + z);
    if (map) {
        target = map->normalizeCoords(target);
    }

    if (dynamic_cast<CMoveable *>(this) && map) {
        auto current = map->normalizeCoords(Coords(posx, posy, posz));
        auto delta = map->getShortestDelta(current, target);
        bool is_registered = map->getObjectByName(getName()) == this->ptr<CMapObject>();
        bool is_step_move = delta.z == 0 && std::abs(delta.x) + std::abs(delta.y) == 1;
        if (is_registered && is_step_move) {
            navigationLock.unlock();
            const bool can_step = map->canStep(target);
            navigationLock.lock();
            if (!can_step) {
                vstd::logger::debug(getName(), "cannot step on:", target.x, target.y, target.z);
                return;
            }
        }
        navigationLock.unlock();
        dynamic_cast<CMoveable *>(this)->beforeMove();
        navigationLock.lock();
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
        navigationLock.unlock();
        dynamic_cast<CMoveable *>(this)->afterMove();
    }
}

void CMapObject::move(Coords coords) { this->move(coords.x, coords.y, coords.z); }

void CMapObject::moveTo(int x, int y, int z) { move(x - posx, y - posy, z - posz); }

void CMapObject::moveTo(Coords coords) { this->moveTo(coords.x, coords.y, coords.z); }

void CMapObject::relocateWithoutMoveHooks(Coords coords) {
    auto map = getMap();
    std::unique_lock<std::recursive_mutex> navigationLock;
    if (map)
        navigationLock = std::unique_lock(map->getNavigationMutex());
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

void CMapObject::setPosX(int posx) {
    auto map = getMap();
    if (map && map->getObjectByName(getName()).get() == this) {
        relocateWithoutMoveHooks(Coords(posx, posy, posz));
        return;
    }
    this->posx = posx;
}

std::string CMapObject::getAffiliation() { return affiliation; }

void CMapObject::setAffiliation(const std::string &affiliation) { CMapObject::affiliation = affiliation; }

void CMapObject::setPosY(int posy) {
    auto map = getMap();
    if (map && map->getObjectByName(getName()).get() == this) {
        relocateWithoutMoveHooks(Coords(posx, posy, posz));
        return;
    }
    this->posy = posy;
}

void CMapObject::setPosZ(int posz) {
    auto map = getMap();
    if (map && map->getObjectByName(getName()).get() == this) {
        relocateWithoutMoveHooks(Coords(posx, posy, posz));
        return;
    }
    this->posz = posz;
}

bool CMapObject::getCanStep() { return canStep; }

void CMapObject::setCanStep(bool step) {
    auto map = getMap();
    std::unique_lock<std::recursive_mutex> lock;
    if (map)
        lock = std::unique_lock(map->getNavigationMutex());
    if (canStep == step)
        return;
    canStep = step;
    if (map && map->getObjectByName(getName()).get() == this)
        map->navigationCellChanged(getCoords());
}
