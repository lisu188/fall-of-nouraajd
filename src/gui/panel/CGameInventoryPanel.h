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

};

