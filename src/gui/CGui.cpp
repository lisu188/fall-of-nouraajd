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
#include "CGui.h"
#include "core/CProvider.h"
#include "core/CUtil.h"
#include "gui/CAnimation.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"
#include "gui/object/CProxyTargetGraphicsObject.h"
#include "gui/panel/CGamePanel.h"

#include <algorithm>
#include <string>

namespace {
constexpr int DRAG_PROXY_FALLBACK_SIZE = 50;
constexpr int GUI_MIN_WIDTH = 320;
constexpr int GUI_MIN_HEIGHT = 240;

std::shared_ptr<CLayout> createDragProxyLayout(const std::shared_ptr<CGui> &gui, const SDL_Point &current) {
    const int size = gui ? std::clamp(gui->getTileSize(), 1, 512) : DRAG_PROXY_FALLBACK_SIZE;
    auto layout = std::make_shared<CLayout>();
    layout->setRect(current.x - size / 2, current.y - size / 2, size, size);
    return layout;
}

std::shared_ptr<CGameGraphicsObject> createDragProxyWidget(const std::shared_ptr<CGui> &gui,
                                                           const std::shared_ptr<CGameObject> &payload) {
    if (!gui || !gui->getGame() || !payload) {
        return nullptr;
    }
    auto animation = CAnimationProvider::getAnimation(gui->getGame(), payload);
    if (!animation) {
        return nullptr;
    }
    animation->withCallback([](std::shared_ptr<CGui>, SDL_EventType, int, int, int) { return false; });
    return animation;
}

void removeDragProxyWidget(const std::shared_ptr<CGui> &gui, CGui::DragSession &session) {
    auto proxyWidget = session.proxyWidget;
    if (!proxyWidget) {
        return;
    }
    session.proxyWidget.reset();
    if (gui && gui->findChild(proxyWidget)) {
        gui->removeChild(proxyWidget);
        return;
    }
    proxyWidget->removeParent();
}

void syncDragProxyWidget(const std::shared_ptr<CGui> &gui, CGui::DragSession &session) {
    if (!gui || !session.payload || session.canceled || session.acceptedTarget.lock()) {
        removeDragProxyWidget(gui, session);
        return;
    }
    if (!session.proxyWidget) {
        session.proxyWidget = createDragProxyWidget(gui, session.payload);
    }
    if (!session.proxyWidget) {
        return;
    }
    session.proxyWidget->setLayout(createDragProxyLayout(gui, session.current));
    if (!session.proxyWidget->isAttachedToGui(gui)) {
        gui->pushChild(session.proxyWidget);
    }
}

void refreshProxyTargets(const std::shared_ptr<CGameGraphicsObject> &root) {
    if (!root) {
        return;
    }
    if (auto proxyTarget = vstd::cast<CProxyTargetGraphicsObject>(root)) {
        proxyTarget->refresh();
    }
    auto children = root->getChildren();
    for (const auto &child : children) {
        refreshProxyTargets(child);
    }
}
} // namespace

CGui::CGui() {
    SDL_SAFE(SDL_Init(SDL_INIT_VIDEO));
    SDL_Window *rawWindow = nullptr;
    SDL_Renderer *rawRenderer = nullptr;
    SDL_SAFE(SDL_CreateWindowAndRenderer(width, height, SDL_WINDOW_RESIZABLE, &rawWindow, &rawRenderer));
    SDL_SetWindowMinimumSize(rawWindow, GUI_MIN_WIDTH, GUI_MIN_HEIGHT);
    window.reset(rawWindow);
    renderer.reset(rawRenderer);
    renderContext.setRenderer(renderer.get());
    // TODO: set icon
    // TODO: check render flags
}

CGui::~CGui() = default;

void CGui::shutdown() {
    if (!active.exchange(false, std::memory_order_acq_rel)) {
        return;
    }

    clearDragSession();
    releasePointerCapture();

    auto topLevelChildren = getChildren();
    for (const auto &child : topLevelChildren) {
        if (!child || !child->getModal() || !findChild(child)) {
            continue;
        }
        if (auto panel = vstd::cast<CGamePanel>(child)) {
            panel->close();
        } else {
            removeChild(child);
        }
    }
    setChildren({});
    _textureCache.clear();
    _textManager.clear();
}

bool CGui::isActive() const { return active.load(std::memory_order_acquire); }

void CGui::render(int i1) {
    if (!isActive()) {
        return;
    }

    CUtil::setRenderDrawColor(renderer.get(), CColors::Black);
    SDL_SAFE(SDL_RenderClear(renderer.get()));
    CGameGraphicsObject::render(this->ptr<CGui>(), i1);
    SDL_SAFE(SDL_RenderPresent(renderer.get()));
}

