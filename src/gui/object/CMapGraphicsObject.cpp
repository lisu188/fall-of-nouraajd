#include "gui/object/CMapGraphicsObject.h"
#include "CWidget.h"
#include "core/CController.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CLuaOverrides.h"
#include "core/CPythonOverrides.h"
#include "core/CWrapper.h"
#include "gui/CAnimation.h"
#include "gui/CGuiTasks.h"
#include "gui/CLayout.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "handler/CEventHandler.h"
#include "object/CTrigger.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "object/CTile.h"

#include <algorithm>
#include <exception>

namespace {
vstd::task<void> emptyMovementPresentation() { co_return; }

bool hasMovementPythonHook(const CGameObject *object, std::initializer_list<const char *> names) {
    if (!Py_IsInitialized())
        return false;
    pybind11::gil_scoped_acquire gil;
    return std::any_of(names.begin(), names.end(), [object](const auto name) {
        if (!CPythonOverrides::find_override(object, name).is_none())
            return true;
        const auto tile = dynamic_cast<const CTile *>(object);
        return tile && static_cast<bool>(pybind11::get_override(tile, name));
    });
}

bool hasKnownMovementController(const std::shared_ptr<CController> &controller) {
    if (!controller)
        return false;
    const auto &type = typeid(*controller);
    return type == typeid(CController) || type == typeid(CPlayerController) || type == typeid(CTargetController) ||
           type == typeid(CRandomController) || type == typeid(CNpcRandomController) ||
           type == typeid(CGroundController) || type == typeid(CRangeController);
}

void reportMovementCleanupFailure(const char *message) noexcept {
    try {
        vstd::logger::error("GUI movement cleanup failed:", message);
    } catch (...) {
    }
}

template <typename Callback> class ScopeExit {
  public:
    explicit ScopeExit(Callback callback) : callback(std::move(callback)) {}
    ScopeExit(const ScopeExit &) = delete;
    ScopeExit &operator=(const ScopeExit &) = delete;
    ~ScopeExit() noexcept {
        try {
            callback();
        } catch (const std::exception &error) {
            reportMovementCleanupFailure(error.what());
        } catch (...) {
            reportMovementCleanupFailure("unknown exception");
        }
    }

  private:
    Callback callback;
};

class CMapProxyLayout : public CProxyGraphicsLayout {
  public:
    explicit CMapProxyLayout(std::weak_ptr<CMapGraphicsObject> owner) : owner(std::move(owner)) {}

    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override {
        auto rect = CProxyGraphicsLayout::getRect(std::move(object));
        if (auto view = owner.lock()) {
            const auto offset = view->getCameraOffset(rect->w);
            rect->x += offset.x - rect->w;
            rect->y += offset.y - rect->h;
        }
        return rect;
    }

  private:
    std::weak_ptr<CMapGraphicsObject> owner;
};

class CMapMotionLayout : public CLayout {
  public:
    explicit CMapMotionLayout(std::weak_ptr<CMapGraphicsObject> owner, std::weak_ptr<CGameObject> actor,
                              Coords offset = ZERO)
        : owner(std::move(owner)), actor(std::move(actor)), offset(offset) {}

    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject>) override {
        if (auto view = owner.lock()) {
            auto rect = view->getMotionRect(actor.lock());
            rect->x += offset.x * rect->w;
            rect->y += offset.y * rect->h;
            return rect;
        }
        return CUtil::rect(0, 0, 0, 0);
    }

  private:
    std::weak_ptr<CMapGraphicsObject> owner;
    std::weak_ptr<CGameObject> actor;
    Coords offset;
};

std::shared_ptr<CAnimation> clone_proxy_animation(const std::shared_ptr<CGui> &gui,
                                                  const std::shared_ptr<CAnimation> &cached) {
    auto animation = gui->getGame()->createObject<CAnimation>(cached->meta()->name());
    animation->setPriority(cached->getPriority());
    return animation;
}
} // namespace

CMapGraphicsObject::CMapGraphicsObject() {}

std::shared_ptr<CAnimation> CMapGraphicsObject::syncProxyAnimation(std::shared_ptr<CGui> gui,
                                                                   const std::shared_ptr<CGameObject> &object,
                                                                   std::shared_ptr<CAnimation> &animation) {
    if (!object) {
        return nullptr;
    }
    auto cached = object->getGraphicsObject();
    if (!cached) {
        return nullptr;
    }
    if (!animation || animation->meta()->name() != cached->meta()->name()) {
        animation = clone_proxy_animation(gui, cached);
    }
    animation->setObject(object);
    animation->setPriority(cached->getPriority());
    return animation;
}

