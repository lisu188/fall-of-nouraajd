/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include "CGamePanel.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextureCache.h"
#include "gui/object/CWidget.h"

#include <algorithm>

bool CGamePanel::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) { return true; }

bool CGamePanel::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    if (button == SDL_BUTTON_LEFT) {
        if (type == SDL_MOUSEBUTTONDOWN && beginResize(x, y)) {
            // Capture the pointer so the resize keeps tracking even if the cursor leaves the panel rect.
            if (sharedPtr) {
                sharedPtr->capturePointer(this->ptr<CGameGraphicsObject>());
            }
            return true;
        }
        if (type == SDL_MOUSEBUTTONUP && isResizing()) {
            endResize();
            if (sharedPtr) {
                sharedPtr->releasePointerCapture();
            }
            return true;
        }
    }
    return true;
}

bool CGamePanel::mouseMotionEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y, int xrel,
                                  int yrel) {
    if (isResizing()) {
        // If the pointer capture ended without this panel seeing the release (e.g. drag cancel or an
        // externally released capture), drop the stale resize instead of resizing with no button held.
        if (sharedPtr && !sharedPtr->isPointerCapturedBy(this->ptr<CGameGraphicsObject>())) {
            endResize();
            return false;
        }
        updateResize(x, y);
        return true;
    }
    return false;
}

bool CGamePanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event && isAttachedToGui(gui) && isVisible()) {
        // A press on the resize handle is claimed before child dispatch: children (e.g. list views)
        // consume left button-downs even on empty cells, so a child covering the bottom-right corner
        // would otherwise swallow the grab. Same for the matching release while a resize is active,
        // which CGui routes through normal hit testing when it lands inside the captured panel.
        if (event->type == SDL_MOUSEBUTTONDOWN && event->button.button == SDL_BUTTON_LEFT) {
            auto rect = getSelfRect();
            if (isInResizeHandle(event->button.x - rect->x, event->button.y - rect->y)) {
                return mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, event->button.x - rect->x,
                                  event->button.y - rect->y);
            }
        }
        if (event->type == SDL_MOUSEBUTTONUP && event->button.button == SDL_BUTTON_LEFT && isResizing()) {
            auto rect = getSelfRect();
            return mouseEvent(gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, event->button.x - rect->x,
                              event->button.y - rect->y);
        }
    }
    return CGameGraphicsObject::event(gui, event);
}

void CGamePanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    // Only opted-in panels paint a grab handle; everything else renders exactly as before.
    if (!resizable || !gui || !rect || rect->w <= 0 || rect->h <= 0) {
        return;
    }
    auto renderer = gui->getRenderer();
    if (!renderer) {
        return;
    }
    int handle = std::clamp(resizeHandleSize, 1, std::min(rect->w, rect->h));
    SDL_Rect handleRect{rect->x + rect->w - handle, rect->y + rect->h - handle, handle, handle};
    CUtil::setRenderDrawColor(renderer, CColors::Yellow);
    SDL_RenderFillRect(renderer, &handleRect);
}

bool CGamePanel::isResizable() { return resizable; }

void CGamePanel::setResizable(bool _resizable) {
    resizable = _resizable;
    if (!resizable) {
        endResize();
    }
}

int CGamePanel::getResizeHandleSize() { return resizeHandleSize; }

void CGamePanel::setResizeHandleSize(int _resizeHandleSize) { resizeHandleSize = std::max(_resizeHandleSize, 1); }

bool CGamePanel::isResizing() { return resizing; }

bool CGamePanel::isInResizeHandle(int x, int y) {
    if (!resizable) {
        return false;
    }
    auto rect = getSelfRect();
    if (rect->w <= 0 || rect->h <= 0) {
        return false;
    }
    int handle = std::clamp(resizeHandleSize, 1, std::min(rect->w, rect->h));
    return x >= rect->w - handle && x <= rect->w && y >= rect->h - handle && y <= rect->h;
}

