#include "core/CJsonUtil.h"
#include "CGameCharacterPanel.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameCharacterPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    std::string text;
    for (auto prop : charSheet->getValues()) {
        text += prop + ": " + vstd::str(gui->getGame()->getMap()->getPlayer()->getNumericProperty(prop)) + "\n";
    }
    gui->getTextManager()->drawText(
            text,
            pRect->x,
            pRect->y,
            pRect->w);

}

void CGameCharacterPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {

}

CGameCharacterPanel::~CGameCharacterPanel() {

}

std::shared_ptr<CListString> CGameCharacterPanel::getCharSheet() {
    return charSheet;
}

void CGameCharacterPanel::setCharSheet(std::shared_ptr<CListString> charSheet) {
    CGameCharacterPanel::charSheet = charSheet;
}
