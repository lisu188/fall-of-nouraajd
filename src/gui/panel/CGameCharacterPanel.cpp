

#include "core/CJsonUtil.h"
#include "CGameCharacterPanel.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"
#include "core/CList.h"

//TODO: make charSheet singleton
void CGameCharacterPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    std::string text;
    for (auto prop : gui->getGame()->createObject<CList>("charSheet")->getValues()) {
        text += prop + ": " + vstd::str(gui->getGame()->getMap()->getPlayer()->getNumericProperty(prop)) + "\n";
    }
    gui->getTextManager()->drawText(
            text,
            pRect->x,
            pRect->y,
            pRect->w);

}

void CGameCharacterPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameCharacterPanel>());
    }
}

CGameCharacterPanel::~CGameCharacterPanel() {

}
