/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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
#include "CGameCampaignPanel.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiArtwork.h"
#include "gui/CUiTheme.h"
#include "gui/object/CWidget.h"

#include <algorithm>
#include <sstream>

bool CGameCampaignPanel::awaitDismissal() {
    vstd::wait_until([this]() { return dismissed != nullptr || !getGui(); });
    return dismissed ? *dismissed : false;
}

bool CGameCampaignPanel::isDismissed() { return dismissed != nullptr && *dismissed; }

std::string CGameCampaignPanel::getTitle() { return title; }

void CGameCampaignPanel::setTitle(std::string value) {
    title = value;
    CGamePanel::setTitle(std::move(value));
}

std::string CGameCampaignPanel::getBody() { return body; }

void CGameCampaignPanel::setBody(std::string value) {
    body = std::move(value);
    bodyOffset = 0;
    measuredWidth = 0;
    paragraphs.clear();
}

std::string CGameCampaignPanel::getVisibleBodyText() const {
    std::string visible;
    for (const auto &paragraph : paragraphs)
        if (paragraph.y + paragraph.height > bodyOffset && paragraph.y < bodyOffset + viewportHeight)
            visible += paragraph.text + "\n";
    return visible;
}

void CGameCampaignPanel::setArtwork(std::string value) {
    artwork = UiArtwork::validPath(value) ? std::move(value) : std::string();
    bodyOffset = 0;
    measuredWidth = 0;
}

std::string CGameCampaignPanel::getActionLabel() { return actionLabel; }

void CGameCampaignPanel::setActionLabel(std::string value) {
    actionLabel = value;
    setCloseable(actionLabel == "Continue");
}

void CGameCampaignPanel::renderTitle(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    // The common panel shell owns the title; keep the configured callback compatible.
}

void CGameCampaignPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    CGamePanel::renderObject(gui, rect, frameTime);
    if (!gui || !rect || rect->w <= 0 || rect->h <= 0)
        return;
    const double displayScale = std::max(1.0, gui->getHeight() / 1080.0);
    const int padding = static_cast<int>(24 * displayScale);
    const int gap = static_cast<int>(16 * displayScale);
    const int width = std::max(1, rect->w - padding * 2);
    const int buttonWidth = rect->w < 1200 * gui->getTextScale() ? width : std::max(240, rect->w * 31 / 100);
    const int buttonHeight = std::max(
        static_cast<int>(48 * displayScale),
        gui->getTextManager()->measureText(actionLabel, std::max(1, buttonWidth - gap * 2), "body").second + gap);
    const int footerTop = rect->h - padding - buttonHeight;
    const int bodyTop = getShellHeaderHeight(gui) + gap;
    for (const auto &child : getChildren()) {
        auto layout = child->getLayout();
        if (!layout)
            continue;
        if (child->getStringProperty("render") == "renderBody")
            layout->setRuntimeRect(padding, bodyTop, width, std::max(1, footerTop - gap - bodyTop));
        if (child->getStringProperty("click") == "clickAction")
            layout->setRuntimeRect(rect->w - padding - buttonWidth, footerTop, buttonWidth, buttonHeight);
    }
}

void CGameCampaignPanel::renderBody(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect || rect->w <= 0 || rect->h <= 0)
        return;
    const int hintHeight = gui->getTextManager()->measureText("Ag", rect->w, "small").second + 8;
    viewportHeight = std::max(1, rect->h - hintHeight);
    const bool compact = rect->w < 1200 * gui->getTextScale();
    auto image = UiArtwork::texture(gui, artwork);
    const auto viewport = CUtil::rect(rect->x, rect->y, rect->w, viewportHeight);
    const auto art = UiArtwork::layout(gui, image, *viewport, compact);
    artworkBounds = art.image;
    textBounds = art.text;
    auto textRect = std::make_shared<SDL_Rect>(art.text);
    if (measuredWidth != textRect->w || measuredTextScale != gui->getTextScale() || measuredInset != art.inset) {
        paragraphs.clear();
        bodyHeight = art.inset;
        const int lineHeight = gui->getTextManager()->measureText("Ag", textRect->w, "dialogue").second;
        std::istringstream lines(body);
        std::string line;
        while (std::getline(lines, line)) {
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + 1024, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80)
                    --end;
                const auto part = line.substr(offset, end - offset);
                const int height =
                    std::max(lineHeight, gui->getTextManager()->measureText(part, textRect->w, "dialogue").second);
                paragraphs.push_back({part, bodyHeight, height});
                bodyHeight += height;
                offset = end;
            } while (offset < line.size());
        }
        measuredWidth = textRect->w;
        measuredTextScale = gui->getTextScale();
        measuredInset = art.inset;
    }
    bodyOffset = std::clamp(bodyOffset, 0, std::max(0, bodyHeight - viewportHeight));
    UiArtwork::draw(gui, image, art.image, *viewport, compact ? bodyOffset : 0);
    for (const auto &paragraph : paragraphs)
        if (paragraph.y + paragraph.height > bodyOffset && paragraph.y < bodyOffset + viewportHeight)
            gui->getTextManager()->drawTextStyled(paragraph.text, textRect, "dialogue", UiTheme::Text, false,
                                                  paragraph.y - bodyOffset);
    if (bodyHeight > viewportHeight) {
        gui->getTextManager()->drawTextStyled("Scroll to read more  |  Page Up / Page Down",
                                              CUtil::rect(rect->x, rect->y + viewportHeight, rect->w, hintHeight),
                                              "small", UiTheme::Muted, true);
    }
}

void CGameCampaignPanel::clickAction(std::shared_ptr<CGui> gui) {
    dismissed = std::make_shared<bool>(true);
    close();
}

bool CGameCampaignPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN) {
        // Continue acknowledges already-resolved lore/rewards. Chapter-start
        // actions still require their deliberate action button or activation key.
        if (key == SDLK_RETURN || key == SDLK_KP_ENTER || key == SDLK_SPACE ||
            (key == SDLK_ESCAPE && actionLabel == "Continue")) {
            clickAction(gui);
        } else if (key == SDLK_UP || key == SDLK_PAGEUP) {
            bodyOffset = std::max(0, bodyOffset - (key == SDLK_UP ? 48 : std::max(48, viewportHeight - 48)));
        } else if (key == SDLK_DOWN || key == SDLK_PAGEDOWN) {
            bodyOffset = std::min(std::max(0, bodyHeight - viewportHeight),
                                  bodyOffset + (key == SDLK_DOWN ? 48 : std::max(48, viewportHeight - 48)));
        } else if (key == SDLK_HOME) {
            bodyOffset = 0;
        } else if (key == SDLK_END) {
            bodyOffset = std::max(0, bodyHeight - viewportHeight);
        }
    }
    return true;
}

bool CGameCampaignPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                         int wheelY) {
    bodyOffset = std::clamp(bodyOffset - wheelY * 48, 0, std::max(0, bodyHeight - viewportHeight));
    return true;
}
