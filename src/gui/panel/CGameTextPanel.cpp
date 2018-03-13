

#include "CGameTextPanel.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

std::string CGameTextPanel::getText() {
    return text;
}

void CGameTextPanel::setText(std::string _text) {
    text = _text;
}

void CGameTextPanel::panelRender(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int i) {
    gui->getTextManager()->drawText(text, pRect->x, pRect->y, pRect->w);

}

struct SDL_Texture *CGameTextPanel::loadTextTexture(std::shared_ptr<CGui> ptr) {

}

void CGameTextPanel::panelKeyboardEvent(std::shared_ptr<CGui> gui, SDL_Keycode i) {
    if (i == SDLK_SPACE) {
        gui->removeObject(this->ptr<CGameTextPanel>());
    }
}

CGameTextPanel::~CGameTextPanel() {

}
