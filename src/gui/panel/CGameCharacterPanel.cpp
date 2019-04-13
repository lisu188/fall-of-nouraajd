

#include "core/CJsonUtil.h"
#include "CGameCharacterPanel.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CGameCharacterPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText(
            JSONIFY(gui->getGame()->getMap()->getPlayer()),
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
