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
#include "CListView.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CProvider.h"
#include "core/CScript.h"
#include "core/CUtil.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextureCache.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/object/CWidget.h"
#include "handler/CEventHandler.h"
#include <cstdlib>
#include <exception>
#include <utility>

namespace {
std::shared_ptr<CAnimation> createListItemAnimation(const std::shared_ptr<CGui> &gui,
                                                    const std::shared_ptr<CGameObject> &object) {
    auto cached = object->getGraphicsObject();
    auto animation = CAnimationProvider::getAnimation(gui->getGame(), object);
    animation->setPriority(cached->getPriority());
    animation->setLayout(std::make_shared<CParentLayout>());
    return animation;
}

bool dragMoved(const CGui::DragSession &session) {
    return std::abs(session.current.x - session.start.x) > 0 || std::abs(session.current.y - session.start.y) > 0;
}
} // namespace

void CListView::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> loc, int frameTime) {}

bool CListView::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONUP && button == SDL_BUTTON_LEFT && gui && gui->hasDragSession()) {
        auto self = this->ptr<CListView>();
        const auto *session = gui->getDragSession();
        auto sourceList = vstd::cast<CListView>(session->sourceWidget.lock());
        const bool sourceIsSelf = session->sourceWidget.lock() == self;
        int index = -1;
        std::shared_ptr<CGameObject> object;
        const bool hitObject = tryGetClickedObject(gui, x, y, index, object, hasTargetDragCallbacks());
        if (sourceIsSelf) {
            if (!session->canceled && dragMoved(*session) && hitObject && hasTargetDragCallbacks()) {
                return runDropCallbacks(gui, index, object, sourceList, session->sourceIndex, session->payload);
            }
            if (session->sourceCallbackDeferred && !session->canceled && !dragMoved(*session) && hitObject) {
                invokeCallback(gui, index, object);
            } else if ((session->canceled || dragMoved(*session)) && !session->acceptedTarget.lock()) {
                invokeDragCancel(gui, session->sourceIndex, session->payload);
            }
            return true;
        }
        if (!session->canceled && dragMoved(*session) && hitObject) {
            if (hasTargetDragCallbacks()) {
                return runDropCallbacks(gui, index, object, sourceList, session->sourceIndex, session->payload);
            }
            invokeCallback(gui, index, object);
            gui->acceptDragSession(self);
            return true;
        }
        if (sourceList) {
            sourceList->notifySourceDragCancel(gui, session->sourceIndex, session->payload);
        }
        return false;
    }
    if (type != SDL_MOUSEBUTTONDOWN || (button != SDL_BUTTON_LEFT && button != SDL_BUTTON_RIGHT)) {
        return true;
    }
    int index = -1;
    std::shared_ptr<CGameObject> object;
    if (!tryGetClickedObject(gui, x, y, index, object)) {
        return button != SDL_BUTTON_RIGHT;
    }
    if (button == SDL_BUTTON_RIGHT) {
        return invokeRightClickCallback(gui, index, object);
    }
    if (gui && !dragStart.empty()) {
        if (invokeDragStart(gui, index, object)) {
            auto rect = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : CUtil::rect(0, 0, 0, 0);
            auto self = this->ptr<CListView>();
            gui->startDragSession(self, object, index, rect->x + x, rect->y + y, true);
            gui->capturePointer(self);
        }
        return true;
    }
    if (gui) {
        auto rect = getLayout() ? getLayout()->getRect(this->ptr<CGameGraphicsObject>()) : CUtil::rect(0, 0, 0, 0);
        auto self = this->ptr<CListView>();
        gui->startDragSession(self, object, index, rect->x + x, rect->y + y);
        gui->capturePointer(self);
    }
    invokeCallback(gui, index, object);
    return true;
}

void CListView::doShift(const std::shared_ptr<CGui> &gui, int val) {
    const int itemTypeCount = getItemTypesCount(gui);
    clampShift(gui, itemTypeCount);
    shift += val;
    clampShift(gui, itemTypeCount);
    refreshAll();
}