std::list<std::shared_ptr<CGameGraphicsObject>> CMapGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui, int x,
                                                                                      int y) {
    validateDestinationPreview(gui);
    auto game = gui->getGame();
    auto map = game->getMap();
    if (!map) {
        return {};
    }
    if (cachedMap.lock() != map) {
        proxyAnimations.clear();
        cachedMap = map;
        hasCachedProxyZ = false;
    }

    std::list<std::shared_ptr<CGameGraphicsObject>> return_val;
    std::shared_ptr<CPlayer> player = map->getPlayer();
    if (!player) {
        return {};
    }
    auto playerCoords = player->getCoords();
    if (!hasCachedProxyZ || cachedProxyZ != playerCoords.z) {
        proxyAnimations.clear();
        cachedProxyZ = playerCoords.z;
        hasCachedProxyZ = true;
    }

    auto proxyCoords = Coords(x, y, playerCoords.z);
    int tileCountX = gui->getTileCountX();
    int tileCountY = gui->getTileCountY();
    auto rawCoords =
        Coords(playerCoords.x - tileCountX / 2 + x - 1, playerCoords.y - tileCountY / 2 + y - 1, playerCoords.z);
    auto actualCoords = map->normalizeCoords(rawCoords);
    auto &slot = proxyAnimations[proxyCoords];

    std::shared_ptr<CTile> tile = map->getTile(actualCoords.x, actualCoords.y, actualCoords.z);
    auto tileAnimation = syncProxyAnimation(gui, tile, slot.tile);
    if (tileAnimation) {
        std::weak_ptr<CMapGraphicsObject> weakSelf = ptr<CMapGraphicsObject>();
        return_val.push_back(tileAnimation->withCallback(
            [actualCoords, weakSelf](std::shared_ptr<CGui> gui, SDL_EventType type, int button, int, int) {
                if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
                    if (auto self = weakSelf.lock())
                        self->startTravel(gui, actualCoords);
                    return true;
                }
                return false;
            }));
    }

    auto objects = map->getObjectsAtCoords(actualCoords);
    if (slot.objects.size() != objects.size()) {
        slot.objects.resize(objects.size());
    }
    std::size_t objectIndex = 0;
    for (const auto &ob : objects) {
        if (std::any_of(motions.begin(), motions.end(), [&](const auto &motion) {
                return motion.overlay && motion.actor.lock() == ob;
            })) {
            ++objectIndex;
            continue;
        }
        if (auto animation = syncProxyAnimation(gui, ob, slot.objects[objectIndex])) {
            return_val.push_back(animation);
        }
        objectIndex++;
    }

    if (map->getBoolProperty("showCoordinates")) {
        showCoordinates(gui, return_val, actualCoords);
    }

    auto playerController = vstd::cast<CPlayerController>(player->getController());
    auto path =
        playerController ? playerController->isOnPath(player, actualCoords) : std::make_pair(false, Coords::UNDEFINED);
    if (actualCoords == playerCoords) {
        const auto player_motion = std::find_if(motions.begin(), motions.end(),
                                                [&](const auto &motion) { return motion.actor.lock() == player; });
        const bool visually_arrived = player_motion == motions.end() || player_motion->reducedMotion ||
                                      (player_motion->started && player_motion->animation.isCompleted());
        if (visually_arrived)
            path.first = false;
        else if (player_motion->arrivalFootprint)
            path = {true, player_motion->arrivalDirection};
    }
    if (path.first) {
        showFootprint(gui, path.second, return_val);
    }

    return return_val;
}

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

void CMapGraphicsObject::showFootprint(std::shared_ptr<CGui> &gui, Coords::Direction dir,
                                       std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    auto footprint = vstd::cast<CStaticAnimation>(CAnimationProvider::getAnimation(gui->getGame(), "images/footprint"));
    switch (dir) {
    case Coords::EAST:
        footprint->setRotation(90);
        break;
    case Coords::SOUTH:
        footprint->setRotation(180);
        break;
    case Coords::WEST:
        footprint->setRotation(270);
        break;
    default:
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
    gui_async::spawn(self, gui_async::whenReady(
                               std::weak_ptr(self),
                               [](const std::shared_ptr<CMapGraphicsObject> &self) {
                                   return self->getGui() && self->getGui()->getGame() &&
                                          self->getGui()->getGame()->getMap();
                               },
                               [](const std::shared_ptr<CMapGraphicsObject> &self) {
                                   self->getGui()->getGame()->getMap()->connect("turnPassed", self, "refreshAll");
                                   self->getGui()->getGame()->getMap()->connect("tileChanged", self, "refreshObject");
                                   self->getGui()->getGame()->getMap()->connect("objectChanged", self, "refreshObject");
                                   self->refresh();
                               }));
}

void CMapGraphicsObject::previewDestination(std::shared_ptr<CGui> gui, Coords destination) {
    validateDestinationPreview(gui);
    auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!player || !player->isAlive() || map->isMoving())
        return;
    auto controller = vstd::cast<CPlayerController>(player->getController());
    if (!controller)
        return;
    destination = map->normalizeCoords(destination);
    if (previewTarget && *previewTarget == destination)
        return;
    controller->setTarget(player, destination);
    previewTarget = destination;
    previewMap = map;
    previewPlayer = player;
    previewController = controller;
    previewContext = gui->getGame()->getContext();
    previewOrigin = player->getCoords();
    previewEpoch = map->getRoutingEpoch();
    previewGeneration = gui->getGame()->getContext()->captureTransitionGeneration();
    previewRequest = controller->getRequestSerial();
    refreshAll();
}

