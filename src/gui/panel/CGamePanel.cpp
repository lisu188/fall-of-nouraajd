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
#include "CGamePanel.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextureCache.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"
#include "handler/CGuiHandler.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CListView.h"

#include <algorithm>

bool CGamePanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN && key == SDLK_ESCAPE) {
        if (closeable) {
            close();
        } else if (getTypeId() == "fightPanel" && gui && gui->getGame()) {
            gui->getGame()->getGuiHandler()->showPauseMenu();
        }
    }
    return true;
}

int CGamePanel::getShellCloseWidth(const std::shared_ptr<CGui> &gui) {
    return std::max(UiTheme::scaled(gui, 112), gui->getTextManager()->measureText("Close  ×", 0, "body").first);
}

int CGamePanel::getShellHeaderHeight(const std::shared_ptr<CGui> &gui) {
    const int padding = UiTheme::scaled(gui, 24);
    const int width = std::max(1, getSelfRect()->w - padding * 2 - (closeable ? getShellCloseWidth(gui) + padding : 0));
    const int titleHeight =
        gui->getTextManager()->measureText(title.empty() ? "Adventure" : title, width, "heading").second;
    const int closeHeight = closeable ? gui->getTextManager()->measureText("Close  ×", 0, "body").second : 0;
    return std::max(UiTheme::scaled(gui, 56), std::max(titleHeight, closeHeight) + UiTheme::scaled(gui, 16));
}