int CListView::shiftIndex(const std::shared_ptr<CGui> &gui, int arg) {
    const int itemTypeCount = getItemTypesCount(gui);
    clampShift(gui, itemTypeCount);
    if (!isOversizedForCount(gui, itemTypeCount)) {
        return arg;
    }
    return arg > getLeftArrowIndex(gui) ? arg + shift - 1 : arg + shift;
}

int CListView::getRightArrowIndex(const std::shared_ptr<CGui> &gui) { return getSizeX(gui) * getSizeY(gui) - 1; }

int CListView::getLeftArrowIndex(const std::shared_ptr<CGui> &gui) { return getSizeX(gui) * (getSizeY(gui) - 1); }

// TODO: maybe return collection pointer to avoid copying
std::unordered_multimap<int, std::shared_ptr<CGameObject>>
CListView::calculateIndices(const std::shared_ptr<CGui> &gui) {
    if (grouping) {
        collection_pointer collection = invokeCollection(gui);
        vstd::list<std::shared_ptr<CGameObject>> &container = *collection;
        auto reduced = vstd::functional::map_reduce<std::string>(container, [](auto ob) { return ob->getTypeId(); });

        std::unordered_multimap<int, std::shared_ptr<CGameObject>> indices;

        int i = -1;

        for (const auto &it : (reduced)) {
            i++;
            for (const auto &it2 : it.second) {
                indices.insert(std::make_pair(i, it2));
            }
        }
        return indices;
    } else {
        std::unordered_multimap<int, std::shared_ptr<CGameObject>> indices;
        int i = -1;
        collection_pointer sharedPtr = invokeCollection(gui);
        for (const auto &it : (*sharedPtr)) {
            indices.insert(std::make_pair(++i, it));
        }
        return indices;
    }
}

std::shared_ptr<SDL_Rect> CListView::calculateIndexPosition(const std::shared_ptr<CGui> &gui,
                                                            const std::shared_ptr<SDL_Rect> &loc, int index) {
    return CUtil::rect(tileSize * (index % getSizeX(gui)) + loc->x, tileSize * (index / getSizeX(gui)) + loc->y,
                       tileSize, tileSize);
}

bool CListView::isOversized(const std::shared_ptr<CGui> &gui) {
    const int itemTypeCount = getItemTypesCount(gui);
    clampShift(gui, itemTypeCount);
    return isOversizedForCount(gui, itemTypeCount);
}

int CListView::getItemTypesCount(const std::shared_ptr<CGui> &gui) {
    auto map = calculateIndices(gui);
    std::set<int> indices;
    for (const auto &it : map) {
        indices.insert(it.first);
    }
    auto size = indices.size();
    return size;
}

// TODO: sizes should be calculated dynamically based on preferences
int CListView::getSizeX(std::shared_ptr<CGui> gui) {
    const int safeTileSize = std::max(1, tileSize);
    return xPrefferedSize != -1 ? std::clamp(xPrefferedSize, 1, 128)
                                : std::max(1, getLayout()->getRect(this->ptr<CListView>())->w / safeTileSize);
}

// TODO: sizes should be calculated dynamically based on preferences
int CListView::getSizeY(std::shared_ptr<CGui> gui) {
    const int safeTileSize = std::max(1, tileSize);
    return yPrefferedSize != -1 ? std::clamp(yPrefferedSize, 1, 128)
                                : std::max(1, getLayout()->getRect(this->ptr<CListView>())->h / safeTileSize);
}

int CListView::getCellCount(const std::shared_ptr<CGui> &gui) { return std::max(1, getSizeX(gui) * getSizeY(gui)); }

bool CListView::isOversizedForCount(const std::shared_ptr<CGui> &gui, int itemTypeCount) {
    return allowOversize && itemTypeCount > getCellCount(gui);
}