void CMapGraphicsObject::commitDestination(std::shared_ptr<CGui> gui) {
    gui_async::spawn(this->ptr<CMapGraphicsObject>(), commitDestinationAsync(std::move(gui)));
}

vstd::task<void> CMapGraphicsObject::commitDestinationAsync(std::shared_ptr<CGui> gui) {
    return travelAsync(std::move(gui), true);
}

void CMapGraphicsObject::startTravel(std::shared_ptr<CGui> gui, Coords destination) {
    submitOrder(std::move(gui), {destination});
}

void CMapGraphicsObject::submitOrder(std::shared_ptr<CGui> gui, TravelOrder order) {
    auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    if (!map || !map->getPlayer() || !map->getPlayer()->isAlive() || !gui->isActive())
        return;
    if (map->isMoving() && !travelling)
        return;
    pendingOrder = order;
    stopRequested = false;
    if (travelling)
        return;
    travelling = true;
    try {
        gui_async::spawn(ptr<CMapGraphicsObject>(), travelAsync(std::move(gui), false));
    } catch (...) {
        travelling = false;
        pendingOrder.reset();
        throw;
    }
}

void CMapGraphicsObject::cancelTravel() {
    stopRequested = true;
    pendingOrder.reset();
}

vstd::task<void> CMapGraphicsObject::travelAsync(std::shared_ptr<CGui> gui, bool reusePreview) {
    return [](std::shared_ptr<CMapGraphicsObject> self, std::shared_ptr<CGui> gui,
              bool reusePreview) -> vstd::task<void> {
        self->validateDestinationPreview(gui);
        auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
        auto player = map ? map->getPlayer() : nullptr;
        if (!player || map->isMoving() ||
            (reusePreview && (!self->previewTarget || self->previewMap.lock() != map || self->travelling))) {
            if (!reusePreview) {
                self->travelling = false;
                self->pendingOrder.reset();
            }
            co_return;
        }
        auto controller = vstd::cast<CPlayerController>(player->getController());
        if (!controller || (reusePreview && controller != self->previewController.lock())) {
            self->clearDestinationPreview();
            self->travelling = false;
            self->pendingOrder.reset();
            co_return;
        }
        auto request = controller->getRequestSerial();
        const auto context = gui->getGame()->getContext();
        const auto generation = context->captureTransitionGeneration();
        self->travelling = true;
        if (reusePreview)
            self->stopRequested = false;
        self->clearDestinationPreview();
        ScopeExit finish([self, gui, context, controller, player, &request] {
            self->travelling = false;
            self->pendingOrder.reset();
            self->stopRequested = false;
            self->clearMotion();
            if (controller->getRequestSerial() == request)
                controller->interrupt(player);
            if (gui->isActive() && context->isActive() && self->isAttachedToGui(gui))
                self->refreshAll();
        });
        bool singleTurn = false;
        while (gui->isActive() && self->isAttachedToGui(gui) && !self->stopRequested &&
               gui->getGame()->getMap() == map && map->getPlayer() == player && player->isAlive() &&
               player->getController() == controller && context->isTransitionGenerationCurrent(generation)) {
            bool wait = false;
            if (self->pendingOrder) {
                const auto order = *std::exchange(self->pendingOrder, std::nullopt);
                singleTurn = order.singleTurn;
                wait = order.wait;
                const auto destination = order.relative ? player->getCoords() + order.destination : order.destination;
                controller->setTarget(player, destination);
                request = controller->getRequestSerial();
                if (!wait && controller->isCompleted(player)) {
                    if (map->normalizeCoords(destination) != player->getCoords())
                        gui->notify("That destination is not reachable.");
                    break;
                }
                self->refreshAll();
            } else if (controller->getRequestSerial() != request || controller->isCompleted(player)) {
                break;
            }
            if (map->isMoving())
                break;
            co_await gui->moveMapTurnAsync();
            if (singleTurn && !self->pendingOrder)
                break;
        }
    }(ptr<CMapGraphicsObject>(), std::move(gui), reusePreview);
}

void CMapGraphicsObject::clearDestinationPreview() {
    previewTarget.reset();
    previewMap.reset();
    previewPlayer.reset();
    previewController.reset();
    previewContext.reset();
    previewOrigin = ZERO;
    previewEpoch = 0;
    previewGeneration = 0;
    previewRequest = 0;
}

