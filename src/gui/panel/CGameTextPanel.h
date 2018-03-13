#pragma once

#include "CGamePanel.h"


class CGameTextPanel : public CGamePanel {
V_META(CGameTextPanel, CGamePanel,
       V_PROPERTY(CGameTextPanel, std::string, text, getText, setText))

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;


private:
    std::string text;
public:
    ~CGameTextPanel();

    std::string getText();

    void setText(std::string ext);

    struct SDL_Texture *loadTextTexture(std::shared_ptr<CGui> ptr);
};