int CListView::getVisibleItemSlots(const std::shared_ptr<CGui> &gui, int itemTypeCount) {
    if (!isOversizedForCount(gui, itemTypeCount)) {
        return getCellCount(gui);
    }
    return std::max(1, getCellCount(gui) - 2);
}

int CListView::getMaxShift(const std::shared_ptr<CGui> &gui, int itemTypeCount) {
    if (!isOversizedForCount(gui, itemTypeCount)) {
        return 0;
    }
    return std::max(0, itemTypeCount - getVisibleItemSlots(gui, itemTypeCount));
}

void CListView::clampShift(const std::shared_ptr<CGui> &gui, int itemTypeCount) {
    shift = std::clamp(shift, 0, getMaxShift(gui, itemTypeCount));
}

CListView::collection_pointer CListView::invokeCollection(std::shared_ptr<CGui> gui) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || collection.empty()) {
        return std::make_shared<CListView::collection_type>();
    }
    try {
        return parent->meta()->invoke_method<CListView::collection_pointer, CGameGraphicsObject, std::shared_ptr<CGui>>(
            collection, vstd::cast<CGameGraphicsObject>(parent), gui);
    } catch (const std::exception &e) {
        vstd::logger::warning("Ignoring list collection callback failure:", collection, "on", parent->getType(),
                              e.what());
        return std::make_shared<CListView::collection_type>();
    }
}

void CListView::invokeCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || callback.empty()) {
        return;
    }
    try {
        parent->meta()
            ->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                callback, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list callback failure:", callback, exception.what());
    }
}

bool CListView::invokeRightClickCallback(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || rightClickCallback.empty()) {
        return false;
    }
    try {
        return parent->meta()
            ->invoke_method<bool, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                rightClickCallback, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list right-click callback failure:", rightClickCallback, exception.what());
        return false;
    }
}

auto CListView::getArrowCallback(bool left) {
    return [this, left](std::shared_ptr<CGui> gui, SDL_EventType type, int button, int, int) {
        if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
            doShift(gui, left ? -1 : 1);
        }
        return true;
    };
}

bool CListView::invokeSelect(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || select.empty()) {
        return false;
    }
    try {
        return parent->meta()
            ->invoke_method<bool, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                select, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list select callback failure:", select, exception.what());
        return false;
    }
}

bool CListView::invokeDragStart(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || dragStart.empty()) {
        return true;
    }
    try {
        return parent->meta()
            ->invoke_method<bool, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                dragStart, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list drag-start callback failure:", dragStart, exception.what());
        return false;
    }
}

bool CListView::invokeDragValidate(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || dragValidate.empty()) {
        return true;
    }
    try {
        return parent->meta()
            ->invoke_method<bool, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                dragValidate, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list drag-validate callback failure:", dragValidate, exception.what());
        return false;
    }
}

void CListView::invokeDrop(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || drop.empty()) {
        return;
    }
    try {
        parent->meta()
            ->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                drop, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list drop callback failure:", drop, exception.what());
    }
}

void CListView::invokeDragCancel(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object) {
    auto parent = getParent();
    if (!canInvokeParentCallback(gui, parent) || dragCancel.empty()) {
        return;
    }
    try {
        parent->meta()
            ->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>>(
                dragCancel, vstd::cast<CGameGraphicsObject>(parent), gui, i, object);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring list drag-cancel callback failure:", dragCancel, exception.what());
    }
}

bool CListView::canInvokeParentCallback(const std::shared_ptr<CGui> &gui,
                                        const std::shared_ptr<CGameGraphicsObject> &parent) {
    return parent && isAttachedToGui(gui) && parent->isAttachedToGui(gui);
}