void CGamePanel::renderShell(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect) {
    if (!gui || !rect || getParent() != gui) {
        return;
    }
    auto renderer = gui->getRenderer();
    SDL_BlendMode previous;
    SDL_GetRenderDrawBlendMode(renderer, &previous);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    UiTheme::fill(renderer, SDL_Rect{0, 0, gui->getWidth(), gui->getHeight()}, {0, 0, 0, 120});
    UiTheme::fill(renderer, *rect, UiTheme::Panel);
    UiTheme::stroke(renderer, *rect, UiTheme::Border);
    SDL_SetRenderDrawBlendMode(renderer, previous);
    const int padding = UiTheme::scaled(gui, 24);
    const int header = getShellHeaderHeight(gui);
    const int closeWidth = getShellCloseWidth(gui);
    layoutResponsiveChildren(gui, rect);
    gui->getTextManager()->drawTextStyled(
        title.empty() ? "Adventure" : title,
        CUtil::rect(rect->x + padding, rect->y + UiTheme::scaled(gui, 8),
                    std::max(1, rect->w - padding * 2 - (closeable ? closeWidth + padding : 0)),
                    header - UiTheme::scaled(gui, 16)),
        "heading", UiTheme::Text);
    if (closeable) {
        gui->getTextManager()->drawTextStyled("Close  ×",
                                              CUtil::rect(rect->x + rect->w - padding - closeWidth,
                                                          rect->y + UiTheme::scaled(gui, 8), closeWidth,
                                                          header - UiTheme::scaled(gui, 16)),
                                              "body", UiTheme::Accent, true);
    }
    UiTheme::fill(renderer, SDL_Rect{rect->x + padding, rect->y + header, rect->w - padding * 2, 1}, UiTheme::Border);
}

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
        if (responsiveNarrow && responsivePageCount > 0 && event->type == SDL_KEYDOWN &&
            (event->key.keysym.sym == SDLK_LEFTBRACKET || event->key.keysym.sym == SDLK_RIGHTBRACKET)) {
            responsivePage =
                (responsivePage + (event->key.keysym.sym == SDLK_LEFTBRACKET ? -1 : 1) + responsivePageCount) %
                responsivePageCount;
            return true;
        }
        if (responsiveNarrow && responsivePageCount > 0 &&
            (event->type == SDL_MOUSEBUTTONDOWN || event->type == SDL_MOUSEBUTTONUP) &&
            event->button.button == SDL_BUTTON_LEFT) {
            auto rect = getSelfRect();
            const int x = event->button.x - rect->x;
            const int y = event->button.y - rect->y;
            const bool inside = x >= responsiveHeaderRect.x && x < responsiveHeaderRect.x + responsiveHeaderRect.w &&
                                y >= responsiveHeaderRect.y && y < responsiveHeaderRect.y + responsiveHeaderRect.h;
            const int direction = x < rect->w / 2 ? -1 : 1;
            if (event->type == SDL_MOUSEBUTTONDOWN) {
                responsiveHeaderPressed = inside ? direction : 0;
                if (inside)
                    return true;
            } else if (responsiveHeaderPressed) {
                const bool matched = inside && responsiveHeaderPressed == direction;
                responsiveHeaderPressed = 0;
                if (matched)
                    responsivePage = (responsivePage + direction + responsivePageCount) % responsivePageCount;
                return true;
            }
        }
        const auto id = getTypeId();
        if (event->type == SDL_KEYDOWN && !event->key.repeat &&
            (id == "inventoryPanel" || id == "characterPanel" || id == "questPanel")) {
            auto preferences = json::parse(gui->getUiPreferences());
            for (const auto &[action, panel] : std::map<std::string, std::string>{
                     {"inventory", "inventoryPanel"}, {"character", "characterPanel"}, {"journal", "questPanel"}}) {
                auto keyName = preferences.at("bindings").at(action).get<std::string>();
                if (event->key.keysym.sym == SDL_GetKeyFromName(keyName.c_str())) {
                    if (id == panel)
                        close();
                    else
                        gui->getGame()->getGuiHandler()->openPanel(panel);
                    return true;
                }
            }
        }
        if (getParent() == gui && closeable &&
            (event->type == SDL_MOUSEBUTTONDOWN || event->type == SDL_MOUSEBUTTONUP) &&
            event->button.button == SDL_BUTTON_LEFT) {
            auto rect = getSelfRect();
            const int x = event->button.x - rect->x;
            const int y = event->button.y - rect->y;
            const bool inside = x >= rect->w - UiTheme::scaled(gui, 24) - getShellCloseWidth(gui) && x < rect->w &&
                                y >= 0 && y < getShellHeaderHeight(gui) && !isInResizeHandle(x, y) && !isResizing();
            if (event->type == SDL_MOUSEBUTTONDOWN && inside) {
                closePressed = true;
                return true;
            }
            if (event->type == SDL_MOUSEBUTTONUP && closePressed) {
                closePressed = false;
                if (inside)
                    close();
                return true;
            }
        }
        // A press on the resize handle is claimed before child dispatch: children (e.g. list views)
        // consume left button-downs even on empty cells, so a child covering the bottom-right corner
        // would otherwise swallow the grab. Same for the matching release while a resize is active,
        // which CGui routes through normal hit testing when it lands inside the captured panel.
        // The calls are qualified (non-virtual): subclass mouseEvent overrides (the inventory, fight,
        // and trade right-click selection resets) do not delegate to the base implementation, so a
        // virtual call would consume the claimed handle press without ever reaching the panel-level
        // resize state machine, leaving an opted-in panel impossible to resize by real input.
        if (event->type == SDL_MOUSEBUTTONDOWN && event->button.button == SDL_BUTTON_LEFT) {
            auto rect = getSelfRect();
            if (isInResizeHandle(event->button.x - rect->x, event->button.y - rect->y)) {
                return CGamePanel::mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, event->button.x - rect->x,
                                              event->button.y - rect->y);
            }
        }
        if (event->type == SDL_MOUSEBUTTONUP && event->button.button == SDL_BUTTON_LEFT && isResizing()) {
            auto rect = getSelfRect();
            return CGamePanel::mouseEvent(gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, event->button.x - rect->x,
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
    CUtil::setRenderDrawColor(renderer, UiTheme::Accent);
    SDL_RenderFillRect(renderer, &handleRect);
}

bool CGamePanel::isResizable() { return resizable; }

void CGamePanel::layoutResponsiveChildren(const std::shared_ptr<CGui> &gui, const std::shared_ptr<SDL_Rect> &rect) {
    std::vector<std::string> groups;
    auto children = getChildren();
    for (const auto &child : children) {
        auto group = child->getStringProperty("uiGroup");
        if (!group.empty() && std::find(groups.begin(), groups.end(), group) == groups.end())
            groups.push_back(group);
    }
    std::sort(groups.begin(), groups.end());
    responsivePageCount = static_cast<int>(groups.size());
    if (!responsivePageCount)
        return;
    responsivePage = std::clamp(responsivePage, 0, responsivePageCount - 1);
    responsiveNarrow =
        rect->w < UiTheme::scaled(gui, 1200) || gui->getTextScale() > 1.5 * std::max(1.0, gui->getHeight() / 1080.0);
    if (!responsiveNarrow)
        responsiveHeaderPressed = 0;
    const double displayScale = std::max(1.0, gui->getHeight() / 1080.0);
    const int padding = static_cast<int>(24 * displayScale);
    const int gap = static_cast<int>(8 * displayScale);
    const int availableWidth = std::max(1, rect->w - padding * 2);
    std::vector<std::shared_ptr<CButton>> tabs;
    std::vector<std::shared_ptr<CButton>> footer;
    for (const auto &child : children) {
        if (auto button = vstd::cast<CButton>(child)) {
            if (button->getBoolProperty("uiTab"))
                tabs.push_back(button);
            if (button->getBoolProperty("uiFooter")) {
                const auto page = button->getStringProperty("uiFooterGroup");
                const bool hidden = responsiveNarrow && !page.empty() && page != groups[responsivePage];
                button->setRuntimeHidden(hidden);
                if (!hidden)
                    footer.push_back(button);
            }
        }
    }
    auto orderButtons = [](auto &buttons) {
        std::sort(buttons.begin(), buttons.end(), [](const auto &left, const auto &right) {
            return left->getNumericProperty("uiOrder") < right->getNumericProperty("uiOrder");
        });
    };
    orderButtons(tabs);
    orderButtons(footer);
    auto rowHeight = [&](const auto &buttons) {
        if (buttons.empty())
            return 0;
        const int width = std::max(1, (availableWidth - gap * (static_cast<int>(buttons.size()) - 1)) /
                                          static_cast<int>(buttons.size()));
        int height = UiTheme::scaled(gui, 40);
        for (const auto &button : buttons)
            height =
                std::max(height, gui->getTextManager()
                                         ->measureText(button->getText(), std::max(1, width - UiTheme::scaled(gui, 16)),
                                                       button->getTextRole())
                                         .second +
                                     UiTheme::scaled(gui, 16));
        return height;
    };
    auto placeRow = [&](const auto &buttons, int y, int height) {
        if (buttons.empty())
            return;
        const int width = std::max(1, (availableWidth - gap * (static_cast<int>(buttons.size()) - 1)) /
                                          static_cast<int>(buttons.size()));
        for (size_t index = 0; index < buttons.size(); ++index)
            buttons[index]->getLayout()->setRuntimeRect(padding + static_cast<int>(index) * (width + gap), y, width,
                                                        height);
    };
    const int tabHeight = rowHeight(tabs);
    const int footerHeight = rowHeight(footer);
    const int tabsTop = getShellHeaderHeight(gui) + gap;
    const int groupTop = tabsTop + (tabs.empty() ? 0 : tabHeight + gap);
    const int groupHeight =
        std::max(static_cast<int>(48 * displayScale),
                 gui->getTextManager()->measureText("Previous / Next region", availableWidth, "body").second + gap);
    const int contentTop = groupTop + groupHeight + gap * 2;
    const int contentBottom = rect->h - padding - (footer.empty() ? 0 : footerHeight + gap * 2);
    if (responsiveNarrow) {
        placeRow(tabs, tabsTop, tabHeight);
        placeRow(footer, rect->h - padding - footerHeight, footerHeight);
        responsiveHeaderRect = {padding, groupTop, availableWidth, groupHeight};
        auto label = groups[responsivePage];
        if (label.size() > 2 && label[1] == ':')
            label.erase(0, 2);
        gui->getTextManager()->drawTextStyled(
            "‹  " + label + "  ›", CUtil::rect(rect->x + padding, rect->y + groupTop, availableWidth, groupHeight),
            "body", UiTheme::Accent, true);
    } else {
        for (const auto &buttons : {tabs, footer})
            for (const auto &button : buttons)
                button->getLayout()->clearRuntimeRect();
    }
    int wideFooterTop = rect->y + rect->h - padding;
    for (const auto &button : footer) {
        wideFooterTop = std::min(wideFooterTop, button->getLayout()->getRect(button)->y);
    }
    for (const auto &child : children) {
        auto group = child->getStringProperty("uiGroup");
        if (group.empty())
            continue;
        auto layout = child->getLayout();
        if (!layout)
            continue;
        const auto before = layout->getRect(child);
        child->setRuntimeHidden(responsiveNarrow &&
                                (group != groups[responsivePage] || child->getBoolProperty("uiHeading")));
        if (!responsiveNarrow) {
            layout->clearRuntimeRect();
            if (auto list = vstd::cast<CListView>(child); list && !footer.empty()) {
                const auto authored = layout->getRect(child);
                const int pagerHeight = std::max(UiTheme::scaled(gui, 40),
                                                 gui->getTextManager()->measureText("Previous", 0, "body").second +
                                                     UiTheme::scaled(gui, 16));
                const int height = std::min(authored->h, std::max(1, wideFooterTop - gap - pagerHeight -
                                                                         UiTheme::scaled(gui, 4) - authored->y));
                layout->setRuntimeRect(authored->x - rect->x, authored->y - rect->y, authored->w, height);
            }
            const auto after = layout->getRect(child);
            if (before->w != after->w || before->h != after->h) {
                if (auto proxy = vstd::cast<CProxyTargetGraphicsObject>(child))
                    proxy->refresh();
            }
            continue;
        }
        if (group != groups[responsivePage])
            continue;
        int top = contentTop;
        int bottom = contentBottom;
        if (auto list = vstd::cast<CListView>(child)) {
            if (list->getSearchable())
                top += UiTheme::scaled(gui, 30);
            bottom -=
                std::max(UiTheme::scaled(gui, 40),
                         gui->getTextManager()->measureText("Previous", 0, "body").second + UiTheme::scaled(gui, 16)) +
                UiTheme::scaled(gui, 4);
        }
        const int height = std::max(1, bottom - top);
        const int part = child->getNumericProperty("uiPart");
        const int parts = std::max(1, child->getNumericProperty("uiParts"));
        layout->setRuntimeRect(padding, top + part * height / parts, availableWidth, std::max(1, height / parts));
        const auto after = layout->getRect(child);
        if (before->w != after->w || before->h != after->h) {
            if (auto proxy = vstd::cast<CProxyTargetGraphicsObject>(child))
                proxy->refresh();
        }
    }
}

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
    auto rect = getSelfRect();
    auto parentRect = getParentRect();
    return getResizeBounds(rect->x - parentRect->x, rect->y - parentRect->y);
}

