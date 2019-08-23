

#include "CGameDialogPanel.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameDialogPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawTextCentered(question, pRect->x, pRect->y, pRect->w, (getYSize() - 100));
    gui->getTextManager()->drawTextCentered("YES", pRect->x,
                                            pRect->y + (getYSize() - 100),
                                            pRect->w / 2, 100);
    gui->getTextManager()->drawTextCentered("NO", pRect->x + (getXSize() / 2),
                                            pRect->y + (getYSize() - 100),
                                            pRect->w / 2, 100);
}


void CGameDialogPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}

std::string CGameDialogPanel::getQuestion() {
    return question;
}

void CGameDialogPanel::setQuestion(std::string question) {
    this->question = question;
}
