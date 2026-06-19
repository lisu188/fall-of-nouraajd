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
#include "core/CUtil.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"

#include <algorithm>

CGui::CGui() {
    SDL_SAFE(SDL_Init(SDL_INIT_VIDEO));
    SDL_Window *rawWindow = nullptr;
    SDL_Renderer *rawRenderer = nullptr;
    SDL_SAFE(SDL_CreateWindowAndRenderer(width, height, 0, &rawWindow, &rawRenderer));
    window.reset(rawWindow);
    renderer.reset(rawRenderer);
    // TODO: set icon
    // TODO: check render flags
}

CGui::~CGui() = default;

void CGui::render(int i1) {
    CUtil::setRenderDrawColor(renderer.get(), CColors::Black);
    SDL_SAFE(SDL_RenderClear(renderer.get()));
    CGameGraphicsObject::render(this->ptr<CGui>(), i1);
    SDL_SAFE(SDL_RenderPresent(renderer.get()));
}

SDL_Renderer *CGui::getRenderer() const { return renderer.get(); }

std::shared_ptr<CTextureCache> CGui::getTextureCache() {
    return _textureCache.get([this]() { return std::make_shared<CTextureCache>(this->ptr<CGui>()); });
}

std::shared_ptr<CTextManager> CGui::getTextManager() {
    return _textManager.get([this]() { return std::make_shared<CTextManager>(this->ptr<CGui>()); });
}

int CGui::getWidth() { return width; }

void CGui::setWidth(int width) { CGui::width = std::clamp(width, 320, 7680); }

int CGui::getHeight() { return height; }

void CGui::setHeight(int height) { CGui::height = std::clamp(height, 240, 4320); }

int CGui::getTileSize() { return tileSize; }

void CGui::setTileSize(int tileSize) { CGui::tileSize = std::clamp(tileSize, 1, 512); }

int CGui::getTileCountX() { return width / tileSize + 1; }

int CGui::getTileCountY() { return height / tileSize + 1; }

bool CGui::event(SDL_Event *event) {
    if (!event) {
        return false;
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
                            int sourceIndex, int startX, int startY) {
    if (!sourceWidget || !sourceWidget->isAttachedToGui(this->ptr<CGui>())) {
        return;
    }
    dragSession =
        DragSession{sourceWidget, std::move(payload), sourceIndex, {startX, startY}, {startX, startY}, {}, false};
}

void CGui::updateDragSession(int currentX, int currentY) {
    if (dragSession) {
        dragSession->current = {currentX, currentY};
    }
}

void CGui::acceptDragSession(std::shared_ptr<CGameGraphicsObject> target) {
    if (dragSession && target && target->isAttachedToGui(this->ptr<CGui>())) {
        dragSession->acceptedTarget = target;
        dragSession->canceled = false;
    }
}

void CGui::cancelDragSession() {
    if (dragSession) {
        dragSession->acceptedTarget.reset();
        dragSession->canceled = true;
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

void CGui::clearDragSession() { dragSession.reset(); }

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
