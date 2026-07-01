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

#include "core/CGame.h"
#include "core/CGlobal.h"
#include "gui/CRenderContext.h"
#include "gui/CSdlResources.h"
#include "gui/object/CGameGraphicsObject.h"
#include "object/CGameObject.h"

#include <atomic>
#include <optional>

class CTextureCache;

class CTextManager;

class CGui : public CGameGraphicsObject {
    V_META(CGui, CGameGraphicsObject, V_PROPERTY(CGui, int, height, getHeight, setHeight),
           V_PROPERTY(CGui, int, width, getWidth, setWidth), V_PROPERTY(CGui, int, tileSize, getTileSize, setTileSize))
    fn::sdl::WindowPtr window;
    fn::sdl::RendererPtr renderer;
    CRenderContext renderContext;

  public:
    struct DragSession {
        std::weak_ptr<CGameGraphicsObject> sourceWidget;
        std::shared_ptr<CGameObject> payload;
        int sourceIndex = -1;
        SDL_Point start{0, 0};
        SDL_Point current{0, 0};
        std::weak_ptr<CGameGraphicsObject> acceptedTarget;
        std::shared_ptr<CGameGraphicsObject> proxyWidget;
        bool canceled = false;
        bool sourceCallbackDeferred = false;
        // Latched once pointer motion first crosses the click-vs-drag movement
        // threshold. While false the session is only a *candidate* drag: no proxy
        // widget is rendered, drops are rejected, and the release is treated as a
        // plain click. Once true it stays true for the lifetime of the session
        // (a drag never demotes back to a click), even if the pointer later drifts
        // back below the threshold. See CGui::dragThresholdCrossed for the rule.
        bool dragActive = false;
    };

    // Canonical click-versus-drag movement threshold, in pixels. This is the SINGLE
    // source of truth reused by every click-vs-drag decision (proxy lifecycle,
    // source-callback deferral, drop acceptance, and the mouse-up branch).
    //
    // Distance metric: Chebyshev (max-axis) distance, i.e. max(|dx|, |dy|).
    // Boundary: EXCLUSIVE. A session is only promoted to an active drag once the
    // Chebyshev distance is STRICTLY GREATER THAN the threshold. With a threshold of
    // 4 this means: 0..4 px of motion on both axes stays a click; the first sample
    // with |dx| >= 5 or |dy| >= 5 becomes a drag. Negative-axis motion is handled by
    // the absolute values, and diagonal motion is governed by whichever axis is
    // larger (so exactly-4/4 diagonal is still a click, 5/0 is a drag).
    static constexpr int DRAG_MOVEMENT_THRESHOLD = 4;

    // Returns true when the displacement between start and current already crosses
    // the movement threshold (Chebyshev distance > DRAG_MOVEMENT_THRESHOLD).
    static bool dragThresholdCrossed(const DragSession &session);

    // Returns true when the session has been promoted to an active drag, i.e. its
    // latched dragActive flag is set. Below-threshold candidate sessions return
    // false. This is the accessor every non-CGui call site (e.g. CListView) must use
    // to decide drag-vs-click, so the rule lives in exactly one place.
    static bool isDragActive(const DragSession &session);

    using CGameGraphicsObject::render;

    SDL_Renderer *getRenderer() const;

    CRenderContext &getRenderContext();

    const CRenderContext &getRenderContext() const;

    int getWidth();

    void setWidth(int width);

    int getHeight();

    void setHeight(int height);

    int getTileSize();

    void setTileSize(int tileSize);

    int getTileCountX();

    int getTileCountY();

  private:
    int height = 1080;
    int tileSize = 50;
    int width = 1920;

  public:
    CGui();

    ~CGui() override;

    void shutdown();

    bool isActive() const;

    void render(int i1);

    bool event(SDL_Event *event);

    void capturePointer(std::shared_ptr<CGameGraphicsObject> widget);

    void releasePointerCapture();

    void releasePointerCaptureFor(const std::shared_ptr<CGameGraphicsObject> &root);

    bool hasPointerCapture() const;

    bool isPointerCapturedBy(const std::shared_ptr<CGameGraphicsObject> &widget) const;

    void startDragSession(std::shared_ptr<CGameGraphicsObject> sourceWidget, std::shared_ptr<CGameObject> payload,
                          int sourceIndex, int startX, int startY, bool sourceCallbackDeferred = false);

    void updateDragSession(int currentX, int currentY);

    void acceptDragSession(std::shared_ptr<CGameGraphicsObject> target);

    void cancelDragSession();

    void cancelDragSessionFor(const std::shared_ptr<CGameGraphicsObject> &root);

    void clearDragSession();

    bool hasDragSession() const;

    const DragSession *getDragSession() const;

    DragSession *getDragSession();

    std::shared_ptr<CTextureCache> getTextureCache();

    std::shared_ptr<CTextManager> getTextManager();

    vstd::lazy<CTextureCache> _textureCache;

    vstd::lazy<CTextManager> _textManager;

  private:
    bool dispatchPointerCaptureEvent(SDL_Event *event);

    void handleWindowSizeChanged(const SDL_WindowEvent &windowEvent);

    void refreshLayout();

    bool isPointerInside(const std::shared_ptr<CGameGraphicsObject> &object, int x, int y);

    bool ownsGraphicsObject(const std::shared_ptr<CGameGraphicsObject> &root,
                            const std::shared_ptr<CGameGraphicsObject> &object) const;

    std::optional<DragSession> dragSession;

    std::weak_ptr<CGameGraphicsObject> pointerCapture;

    std::atomic<bool> active = true;
};
