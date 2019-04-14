#pragma once

#include "CGamePanel.h"
#include "core/CList.h"

class CGameCharacterPanel : public CGamePanel {
V_META(CGameCharacterPanel, CGamePanel,
       V_PROPERTY(CGameCharacterPanel, std::shared_ptr<CList>, charSheet, getCharSheet, setCharSheet))

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

public:


    std::shared_ptr<CList> getCharSheet();

    void setCharSheet(std::shared_ptr<CList> charSheet);

    ~CGameCharacterPanel();

private:
    std::shared_ptr<CList> charSheet;
};

