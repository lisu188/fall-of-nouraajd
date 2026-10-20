/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#pragma once

#include <unordered_map>
#include <vector>

#include "core/CList.h"
#include "core/CMovementPresenter.h"
#include "gui/CMovementAnimation.h"
#include "gui/CMovementBatch.h"
#include "gui/object/CProxyTargetGraphicsObject.h"

class CProxyGraphicsObject;
class CMap;
class CPlayer;
class CPlayerController;
class CGameContext;

class CMapGraphicsObject : public CProxyTargetGraphicsObject {
    V_META(CMapGraphicsObject, CProxyTargetGraphicsObject, V_METHOD(CMapGraphicsObject, initialize),
           V_METHOD(CMapGraphicsObject, commitDestination, void, std::shared_ptr<CGui>),
           V_METHOD(CMapGraphicsObject, refreshObject, void, Coords))

  public:
    CMapGraphicsObject();

    void initialize();

    std::list<std::shared_ptr<CGameGraphicsObject>> getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) override;

    int getSizeX(std::shared_ptr<CGui> gui) override;

    int getSizeY(std::shared_ptr<CGui> gui) override;

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode i) override;

    void refreshObject(Coords coords);
    void previewDestination(std::shared_ptr<CGui> gui, Coords destination);
    void commitDestination(std::shared_ptr<CGui> gui);

    vstd::task<void> commitDestinationAsync(std::shared_ptr<CGui> gui);
    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;
    void startTravel(std::shared_ptr<CGui> gui, Coords destination);
    void cancelTravel();
    bool isTravelling() const { return travelling; }
    CMovementPresenter movementPresenter(std::shared_ptr<CGui> gui);
    CMovementPresentation movementPresentation(std::shared_ptr<CGui> gui);
    vstd::task<void> presentMoveAsync(std::shared_ptr<CGui> gui, std::shared_ptr<CMapObject> actor, Coords origin,
                                      Coords destination);
    SDL_Point getCameraOffset(int tileSize) const;
    SDL_Point getActorOffset(const std::shared_ptr<CGameObject> &object, int tileSize) const;
    std::shared_ptr<SDL_Rect> getMotionRect();
    std::shared_ptr<SDL_Rect> getMotionRect(const std::shared_ptr<CGameObject> &actor);

  protected:
    void render(std::shared_ptr<CGui> gui, int frameTime) override;
    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

  private:
    struct ProxyAnimationSlot {
        std::shared_ptr<CAnimation> tile;
        std::vector<std::shared_ptr<CAnimation>> objects;
    };

    std::unordered_map<Coords, ProxyAnimationSlot> proxyAnimations;
    std::weak_ptr<CMap> cachedMap;
    int cachedProxyZ = 0;
    bool hasCachedProxyZ = false;
    std::optional<Coords> previewTarget;
    std::weak_ptr<CMap> previewMap;
    std::weak_ptr<CPlayer> previewPlayer;
    std::weak_ptr<CPlayerController> previewController;
    std::weak_ptr<CGameContext> previewContext;
    Coords previewOrigin = ZERO;
    std::uint64_t previewEpoch = 0;
    std::uint64_t previewGeneration = 0;
    std::uint64_t previewRequest = 0;
    struct TravelOrder {
        Coords destination;
        bool relative = false;
        bool singleTurn = false;
        bool wait = false;
    };
    struct Motion {
        std::weak_ptr<CMapObject> actor;
        std::weak_ptr<CMap> map;
        std::weak_ptr<CGameContext> context;
        Coords destination;
        Coords delta;
        std::uint64_t generation = 0;
        bool reducedMotion = false;
        bool movesCamera = false;
        bool started = false;
        bool arrivalFootprint = false;
        Coords::Direction arrivalDirection = Coords::UNDEFINED;
        CMovementAnimation animation;
        std::shared_ptr<CAnimation> overlay;
        std::vector<std::shared_ptr<CAnimation>> overlays;
    };
    struct PresentationBatch {
        CMovementBatch occupied;
        bool sequential = false;
        std::optional<std::pair<bool, Coords::Direction>> arrivalFootprint;
    };
    std::optional<TravelOrder> pendingOrder;
    std::vector<Motion> motions;
    bool motionBatchStarted = false;
    bool travelling = false;
    bool stopRequested = false;
    void submitOrder(std::shared_ptr<CGui> gui, TravelOrder order);
    vstd::task<void> travelAsync(std::shared_ptr<CGui> gui, bool reusePreview);
    bool motionIsCurrent(const std::shared_ptr<CGui> &gui, const Motion &motion);
    bool stepNeedsSequentialPresentation(const std::shared_ptr<CMapObject> &actor, Coords origin, Coords destination);
    bool enqueueMotion(const std::shared_ptr<CGui> &gui, const std::shared_ptr<CMapObject> &actor, Coords origin,
                       Coords destination,
                       std::optional<std::pair<bool, Coords::Direction>> arrivalFootprint = std::nullopt);
    vstd::task<void> finishMotionBatchAsync(std::shared_ptr<CGui> gui);
    vstd::task<void> preparePresentationStepAsync(std::shared_ptr<CGui> gui, std::shared_ptr<PresentationBatch> batch,
                                                  std::shared_ptr<CMapObject> actor, Coords origin, Coords destination);
    vstd::task<void> presentPresentationStepAsync(std::shared_ptr<CGui> gui, std::shared_ptr<PresentationBatch> batch,
                                                  std::shared_ptr<CMapObject> actor, Coords origin, Coords destination);
    void clearMotion();
    void clearDestinationPreview();
    void validateDestinationPreview(const std::shared_ptr<CGui> &gui);

    Coords guiToMap(std::shared_ptr<CGui> gui, Coords coords);

    Coords mapToGui(std::shared_ptr<CGui> gui, Coords coords);

    std::shared_ptr<CAnimation> syncProxyAnimation(std::shared_ptr<CGui> gui,
                                                   const std::shared_ptr<CGameObject> &object,
                                                   std::shared_ptr<CAnimation> &animation);

    void showCoordinates(std::shared_ptr<CGui> &gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                         const Coords &actualCoords) const;

    void showFootprint(std::shared_ptr<CGui> &gui, Coords::Direction dir,
                       std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const;

    void onProxyGridResized(int sizeX, int sizeY) override;

    void pruneProxyAnimationCache(int sizeX, int sizeY, int z);
};