bool CListView::tryGetClickedObject(std::shared_ptr<CGui> gui, int x, int y, int &index,
                                    std::shared_ptr<CGameObject> &object, bool allowEmptyCell) {
    const int itemTypeCount = getItemTypesCount(gui);
    clampShift(gui, itemTypeCount);
    const int safeTileSize = std::max(1, tileSize);
    int xIndex = x / safeTileSize;
    int yIndex = y / safeTileSize;
    if (xIndex < 0 || yIndex < 0 || xIndex >= getSizeX(gui) || yIndex >= getSizeY(gui)) {
        return false;
    }
    index = shiftIndex(gui, xIndex + (yIndex * getSizeX(gui)));
    auto indexedCollection = calculateIndices(gui);
    if (!vstd::ctn(indexedCollection, index)) {
        if (allowEmptyCell && showEmpty && !isOversizedForCount(gui, itemTypeCount)) {
            object = nullptr;
            return true;
        }
        return false;
    }
    object = indexedCollection.find(index)->second;
    return true;
}

bool CListView::hasSourceDragCallbacks() const { return !dragStart.empty(); }

bool CListView::hasTargetDragCallbacks() const { return !dragValidate.empty() || !drop.empty(); }

bool CListView::runDropCallbacks(std::shared_ptr<CGui> gui, int i, std::shared_ptr<CGameObject> object,
                                 const std::shared_ptr<CListView> &sourceList, int sourceIndex,
                                 std::shared_ptr<CGameObject> sourceObject) {
    if (!invokeDragValidate(gui, i, object)) {
        if (sourceList) {
            sourceList->notifySourceDragCancel(gui, sourceIndex, sourceObject);
        }
        return false;
    }
    invokeDrop(gui, i, object);
    if (gui) {
        gui->acceptDragSession(this->ptr<CListView>());
    }
    return true;
}

void CListView::notifySourceDragCancel(std::shared_ptr<CGui> gui, int sourceIndex,
                                       std::shared_ptr<CGameObject> sourceObject) {
    invokeDragCancel(gui, sourceIndex, sourceObject);
}

std::list<std::shared_ptr<CGameGraphicsObject>> CListView::getProxiedObjects(std::shared_ptr<CGui> gui, int x, int y) {
    std::list<std::shared_ptr<CGameGraphicsObject>> return_val;
    if (!isAttachedToGui(gui) || !gui->getGame()) {
        return return_val;
    }
    const int itemTypeCount = getItemTypesCount(gui);
    clampShift(gui, itemTypeCount);
    int i = getSizeX(gui) * y + x;
    const bool oversized = isOversizedForCount(gui, itemTypeCount);
    if (i == getLeftArrowIndex(gui) && oversized) {
        return_val.push_back(CAnimationProvider::getAnimation(gui->getGame(),
                                                              "images/arrows/left")
                                 ->withCallback(getArrowCallback(true))); // TODO: cache
    } else if (i == getRightArrowIndex(gui) && oversized) {
        return_val.push_back(CAnimationProvider::getAnimation(gui->getGame(),
                                                              "images/arrows/right")
                                 ->withCallback(getArrowCallback(false))); // TODO: cache
    } else {
        auto indexedCollection = calculateIndices(gui);
        int itemIndex = shiftIndex(gui, i);

        bool isItemPresent = vstd::ctn(indexedCollection, itemIndex) && indexedCollection.find(itemIndex)->second;

        if (isItemPresent || showEmpty) {
            addItemBox(gui, return_val);
        }
        if (isItemPresent) {
            addItem(gui, return_val, indexedCollection, itemIndex);
        }
        if (invokeSelect(gui, itemIndex, isItemPresent ? indexedCollection.find(itemIndex)->second : nullptr)) {
            addSelectionBox(gui, return_val);
        }
        if (indexedCollection.count(itemIndex) > 1) {
            addCountBox(gui, indexedCollection.count(itemIndex), return_val);
        }
    }
    return return_val;
}

