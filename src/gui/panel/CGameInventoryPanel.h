#pragma once

#include "object/CPlayer.h"
#include "CGamePanel.h"

//TODO: dynamic load of layout from slot configuration
//TODO: make x y adequate to panel size
//TODO: make icons on empty inventory slots
class CGameInventoryPanel : public CGamePanel {
V_META(CGameInventoryPanel, CGamePanel,
       V_PROPERTY(CGameInventoryPanel, int, xInv, getXInv, setXInv),
       V_PROPERTY(CGameInventoryPanel, int, yInv, getYInv, setYInv),
       V_PROPERTY(CGameInventoryPanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness))

public:
    CGameInventoryPanel();

    int getXInv();

    void setXInv(int xInv);

    int getYInv();

    void setYInv(int yInv);

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

private:
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> inventoryView;
    std::shared_ptr<CListView<CItemMap>> equippedView;

    int xInv = 4;
    int yInv = 4;
    int selectionBarThickness = 5;
    std::weak_ptr<CItem> selected;
    std::weak_ptr<CItem> selectedEquipped;

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

    void drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

    bool isInEquipped(std::shared_ptr<CGui> shared_ptr, int x, int y);

    void handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleEnter(std::shared_ptr<CGui> shared_ptr);
};

