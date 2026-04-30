#include "gui/object/CMapGraphicsObject.h"
#include "CWidget.h"
#include "core/CController.h"
#include "core/CLoader.h"
#include "gui/CAnimation.h"
#include "gui/CLayout.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/panel/CGameInventoryPanel.h"

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
    auto cached = object->getGraphicsObject();
    if (!animation || animation->meta()->name() != cached->meta()->name()) {
        animation = clone_proxy_animation(gui, cached);
    }
    animation->setObject(object);
    animation->setPriority(cached->getPriority());
    return animation;
}

std::list<std::shared_ptr<CGameGraphicsObject>> CMapGraphicsObject::getProxiedObjects(std::shared_ptr<CGui> gui, int x,
                                                                                      int y) {
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
    return_val.push_back(
        syncProxyAnimation(gui, tile, slot.tile)
            ->withCallback([actualCoords](std::shared_ptr<CGui> gui, SDL_EventType type, int button, int, int) {
                if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
                    auto game = gui->getGame();
                    auto map = game->getMap();
                    auto player = map->getPlayer();
                    auto controller = vstd::cast<CPlayerController>(player->getController());
                    if (!controller) {
                        return false;
                    }
                    controller->setTarget(player, actualCoords);
                    if (!map->isMoving()) {
                        while (!controller->isCompleted(player)) {
                            map->move();
                        }
                    }
                    return true;
                }
                return false;
            }));

    auto objects = map->getObjectsAtCoords(actualCoords);
    if (slot.objects.size() != objects.size()) {
        slot.objects.resize(objects.size());
    }
    std::size_t objectIndex = 0;
    for (const auto &ob : objects) {
        return_val.push_back(syncProxyAnimation(gui, ob, slot.objects[objectIndex]));
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
        });
}

int CMapGraphicsObject::getSizeY(std::shared_ptr<CGui> gui) { return gui->getTileCountY(); }

int CMapGraphicsObject::getSizeX(std::shared_ptr<CGui> gui) { return gui->getTileCountX(); }

bool CMapGraphicsObject::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) {
    if (type == SDL_KEYDOWN) {
        if (gui->getGame()->getMap()->isMoving()) {
            return true;
        }
        std::shared_ptr<CPlayer> player = gui->getGame()->getMap()->getPlayer();
        switch (i) {
        case SDLK_UP:
            vstd::cast<CPlayerController>(player->getController())->setTarget(player, player->getCoords() + NORTH);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_DOWN:
            vstd::cast<CPlayerController>(player->getController())->setTarget(player, player->getCoords() + SOUTH);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_LEFT:
            vstd::cast<CPlayerController>(player->getController())->setTarget(player, player->getCoords() + WEST);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_RIGHT:
            vstd::cast<CPlayerController>(player->getController())->setTarget(player, player->getCoords() + EAST);
            gui->getGame()->getMap()->move();
            return true;
        case SDLK_SPACE:
            vstd::cast<CPlayerController>(player->getController())->setTarget(player, player->getCoords() + ZERO);
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
    auto map = gui->getGame()->getMap();
    auto playerCoords = map->getPlayer()->getCoords();
    auto delta = map->getShortestDelta(playerCoords, coords);
    return Coords(delta.x + gui->getTileCountX() / 2, delta.y + gui->getTileCountY() / 2, coords.z);
}

Coords CMapGraphicsObject::guiToMap(std::shared_ptr<CGui> gui, Coords coords) {
    auto map = gui->getGame()->getMap();
    auto playerCoords = map->getPlayer()->getCoords();
    auto raw = Coords(playerCoords.x - gui->getTileCountX() / 2 + coords.x,
                      playerCoords.y - gui->getTileCountY() / 2 + coords.y, playerCoords.z);
    return map->normalizeCoords(raw);
}

void CMapGraphicsObject::refreshObject(Coords coords) {
    auto gui = getGui();
    auto map = gui->getGame()->getMap();
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