void CMapGraphicsObject::validateDestinationPreview(const std::shared_ptr<CGui> &gui) {
    if (!previewTarget)
        return;
    const auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    const auto player = map ? map->getPlayer() : nullptr;
    const auto controller = player ? vstd::cast<CPlayerController>(player->getController()) : nullptr;
    const auto context = gui && gui->getGame() ? gui->getGame()->getContext() : nullptr;
    if (!player || map != previewMap.lock() || player != previewPlayer.lock() || !player->isAlive() ||
        player->getCoords() != previewOrigin || controller != previewController.lock() ||
        context != previewContext.lock() || !context || !context->isTransitionGenerationCurrent(previewGeneration) ||
        map->getRoutingEpoch() != previewEpoch || !controller || controller->getRequestSerial() != previewRequest) {
        if (controller && controller == previewController.lock() && controller->getRequestSerial() == previewRequest)
            controller->interrupt(player);
        clearDestinationPreview();
    }
}

bool CMapGraphicsObject::motionIsCurrent(const std::shared_ptr<CGui> &gui, const Motion &motion) {
    if (!gui || !gui->isActive() || !isVisible())
        return false;
    const auto actor = motion.actor.lock();
    const auto map = motion.map.lock();
    const auto context = motion.context.lock();
    const auto game = gui->getGame();
    return actor && map && context && context->isActive() &&
           context->isTransitionGenerationCurrent(motion.generation) && game && game->getMap() == map &&
           actor->getMap() == map && map->getObjectByName(actor->getName()) == actor &&
           actor->getCoords() == motion.destination;
}

bool CMapGraphicsObject::stepNeedsSequentialPresentation(const std::shared_ptr<CMapObject> &actor, Coords origin,
                                                         Coords destination) {
    const auto creature = std::dynamic_pointer_cast<CCreature>(actor);
    const auto map = actor ? actor->getMap() : nullptr;
    if (!creature || !map || (typeid(*creature) != typeid(CCreature) && typeid(*creature) != typeid(CPlayer)) ||
        !hasKnownMovementController(creature->getController()) || CLuaOverrides::find(actor.get()) ||
        hasMovementPythonHook(actor.get(), {"beforeMove", "beforeMoveAsync", "afterMove", "afterMoveAsync", "onLeave",
                                            "onLeaveFlow", "onEnter", "onEnterFlow"}) ||
        hasMovementPythonHook(creature->getController().get(), {"onStepCommitted", "onTurnEnded", "interrupt"}))
        return true;
    for (const auto endpoint : {origin, destination}) {
        for (const auto &object : map->getObjectsAtCoords(endpoint)) {
            if (object != actor && std::dynamic_pointer_cast<CVisitable>(object))
                return true;
        }
    }
    const auto tile = map->getTile(destination);
    if (!tile || (typeid(*tile) != typeid(CTile) && typeid(*tile) != typeid(CWrapper<CTile>)) ||
        CLuaOverrides::find(tile.get()) || hasMovementPythonHook(tile.get(), {"onStep", "onStepFlow"}))
        return true;
    for (const auto &trigger : map->getEventHandler()->getTriggers()) {
        if (trigger && trigger->getObject() == actor->getName() &&
            (trigger->getEvent() == "onLeave" || trigger->getEvent() == "onEnter"))
            return true;
    }
    return false;
}

CMovementPresenter CMapGraphicsObject::movementPresenter(std::shared_ptr<CGui> gui) {
    return [owner = std::weak_ptr(ptr<CMapGraphicsObject>()), gui = std::weak_ptr(gui)](
               std::shared_ptr<CMapObject> actor, Coords origin, Coords destination) -> vstd::task<void> {
        auto view = owner.lock();
        auto activeGui = gui.lock();
        if (view && activeGui)
            return view->presentMoveAsync(std::move(activeGui), std::move(actor), origin, destination);
        return emptyMovementPresentation();
    };
}

