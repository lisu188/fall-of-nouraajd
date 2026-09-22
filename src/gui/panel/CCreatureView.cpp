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
#include "CCreatureView.h"
#include "core/CScript.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"
#include "gui/CUiTheme.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "object/CCreature.h"
#include "object/CEffect.h"

namespace {
class CreaturePortraitLayout : public CLayout {
  public:
    explicit CreaturePortraitLayout(double aspect) : aspect(aspect) {}

    std::shared_ptr<SDL_Rect> getRect(std::shared_ptr<CGameGraphicsObject> object) override {
        auto parent = getParentRect(object);
        auto gui = object ? object->getGui() : nullptr;
        const int padding = gui ? std::max(8, static_cast<int>(8 * gui->getUiScale() / 2)) : 8;
        const int lineHeight = gui ? gui->getTextManager()->measureText("Ag", 0, "small").second : 28;
        const int width = std::max(1, parent->w - padding * 2);
        const int height = std::max(1, parent->h - lineHeight * 2 - padding * 3);
        const int fittedWidth = std::min(width, std::max(1, static_cast<int>(height * aspect)));
        const int fittedHeight = std::min(height, std::max(1, static_cast<int>(fittedWidth / aspect)));
        return CUtil::rect(parent->x + (parent->w - fittedWidth) / 2, parent->y + padding + (height - fittedHeight) / 2,
                           fittedWidth, fittedHeight);
    }

  private:
    double aspect;
};
} // namespace

std::shared_ptr<CScript> CCreatureView::getCreatureScript() { return creatureScript; }

void CCreatureView::setCreatureScript(std::shared_ptr<CScript> _creatureScript) { creatureScript = _creatureScript; }

std::list<std::shared_ptr<CGameGraphicsObject>> CCreatureView::getProxiedObjects(std::shared_ptr<CGui> gui, int x,
                                                                                 int y) {
    auto creature = getCreature();
    if (!creature) {
        return {};
    }
    std::shared_ptr<CGameGraphicsObject> graphicsObject = creature->getGraphicsObject();
    if (!graphicsObject) {
        return {};
    }
    int width = 1;
    int height = 1;
    if (gui && !creature->getAnimation().empty()) {
        if (auto texture = gui->getTextureCache()->getTexture(creature->getAnimation())) {
            SDL_QueryTexture(texture, nullptr, nullptr, &width, &height);
        }
    }
    graphicsObject->setLayout(
        std::make_shared<CreaturePortraitLayout>(static_cast<double>(std::max(1, width)) / std::max(1, height)));
    return vstd::as_list(graphicsObject);
}

int CCreatureView::getSizeX(std::shared_ptr<CGui> gui) { return 1; }

int CCreatureView::getSizeY(std::shared_ptr<CGui> gui) { return 1; }

void CCreatureView::initialize() {
    auto self = this->ptr<CCreatureView>();
    vstd::call_when(
        [self]() {
            return self->getGui() != nullptr && self->getGui()->getGame() != nullptr &&
                   self->getGui()->getGame()->getMap() != nullptr;
        },
        [self]() { self->refresh(); });
}

CListView::collection_pointer CCreatureView::getEffects(std::shared_ptr<CGui>) {
    auto creature = getCreature();
    if (!creature) {
        return std::make_shared<CListView::collection_type>();
    }
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(creature->getEffects()));
}

std::shared_ptr<CCreature> CCreatureView::getCreature() {
    auto gui = getGui();
    return creatureScript && gui && gui->getGame() ? creatureScript->invoke<CCreature>(gui->getGame(), this->ptr())
                                                   : nullptr;
}

std::string CCreatureView::getStatusText(const std::shared_ptr<CCreature> &creature) {
    if (!creature) {
        return "";
    }
    std::string text;
    for (const auto &effect : creature->getEffects()) {
        if (!effect) {
            continue;
        }
        if (!text.empty()) {
            text += " | ";
        }
        text += effect->getLabel();
        text += " (" + std::to_string(std::max(0, effect->getTimeLeft())) + " turns)";
    }
    return text.empty() ? "No active effects" : text;
}

void CCreatureView::layoutCombatantCard(const std::shared_ptr<CGui> &gui,
                                        const std::shared_ptr<CGameGraphicsObject> &card,
                                        const std::shared_ptr<CCreature> &creature) {
    if (!gui || !card || !creature || !card->getLayout())
        return;
    const auto rect = card->getLayout()->getRect(card);
    const int barCount = 1 + (creature->getManaMax() > 0 ? 1 : 0) + (creature->isPlayer() ? 1 : 0);
    const int lineHeight = gui->getTextManager()->measureText("HP 999 / 999", 0, "small").second;
    const int barsHeight = (lineHeight + std::max(8, static_cast<int>(4 * gui->getUiScale()))) * barCount;
    const bool horizontal = rect->w > rect->h * 2;
    const int portraitWidth = horizontal ? rect->w * 46 / 100 : rect->w;
    const int statsHeight = horizontal ? std::min(rect->h, barsHeight) : std::max(rect->h / 3, barsHeight);
    for (const auto &child : card->getChildren()) {
        if (!child->getLayout())
            continue;
        if (vstd::cast<CCreatureView>(child)) {
            child->getLayout()->setRuntimeRect(0, 0, portraitWidth,
                                               horizontal ? rect->h : std::max(1, rect->h - statsHeight));
        } else if (vstd::cast<CStatsGraphicsObject>(child)) {
            child->getLayout()->setRuntimeRect(horizontal ? portraitWidth + 16 : 0,
                                               horizontal ? (rect->h - statsHeight) / 2 : rect->h - statsHeight,
                                               horizontal ? rect->w - portraitWidth - 16 : rect->w, statsHeight);
        }
    }
}

void CCreatureView::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect) {
        return;
    }
    UiTheme::fill(gui->getRenderer(), *rect, UiTheme::Background);
    UiTheme::stroke(gui->getRenderer(), *rect, UiTheme::Border);
    auto creature = getCreature();
    if (!creature) {
        return;
    }
    for (const auto &child : getChildren()) {
        if (auto effects = vstd::cast<CListView>(child); effects && effects->getCollection() == "getEffects")
            effects->setRuntimeHidden(creature->getEffects().empty());
    }
    const int inset = std::max(8, static_cast<int>(4 * gui->getUiScale()));
    const int nameHeight = gui->getTextManager()->measureText("Ag", 0, "small").second;
    const int statusHeight = nameHeight + inset;
    auto name = CUtil::rect(rect->x + inset, rect->y + rect->h - statusHeight - nameHeight,
                            std::max(1, rect->w - inset * 2), nameHeight);
    auto status = CUtil::rect(name->x, name->y + nameHeight, name->w, statusHeight);
    gui->getTextManager()->drawTextStyled(creature->getLabel(), name, "small", UiTheme::Text, true);
    auto statusText = getStatusText(creature);
    if (gui->getTextManager()->measureText(statusText, name->w, "small").second > statusHeight)
        statusText = std::to_string(creature->getEffects().size()) + " active effects - inspect icons";
    gui->getTextManager()->drawTextStyled(statusText, status, "small", UiTheme::Muted);
}
