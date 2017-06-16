#pragma once

#include "CGamePanel.h"


class CGameTextPanel : public CGamePanel {
V_META(CGameTextPanel, CGamePanel,
       V_PROPERTY(CGameTextPanel, std::string, text, getText, setText))

    void
    panelRender(std::shared_ptr<CGui> shared_ptr, SDL_Rect *pRect, int i) override;

    void panelEvent(std::shared_ptr<CGui> gui, SDL_Event *pEvent) override;

private:
    struct SDL_Texture *texture = nullptr;
    std::string text;
public:
    std::string getText();

    void setText(std::string ext);

    struct SDL_Texture *loadTextTexture(std::shared_ptr<CGui> ptr);
};

