#include "CMapObject.h"
#include "core/CAsync.h"
#include "core/CGameContext.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "handler/CEventHandler.h"

CMapObject::CMapObject() {}

CMapObject::~CMapObject() {}

void CMapObject::move(int x, int y, int z) {
    auto task = moveAsync(Coords(x, y, z));
    if (auto game = getGame()) {
        game_async::wait(game->getContext()->spawnTask(std::move(task)),
                         game->getGui() ? game_async::WaitMode::Frames : game_async::WaitMode::PostedWork);
    } else {
        game_async::run(std::move(task), game_async::WaitMode::PostedWork);
    }
}

vstd::task<void> CMapObject::moveAsync(Coords delta) { return moveOwnedAsync(this->ptr<CMapObject>(), delta, false); }

vstd::task<void> CMapObject::moveToAsync(Coords coords, std::move_only_function<void()> positionCommit,
                                         CMovementPresenter presenter) {
    return moveOwnedAsync(this->ptr<CMapObject>(), coords, true, std::move(positionCommit), std::move(presenter));
}

vstd::task<void> CMapObject::moveOwnedAsync(std::shared_ptr<CMapObject> object, Coords coords, bool absolute,
                                            std::move_only_function<void()> positionCommit,
                                            CMovementPresenter presenter) {
    auto loop = vstd::event_loop<>::instance();
    if (!loop->isMainThread()) {
        co_await vstd::post(loop);
    }
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    auto map = object->getMap();
    std::unique_lock<std::recursive_mutex> navigationLock;
    if (map)
        navigationLock = std::unique_lock(map->getNavigationMutex());
    Coords target = absolute ? coords : object->getCoords() + coords;
    if (map) {
        target = map->normalizeCoords(target);
    }

    auto moveable = dynamic_cast<CMoveable *>(object.get());
    const auto origin = object->getCoords();
    const auto name = object->getName();
    std::weak_ptr<CGame> weakGame;
    std::shared_ptr<CMap> activeMap;
    std::shared_ptr<CGameContext> context;
    CGameContext::TransitionGeneration generation = 0;
    bool is_registered = false;
    bool is_step_move = false;

    if (moveable && map) {
        auto current = map->normalizeCoords(object->getCoords());
        auto delta = map->getShortestDelta(current, target);
        auto game = object->getGame();
        weakGame = game;
        activeMap = game ? game->getMap() : nullptr;
        context = game ? game->getContext() : nullptr;
        generation = context ? context->captureTransitionGeneration() : 0;
        game.reset();
        is_registered = map->getObjectByName(name) == object;
        is_step_move = delta.z == 0 && std::abs(delta.x) + std::abs(delta.y) == 1;
        if (is_registered && is_step_move) {
            navigationLock.unlock();
            const bool can_step = map->canStep(target);
            navigationLock.lock();
            if (!can_step) {
                vstd::logger::debug(object->getName(), "cannot step on:", target.x, target.y, target.z);
                co_return;
            }
        }
        const auto routingEpoch = map->getRoutingEpoch();
        navigationLock.unlock();
        gil.reset();
        try {
            co_await moveable->beforeMoveAsync();
        } catch (...) {
            moveable->cancelMove();
            throw;
        }
        if (Py_IsInitialized()) {
            gil.emplace();
        }
        navigationLock.lock();
        game = weakGame.lock();
        if (object->getMap() != map || object->getCoords() != origin || object->getName() != name ||
            (game && game->getMap() != activeMap) || (is_registered && map->getObjectByName(name) != object) ||
            (context && !context->isTransitionGenerationCurrent(generation))) {
            navigationLock.unlock();
            moveable->cancelMove();
            co_return;
        }
        if (is_registered && is_step_move && map->getRoutingEpoch() != routingEpoch) {
            navigationLock.unlock();
            const bool canStep = map->canStep(target);
            navigationLock.lock();
            if (!canStep) {
                navigationLock.unlock();
                moveable->cancelMove();
                co_return;
            }
        }
    }

    Coords oldCoords = object->getCoords();
    object->posx = target.x;
    object->posy = target.y;
    object->posz = target.z;
    std::exception_ptr commitFailure;
    if (positionCommit) {
        try {
            positionCommit();
        } catch (...) {
            commitFailure = std::current_exception();
        }
    }
    Coords newCoords = object->getCoords();

    if (map && map->getObjectByName(object->getName()) == object) {
        map->objectMoved(object, oldCoords, newCoords);
    }
    if (commitFailure) {
        if (moveable) {
            moveable->cancelMove();
        }
        std::rethrow_exception(commitFailure);
    }

    if (moveable && map) {
        navigationLock.unlock();
        gil.reset();
        if (presenter && is_registered && is_step_move && newCoords == target && oldCoords != newCoords) {
            const auto stop = co_await vstd::thisTaskStopToken();
            try {
                co_await presenter(object, oldCoords, newCoords);
                if (!loop->isMainThread()) {
                    co_await vstd::post(loop);
                }
                if (stop.stop_requested()) {
                    throw vstd::task_cancelled();
                }
            } catch (...) {
                moveable->cancelMove();
                throw;
            }
            if (Py_IsInitialized()) {
                gil.emplace();
            }
            navigationLock.lock();
            const auto game = weakGame.lock();
            const bool stale = object->getMap() != map || object->getCoords() != newCoords ||
                               object->getName() != name || map->getObjectByName(name) != object ||
                               (game && (game->getMap() != activeMap || object->getGame() != game)) ||
                               (context && (!game || !context->isTransitionGenerationCurrent(generation)));
            navigationLock.unlock();
            gil.reset();
            if (stale) {
                moveable->cancelMove();
                co_return;
            }
        }
        co_await moveable->afterMoveAsync();
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