CMovementPresentation CMapGraphicsObject::movementPresentation(std::shared_ptr<CGui> gui) {
    const auto owner = std::weak_ptr(ptr<CMapGraphicsObject>());
    const auto weakGui = std::weak_ptr(gui);
    const auto batch = std::make_shared<PresentationBatch>();
    CMovementPresentation presentation;
    presentation.beforeStep = [owner, weakGui, batch](std::shared_ptr<CMapObject> actor, Coords origin,
                                                      Coords destination) {
        auto self = owner.lock();
        auto gui = weakGui.lock();
        return self && gui
                   ? self->preparePresentationStepAsync(std::move(gui), batch, std::move(actor), origin, destination)
                   : emptyMovementPresentation();
    };
    presentation.presentStep = [owner, weakGui, batch](std::shared_ptr<CMapObject> actor, Coords origin,
                                                       Coords destination) {
        auto self = owner.lock();
        auto gui = weakGui.lock();
        return self && gui
                   ? self->presentPresentationStepAsync(std::move(gui), batch, std::move(actor), origin, destination)
                   : emptyMovementPresentation();
    };
    presentation.finish = [owner, weakGui, batch] {
        batch->occupied.clear();
        auto self = owner.lock();
        auto gui = weakGui.lock();
        return self && gui ? self->finishMotionBatchAsync(std::move(gui)) : emptyMovementPresentation();
    };
    presentation.cancel = [owner, weakGui, batch] {
        batch->occupied.clear();
        if (auto self = owner.lock()) {
            self->clearMotion();
            auto gui = weakGui.lock();
            if (gui && gui->isActive() && self->isAttachedToGui(gui) && gui->getGame() &&
                gui->getGame()->getContext()->isActive())
                self->refreshAll();
        }
    };
    return presentation;
}

vstd::task<void> CMapGraphicsObject::preparePresentationStepAsync(std::shared_ptr<CGui> gui,
                                                                  std::shared_ptr<PresentationBatch> batch,
                                                                  std::shared_ptr<CMapObject> actor, Coords origin,
                                                                  Coords destination) {
    return [](std::shared_ptr<CMapGraphicsObject> self, std::shared_ptr<CGui> gui,
              std::shared_ptr<PresentationBatch> batch, std::shared_ptr<CMapObject> actor, Coords origin,
              Coords destination) -> vstd::task<void> {
        const auto map = actor ? actor->getMap() : nullptr;
        if (!map)
            co_return;
        const auto footprint = CMovementBatch::interactionCells(*map, origin, destination);
        batch->sequential = self->stepNeedsSequentialPresentation(actor, origin, destination);
        if (batch->sequential || batch->occupied.conflicts(footprint)) {
            co_await self->finishMotionBatchAsync(gui);
            batch->occupied.clear();
            batch->sequential = self->stepNeedsSequentialPresentation(actor, origin, destination);
        }
        batch->arrivalFootprint.reset();
        if (const auto player = map->getPlayer(); player == actor) {
            if (const auto controller = std::dynamic_pointer_cast<CPlayerController>(player->getController()))
                batch->arrivalFootprint = controller->isOnPath(player, destination);
        }
    }(ptr<CMapGraphicsObject>(), std::move(gui), std::move(batch), std::move(actor), origin, destination);
}

vstd::task<void> CMapGraphicsObject::presentPresentationStepAsync(std::shared_ptr<CGui> gui,
                                                                  std::shared_ptr<PresentationBatch> batch,
                                                                  std::shared_ptr<CMapObject> actor, Coords origin,
                                                                  Coords destination) {
    return [](std::shared_ptr<CMapGraphicsObject> self, std::shared_ptr<CGui> gui,
              std::shared_ptr<PresentationBatch> batch, std::shared_ptr<CMapObject> actor, Coords origin,
              Coords destination) -> vstd::task<void> {
        if (batch->sequential || self->stepNeedsSequentialPresentation(actor, origin, destination)) {
            co_await self->finishMotionBatchAsync(gui);
            batch->occupied.clear();
            co_await self->presentMoveAsync(std::move(gui), std::move(actor), origin, destination);
        } else if (self->enqueueMotion(gui, actor, origin, destination, batch->arrivalFootprint)) {
            if (const auto map = actor->getMap())
                batch->occupied.add(CMovementBatch::interactionCells(*map, origin, destination));
        }
    }(ptr<CMapGraphicsObject>(), std::move(gui), std::move(batch), std::move(actor), origin, destination);
}

