#pragma once

#include "CGamePanel.h"


class CGameQuestPanel : public CGamePanel {
V_META(CGameQuestPanel, CGamePanel,
       vstd::meta::empty())

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

public:

    std::string getText(std::shared_ptr<CGui> ptr);
};