void CListView::addCountBox(const std::shared_ptr<CGui> &gui, int count,
                            std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    auto countBox = gui->getGame()->getObjectHandler()->createObject<CTextWidget>(gui->getGame());
    countBox->setText(vstd::str(count));
    auto layout = gui->getGame()->getObjectHandler()->createObject<CLayout>(gui->getGame());
    layout->setHorizontal("LEFT");
    layout->setVertical("UP");
    layout->setW("25%");
    layout->setH("25%");
    countBox->setLayout(layout);
    countBox->setPriority(4);
    return_val.push_back(countBox); // TODO: cache
}

void CListView::addSelectionBox(const std::shared_ptr<CGui> &gui,
                                std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    auto selectionBox = gui->getGame()->getObjectHandler()->createObject<CSelectionBox>(gui->getGame());
    selectionBox->setThickness(5);
    selectionBox->setPriority(3);
    return_val.push_back(selectionBox); // TODO: cache
}

void CListView::addItem(const std::shared_ptr<CGui> &gui, std::list<std::shared_ptr<CGameGraphicsObject>> &return_val,
                        std::unordered_multimap<int, std::shared_ptr<CGameObject>> indexedCollection,
                        int itemIndex) const {
    auto self = const_cast<CListView *>(this)->ptr<CListView>();
    auto object = indexedCollection.find(itemIndex)->second;
    auto itemAnimation = createListItemAnimation(gui, object);
    std::weak_ptr<CGameGraphicsObject> sourceGraphic = itemAnimation;
    std::shared_ptr<CGameGraphicsObject> objectGraphic =
        itemAnimation->withCallback([self, sourceGraphic, itemIndex,
                                     object](std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
            if (type != SDL_MOUSEBUTTONDOWN) {
                return false;
            }
            if (!self->isAttachedToGui(gui)) {
                return true;
            }
            if (button == SDL_BUTTON_LEFT) {
                const bool deferSourceCallback = self->invokeSelect(gui, itemIndex, object);
                bool dragStarted = false;
                if (auto source = sourceGraphic.lock()) {
                    auto rect = source->getLayout() ? source->getLayout()->getRect(source) : CUtil::rect(0, 0, 0, 0);
                    if (self->hasSourceDragCallbacks()) {
                        if (self->invokeDragStart(gui, itemIndex, object)) {
                            gui->startDragSession(self, object, itemIndex, rect->x + x, rect->y + y, true);
                            gui->capturePointer(self);
                            dragStarted = gui->hasDragSession();
                        }
                    } else {
                        gui->startDragSession(self, object, itemIndex, rect->x + x, rect->y + y, deferSourceCallback);
                        gui->capturePointer(self);
                        dragStarted = gui->hasDragSession();
                    }
                }
                if (!self->hasSourceDragCallbacks() && (!deferSourceCallback || !dragStarted)) {
                    self->invokeCallback(gui, itemIndex, object);
                }
                return true;
            }
            if (button == SDL_BUTTON_RIGHT) {
                return self->invokeRightClickCallback(gui, itemIndex, object);
            }
            return false;
        });
    objectGraphic->setPriority(2);
    return_val.push_back(objectGraphic);
}

void CListView::addItemBox(const std::shared_ptr<CGui> &gui,
                           std::list<std::shared_ptr<CGameGraphicsObject>> &return_val) const {
    std::shared_ptr<CAnimation> itemBox =
        CAnimationProvider::getAnimation(gui->getGame(), "images/item")
            ->withCallback([](std::shared_ptr<CGui>, SDL_EventType, int, int, int) { return false; });
    itemBox->setPriority(1);
    return_val.push_back(itemBox); // TODO: cache
}

std::string CListView::getCollection() { return collection; }

void CListView::setCollection(std::string collection) { CListView::collection = collection; }

std::string CListView::getCallback() { return callback; }

void CListView::setCallback(std::string callback) { CListView::callback = callback; }

std::string CListView::getRightClickCallback() { return rightClickCallback; }

void CListView::setRightClickCallback(std::string rightClickCallback) {
    CListView::rightClickCallback = rightClickCallback;
}