bool CMapGraphicsObject::enqueueMotion(const std::shared_ptr<CGui> &gui, const std::shared_ptr<CMapObject> &actor,
                                       Coords origin, Coords destination,
                                       std::optional<std::pair<bool, Coords::Direction>> arrivalFootprint) {
    const auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    const auto player = map ? map->getPlayer() : nullptr;
    if (!player || !actor || actor->getMap() != map || !gui->isActive() || !gui->getRenderer() ||
        !isAttachedToGui(gui) || !isVisible() || origin.z != destination.z || destination.z != player->getCoords().z)
        return false;
    const auto delta = map->getShortestDelta(origin, destination);
    if (delta.z || std::abs(delta.x) + std::abs(delta.y) != 1)
        return false;
    auto inView = [&](Coords coords) {
        const auto distance = map->getShortestDelta(player->getCoords(), coords);
        return std::abs(distance.x) <= gui->getTileCountX() / 2 + 1 &&
               std::abs(distance.y) <= gui->getTileCountY() / 2 + 1;
    };
    if (!inView(origin) && !inView(destination))
        return false;
    const auto self = ptr<CMapGraphicsObject>();
    Motion motion;
    motion.actor = actor;
    motion.map = map;
    motion.context = gui->getGame()->getContext();
    motion.destination = destination;
    motion.delta = delta;
    motion.generation = gui->getGame()->getContext()->captureTransitionGeneration();
    motion.reducedMotion = json::parse(gui->getUiPreferences()).value("reducedMotion", false);
    motion.movesCamera = actor == player;
    if (motion.movesCamera) {
        if (!arrivalFootprint && map->isMoving()) {
            if (const auto controller = std::dynamic_pointer_cast<CPlayerController>(player->getController()))
                arrivalFootprint = controller->isOnPath(player, destination);
        }
        if (arrivalFootprint) {
            motion.arrivalFootprint = arrivalFootprint->first;
            motion.arrivalDirection = arrivalFootprint->second;
        }
    }
    if (const auto cached = actor->getGraphicsObject()) {
        motion.overlay = clone_proxy_animation(gui, cached);
        motion.overlay->setObject(actor);
        motion.overlay->setLayout(std::make_shared<CMapMotionLayout>(self, actor));
        motion.overlays.push_back(motion.overlay);
        if (map->wrapsX(destination.z) || map->wrapsY(destination.z)) {
            const auto primary = mapToGui(gui, destination);
            for (const auto &child : getChildren()) {
                const auto proxy = vstd::cast<CProxyGraphicsObject>(child);
                if (!proxy)
                    continue;
                const Coords cell(proxy->getX(), proxy->getY(), destination.z);
                if (cell == primary || guiToMap(gui, cell) != destination)
                    continue;
                auto overlay = clone_proxy_animation(gui, cached);
                overlay->setObject(actor);
                overlay->setLayout(std::make_shared<CMapMotionLayout>(self, actor, cell - primary));
                motion.overlays.push_back(std::move(overlay));
            }
        }
    }
    motions.push_back(std::move(motion));
    for (const auto &overlay : motions.back().overlays)
        pushChild(overlay);
    if (actor == player)
        refreshAll();
    else {
        refreshObject(origin);
        refreshObject(destination);
    }
    return true;
}

vstd::task<void> CMapGraphicsObject::finishMotionBatchAsync(std::shared_ptr<CGui> gui) {
    return [](std::shared_ptr<CMapGraphicsObject> self, std::shared_ptr<CGui> gui) -> vstd::task<void> {
        if (self->motions.empty())
            co_return;
        ScopeExit clear([self, gui] {
            self->clearMotion();
            if (gui->isActive() && self->isAttachedToGui(gui) && gui->getGame() &&
                gui->getGame()->getContext()->isActive())
                self->refreshAll();
        });
        self->motionBatchStarted = true;
        self->refreshAll();
        const auto loop = vstd::event_loop<>::instance();
        while (!loop->quitRequested() && self->isAttachedToGui(gui) &&
               std::any_of(self->motions.begin(), self->motions.end(), [&](const auto &motion) {
                   return self->motionIsCurrent(gui, motion) && (!motion.started || !motion.animation.isCompleted());
               }))
            co_await vstd::nextFrame(loop);
    }(ptr<CMapGraphicsObject>(), std::move(gui));
}

vstd::task<void> CMapGraphicsObject::presentMoveAsync(std::shared_ptr<CGui> gui, std::shared_ptr<CMapObject> actor,
                                                      Coords origin, Coords destination) {
    return [](std::shared_ptr<CMapGraphicsObject> self, std::shared_ptr<CGui> gui, std::shared_ptr<CMapObject> actor,
              Coords origin, Coords destination) -> vstd::task<void> {
        if (self->enqueueMotion(gui, actor, origin, destination))
            co_await self->finishMotionBatchAsync(std::move(gui));
    }(ptr<CMapGraphicsObject>(), std::move(gui), std::move(actor), origin, destination);
}

SDL_Point CMapGraphicsObject::getCameraOffset(int tileSize) const {
    const auto motion =
        std::find_if(motions.begin(), motions.end(), [](const auto &entry) { return entry.movesCamera; });
    if (motion == motions.end() || motion->reducedMotion)
        return {0, 0};
    if (!motion->started)
        return {motion->delta.x * tileSize, motion->delta.y * tileSize};
    return motion->animation.cameraOffset(tileSize);
}

SDL_Point CMapGraphicsObject::getActorOffset(const std::shared_ptr<CGameObject> &object, int tileSize) const {
    const auto motion =
        std::find_if(motions.begin(), motions.end(), [&](const auto &entry) { return entry.actor.lock() == object; });
    if (motion == motions.end() || motion->reducedMotion)
        return {0, 0};
    if (!motion->started)
        return {-motion->delta.x * tileSize, -motion->delta.y * tileSize};
    return motion->animation.actorOffset(tileSize);
}

