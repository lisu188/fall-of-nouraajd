#include "object/CPlayer.h"
#include "CStatsGraphicsObject.h"
#include "gui/CGui.h"
#include "core/CMap.h"
#include "gui/CTextManager.h"

void CStatsGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    drawBar(gui, gui->getGame()->getMap()->getPlayer()->getHpRatio(), 0, pos, RED);
    drawValues(gui, gui->getGame()->getMap()->getPlayer()->getHp(), gui->getGame()->getMap()->getPlayer()->getHpMax(),
               0, pos);
    drawBar(gui, gui->getGame()->getMap()->getPlayer()->getManaRatio(), 1, pos, BLUE);
    drawValues(gui, gui->getGame()->getMap()->getPlayer()->getMana(),
               gui->getGame()->getMap()->getPlayer()->getManaMax(), 1, pos);
    drawBar(gui, gui->getGame()->getMap()->getPlayer()->getExpRatio(), 2, pos, YELLOW);
    drawValues(gui, gui->getGame()->getMap()->getPlayer()->getExp(),
               gui->getGame()->getMap()->getPlayer()->getExpForNextLevel(), 2,
               pos);
}


CStatsGraphicsObject::CStatsGraphicsObject() {

}

void
CStatsGraphicsObject::drawBar(std::shared_ptr<CGui> gui, int ratio, int index, SDL_Rect *pos, Uint8 r, Uint8 g, Uint8 b,
                              Uint8 a) {
    SDL_Rect filledBar;
    filledBar.x = pos->x;
    filledBar.y = pos->y + index * height;
    filledBar.h = height;
    filledBar.w = (int) (ratio / 100.0 * width);

    SDL_SetRenderDrawColor(gui->getRenderer(), r, g, b, a);
    SDL_RenderFillRect(gui->getRenderer(), &filledBar);

    SDL_Rect emptyBar;
    emptyBar.x = pos->x + filledBar.w;
    emptyBar.y = pos->y + index * height;
    emptyBar.h = height;
    emptyBar.w = width - filledBar.w;

    SDL_SetRenderDrawColor(gui->getRenderer(), BLACK);
    SDL_RenderFillRect(gui->getRenderer(), &emptyBar);
}

void
CStatsGraphicsObject::drawValues(std::shared_ptr<CGui> gui, int left, int right, int index, SDL_Rect *pos) {
    gui->getTextManager()->drawTextCentered(vstd::str(left) + "/" + vstd::str(right), pos->x, pos->y + index * height,
                                            width, height);
}