std::string CListView::getSelect() { return select; }

void CListView::setSelect(std::string select) { CListView::select = select; }

std::string CListView::getDragStart() { return dragStart; }

void CListView::setDragStart(std::string dragStart) { CListView::dragStart = dragStart; }

std::string CListView::getDragValidate() { return dragValidate; }

void CListView::setDragValidate(std::string dragValidate) { CListView::dragValidate = dragValidate; }

std::string CListView::getDrop() { return drop; }

void CListView::setDrop(std::string drop) { CListView::drop = drop; }

std::string CListView::getDragCancel() { return dragCancel; }

void CListView::setDragCancel(std::string dragCancel) { CListView::dragCancel = dragCancel; }

std::shared_ptr<CScript> CListView::getRefreshObject() { return refreshObject; }

void CListView::setRefreshObject(std::shared_ptr<CScript> refreshObject) {
    CListView::refreshObject = refreshObject;
    refreshSubscriptions();
}

std::string CListView::getRefreshEvent() { return refreshEvent; }

void CListView::setRefreshEvent(std::string refreshEvent) {
    CListView::refreshEvent = refreshEvent;
    refreshSubscriptions();
}

bool CListView::getRefreshOnPropertyChanged() { return refreshOnPropertyChanged; }

void CListView::setRefreshOnPropertyChanged(bool refreshOnPropertyChanged) {
    CListView::refreshOnPropertyChanged = refreshOnPropertyChanged;
    refreshSubscriptions();
}

std::set<std::string> CListView::getRefreshProperties() { return refreshProperties; }

void CListView::setRefreshProperties(std::set<std::string> refreshProperties) {
    CListView::refreshProperties = std::move(refreshProperties);
    refreshSubscriptions();
}

void CListView::initialize() {
    auto self = this->ptr<CListView>();
    vstd::call_when(
        [self]() {
            return self->getGui() != nullptr && self->getGui()->getGame() != nullptr &&
                   self->getGui()->getGame()->getMap() != nullptr;
        },
        [self]() {
            self->refreshSubscriptions();
            self->refresh();
        });
}

void CListView::refresh() {
    refreshSubscriptions();
    CProxyTargetGraphicsObject::refresh();
    refreshAll();
}

void CListView::refreshFromRefreshEvent() { refreshFromSubscription(); }

void CListView::refreshFromPropertyChanged(std::string propertyName) {
    refreshSubscriptions();
    if (shouldRefreshForProperty(propertyName)) {
        refreshFromSubscription();
    }
}

void CListView::refreshFromPropertiesChanged(std::set<std::string> propertyNames) {
    refreshSubscriptions();
    bool shouldRefresh = refreshOnPropertyChanged;
    for (const auto &propertyName : propertyNames) {
        shouldRefresh = shouldRefresh || shouldRefreshForProperty(propertyName);
    }
    if (shouldRefresh) {
        refreshFromSubscription();
    }
}

void CListView::refreshFromPropertySpecificChanged() {
    refreshSubscriptions();
    refreshFromSubscription();
}

std::shared_ptr<CGameObject> CListView::resolveRefreshTarget() {
    if (!refreshObject) {
        return nullptr;
    }
    auto gui = getGui();
    if (!gui || !gui->getGame()) {
        return nullptr;
    }
    return refreshObject->invoke(gui->getGame(), this->ptr<CListView>());
}

void CListView::refreshSubscriptions() {
    auto refreshTarget = resolveRefreshTarget();
    auto subscribedTarget = refreshSubscriptionTarget.lock();
    if (subscribedTarget == refreshTarget && subscribedRefreshEvent == refreshEvent &&
        subscribedRefreshOnPropertyChanged == refreshOnPropertyChanged &&
        subscribedRefreshProperties == refreshProperties) {
        return;
    }

    disconnectRefreshSubscriptions();
    refreshSubscriptionTarget = refreshTarget;
    subscribedRefreshEvent = refreshEvent;
    subscribedRefreshOnPropertyChanged = refreshOnPropertyChanged;
    subscribedRefreshProperties = refreshProperties;
    connectRefreshSubscriptions(refreshTarget);
}

