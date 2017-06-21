#pragma once

#include <object/CPlayer.h>
#include "CGamePanel.h"

//TODO: dynamic load of layout from slot configuration
class CGameInventoryPanel : public CGamePanel {
V_META(CGameInventoryPanel, CGamePanel,
       V_PROPERTY(CGameInventoryPanel, int, xInv, getXInv, setXInv),
       V_PROPERTY(CGameInventoryPanel, int, yInv, getYInv, setYInv),
       V_PROPERTY(CGameInventoryPanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness))

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

public:
    CGameInventoryPanel();

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

private:
    int xInv = 0;
    int yInv = 0;

    int selectionBarThickness = 0;
public:
    int getXInv();

    void setXInv(int xInv);

    int getYInv();

    void setYInv(int yInv);

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

private:


    std::weak_ptr<CItem> selected;

    void drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location, int thickness);

    void drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawEquipped(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInEquipped(std::shared_ptr<CGui> shared_ptr, int x, int y);

    void handleEquippedClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleEnter(std::shared_ptr<CGui> shared_ptr);
};

