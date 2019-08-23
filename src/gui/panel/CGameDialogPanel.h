#pragma once

#include "CGamePanel.h"


class CGameDialogPanel : public CGamePanel {
V_META(CGameDialogPanel, CGamePanel,
       V_PROPERTY(CGameDialogPanel, std::string, question, getQuestion, setQuestion))

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

public:

    std::string getQuestion();

    void setQuestion(std::string question);

private:
    std::shared_ptr<SDL_Rect> getLeftButtonRect(std::shared_ptr<SDL_Rect> pRect);

    std::shared_ptr<SDL_Rect> getRightButtonRect(std::shared_ptr<SDL_Rect> pRect);

    std::shared_ptr<SDL_Rect> getTextRect(std::shared_ptr<SDL_Rect> pRect);

    std::string question;
};

