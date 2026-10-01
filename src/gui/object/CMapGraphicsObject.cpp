#include "gui/object/CMapGraphicsObject.h"
#include "CWidget.h"
#include "core/CController.h"
#include "core/CLoader.h"
#include "gui/CAnimation.h"
#include "gui/CLayout.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/panel/CGameInventoryPanel.h"

#include <algorithm>

namespace {
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
    auto rawCoords = Coords(playerCoords.x - tileCountX / 2 + x, playerCoords.y - tileCountY / 2 + y, playerCoords.z);
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
                        self->previewDestination(gui, actualCoords);
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
    vstd::call_when(
        [self]() { return self->getGui() && self->getGui()->getGame() && self->getGui()->getGame()->getMap(); },
        [self]() {
            self->getGui()->getGame()->getMap()->connect("turnPassed", self, "refreshAll");
            self->getGui()->getGame()->getMap()->connect("tileChanged", self, "refreshObject");
            self->getGui()->getGame()->getMap()->connect("objectChanged", self, "refreshObject");
            self->refresh();
            auto action = self->getGui()->getGame()->createObject<CButton>();
            action->setText("Travel to destination  Enter");
            action->setClick("commitDestination");
            auto layout = std::make_shared<CLayout>();
            layout->setHorizontal("CENTER");
            layout->setVertical("DOWN");
            layout->setW("400");
            layout->setH("56");
            action->setLayout(layout);
            action->setPriority(10);
            action->setRuntimeHidden(true);
            self->destinationButton = action;
            self->addChild(action);
        });
}

void CMapGraphicsObject::previewDestination(std::shared_ptr<CGui> gui, Coords destination) {
    auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!player || !player->isAlive() || map->isMoving())
        return;
    auto controller = vstd::cast<CPlayerController>(player->getController());
    if (!controller)
        return;
    controller->setTarget(player, destination);
    previewTarget = destination;
    previewMap = map;
    previewPlayer = player;
    previewOrigin = player->getCoords();
    if (destinationButton)
        destinationButton->setRuntimeHidden(false);
    gui->notify("Destination " + std::to_string(destination.x) + ", " + std::to_string(destination.y) +
                ". Inspect the route, then choose Travel to destination.");
    refreshAll();
}

void CMapGraphicsObject::commitDestination(std::shared_ptr<CGui> gui) {
    validateDestinationPreview(gui);
    auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!player || !previewTarget || previewMap.lock() != map || map->isMoving())
        return;
    auto controller = vstd::cast<CPlayerController>(player->getController());
    if (!controller) {
        clearDestinationPreview();
        return;
    }
    controller->setTarget(player, *previewTarget);
    clearDestinationPreview();
    const int maxSteps = std::max(1, gui->getTileCountX() * gui->getTileCountY() * 4);
    for (int step = 0; step < maxSteps && gui->getGame()->getMap() == map && !controller->isCompleted(player); ++step)
        map->move();
}

void CMapGraphicsObject::clearDestinationPreview() {
    previewTarget.reset();
    previewMap.reset();
    previewPlayer.reset();
    previewOrigin = ZERO;
    if (destinationButton)
        destinationButton->setRuntimeHidden(true);
}

void CMapGraphicsObject::validateDestinationPreview(const std::shared_ptr<CGui> &gui) {
    if (!previewTarget)
        return;
    const auto map = gui && gui->getGame() ? gui->getGame()->getMap() : nullptr;
    const auto player = map ? map->getPlayer() : nullptr;
    if (!player || map != previewMap.lock() || player != previewPlayer.lock() || !player->isAlive() ||
        player->getCoords() != previewOrigin) {
        clearDestinationPreview();
    }
}

void CMapGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect>, int) {
    validateDestinationPreview(gui);
}

int CMapGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) { return gui->getTileCountY(); }

int CMapGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) { return gui->getTileCountX(); }

bool CMapGraphicsObject::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        validateDestinationPreview(gui);
        if (!gui->getGame() || !gui->getGame()->getMap())
            return false;
        if (i == SDLK_RETURN && previewTarget) {
            commitDestination(gui);
            return true;
        }
        if (gui->getGame()->getMap()->isMoving()) {
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
            controller->setTarget(player, player->getCoords() + NORTH);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_DOWN:
            controller->setTarget(player, player->getCoords() + SOUTH);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_LEFT:
            controller->setTarget(player, player->getCoords() + WEST);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_RIGHT:
            controller->setTarget(player, player->getCoords() + EAST);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_SPACE:
            controller->setTarget(player, player->getCoords() + ZERO);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_s:
            gui->getGame()->getGuiHandler()->showSaveMenu();
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
    return Coords(delta.x + gui->getTileCountX() / 2, delta.y + gui->getTileCountY() / 2, coords.z);
}

Coords CMapGraphicsObject::guiToMap(std::shared_ptr<CGui> gui, Coords coords) {
    auto map = gui->getGame()->getMap();
    auto player = map ? map->getPlayer() : nullptr;
    if (!player) {
        return ZERO;
    }
    auto playerCoords = player->getCoords();
    auto raw = Coords(playerCoords.x - gui->getTileCountX() / 2 + coords.x,
                      playerCoords.y - gui->getTileCountY() / 2 + coords.y, playerCoords.z);
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