SDL_Renderer *CGui::getRenderer() const { return renderer.get(); }

CRenderContext &CGui::getRenderContext() { return renderContext; }

const CRenderContext &CGui::getRenderContext() const { return renderContext; }

std::shared_ptr<CTextureCache> CGui::getTextureCache() {
    return _textureCache.get([this]() { return std::make_shared<CTextureCache>(this->ptr<CGui>()); });
}

std::shared_ptr<CTextManager> CGui::getTextManager() {
    return _textManager.get([this]() { return std::make_shared<CTextManager>(this->ptr<CGui>()); });
}

int CGui::getWidth() { return width; }

void CGui::setWidth(int width) {
    const int clampedWidth = std::clamp(width, GUI_MIN_WIDTH, 7680);
    const bool changed = CGui::width != clampedWidth;
    CGui::width = clampedWidth;
    if (auto layout = getLayout()) {
        layout->setRuntimeW(CGui::width);
    }
    if (changed) {
        recordDirectPropertyChanged("width");
    }
}

int CGui::getHeight() { return height; }

void CGui::setHeight(int height) {
    const int clampedHeight = std::clamp(height, GUI_MIN_HEIGHT, 4320);
    const bool changed = CGui::height != clampedHeight;
    CGui::height = clampedHeight;
    if (auto layout = getLayout()) {
        layout->setRuntimeH(CGui::height);
    }
    if (changed) {
        recordDirectPropertyChanged("height");
    }
}

int CGui::getTileSize() { return tileSize; }

void CGui::setTileSize(int tileSize) { CGui::tileSize = std::clamp(tileSize, 1, 512); }

int CGui::getTileCountX() { return width / tileSize + 1; }

int CGui::getTileCountY() { return height / tileSize + 1; }

bool CGui::event(SDL_Event *event) {
    if (!isActive() || !event) {
        return false;
    }
    if (event->type == SDL_WINDOWEVENT && event->window.event == SDL_WINDOWEVENT_SIZE_CHANGED) {
        handleWindowSizeChanged(event->window);
    }
    if (event->type == SDL_MOUSEMOTION) {
        updateDragSession(event->motion.x, event->motion.y);
        if (hasPointerCapture()) {
            return dispatchPointerCaptureEvent(event);
        }
    }
    if (event->type == SDL_MOUSEBUTTONUP) {
        updateDragSession(event->button.x, event->button.y);
        if (!hasDragSession() && !hasPointerCapture()) {
            return CGameGraphicsObject::event(this->ptr<CGui>(), event);
        }
        const auto captured = pointerCapture.lock();
        const bool releaseInsideCapture = isPointerInside(captured, event->button.x, event->button.y);
        const bool targetHandled =
            (hasDragSession() || releaseInsideCapture) ? CGameGraphicsObject::event(this->ptr<CGui>(), event) : false;
        const bool capturedHandled = releaseInsideCapture ? false : dispatchPointerCaptureEvent(event);
        if (hasDragSession() && !getDragSession()->acceptedTarget.lock()) {
            cancelDragSession();
        }
        releasePointerCapture();
        clearDragSession();
        return targetHandled || capturedHandled;
    }
    if (event->type == SDL_WINDOWEVENT && event->window.event == SDL_WINDOWEVENT_LEAVE) {
        cancelDragSession();
        releasePointerCapture();
        clearDragSession();
    }
    return CGameGraphicsObject::event(this->ptr<CGui>(), event);
}

void CGui::capturePointer(std::shared_ptr<CGameGraphicsObject> widget) {
    if (widget && widget->isAttachedToGui(this->ptr<CGui>())) {
        pointerCapture = widget;
    }
}

void CGui::releasePointerCapture() { pointerCapture.reset(); }

void CGui::releasePointerCaptureFor(const std::shared_ptr<CGameGraphicsObject> &root) {
    auto captured = pointerCapture.lock();
    if (ownsGraphicsObject(root, captured)) {
        releasePointerCapture();
    }
}

bool CGui::hasPointerCapture() const { return !pointerCapture.expired(); }

bool CGui::isPointerCapturedBy(const std::shared_ptr<CGameGraphicsObject> &widget) const {
    return widget && pointerCapture.lock() == widget;
}