void CMapGraphicsObject::clearMotion() {
    auto retired = std::move(motions);
    motions.clear();
    motionBatchStarted = false;
    for (const auto &motion : retired)
        for (const auto &overlay : motion.overlays)
            removeChild(overlay);
}

std::shared_ptr<SDL_Rect> CMapGraphicsObject::getMotionRect() {
    return getMotionRect(motions.empty() ? nullptr : motions.front().actor.lock());
}

std::shared_ptr<SDL_Rect> CMapGraphicsObject::getMotionRect(const std::shared_ptr<CGameObject> &object) {
    const auto found =
        std::find_if(motions.begin(), motions.end(), [&](const auto &motion) { return motion.actor.lock() == object; });
    const auto gui = getGui();
    const auto map = found == motions.end() ? nullptr : found->map.lock();
    const auto actor = found == motions.end() ? nullptr : found->actor.lock();
    const auto player = map ? map->getPlayer() : nullptr;
    if (!gui || !actor || !player || !getLayout())
        return CUtil::rect(0, 0, 0, 0);
    const auto viewport = getLayout()->getRect(ptr<CGameGraphicsObject>());
    const auto delta = map->getShortestDelta(player->getCoords(), found->destination);
    const int tileSize = getTileSize(ptr<CGameGraphicsObject>());
    const auto camera = getCameraOffset(tileSize);
    const auto sprite = getActorOffset(actor, tileSize);
    return CUtil::rect(viewport->x + (delta.x + gui->getTileCountX() / 2) * tileSize + camera.x + sprite.x,
                       viewport->y + (delta.y + gui->getTileCountY() / 2) * tileSize + camera.y + sprite.y, tileSize,
                       tileSize);
}

bool CMapGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (!event || !getLayout())
        return false;
    SDL_Point point{};
    bool positional = true;
    switch (event->type) {
    case SDL_MOUSEBUTTONDOWN:
    case SDL_MOUSEBUTTONUP:
        point = {event->button.x, event->button.y};
        break;
    case SDL_MOUSEMOTION:
        point = {event->motion.x, event->motion.y};
        break;
    case SDL_MOUSEWHEEL:
#if SDL_VERSION_ATLEAST(2, 26, 0)
        point = {event->wheel.mouseX, event->wheel.mouseY};
#else
        SDL_GetMouseState(&point.x, &point.y);
#endif
        break;
    default:
        positional = false;
    }
    if (positional && !SDL_PointInRect(&point, getLayout()->getRect(ptr<CGameGraphicsObject>()).get()))
        return false;
    return CGameGraphicsObject::event(std::move(gui), event);
}

void CMapGraphicsObject::render(std::shared_ptr<CGui> gui, int frameTime) {
    auto renderer = gui ? gui->getRenderer() : nullptr;
    if (!renderer || !getLayout())
        return;
    SDL_Rect previous{};
    const bool clipped = SDL_RenderIsClipEnabled(renderer);
    SDL_RenderGetClipRect(renderer, &previous);
    auto viewport = *getLayout()->getRect(ptr<CGameGraphicsObject>());
    if (clipped)
        SDL_IntersectRect(&previous, &viewport, &viewport);
    SDL_RenderSetClipRect(renderer, &viewport);
    ScopeExit restore([gui, renderer, clipped, previous] {
        if (gui->getRenderer() == renderer)
            SDL_RenderSetClipRect(renderer, clipped ? &previous : nullptr);
    });
    CGameGraphicsObject::render(std::move(gui), frameTime);
}

void CMapGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect>, int frameTime) {
    validateDestinationPreview(gui);
    const auto previous_count = motions.size();
    std::erase_if(motions, [&](const auto &motion) {
        if (motionIsCurrent(gui, motion))
            return false;
        for (const auto &overlay : motion.overlays)
            removeChild(overlay);
        return true;
    });
    if (motions.size() != previous_count)
        refreshAll();
    if (!motionBatchStarted)
        return;
    std::optional<Coords> player_arrival;
    for (auto &motion : motions) {
        if (!motionIsCurrent(gui, motion))
            continue;
        const bool was_started = motion.started;
        const bool was_completed = motion.started && motion.animation.isCompleted();
        if (!motion.started) {
            motion.animation.begin(motion.delta, static_cast<Uint32>(frameTime), motion.reducedMotion,
                                   motion.movesCamera);
            motion.started = true;
        } else {
            motion.animation.advance(static_cast<Uint32>(frameTime));
        }
        if (motion.movesCamera &&
            ((!was_completed && motion.animation.isCompleted()) || (!was_started && motion.reducedMotion)))
            player_arrival = motion.destination;
    }
    if (player_arrival)
        refreshObject(*player_arrival);
}

int CMapGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) { return gui->getTileCountY() + 2; }

int CMapGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) { return gui->getTileCountX() + 2; }

