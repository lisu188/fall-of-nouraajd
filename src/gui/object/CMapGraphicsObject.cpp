#include "gui/object/CMapGraphicsObject.h"
#include "CWidget.h"
#include "core/CController.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "gui/CAnimation.h"
#include "gui/CGuiTasks.h"
#include "gui/CLayout.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/panel/CGameInventoryPanel.h"

#include <algorithm>

namespace {
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
    explicit CMapMotionLayout(std::weak_ptr<CMapGraphicsObject> owner, Coords offset = ZERO)
        : owner(std::move(owner)), offset(offset) {}

    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject>) override {
        if (auto view = owner.lock()) {
            auto rect = view->getMotionRect();
            rect->x += offset.x * rect->w;
            rect->y += offset.y * rect->h;
            return rect;
        }
        return CUtil::rect(0, 0, 0, 0);
    }

  private:
    std::weak_ptr<CMapGraphicsObject> owner;
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
        if (motion && motion->overlay && motion->actor.lock() == ob) {
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
            if (controller->getRequestSerial() == request)
                controller->interrupt(player);
            self->travelling = false;
            self->pendingOrder.reset();
            self->stopRequested = false;
            self->clearMotion();
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

bool CMapGraphicsObject::motionIsCurrent(const std::shared_ptr<CGui> &gui) {
    if (!motion || !gui || !gui->isActive() || !isVisible())
        return false;
    const auto actor = motion->actor.lock();
    const auto map = motion->map.lock();
    const auto context = motion->context.lock();
    const auto game = gui->getGame();
    return actor && map && context && context->isActive() &&
           context->isTransitionGenerationCurrent(motion->generation) && game && game->getMap() == map &&
           actor->getMap() == map && map->getObjectByName(actor->getName()) == actor &&
           actor->getCoords() == motion->destination;
}

CMovementPresenter CMapGraphicsObject::movementPresenter(std::shared_ptr<CGui> gui) {
    return [owner = std::weak_ptr(ptr<CMapGraphicsObject>()), gui = std::weak_ptr(gui)](
               std::shared_ptr<CMapObject> actor, Coords origin, Coords destination) -> vstd::task<void> {
        auto view = owner.lock();
        auto activeGui = gui.lock();
        if (view && activeGui)
            return view->presentMoveAsync(std::move(activeGui), std::move(actor), origin, destination);
        return [](std::shared_ptr<CMapObject>) -> vstd::task<void> { co_return; }(std::move(actor));
    };
}

vstd::task<void> CMapGraphicsObject::presentMoveAsync(std::shared_ptr<CGui> gui, std::shared_ptr<CMapObject> actor,
                                                      Coords origin, Coords destination) {
    return [](std::shared_ptr<CMapGraphicsObject> self, std::shared_ptr<CGui> gui, std::shared_ptr<CMapObject> actor,
              Coords origin, Coords destination) -> vstd::task<void> {
        auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
        auto player = map ? map->getPlayer() : nullptr;
        if (!player || !actor || actor->getMap() != map || !gui->isActive() || !gui->getRenderer() ||
            !self->isAttachedToGui(gui) || !self->isVisible() || origin.z != destination.z ||
            destination.z != player->getCoords().z)
            co_return;
        const auto delta = map->getShortestDelta(origin, destination);
        if (delta.z || std::abs(delta.x) + std::abs(delta.y) != 1)
            co_return;
        auto inView = [&](Coords coords) {
            const auto distance = map->getShortestDelta(player->getCoords(), coords);
            return std::abs(distance.x) <= gui->getTileCountX() / 2 + 1 &&
                   std::abs(distance.y) <= gui->getTileCountY() / 2 + 1;
        };
        if (!inView(origin) && !inView(destination))
            co_return;
        auto context = gui->getGame()->getContext();
        Motion motion;
        motion.actor = actor;
        motion.map = map;
        motion.context = context;
        motion.destination = destination;
        motion.delta = delta;
        motion.generation = context->captureTransitionGeneration();
        motion.reducedMotion = json::parse(gui->getUiPreferences()).value("reducedMotion", false);
        motion.movesCamera = actor == player;
        if (const auto cached = actor->getGraphicsObject()) {
            motion.overlay = clone_proxy_animation(gui, cached);
            motion.overlay->setObject(actor);
            motion.overlay->setLayout(std::make_shared<CMapMotionLayout>(self));
            motion.overlays.push_back(motion.overlay);
            if (map->wrapsX(destination.z) || map->wrapsY(destination.z)) {
                const auto primary = self->mapToGui(gui, destination);
                for (const auto &child : self->getChildren()) {
                    const auto proxy = vstd::cast<CProxyGraphicsObject>(child);
                    if (!proxy)
                        continue;
                    const Coords cell(proxy->getX(), proxy->getY(), destination.z);
                    if (cell == primary || self->guiToMap(gui, cell) != destination)
                        continue;
                    auto overlay = clone_proxy_animation(gui, cached);
                    overlay->setObject(actor);
                    overlay->setLayout(std::make_shared<CMapMotionLayout>(self, cell - primary));
                    motion.overlays.push_back(std::move(overlay));
                }
            }
        }
        self->motion = std::move(motion);
        ScopeExit clear([self, gui, context, map, origin, destination, player, actor] {
            self->clearMotion();
            if (gui->isActive() && context->isActive() && self->isAttachedToGui(gui) && gui->getGame() &&
                gui->getGame()->getMap() == map) {
                if (actor == player)
                    self->refreshAll();
                else {
                    self->refreshObject(origin);
                    self->refreshObject(destination);
                }
            }
        });
        for (const auto &overlay : self->motion->overlays)
            self->pushChild(overlay);
        if (actor == player) {
            self->refreshAll();
        } else {
            self->refreshObject(origin);
            self->refreshObject(destination);
        }
        auto loop = vstd::event_loop<>::instance();
        while (self->motionIsCurrent(gui) && self->isAttachedToGui(gui) &&
               (!self->motion->started || !self->motion->animation.isCompleted()))
            co_await vstd::nextFrame(loop);
    }(ptr<CMapGraphicsObject>(), std::move(gui), std::move(actor), origin, destination);
}

SDL_Point CMapGraphicsObject::getCameraOffset(int tileSize) const {
    if (!motion || !motion->movesCamera || motion->reducedMotion)
        return {0, 0};
    if (!motion->started)
        return {motion->delta.x * tileSize, motion->delta.y * tileSize};
    return motion->animation.cameraOffset(tileSize);
}

SDL_Point CMapGraphicsObject::getActorOffset(const std::shared_ptr<CGameObject> &object, int tileSize) const {
    if (!motion || motion->actor.lock() != object || motion->reducedMotion)
        return {0, 0};
    if (!motion->started)
        return {-motion->delta.x * tileSize, -motion->delta.y * tileSize};
    return motion->animation.actorOffset(tileSize);
}

void CMapGraphicsObject::clearMotion() {
    auto overlays = motion ? std::move(motion->overlays) : std::vector<std::shared_ptr<CAnimation>>{};
    motion.reset();
    for (const auto &overlay : overlays)
        removeChild(overlay);
}

std::shared_ptr<SDL_Rect> CMapGraphicsObject::getMotionRect() {
    auto gui = getGui();
    auto map = motion ? motion->map.lock() : nullptr;
    auto actor = motion ? motion->actor.lock() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!gui || !actor || !player || !getLayout())
        return CUtil::rect(0, 0, 0, 0);
    auto viewport = getLayout()->getRect(ptr<CGameGraphicsObject>());
    const auto delta = map->getShortestDelta(player->getCoords(), motion->destination);
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
    if (motion) {
        if (!motionIsCurrent(gui)) {
            clearMotion();
        } else if (!motion->started) {
            motion->animation.begin(motion->delta, static_cast<Uint32>(frameTime), motion->reducedMotion,
                                    motion->movesCamera);
            motion->started = true;
        } else {
            motion->animation.advance(static_cast<Uint32>(frameTime));
        }
    }
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