CGamePanel::ResizeBounds CGamePanel::getResizeBounds(int originX, int originY) {
    ResizeBounds bounds{RESIZE_MIN_SIZE, RESIZE_MIN_SIZE, RESIZE_MAX_FALLBACK, RESIZE_MAX_FALLBACK};
    if (auto layout = getLayout()) {
        bounds.minW = std::max(RESIZE_MIN_SIZE, layout->getMinW());
        bounds.minH = std::max(RESIZE_MIN_SIZE, layout->getMinH());
    }
    if (auto parent = getParent()) {
        if (auto parentLayout = parent->getLayout()) {
            auto parentRect = parentLayout->getRect(parent);
            // Keep the panel fully inside its parent: the max edge is the room left of the parent's
            // right/bottom edge from the given parent-relative top-left origin.
            bounds.maxW = std::max(bounds.minW, parentRect->w - originX);
            bounds.maxH = std::max(bounds.minH, parentRect->h - originY);
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
    auto parentOrigin = getParentRect();
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

void CGamePanel::endResize() {
    if (!resizing) {
        return;
    }
    resizing = false;
    // The drag is over: remember the panel's runtime geometry for the rest of the session, so a
    // closed/reopened (or rebuilt) panel with the same identity comes back with the same rectangle.
    recordSessionGeometry();
}

void CGamePanel::recordSessionGeometry() {
    auto gui = getGui();
    if (!gui || getTypeId().empty() || !getLayout()) {
        return;
    }
    auto rect = getSelfRect();
    auto parentOrigin = getParentRect();
    // Stored x/y are parent-relative (the space CLayout keeps runtime X/Y in); w/h are pixels. The
    // store lives on the CGui only, so nothing here can reach a layout config or a save file.
    gui->setSessionPanelGeometry(getTypeId(), {rect->x - parentOrigin->x, rect->y - parentOrigin->y, rect->w, rect->h});
}

void CGamePanel::applySessionGeometry(const std::shared_ptr<CGui> &gui) {
    if (!gui || !resizable || getTypeId().empty()) {
        return;
    }
    auto layout = getLayout();
    if (!layout) {
        return;
    }
    auto stored = gui->getSessionPanelGeometry(getTypeId());
    if (!stored) {
        return;
    }
    // Clamp exactly like a live resize, but against the CURRENT parent rectangle: the window (and
    // with it the scaled runtime layout) may have changed since the geometry was recorded, and the
    // restored panel must never land outside the new bounds. First keep the origin inside the parent
    // with at least the minimum size of room, then clamp the edges to the room left from that origin.
    auto originBounds = getResizeBounds(0, 0);
    int x = std::clamp(stored->x, 0, std::max(0, originBounds.maxW - originBounds.minW));
    int y = std::clamp(stored->y, 0, std::max(0, originBounds.maxH - originBounds.minH));
    auto sizeBounds = getResizeBounds(x, y);
    // Runtime overrides only: the serialized layout values stay untouched (mirrors the resize path).
    layout->setRuntimeRect(x, y, std::clamp(stored->w, sizeBounds.minW, sizeBounds.maxW),
                           std::clamp(stored->h, sizeBounds.minH, sizeBounds.maxH));
}

std::shared_ptr<SDL_Rect> CGamePanel::getSelfRect() {
    auto layout = getLayout();
    return layout ? layout->getRect(this->ptr<CGameGraphicsObject>()) : CUtil::rect(0, 0, 0, 0);
}

std::shared_ptr<SDL_Rect> CGamePanel::getParentRect() {
    if (auto parent = getParent()) {
        if (auto parentLayout = parent->getLayout()) {
            return parentLayout->getRect(parent);
        }
    }
    return CUtil::rect(0, 0, 0, 0);
}

void CGamePanel::refreshViews() {
    for (auto child : getChildren()) {
        if (child && child->meta()->inherits(CListView::static_meta()->name())) {
            vstd::cast<CListView>(child)->refreshAll();
        }
    }
}

CGamePanel::CGamePanel() {
    setBackground("");
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
