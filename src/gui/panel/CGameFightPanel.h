#pragma once

#include "object/CPlayer.h"
#include "CGamePanel.h"
#include "gui/panel/CListView.h"

class CGameFightPanel : public CGamePanel {
V_META(CGameFightPanel, CGamePanel,
       V_PROPERTY(CGameFightPanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness))

public:
    CGameFightPanel();

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

    std::shared_ptr<CInteraction> selectInteraction();

    std::shared_ptr<CCreature> getEnemy();

    void setEnemy(std::shared_ptr<CCreature> en);

private:
    std::shared_ptr<CListView<std::set<std::shared_ptr<CInteraction>>>> interactionsView;
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> itemsView;

    int selectionBarThickness = 5;
    std::weak_ptr<CCreature> enemy;
    std::weak_ptr<CInteraction> selected;
    std::weak_ptr<CItem> selectedItem;
    std::weak_ptr<CInteraction> finalSelected;

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

    void drawInteractions(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawEnemy(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInteractions(std::shared_ptr<CGui> x, int y, int i1);

    void handleInteractionsClick(std::shared_ptr<CGui> gui, int x, int y);

    bool isInInventory(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    int tileSize = 50;//TODO: make property
    int getInventoryLocation(std::shared_ptr<CGui> gui);

    int getInteractionsLocation(std::shared_ptr<CGui> gui);
};

