#include "CGameFightPanel.h"
#include "gui/CAnimation.h"
#include "gui/CTextureCache.h"
#include "core/CMap.h"
#include "gui/object/CStatsGraphicsObject.h"

void CGameFightPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    drawInteractions(gui, pRect, i);
    drawEnemy(gui, pRect, i);
}

void CGameFightPanel::drawInteractions(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr<SDL_Rect> location = std::make_shared<SDL_Rect>(*pRect.get());//cloning, do not remove
    location->y += (getYSize() - gui->getTileSize());

    interactionsView->drawCollection(gui,
                                     location,
                                     [this, gui](int index, auto object) {
                                         return selected.lock() == object;
                                     },
                                     selectionBarThickness, frameTime);

    location->y -= gui->getTileSize();

    itemsView->drawCollection(gui,
                              location,
                              [this, gui](int index, auto object) {
                                  return selectedItem.lock() == object;
                              },
                              selectionBarThickness, frameTime);
}


CGameFightPanel::CGameFightPanel() {
    interactionsView = std::make_shared<CListView<std::set<
            std::shared_ptr<
                    CInteraction>>>>(
            getXSize() / tileSize, 1,
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getInteractions();
            },
            [](auto ob, int prevIndex) {
                return prevIndex + 1;
            },
            [this](std::shared_ptr<CGui> gui,
                   auto newSelection) {
                if (selected.lock() !=
                    newSelection) {
                    selected = newSelection;
                } else if (
                        selected.lock() ==
                        newSelection &&
                        newSelection->getManaCost() <=
                        gui->getGame()->getMap()->getPlayer()->getMana()) {
                    finalSelected = newSelection;
                } else {
                    //TODO: rethink moving selection to CListView
                    selected.reset();
                }
            },
            [](auto gui, auto item, auto loc, auto frameTime) {
                item->getAnimationObject()->render(gui, loc, frameTime);
            },
            tileSize,
            true);

    itemsView = std::make_shared<CListView<std::set<
            std::shared_ptr<
                    CItem>>>>(
            getXSize() / tileSize, 1,
            [](std::shared_ptr<CGui> gui) {
                return gui->getGame()->getMap()->getPlayer()->getItems();
            },
            [](auto ob, int prevIndex) {
                return prevIndex + 1;
            },
            [this](std::shared_ptr<CGui> gui,
                   auto newSelection) {

                if (selectedItem.lock() != newSelection) {
                    selectedItem = newSelection;
                } else if (selectedItem.lock() == newSelection) {
                    gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
                    selectedItem.reset();
                }
            },
            [](auto gui, auto item, auto loc, auto frameTime) {
                item->getAnimationObject()->render(gui, loc, frameTime);
            },
            tileSize,
            true);
}

void CGameFightPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    //TODO: shift values
    if (isInInteractions(gui, x, y)) {
        handleInteractionsClick(gui, x, y - getInteractionsLocation(gui));
    } else if (isInInventory(gui, x, y)) {
        handleInventoryClick(gui, x, y - getInventoryLocation(gui));
    }
}

void CGameFightPanel::handleInteractionsClick(std::shared_ptr<CGui> gui, int x, int y) {
    interactionsView->onClicked(gui, x, y);
}


void CGameFightPanel::handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y) {
    itemsView->onClicked(gui, x, y);

}

bool CGameFightPanel::isInInteractions(std::shared_ptr<CGui> gui, int x, int y) {
    return y > (getInteractionsLocation(gui)) && !isInInventory(gui, x, y);
}

int CGameFightPanel::getInteractionsLocation(std::shared_ptr<CGui> gui) { return getYSize() - gui->getTileSize(); }

//TODO: make this method strict
bool CGameFightPanel::isInInventory(std::shared_ptr<CGui> gui, int x, int y) {
    return y > (getInventoryLocation(gui));
}

int CGameFightPanel::getInventoryLocation(std::shared_ptr<CGui> gui) { return getYSize() - (gui->getTileSize() * 2); }


int CGameFightPanel::getSelectionBarThickness() {
    return selectionBarThickness;
}

void CGameFightPanel::setSelectionBarThickness(int selectionBarThickness) {
    CGameFightPanel::selectionBarThickness = selectionBarThickness;
}

std::shared_ptr<CInteraction> CGameFightPanel::getInteraction() {
    vstd::wait_until([this]() {
        return finalSelected.lock() != nullptr;
    });
    return finalSelected.lock();
}

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() {
    return enemy.lock();
}

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) {
    enemy = en;
}

void CGameFightPanel::drawEnemy(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    int size = gui->getTileSize() * 4;
    std::shared_ptr<SDL_Rect> loc = std::make_shared<SDL_Rect>();
    loc->x = pRect->x + (getXSize() / 2 - size / 2);
    loc->y = pRect->y + ((getYSize() - gui->getTileSize()) / 2 - size / 2);
    loc->w = size;
    loc->h = size;
    enemy.lock()->getAnimationObject()->render(gui, loc, frameTime);

    CStatsGraphicsUtil::drawStats(gui, enemy.lock(), loc->x, loc->y + loc->h, loc->w, loc->h / 4.0, false, false);
}