void CListView::disconnectRefreshSubscriptions() {
    auto refreshTarget = refreshSubscriptionTarget.lock();
    if (!refreshTarget) {
        return;
    }

    auto self = this->ptr<CListView>();
    if (!subscribedRefreshEvent.empty()) {
        refreshTarget->disconnect(subscribedRefreshEvent, self, "refreshFromRefreshEvent");
    }
    if (subscribedRefreshOnPropertyChanged) {
        refreshTarget->disconnect("propertyChanged", self, "refreshFromPropertyChanged");
    }
    if (subscribedRefreshOnPropertyChanged || !subscribedRefreshProperties.empty()) {
        refreshTarget->disconnect("propertiesChanged", self, "refreshFromPropertiesChanged");
    }
    if (!subscribedRefreshOnPropertyChanged) {
        for (const auto &propertyName : subscribedRefreshProperties) {
            if (!propertyName.empty()) {
                refreshTarget->disconnect(propertyName + "Changed", self, "refreshFromPropertySpecificChanged");
            }
        }
    }
}

void CListView::connectRefreshSubscriptions(const std::shared_ptr<CGameObject> &refreshTarget) {
    if (!refreshTarget) {
        return;
    }

    auto self = this->ptr<CListView>();
    if (!refreshEvent.empty()) {
        refreshTarget->connect(refreshEvent, self, "refreshFromRefreshEvent");
    }
    if (refreshOnPropertyChanged) {
        refreshTarget->connect("propertyChanged", self, "refreshFromPropertyChanged");
    }
    if (refreshOnPropertyChanged || !refreshProperties.empty()) {
        refreshTarget->connect("propertiesChanged", self, "refreshFromPropertiesChanged");
    }
    if (!refreshOnPropertyChanged) {
        for (const auto &propertyName : refreshProperties) {
            if (!propertyName.empty()) {
                refreshTarget->connect(propertyName + "Changed", self, "refreshFromPropertySpecificChanged");
            }
        }
    }
}

void CListView::refreshFromSubscription() {
    if (refreshFromSubscriptionQueued) {
        return;
    }

    refreshFromSubscriptionQueued = true;
    std::weak_ptr<CListView> weakSelf = this->ptr<CListView>();
    vstd::call_later([weakSelf]() {
        auto self = weakSelf.lock();
        if (!self) {
            return;
        }

        self->refreshFromSubscriptionQueued = false;
        auto gui = self->getGui();
        if (!self->isAttachedToGui(gui)) {
            return;
        }

        self->refreshSubscriptions();
        self->refresh();
    });
}

bool CListView::shouldRefreshForProperty(const std::string &propertyName) const {
    return refreshOnPropertyChanged || refreshProperties.contains(propertyName);
}

int CListView::getXPrefferedSize() const { return xPrefferedSize; }

void CListView::setXPrefferedSize(int xPrefferedSize) { CListView::xPrefferedSize = xPrefferedSize; }

int CListView::getYPrefferedSize() const { return yPrefferedSize; }

void CListView::setYPrefferedSize(int yPrefferedSize) { CListView::yPrefferedSize = yPrefferedSize; }

int CListView::getTileSize() { return tileSize; }

void CListView::setTileSize(int _tileSize) { tileSize = std::clamp(_tileSize, 1, 512); }

bool CListView::getAllowOversize() { return allowOversize; }

void CListView::setAllowOversize(bool _allowOversize) { allowOversize = _allowOversize; }

bool CListView::getShowEmpty() { return showEmpty; }

void CListView::setShowEmpty(bool _showEmpty) { showEmpty = _showEmpty; }

bool CListView::getGrouping() { return grouping; }

void CListView::setGrouping(bool _grouping) { grouping = _grouping; }
