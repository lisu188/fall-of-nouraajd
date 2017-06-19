#include "object/CPlayer.h"
#include "CStatsGraphicsObject.h"
#include "gui/CGui.h"

void CStatsGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) {
    drawBar(gui, _player()->getHpRatio(), 0, pos, CColor<>::red());
    drawBar(gui, _player()->getManaRatio(), 1, pos, CColor<>::blue());
    drawBar(gui, _player()->getExpRatio(), 2, pos, CColor<>::yellow());
}

CStatsGraphicsObject::CStatsGraphicsObject(std::function<std::shared_ptr<CPlayer>()> _player) : _player(_player) {

}

CStatsGraphicsObject::CStatsGraphicsObject() {

}

void
CStatsGraphicsObject::drawBar(std::shared_ptr<CGui> gui, int ratio, int index, SDL_Rect *pos, const SDL_Color *color) {
    SDL_Rect filledBar;
    filledBar.x = pos->x;
    filledBar.y = pos->y + index * height;
    filledBar.h = height;
    filledBar.w = (int) (ratio / 100.0 * width);

    SDL_SetRenderDrawColor(gui->getRenderer(), COLOR(color));
    SDL_RenderFillRect(gui->getRenderer(), &filledBar);

    SDL_Rect emptyBar;
    emptyBar.x = pos->x + filledBar.w;
    emptyBar.y = pos->y + index * height;
    emptyBar.h = height;
    emptyBar.w = width - filledBar.w;

    SDL_SetRenderDrawColor(gui->getRenderer(), COLOR(CColor<>::black()));
    SDL_RenderFillRect(gui->getRenderer(), &emptyBar);
}
