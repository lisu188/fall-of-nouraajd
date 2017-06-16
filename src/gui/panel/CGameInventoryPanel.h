#pragma once

#include <object/CPlayer.h>
#include "CGamePanel.h"


class CGameInventoryPanel : public CGamePanel {
V_META(CGameInventoryPanel, CGamePanel, vstd::meta::empty())
//TODO: get rid of this!
    std::shared_ptr<CPlayer> _player;
public:
    CGameInventoryPanel();

    CGameInventoryPanel(std::shared_ptr<CPlayer> _player);

    void panelRender(std::shared_ptr<CGui> shared_ptr, SDL_Rect *pRect, int i, std::string basic_string) override;

    void panelEvent(std::shared_ptr<CGui> gui, SDL_Event *pEvent) override;

};

