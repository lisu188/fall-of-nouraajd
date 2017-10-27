#pragma once

#include "CGamePanel.h"


class CGameCharacterPanel : public CGamePanel {
V_META(CGameCharacterPanel, CGamePanel,
       vstd::meta::empty())

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

private:
    struct SDL_Texture *texture = nullptr;
public:

    ~CGameCharacterPanel();

    struct SDL_Texture *loadTextTexture(std::shared_ptr<CGui> ptr);
};

