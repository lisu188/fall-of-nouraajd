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
#pragma once

#include "gui/CGui.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/panel/CListView.h"

class CWidget;

class CGamePanel : public CGameGraphicsObject {
    V_META(CGamePanel, CGameGraphicsObject, V_PROPERTY(CGamePanel, bool, resizable, isResizable, setResizable),
           V_PROPERTY(CGamePanel, int, resizeHandleSize, getResizeHandleSize, setResizeHandleSize))
  public:
    CGamePanel();

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

    bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) override;

    bool mouseMotionEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int x, int y, int xrel,
                          int yrel) override;

    void renderObject(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

    void refreshViews();

    void awaitClosing();

    virtual void close();

    // Opt-in user resize handle. Off by default so existing panels are unchanged: only a panel that
    // explicitly opts in exposes a bottom-right drag handle that resizes it via runtime layout overrides.
    bool isResizable();

    void setResizable(bool _resizable);

    int getResizeHandleSize();

    void setResizeHandleSize(int _resizeHandleSize);

    // True when panel-local (x, y) falls inside the bottom-right resize handle of the current rect.
    // Always false while the panel is not resizable, so a non-opted-in panel never treats the corner
    // specially.
    bool isInResizeHandle(int x, int y);

    // Pure resize-drag state machine driven in panel-local coordinates (pointer position relative to
    // the panel's fixed top-left corner). beginResize latches the grab offset and returns whether a
    // resize started; updateResize writes clamped runtime width/height onto the layout; endResize
    // clears the state. These carry the geometry so they can be exercised without SDL rendering.
    bool beginResize(int x, int y);

    void updateResize(int x, int y);

    void endResize();

    bool isResizing();

  private:
    // Minimum edge length a resizable panel is ever clamped to, independent of the layout's own minW/minH.
    // Keeps the panel at least as large as its handle so the handle stays grabbable.
    static constexpr int RESIZE_MIN_SIZE = 32;
    // Fallback maximum edge used when the panel has no parent rectangle to bound it (matches the GUI's
    // logical maximum so a detached panel still cannot grow without limit).
    static constexpr int RESIZE_MAX_FALLBACK = 7680;
    static constexpr int DEFAULT_HANDLE_SIZE = 24;

    struct ResizeBounds {
        int minW;
        int minH;
        int maxW;
        int maxH;
    };

    ResizeBounds getResizeBounds();

    // Base CGameGraphicsObject::getRect() is private; resolve this panel's own rectangle through its layout.
    std::shared_ptr<SDL_Rect> getSelfRect();

    bool resizable = false;
    int resizeHandleSize = DEFAULT_HANDLE_SIZE;
    bool resizing = false;
    int resizeGrabOffsetW = 0;
    int resizeGrabOffsetH = 0;
};
