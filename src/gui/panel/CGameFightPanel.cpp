

#include "core/CEventLoop.h"
#include "CGameFightPanel.h"
#include "gui/CGui.h"

void CGameFightPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    SDL_RenderFillRect(gui->getRenderer(), pRect.get());
    drawInteractions(gui, pRect, i);
    drawEnemy(gui, pRect, i);
}

void CGameFightPanel::drawInteractions(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime) {
    std::shared_ptr < SDL_Rect > location = std::make_shared<SDL_Rect>(*pRect.get());
    location->y += (getYSize() - gui->getTileSize());

    drawCollection(gui, location,
                   [this, gui]() {
                       return gui->getGame()->getMap()->getPlayer()->getInteractions();
                   }, getXSize() / gui->getTileSize(), 1, gui->getTileSize(),
                   [this, gui](auto ob, int prevIndex) {
                       return prevIndex + 1;
                   },
                   [this, gui, frameTime](auto item, auto loc) {
                       item->getAnimationObject()->render(gui, loc, frameTime);
                   }, [this, gui](auto object) {
                return selected.lock() == object;
            }, [this](auto g, auto l, auto t) {
                this->drawSelection(g, l, t);
            }, selectionBarThickness);
}


CGameFightPanel::CGameFightPanel() {

}

void CGameFightPanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    if (isInInteractions(gui, x, y)) {
        handleInteractionsClick(gui, x, y);
    }
}

void CGameFightPanel::handleInteractionsClick(std::shared_ptr<CGui> gui, int x, int y) {
    onClicked([this, gui]() {
                  return gui->getGame()->getMap()->getPlayer()->getInteractions();
              }, x, y - (getYSize() - gui->getTileSize()), getXSize() / gui->getTileSize(), 1, gui->getTileSize(),
              [this, gui](auto item, int prevIndex) {
                  return prevIndex + 1;
              }, [this, gui](auto newSelection) {
                if (selected.lock() != newSelection) {
                    selected = newSelection;
                } else if (selected.lock() == newSelection) {
                    finalSelected = newSelection;
                } else {
                    selected.reset();
                }
            });

}


bool CGameFightPanel::isInInteractions(std::shared_ptr<CGui> gui, int x, int y) {
    return y > (getYSize() - gui->getTileSize());
}


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
    SDL_Rect loc;
    loc.x = pRect->x + (getXSize() / 2 - size / 2);
    loc.y = pRect->y + ((getYSize() - gui->getTileSize()) / 2 - size / 2);
    loc.w = size;
    loc.h = size;
    enemy.lock()->getAnimationObject()->render(gui, &loc, frameTime);
}
