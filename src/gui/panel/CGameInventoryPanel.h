#pragma once

#include <object/CPlayer.h>
#include "CGamePanel.h"

//TODO: dynamic load of layout from slot configuration
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
    int xInv = 0;
    int yInv = 0;
    int selectionBarThickness = 0;
    std::weak_ptr<CItem> selected;

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

    void drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location, int thickness);

    void drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

    bool isInEquipped(std::shared_ptr<CGui> shared_ptr, int x, int y);

    void handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleEnter(std::shared_ptr<CGui> shared_ptr);
};

