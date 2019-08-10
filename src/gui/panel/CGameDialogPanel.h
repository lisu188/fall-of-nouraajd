#pragma once

#include "CGamePanel.h"


class CGameDialogPanel : public CGamePanel {
V_META(CGameDialogPanel, CGamePanel,
       vstd::meta::empty())

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

public:

};

