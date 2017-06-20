#pragma once

#include <object/CPlayer.h>
#include "CGamePanel.h"


class CGameInventoryPanel : public CGamePanel {
V_META(CGameInventoryPanel, CGamePanel, vstd::meta::empty())

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

//TODO: get rid of this!
    std::shared_ptr<CPlayer> _player;
public:
    CGameInventoryPanel();

    CGameInventoryPanel(std::shared_ptr<CPlayer> _player);

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

private:
    int xInv = 4;
    int yInv = 4;

    int selectionBarThickness = 5;

    std::string selected = "";

    void drawSelection(std::shared_ptr<CGui> gui, SDL_Rect *location);
};

