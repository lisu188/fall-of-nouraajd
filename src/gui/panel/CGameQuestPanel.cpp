

#include "CGameQuestPanel.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameQuestPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText(getText(gui), pRect->x, pRect->y, pRect->w);
}


std::string CGameQuestPanel::getText(std::shared_ptr<CGui> ptr) {
    std::__cxx11::string text = "";
    for (auto quest:ptr->getGame()->getMap()->getPlayer()->getCompletedQuests()) {
        text += quest->getDescription();
            text += "(completed)";
        text += "\n";
    }
    for (auto quest:ptr->getGame()->getMap()->getPlayer()->getQuests()) {
        text += quest->getDescription();
        text += "\n";
    }
    return text;
}

void CGameQuestPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}
