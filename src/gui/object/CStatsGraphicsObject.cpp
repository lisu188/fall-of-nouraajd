/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "CStatsGraphicsObject.h"
#include "core/CMap.h"
#include "core/CScript.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"
#include "object/CPlayer.h"
#include "gui/CUiTheme.h"
#include "gui/CLayout.h"

void CStatsGraphicsUtil::drawStats(std::shared_ptr<CGui> gui, std::shared_ptr<CCreature> creature, int x, int y, int w,
                                   int h, bool showNumeric, bool showExp) {
    if (!creature) {
        return;
    }

    showExp = showExp && creature->isPlayer();
    const bool showMana = creature->getManaMax() > 0;
    const int barCount = 1 + (showMana ? 1 : 0) + (showExp ? 1 : 0);

    drawBar(gui, creature->getHpRatio(), 0, barCount, {125, 51, 57, 255}, x, y, w, h);
    if (showNumeric) {
        drawValues(gui, "HP", creature->getHp(), creature->getHpMax(), 0, barCount, x, y, w, h);
    }
    if (showMana) {
        drawBar(gui, creature->getManaRatio(), 1, barCount, {43, 78, 115, 255}, x, y, w, h);
        if (showNumeric) {
            drawValues(gui, "MP", creature->getMana(), creature->getManaMax(), 1, barCount, x, y, w, h);
        }
    }
    if (showExp) {
        const int index = showMana ? 2 : 1;
        drawBar(gui, creature->getExpRatio(), index, barCount, {97, 81, 48, 255}, x, y, w, h);
        if (showNumeric) {
            drawValues(gui, "XP", creature->getExp(), creature->getExpForNextLevel(), index, barCount, x, y, w, h);
        }
    }
}

void CStatsGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!creature) {
        return;
    }
    auto cret = creature->invoke<CCreature>(gui->getGame(), this->ptr());
    if (getParent() == gui) {
        const double scale = std::max(gui->getUiScale(), gui->getTextScale());
        if (gui->getWidth() < 1200 * scale && cret) {
            const int height = std::max(UiTheme::scaled(gui, 44),
                                        gui->getTextManager()->measureText("HP 999 / 999", 0, "small").second +
                                            UiTheme::scaled(gui, 16));
            getLayout()->setRuntimeRect(0, 0, gui->getWidth(), height);
            const int width = gui->getWidth() / 3;
            const std::vector<std::tuple<std::string, int, int, int, SDL_Color>> resources{
                {"HP", cret->getHp(), cret->getHpMax(), cret->getHpRatio(), {125, 51, 57, 255}},
                {"MP", cret->getMana(), cret->getManaMax(), cret->getManaRatio(), {43, 78, 115, 255}},
                {"XP", cret->getExp(), cret->getExpForNextLevel(), cret->getExpRatio(), {97, 81, 48, 255}}};
            for (size_t index = 0; index < resources.size(); ++index) {
                const auto &[label, current, maximum, ratio, color] = resources[index];
                const int x = static_cast<int>(index) * width;
                CStatsGraphicsUtil::drawBar(gui, ratio, 0, 1, color, x, 0, width, height);
                if (label == "MP" && maximum <= 0)
                    gui->getTextManager()->drawTextStyled("MP —", CUtil::rect(x, 0, width, height), "small",
                                                          UiTheme::Text, true);
                else
                    CStatsGraphicsUtil::drawValues(gui, label, current, maximum, 0, 1, x, 0, width, height);
            }
            return;
        }
        getLayout()->setRuntimeRect(0, 0, static_cast<int>(312 * scale), static_cast<int>(132 * scale));
        rect = getLayout()->getRect(ptr<CGameGraphicsObject>());
    }
    CStatsGraphicsUtil::drawStats(gui, cret, rect->x, rect->y, rect->w, rect->h, true, true);
}

CStatsGraphicsObject::CStatsGraphicsObject() {}

std::shared_ptr<CScript> CStatsGraphicsObject::getCreature() { return creature; }

void CStatsGraphicsObject::setCreature(std::shared_ptr<CScript> _creature) { creature = _creature; }

void CStatsGraphicsUtil::drawBar(std::shared_ptr<CGui> gui, int ratio, int index, int barCount, SDL_Color color, int x,
                                 int y, int w, int h) {
    h = h / std::max(1, barCount);
    SDL_Rect filledBar;
    filledBar.x = x;
    filledBar.y = y + index * h;
    filledBar.h = h;
    filledBar.w = (int)(std::clamp(ratio, 0, 100) / 100.0 * w);

    CUtil::setRenderDrawColor(gui->getRenderer(), color);
    SDL_RenderFillRect(gui->getRenderer(), &filledBar);

    SDL_Rect emptyBar;
    emptyBar.x = x + filledBar.w;
    emptyBar.y = y + index * h;
    emptyBar.h = h;
    emptyBar.w = w - filledBar.w;

    CUtil::setRenderDrawColor(gui->getRenderer(), UiTheme::Background);
    SDL_RenderFillRect(gui->getRenderer(), &emptyBar);
}

void CStatsGraphicsUtil::drawValues(std::shared_ptr<CGui> gui, const std::string &label, int left, int right, int index,
                                    int barCount, int x, int y, int w, int h) {
    h = h / std::max(1, barCount);
    gui->getTextManager()->drawTextStyled(label + " " + vstd::str(left) + " / " + vstd::str(right),
                                          CUtil::rect(x, y + index * h, w, h), "small", UiTheme::Text, true);
}

bool CStatsGraphicsObject::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    return true;
}