bool CMapGraphicsObject::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        validateDestinationPreview(gui);
        if (!gui->getGame() || !gui->getGame()->getMap())
            return false;
        if (i == SDLK_RETURN && previewTarget) {
            commitDestination(gui);
            return true;
        }
        std::shared_ptr<CPlayer> player = gui->getGame()->getMap()->getPlayer();
        if (!player) {
            return false;
        }
        auto controller = vstd::cast<CPlayerController>(player->getController());
        if (!controller) {
            return false;
        }
        if (i == SDLK_UP || i == SDLK_DOWN || i == SDLK_LEFT || i == SDLK_RIGHT || i == SDLK_SPACE)
            clearDestinationPreview();
        switch (i) {
        case SDLK_UP:
            submitOrder(gui, {NORTH, true, true});
            return true;
        case SDLK_DOWN:
            submitOrder(gui, {SOUTH, true, true});
            return true;
        case SDLK_LEFT:
            submitOrder(gui, {WEST, true, true});
            return true;
        case SDLK_RIGHT:
            submitOrder(gui, {EAST, true, true});
            return true;
        case SDLK_SPACE:
            submitOrder(gui, {ZERO, true, true, true});
            return true;
        case SDLK_s:
            gui->getGame()->getContext()->spawnTask(gui->getGame()->getGuiHandler()->showSaveMenuAsync());
            return true;
        }
    }
    return false;
}

Coords CMapGraphicsObject::mapToGui(std::shared_ptr<CGui> gui, Coords coords) {
    auto map = gui->getGame()->getMap();
    auto player = map ? map->getPlayer() : nullptr;
    if (!player) {
        return ZERO;
    }
    auto playerCoords = player->getCoords();
    auto delta = map->getShortestDelta(playerCoords, coords);
    return Coords(delta.x + gui->getTileCountX() / 2 + 1, delta.y + gui->getTileCountY() / 2 + 1, coords.z);
}

Coords CMapGraphicsObject::guiToMap(std::shared_ptr<CGui> gui, Coords coords) {
    auto map = gui->getGame()->getMap();
    auto player = map ? map->getPlayer() : nullptr;
    if (!player) {
        return ZERO;
    }
    auto playerCoords = player->getCoords();
    auto raw = Coords(playerCoords.x - gui->getTileCountX() / 2 + coords.x - 1,
                      playerCoords.y - gui->getTileCountY() / 2 + coords.y - 1, playerCoords.z);
    return map->normalizeCoords(raw);
}

void CMapGraphicsObject::refreshObject(Coords coords) {
    auto gui = getGui();
    if (!gui || !gui->getGame()) {
        return;
    }
    auto map = gui->getGame()->getMap();
    if (!map || !map->getPlayer()) {
        return;
    }
    Coords normalized = map->normalizeCoords(coords);

    // Player relocation changes the camera origin used by every cached tile callback.
    if (normalized == map->getPlayer()->getCoords()) {
        refreshAll();
        return;
    }

    if (map->wrapsX(normalized.z) || map->wrapsY(normalized.z)) {
        for (int x = 0; x < getSizeX(gui); x++) {
            for (int y = 0; y < getSizeY(gui); y++) {
                if (guiToMap(gui, Coords(x, y, normalized.z)) == normalized) {
                    CProxyTargetGraphicsObject::refreshObject(x, y);
                }
            }
        }
        return;
    }

    auto translated = mapToGui(gui, normalized);
    CProxyTargetGraphicsObject::refreshObject(translated.x, translated.y);
}

void CMapGraphicsObject::onProxyGridResized(int sizeX, int sizeY) {
    auto gui = getGui();
    for (const auto &child : getChildren()) {
        if (vstd::cast<CProxyGraphicsObject>(child)) {
            auto layout = std::make_shared<CMapProxyLayout>(ptr<CMapGraphicsObject>());
            layout->setTileSize(getTileSize(ptr<CGameGraphicsObject>()));
            child->setLayout(std::move(layout));
        }
    }
    auto map = gui->getGame()->getMap();
    if (!map) {
        proxyAnimations.clear();
        cachedMap.reset();
        hasCachedProxyZ = false;
        return;
    }
    auto player = map->getPlayer();
    if (!player) {
        proxyAnimations.clear();
        return;
    }
    pruneProxyAnimationCache(sizeX, sizeY, player->getCoords().z);
}

void CMapGraphicsObject::pruneProxyAnimationCache(int sizeX, int sizeY, int z) {
    for (auto it = proxyAnimations.begin(); it != proxyAnimations.end();) {
        const auto &coords = it->first;
        if (coords.x < 0 || coords.x >= sizeX || coords.y < 0 || coords.y >= sizeY || coords.z != z) {
            it = proxyAnimations.erase(it);
        } else {
            ++it;
        }
    }
}
