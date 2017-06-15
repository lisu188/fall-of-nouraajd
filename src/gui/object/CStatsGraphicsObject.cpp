#include "object/CPlayer.h"
#include "CStatsGraphicsObject.h"
#include "gui/CGui.h"

void CStatsGraphicsObject::render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime, std::string data) {
    int ratio = _player()->getHpRatio();
    int revRatio = 100 - ratio;
    SDL_Rect actual;
    actual.x = pos->x;
    actual.y = pos->y;
    actual.h = 20;
    actual.w = ratio;

    SDL_SetRenderDrawColor(gui->getRenderer(), 255, 0, 0, 0);
    SDL_RenderFillRect(gui->getRenderer(), &actual);

    actual.x = pos->x + ratio;
    actual.y = pos->y;
    actual.h = 20;
    actual.w = revRatio;

    SDL_SetRenderDrawColor(gui->getRenderer(), 0, 0, 0, 0);
    SDL_RenderFillRect(gui->getRenderer(), &actual);

    ratio = _player()->getManaRatio();
    revRatio = 100 - ratio;
    actual.x = pos->x;
    actual.y = pos->y + 20;
    actual.h = 20;
    actual.w = ratio;

    SDL_SetRenderDrawColor(gui->getRenderer(), 0, 0, 255, 0);
    SDL_RenderFillRect(gui->getRenderer(), &actual);

    actual.x = pos->x + ratio;
    actual.y = pos->y + 20;
    actual.h = 20;
    actual.w = revRatio;

    SDL_SetRenderDrawColor(gui->getRenderer(), 0, 0, 0, 0);
    SDL_RenderFillRect(gui->getRenderer(), &actual);

    ratio = _player()->getExpRatio();
    revRatio = 100 - ratio;
    actual.x = pos->x;
    actual.y = pos->y + 40;
    actual.h = 20;
    actual.w = ratio;

    SDL_SetRenderDrawColor(gui->getRenderer(), 255, 255, 0, 0);
    SDL_RenderFillRect(gui->getRenderer(), &actual);

    actual.x = pos->x + ratio;
    actual.y = pos->y + 40;
    actual.h = 20;
    actual.w = revRatio;

    SDL_SetRenderDrawColor(gui->getRenderer(), 0, 0, 0, 0);
    SDL_RenderFillRect(gui->getRenderer(), &actual);

}

CStatsGraphicsObject::CStatsGraphicsObject(std::function<std::shared_ptr<CPlayer>()> _player) : _player(_player) {

}