void CGui::startDragSession(std::shared_ptr<CGameGraphicsObject> sourceWidget, std::shared_ptr<CGameObject> payload,
                            int sourceIndex, int startX, int startY, bool sourceCallbackDeferred) {
    if (!sourceWidget || !sourceWidget->isAttachedToGui(this->ptr<CGui>())) {
        return;
    }
    clearDragSession();
    DragSession session;
    session.sourceWidget = sourceWidget;
    session.payload = std::move(payload);
    session.sourceIndex = sourceIndex;
    session.start = {startX, startY};
    session.current = {startX, startY};
    session.sourceCallbackDeferred = sourceCallbackDeferred;
    dragSession = std::move(session);
    syncDragProxyWidget(this->ptr<CGui>(), *dragSession);
}

void CGui::updateDragSession(int currentX, int currentY) {
    if (dragSession) {
        dragSession->current = {currentX, currentY};
        syncDragProxyWidget(this->ptr<CGui>(), *dragSession);
    }
}

void CGui::acceptDragSession(std::shared_ptr<CGameGraphicsObject> target) {
    if (dragSession && target && target->isAttachedToGui(this->ptr<CGui>())) {
        dragSession->acceptedTarget = target;
        dragSession->canceled = false;
        removeDragProxyWidget(this->ptr<CGui>(), *dragSession);
    }
}

void CGui::cancelDragSession() {
    if (dragSession) {
        dragSession->acceptedTarget.reset();
        dragSession->canceled = true;
        removeDragProxyWidget(this->ptr<CGui>(), *dragSession);
    }
}

void CGui::cancelDragSessionFor(const std::shared_ptr<CGameGraphicsObject> &root) {
    if (!dragSession) {
        return;
    }
    if (ownsGraphicsObject(root, dragSession->sourceWidget.lock()) ||
        ownsGraphicsObject(root, dragSession->acceptedTarget.lock())) {
        cancelDragSession();
        clearDragSession();
    }
}

void CGui::clearDragSession() {
    if (dragSession) {
        removeDragProxyWidget(this->ptr<CGui>(), *dragSession);
    }
    dragSession.reset();
}

bool CGui::hasDragSession() const { return dragSession.has_value(); }

const CGui::DragSession *CGui::getDragSession() const { return dragSession ? &*dragSession : nullptr; }

CGui::DragSession *CGui::getDragSession() { return dragSession ? &*dragSession : nullptr; }

bool CGui::dispatchPointerCaptureEvent(SDL_Event *event) {
    auto captured = pointerCapture.lock();
    if (!captured || !captured->isAttachedToGui(this->ptr<CGui>())) {
        releasePointerCapture();
        return false;
    }
    auto rect = captured->getRect();
    if (event->type == SDL_MOUSEMOTION) {
        return captured->mouseMotionEvent(this->ptr<CGui>(), static_cast<SDL_EventType>(event->type),
                                          event->motion.x - rect->x, event->motion.y - rect->y, event->motion.xrel,
                                          event->motion.yrel);
    }
    if (event->type == SDL_MOUSEBUTTONUP || event->type == SDL_MOUSEBUTTONDOWN) {
        return captured->mouseEvent(this->ptr<CGui>(), static_cast<SDL_EventType>(event->type), event->button.button,
                                    event->button.x - rect->x, event->button.y - rect->y);
    }
    return false;
}

void CGui::handleWindowSizeChanged(const SDL_WindowEvent &windowEvent) {
    int windowWidth = 0;
    int windowHeight = 0;
    if (window) {
        if (windowEvent.windowID != 0 && SDL_GetWindowID(window.get()) != windowEvent.windowID) {
            return;
        }
        SDL_GetWindowSize(window.get(), &windowWidth, &windowHeight);
    }
    if (windowWidth <= 0 || windowHeight <= 0) {
        windowWidth = windowEvent.data1;
        windowHeight = windowEvent.data2;
    }
    if (windowWidth <= 0 || windowHeight <= 0) {
        return;
    }
    const int previousWidth = width;
    const int previousHeight = height;
    setWidth(windowWidth);
    setHeight(windowHeight);
    if (width != previousWidth || height != previousHeight) {
        refreshLayout();
    }
}

void CGui::refreshLayout() { refreshProxyTargets(this->ptr<CGui>()); }

bool CGui::isPointerInside(const std::shared_ptr<CGameGraphicsObject> &object, int x, int y) {
    if (!object || !object->isAttachedToGui(this->ptr<CGui>())) {
        return false;
    }
    return CUtil::isIn(object->getRect(), x, y);
}

bool CGui::ownsGraphicsObject(const std::shared_ptr<CGameGraphicsObject> &root,
                              const std::shared_ptr<CGameGraphicsObject> &object) const {
    return root && object && (root == object || root->findChild(object) != nullptr);
}