CGamePanel::ResizeBounds CGamePanel::getResizeBounds() {
    ResizeBounds bounds{RESIZE_MIN_SIZE, RESIZE_MIN_SIZE, RESIZE_MAX_FALLBACK, RESIZE_MAX_FALLBACK};
    if (auto layout = getLayout()) {
        bounds.minW = std::max(RESIZE_MIN_SIZE, layout->getMinW());
        bounds.minH = std::max(RESIZE_MIN_SIZE, layout->getMinH());
    }
    if (auto parent = getParent()) {
        if (auto parentLayout = parent->getLayout()) {
            auto parentRect = parentLayout->getRect(parent);
            auto rect = getSelfRect();
            // Keep the panel fully inside its parent: the max edge is the room left of the parent's
            // right/bottom edge from the panel's fixed top-left corner.
            int roomW = parentRect->w - (rect->x - parentRect->x);
            int roomH = parentRect->h - (rect->y - parentRect->y);
            bounds.maxW = std::max(bounds.minW, roomW);
            bounds.maxH = std::max(bounds.minH, roomH);
        }
    }
    return bounds;
}

bool CGamePanel::beginResize(int x, int y) {
    if (!isInResizeHandle(x, y)) {
        return false;
    }
    auto layout = getLayout();
    if (!layout) {
        return false;
    }
    auto rect = getSelfRect();
    // Pin the top-left corner for the whole drag: centered/right/bottom-aligned layouts recompute
    // x/y from the current size, so runtime W/H alone would move the origin (and with it the
    // panel-local pointer space) on every update. Latching runtime X/Y freezes the origin relative
    // to the parent so the panel resizes from a stable corner.
    auto parentOrigin = CUtil::rect(0, 0, 0, 0);
    if (auto parent = getParent()) {
        if (auto parentLayout = parent->getLayout()) {
            parentOrigin = parentLayout->getRect(parent);
        }
    }
    layout->setRuntimeX(rect->x - parentOrigin->x);
    layout->setRuntimeY(rect->y - parentOrigin->y);
    // Latch the offset from the pointer to the panel's right/bottom edge so the drag is jump-free.
    resizeGrabOffsetW = rect->w - x;
    resizeGrabOffsetH = rect->h - y;
    resizing = true;
    return true;
}

void CGamePanel::updateResize(int x, int y) {
    if (!resizing) {
        return;
    }
    auto layout = getLayout();
    if (!layout) {
        endResize();
        return;
    }
    auto bounds = getResizeBounds();
    int newW = std::clamp(x + resizeGrabOffsetW, bounds.minW, bounds.maxW);
    int newH = std::clamp(y + resizeGrabOffsetH, bounds.minH, bounds.maxH);
    // Resize via runtime overrides so the serialized layout values stay intact (mirrors window scaling).
    layout->setRuntimeW(newW);
    layout->setRuntimeH(newH);
}

void CGamePanel::endResize() { resizing = false; }

std::shared_ptr<SDL_Rect> CGamePanel::getSelfRect() {
    auto layout = getLayout();
    return layout ? layout->getRect(this->ptr<CGameGraphicsObject>()) : CUtil::rect(0, 0, 0, 0);
}

void CGamePanel::refreshViews() {
    for (auto child : getChildren()) {
        if (child && child->meta()->inherits(CListView::static_meta()->name())) {
            vstd::cast<CListView>(child)->refreshAll();
        }
    }
}

CGamePanel::CGamePanel() {
    // TODO: extract to json
    setBackground("images/panel");
    setModal(true);
}

void CGamePanel::awaitClosing() {
    auto self = this->ptr<CGamePanel>();
    vstd::wait_until([self]() { return !self->getGui() || self->getGui()->findChild(self) == nullptr; });
}

void CGamePanel::close() {
    if (auto gui = getGui()) {
        gui->removeChild(this->ptr<CGamePanel>());
    }
}
