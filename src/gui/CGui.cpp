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
#include "gui/CUiPreferences.h"
#include "gui/CUiTheme.h"
#include "gui/CTooltip.h"
#include "gui/object/CWidget.h"
#include "gui/object/CProxyTargetGraphicsObject.h"
#include "gui/panel/CGamePanel.h"
#include "handler/CTooltipHandler.h"
#include "core/CMap.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"

#include <algorithm>
#include <cstdlib>
#include <string>
#include <filesystem>
#include <fstream>

namespace {
constexpr int DRAG_PROXY_FALLBACK_SIZE = 50;
constexpr int GUI_MIN_WIDTH = 320;
constexpr int GUI_MIN_HEIGHT = 240;

std::filesystem::path preferencesPath() {
    // Tests can isolate preferences alongside their other temporary resources.
    if (const auto *path = SDL_getenv("GAME_UI_PREFERENCES_PATH"))
        return std::filesystem::path(path);
    auto directory = SDL_GetPrefPath("nouraajd", "fall-of-nouraajd");
    if (!directory)
        return {};
    auto path = std::filesystem::path(directory) / "interface.json";
    SDL_free(directory);
    return path;
}

void collectFocusable(const std::shared_ptr<CGameGraphicsObject> &root,
                      std::vector<std::shared_ptr<CGameGraphicsObject>> &result) {
    if (!root || !root->isVisible())
        return;
    auto widget = vstd::cast<CWidget>(root);
    if ((widget && widget->getEnabled() && !widget->getClick().empty()) || vstd::cast<CListView>(root)) {
        result.push_back(root);
        return;
    }
    for (const auto &child : root->getChildren())
        collectFocusable(child, result);
}

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
    // A candidate drag (below-threshold motion) must NOT render a proxy widget: the
    // interaction is still a click until the movement threshold is crossed.
    if (!gui || !session.payload || session.canceled || !CGui::isDragActive(session) || session.acceptedTarget.lock()) {
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
    // Video lives for the process; repeated initialization can overflow SDL 2's
    // subsystem reference counter and invalidate windows from earlier sessions.
    if ((SDL_WasInit(SDL_INIT_VIDEO) & SDL_INIT_VIDEO) == 0) {
        SDL_SAFE(SDL_Init(SDL_INIT_VIDEO));
    }
    SDL_Window *rawWindow = nullptr;
    SDL_Renderer *rawRenderer = nullptr;
    SDL_SAFE(SDL_CreateWindowAndRenderer(width, height, SDL_WINDOW_RESIZABLE, &rawWindow, &rawRenderer));
    SDL_SetWindowMinimumSize(rawWindow, GUI_MIN_WIDTH, GUI_MIN_HEIGHT);
    window.reset(rawWindow);
    renderer.reset(rawRenderer);
    renderContext.setRenderer(renderer.get());
    loadUiPreferences();
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
    // The GUI shutdown is the session boundary (CGameContext drives it when the game session ends):
    // user-adjusted panel geometry must not survive into the next session.
    clearSessionPanelGeometry();
    _textureCache.clear();
    _textManager.clear();
}

void CGui::setSessionPanelGeometry(const std::string &panelType, const PanelGeometry &geometry) {
    if (panelType.empty()) {
        return;
    }
    sessionPanelGeometry[panelType] = geometry;
}

std::optional<CGui::PanelGeometry> CGui::getSessionPanelGeometry(const std::string &panelType) const {
    auto found = sessionPanelGeometry.find(panelType);
    if (found == sessionPanelGeometry.end()) {
        return std::nullopt;
    }
    return found->second;
}

void CGui::clearSessionPanelGeometry() { sessionPanelGeometry.clear(); }

void CGui::addChild(const std::shared_ptr<CGameGraphicsObject> &child) {
    const bool attached = child && child->isAttachedToGui(this->ptr<CGui>());
    CGameGraphicsObject::addChild(child);
    // A panel joining the GUI gets any geometry the user gave it earlier this session, so a
    // closed/reopened or rebuilt panel keeps its adjusted size. The panel clamps against its
    // current parent bounds, so a window resized in between cannot restore an out-of-range rect.
    if (auto panel = vstd::cast<CGamePanel>(child)) {
        panel->applySessionGeometry(this->ptr<CGui>());
    }
    if (!attached && child && child->getParent() == this->ptr<CGui>() &&
        (vstd::cast<CGamePanel>(child) || vstd::cast<CTooltip>(child))) {
        suppressedKeys.insert(heldKeys.begin(), heldKeys.end());
        focusHistory.emplace_back(child, focusedWidget);
        focusedWidget.reset();
    }
}

bool CGui::isActive() const { return active.load(std::memory_order_acquire); }

void CGui::render(int i1) {
    if (!isActive()) {
        return;
    }

    CUtil::setRenderDrawColor(renderer.get(), CColors::Black);
    SDL_SAFE(SDL_RenderClear(renderer.get()));
    CGameGraphicsObject::render(this->ptr<CGui>(), i1);
    renderHoverPreview();
    renderActionFeedback();
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
    SDL_Event mappedEvent = *event;
    if (event->type == SDL_TEXTINPUT) {
        if (auto list = vstd::cast<CListView>(focusedWidget.lock());
            list && list->textInput(this->ptr<CGui>(), event->text.text))
            return true;
    }
    if (event->type == SDL_KEYDOWN || event->type == SDL_KEYUP) {
        const auto key = event->key.keysym.sym;
        if (event->type == SDL_KEYUP) {
            heldKeys.erase(key);
            if (suppressedKeys.erase(key))
                return true;
        } else if (!event->key.repeat) {
            // A fresh press starts a new gesture, including synthetic/test input without a prior release.
            heldKeys.insert(key);
            suppressedKeys.erase(key);
        } else if (suppressedKeys.contains(key)) {
            return true;
        }
        if (handleFocusKey(event))
            return true;
        bool modal = false;
        for (const auto &child : getChildren())
            modal = modal || (child->isVisible() && child->getModal());
        if (!modal) {
            mappedEvent.key.keysym.sym = remapKey(event->key.keysym.sym);
            event = &mappedEvent;
        }
    }
    if (event->type == SDL_WINDOWEVENT && event->window.event == SDL_WINDOWEVENT_SIZE_CHANGED) {
        handleWindowSizeChanged(event->window);
    }
    if (event->type == SDL_MOUSEMOTION) {
        hoverSeen = false;
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
    const bool handled = CGameGraphicsObject::event(this->ptr<CGui>(), event);
    if (event->type == SDL_MOUSEMOTION && !hoverSeen) {
        hoverObject.reset();
        hoverSource.reset();
    }
    return handled;
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

bool CGui::dragThresholdCrossed(const DragSession &session) {
    const int dx = std::abs(session.current.x - session.start.x);
    const int dy = std::abs(session.current.y - session.start.y);
    // Chebyshev (max-axis) distance, boundary exclusive: promote to a drag only when
    // motion strictly exceeds the threshold on either axis.
    return std::max(dx, dy) > DRAG_MOVEMENT_THRESHOLD;
}

bool CGui::isDragActive(const DragSession &session) { return session.dragActive; }

void CGui::updateDragSession(int currentX, int currentY) {
    if (dragSession) {
        dragSession->current = {currentX, currentY};
        // Latch the active-drag state the moment motion first crosses the threshold.
        // Once active it never demotes back to a candidate/click, matching standard
        // click-vs-drag UX.
        if (!dragSession->dragActive && dragThresholdCrossed(*dragSession)) {
            dragSession->dragActive = true;
        }
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

double CGui::getUiScale() const { return std::max(1.0, height / 1080.0) * uiPreferences.value("uiScale", 100) / 100.0; }

double CGui::getTextScale() const {
    return std::max(1.0, height / 1080.0) *
           std::max(uiPreferences.value("uiScale", 100), uiPreferences.value("textScale", 100)) / 100.0;
}

std::string CGui::getUiPreferences() const { return uiPreferences.dump(); }

void CGui::loadUiPreferences() {
    uiPreferences = UiPreferences::defaults();
    try {
        auto path = preferencesPath();
        std::ifstream file(path);
        if (!file)
            return;
        std::string serialized((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        auto stored = json::parse(serialized);
        if (!UiPreferences::validate(stored))
            return;
        for (const auto &[key, value] : stored.items())
            uiPreferences[key] = value;
        if (uiPreferences.value("fullscreen", false))
            SDL_SetWindowFullscreen(window.get(), SDL_WINDOW_FULLSCREEN_DESKTOP);
    } catch (const std::exception &) {
        vstd::logger::warning("Ignoring invalid interface preferences.");
    }
}

bool CGui::applyUiPreferences(const std::string &serialized) {
    try {
        auto requested = json::parse(serialized);
        if (!UiPreferences::validate(requested))
            return false;
        auto next = UiPreferences::defaults();
        for (const auto &[key, value] : requested.items())
            next[key] = value;
        const auto path = preferencesPath();
        if (path.empty())
            return false;
        auto temporary = path;
        temporary += ".tmp";
        if (!path.parent_path().empty())
            std::filesystem::create_directories(path.parent_path());
        {
            std::ofstream file(temporary, std::ios::trunc);
            file << next.dump(2);
            file.close();
            if (!file)
                return false;
        }
        if (next.value("fullscreen", false) != uiPreferences.value("fullscreen", false) &&
            SDL_SetWindowFullscreen(window.get(), next.value("fullscreen", false) ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0) <
                0)
            return false;
        // Resource preferences are separate from save data; replace the small settings file only after validation.
        std::error_code error;
        std::filesystem::rename(temporary, path, error);
        if (error) {
            std::filesystem::copy_file(temporary, path, std::filesystem::copy_options::overwrite_existing);
            std::filesystem::remove(temporary);
        }
        uiPreferences = std::move(next);
        getTextManager()->clearCache();
        refreshLayout();
        return true;
    } catch (const std::exception &exception) {
        vstd::logger::warning("Unable to apply interface preferences:", exception.what());
        return false;
    }
}

SDL_Keycode CGui::remapKey(SDL_Keycode key) const {
    const auto defaults = UiPreferences::defaults().at("bindings");
    const auto bindings = uiPreferences.contains("bindings") ? uiPreferences.at("bindings") : defaults;
    for (const auto &[action, name] : bindings.items()) {
        if (SDL_GetKeyFromName(name.get<std::string>().c_str()) == key)
            return SDL_GetKeyFromName(defaults.at(action).get<std::string>().c_str());
    }
    for (const auto &[action, name] : defaults.items()) {
        if (SDL_GetKeyFromName(name.get<std::string>().c_str()) == key)
            return SDLK_UNKNOWN;
    }
    return key;
}

void CGui::notify(const std::string &message) {
    if (message.empty())
        return;
    feedbackTarget.reset();
    feedbackMap.reset();
    actionFeedback.clear();
    if (activityHistory.empty() || activityHistory.back() != message)
        activityHistory.push_back(message);
    while (activityHistory.size() > 200)
        activityHistory.pop_front();
    notificationTime = SDL_GetTicks();
}

void CGui::notifyAt(const std::shared_ptr<CMapObject> &target, const std::string &message) {
    notify(message);
    auto map = getGame() ? getGame()->getMap() : nullptr;
    if (!target || !map || target->getMap() != map || map->getObjectByName(target->getName()) != target ||
        message.empty())
        return;
    feedbackTarget = target;
    feedbackMap = map;
    actionFeedback = message;
}

std::string CGui::getActionFeedback() const {
    auto target = feedbackTarget.lock();
    auto map = feedbackMap.lock();
    auto game = const_cast<CGui *>(this)->getGame();
    return target && map && game && game->getMap() == map && target->getMap() == map &&
                   map->getObjectByName(target->getName()) == target && SDL_GetTicks() - notificationTime < 8000
               ? actionFeedback
               : "";
}

void CGui::renderActionFeedback() {
    const auto message = getActionFeedback();
    const auto target = feedbackTarget.lock();
    const auto map = feedbackMap.lock();
    const auto player = map ? map->getPlayer() : nullptr;
    if (message.empty() || !target || !player || target->getCoords().z != player->getCoords().z)
        return;
    for (const auto &child : getChildren())
        if (child->isVisible() && child->getModal())
            return;
    const auto delta = map->getShortestDelta(player->getCoords(), target->getCoords());
    const int x = (getTileCountX() / 2 + delta.x) * tileSize;
    const int y = (getTileCountY() / 2 + delta.y) * tileSize;
    if (x < 0 || y < 0 || x >= width || y >= height)
        return;
    auto self = ptr<CGui>();
    const int padding = UiTheme::scaled(self, 12);
    const int boxWidth = std::min(width - padding * 2, UiTheme::scaled(self, 560));
    const auto body = "Cannot proceed\n" + message;
    const int boxHeight = std::min(
        height / 2, getTextManager()->measureText(body, std::max(1, boxWidth - padding * 2)).second + padding * 2);
    auto rect = CUtil::rect(std::clamp(x + tileSize, padding, std::max(padding, width - boxWidth - padding)),
                            std::clamp(y - boxHeight, padding, std::max(padding, height - boxHeight - padding)),
                            boxWidth, boxHeight);
    UiTheme::fill(renderer.get(), *rect, UiTheme::Background);
    UiTheme::stroke(renderer.get(), *rect, UiTheme::Danger);
    getTextManager()->drawTextStyled(body, UiTheme::inset(rect, padding), "body", UiTheme::Text);
}

std::string CGui::getUiHistory() const {
    auto entries = json::array();
    for (const auto &entry : activityHistory)
        entries[entries.size()] = entry;
    return entries.dump();
}

std::string CGui::getRecentNotification() const {
    return getActionFeedback().empty() && !activityHistory.empty() && SDL_GetTicks() - notificationTime < 8000
               ? activityHistory.back()
               : "";
}

void CGui::focusWidget(const std::shared_ptr<CGameGraphicsObject> &widget) {
    if (widget && widget->isAttachedToGui(this->ptr<CGui>()))
        focusedWidget = widget;
}

bool CGui::isFocused(const CGameGraphicsObject *widget) const { return focusedWidget.lock().get() == widget; }

void CGui::previewObject(const std::shared_ptr<CGameGraphicsObject> &source, const std::shared_ptr<CGameObject> &object,
                         int x, int y) {
    if (!source || !object)
        return;
    if (hoverObject.lock() != object || hoverSource.lock() != source)
        hoverStarted = SDL_GetTicks();
    hoverObject = object;
    hoverSource = source;
    hoverPosition = {x, y};
    hoverSeen = true;
}

void CGui::renderHoverPreview() {
    auto object = hoverObject.lock();
    auto source = hoverSource.lock();
    if (!object || !source || !source->isAttachedToGui(ptr<CGui>()) || !source->isVisible() || hasDragSession() ||
        SDL_GetTicks() - hoverStarted < static_cast<Uint32>(uiPreferences.value("tooltipDelayMs", 300)))
        return;
    for (const auto &child : getChildren()) {
        if (child->isVisible() && child->getModal() && !ownsGraphicsObject(child, source))
            return;
    }
    auto body = CTooltipHandler::buildTooltip(object);
    if (body.empty())
        return;
    if (body.size() > 800) {
        auto end = std::size_t(800);
        while (end > 0 && (static_cast<unsigned char>(body[end]) & 0xc0) == 0x80)
            --end;
        body.resize(end);
        body += "…";
    }
    body += "\nRight-click to pin inspection";
    const int padding = UiTheme::scaled(ptr<CGui>(), 16);
    const int w = std::min(UiTheme::scaled(ptr<CGui>(), 440), width - padding * 2);
    const int h = std::min(getTextManager()->measureText(body, w - padding * 2).second + padding * 2, height / 2);
    auto rect = CUtil::rect(std::clamp(hoverPosition.x + 20, padding, std::max(padding, width - w - padding)),
                            std::clamp(hoverPosition.y + 20, padding, std::max(padding, height - h - padding)), w, h);
    UiTheme::fill(renderer.get(), *rect, UiTheme::Background);
    UiTheme::stroke(renderer.get(), *rect, UiTheme::Accent);
    getTextManager()->drawTextStyled(body, UiTheme::inset(rect, padding));
}

void CGui::releaseFocusFor(const std::shared_ptr<CGameGraphicsObject> &root) {
    if (ownsGraphicsObject(root, focusedWidget.lock()))
        focusedWidget.reset();
    auto entry = std::find_if(focusHistory.begin(), focusHistory.end(),
                              [&root](const auto &value) { return value.first.lock() == root; });
    if (entry != focusHistory.end()) {
        suppressedKeys.insert(heldKeys.begin(), heldKeys.end());
        auto previous = entry->second.lock();
        const bool top = std::next(entry) == focusHistory.end();
        focusHistory.erase(entry);
        if (top && previous && previous->isAttachedToGui(this->ptr<CGui>()))
            focusedWidget = previous;
    }
}

bool CGui::handleFocusKey(SDL_Event *event) {
    if (event->type != SDL_KEYDOWN && event->type != SDL_KEYUP)
        return false;
    auto self = this->ptr<CGui>();
    std::shared_ptr<CGameGraphicsObject> root = self;
    for (const auto &child : getChildren()) {
        if (child->isVisible() && child->getModal() && (root == self || child->getPriority() > root->getPriority()))
            root = child;
    }
    const auto key = event->key.keysym.sym;
    if (root != self && event->type == SDL_KEYDOWN && event->key.repeat &&
        (key == SDLK_RETURN || key == SDLK_KP_ENTER || key == SDLK_SPACE || (key >= SDLK_1 && key <= SDLK_9)))
        return true;
    std::vector<std::shared_ptr<CGameGraphicsObject>> focusable;
    collectFocusable(root, focusable);
    std::stable_sort(focusable.begin(), focusable.end(), [](const auto &left, const auto &right) {
        const auto a = left->getLayout()->getRect(left);
        const auto b = right->getLayout()->getRect(right);
        return std::tie(a->y, a->x) < std::tie(b->y, b->x);
    });
    auto focused = focusedWidget.lock();
    if (focused && (!ownsGraphicsObject(root, focused) || !focused->isVisible())) {
        focused.reset();
        focusedWidget.reset();
    }
    if (auto list = vstd::cast<CListView>(focused);
        list && list->isSearching() && key >= SDLK_SPACE && key < SDLK_SCANCODE_MASK && key != SDLK_DELETE) {
        // Printable keys belong to SDL_TEXTINPUT until search is dismissed, including
        // letters which are also adventure shortcuts and Space which activates controls.
        return true;
    }
    if (focused && vstd::cast<CListView>(focused) &&
        (key == SDLK_SLASH || key == SDLK_BACKSPACE || key == SDLK_ESCAPE) &&
        focused->keyboardEvent(self, static_cast<SDL_EventType>(event->type), key))
        return true;
    if (key == SDLK_TAB && !focusable.empty()) {
        if (event->type == SDL_KEYDOWN) {
            const bool backward = (event->key.keysym.mod & KMOD_SHIFT) != 0;
            auto found = std::find(focusable.begin(), focusable.end(), focused);
            const auto index = found == focusable.end() ? (backward ? 0 : -1) : std::distance(focusable.begin(), found);
            focusedWidget = focusable[(index + (backward ? -1 : 1) + focusable.size()) % focusable.size()];
        }
        return true;
    }
    if (focused && (key == SDLK_RETURN || key == SDLK_KP_ENTER || key == SDLK_SPACE || key == SDLK_UP ||
                    key == SDLK_DOWN || key == SDLK_LEFT || key == SDLK_RIGHT || key == SDLK_PAGEUP ||
                    key == SDLK_PAGEDOWN || key == SDLK_HOME || key == SDLK_END)) {
        if (focused->keyboardEvent(self, static_cast<SDL_EventType>(event->type), key))
            return true;
        if (vstd::cast<CWidget>(focused) && event->type == SDL_KEYDOWN &&
            (key == SDLK_UP || key == SDLK_DOWN || key == SDLK_LEFT || key == SDLK_RIGHT) && !focusable.empty()) {
            auto index = std::distance(focusable.begin(), std::find(focusable.begin(), focusable.end(), focused));
            focusedWidget = focusable[(index + (key == SDLK_UP || key == SDLK_LEFT ? -1 : 1) + focusable.size()) %
                                      focusable.size()];
            return true;
        }
        if (key == SDLK_SPACE || key == SDLK_RETURN || key == SDLK_KP_ENTER)
            return true;
    }
    return false;
}
