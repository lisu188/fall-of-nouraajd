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
#include "CGameQuestionPanel.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"
#include "gui/object/CWidget.h"

#include <algorithm>
#include <sstream>

std::string CGameQuestionPanel::getQuestion() { return question; }

void CGameQuestionPanel::setQuestion(std::string value) {
    question = std::move(value);
    focusedAnswer = false;
    selection.reset();
    measuredWidth = 0;
    bodyScroll = 0;
    bodyMaximum = 0;
    refreshButtons();
}

std::string CGameQuestionPanel::getConfirmLabel() const { return confirmLabel; }

void CGameQuestionPanel::setConfirmLabel(std::string value) {
    confirmLabel = std::move(value);
    refreshButtons();
}

std::string CGameQuestionPanel::getCancelLabel() const { return cancelLabel; }

void CGameQuestionPanel::setCancelLabel(std::string value) {
    cancelLabel = std::move(value);
    refreshButtons();
}

void CGameQuestionPanel::refreshButtons() {
    for (const auto &child : getChildren()) {
        auto button = vstd::cast<CButton>(child);
        if (!button) {
            continue;
        }
        if (button->getClick() == "clickYes") {
            button->setText(confirmLabel);
            button->setBoolProperty("selected", focusedAnswer);
        } else if (button->getClick() == "clickNo") {
            button->setText(cancelLabel);
            button->setBoolProperty("selected", !focusedAnswer);
        }
    }
}

bool CGameQuestionPanel::awaitAnswer() {
    vstd::wait_until([this]() { return selection != nullptr || !getGui(); });
    return selection ? *selection : false;
}

void CGameQuestionPanel::clickNo(std::shared_ptr<CGui>) {
    selection = std::make_shared<bool>(false);
    close();
}

void CGameQuestionPanel::clickYes(std::shared_ptr<CGui>) {
    selection = std::make_shared<bool>(true);
    close();
}

void CGameQuestionPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) {
    if (!gui || !rect)
        return;
    const int padding = UiTheme::scaled(gui, 24);
    const int gap = UiTheme::scaled(gui, 16);
    const int width = std::max(1, rect->w - padding * 2);
    const int buttonWidth = std::max(1, (width - gap) / 2);
    const int textWidth = std::max(1, buttonWidth - gap);
    auto manager = gui->getTextManager();
    const int buttonHeight = std::max({UiTheme::scaled(gui, 44),
                                       manager->measureText(confirmLabel, textWidth).second + gap,
                                       manager->measureText(cancelLabel, textWidth).second + gap});
    const int top = getShellHeaderHeight(gui) + gap;
    const int footerTop = rect->h - padding - buttonHeight;
    questionRect = CUtil::rect(rect->x + padding, rect->y + top, width, std::max(1, footerTop - gap - top));
    footerRect = CUtil::rect(rect->x + padding, rect->y + footerTop, width, buttonHeight);
    for (const auto &child : getChildren()) {
        if (!child->getLayout())
            continue;
        if (auto button = vstd::cast<CButton>(child)) {
            if (button->getClick() == "clickYes" || button->getClick() == "clickNo") {
                const int x = padding + (button->getClick() == "clickYes" ? buttonWidth + gap : 0);
                button->getLayout()->setRuntimeRect(x, footerTop, buttonWidth, buttonHeight);
            }
        } else if (auto widget = vstd::cast<CWidget>(child); widget && widget->getRender() == "renderQuestion") {
            widget->getLayout()->setRuntimeRect(padding, top, width, questionRect->h);
        }
    }
}

void CGameQuestionPanel::renderQuestion(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) {
    if (!gui || !rect)
        return;
    auto viewport = UiTheme::inset(rect, UiTheme::scaled(gui, 16));
    auto textManager = gui->getTextManager();
    const int width = std::max(1, viewport->w);
    if (measuredWidth != width || measuredScale != gui->getUiScale() || measuredTextScale != gui->getTextScale()) {
        measuredWidth = width;
        measuredScale = gui->getUiScale();
        measuredTextScale = gui->getTextScale();
        paragraphs.clear();
        contentHeight = 0;
        const int lineHeight = std::max(1, textManager->measureText("Ag", width).second);
        std::istringstream lines(question);
        std::string line;
        while (std::getline(lines, line)) {
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + 1024, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80) {
                    --end;
                }
                const auto chunk = line.substr(offset, end - offset);
                const int height = std::max(lineHeight, textManager->measureText(chunk, width).second);
                paragraphs.push_back({chunk, contentHeight, height});
                contentHeight += height;
                offset = end;
            } while (offset < line.size());
        }
    }
    if (contentHeight > viewport->h) {
        const std::string label = "Scroll or PgUp / PgDn to review";
        const int hintHeight = textManager->measureText(label, width, "caption").second;
        auto hint = CUtil::rect(viewport->x, viewport->y + viewport->h - hintHeight, viewport->w, hintHeight);
        textManager->drawTextStyled(label, hint, "caption", UiTheme::Muted);
        viewport->h = std::max(1, viewport->h - hintHeight - UiTheme::scaled(gui, 8));
    }
    bodyHeight = viewport->h;
    bodyMaximum = std::max(0, contentHeight - bodyHeight);
    bodyScroll = std::clamp(bodyScroll, 0, bodyMaximum);
    for (const auto &paragraph : paragraphs) {
        if (paragraph.y + paragraph.height > bodyScroll && paragraph.y < bodyScroll + bodyHeight) {
            textManager->drawTextStyled(paragraph.text, viewport, "body", UiTheme::Text, false,
                                        paragraph.y - bodyScroll);
        }
    }
}

bool CGameQuestionPanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event && event->type == SDL_KEYDOWN && event->key.repeat &&
        (event->key.keysym.sym == SDLK_RETURN || event->key.keysym.sym == SDLK_SPACE ||
         event->key.keysym.sym == SDLK_y || event->key.keysym.sym == SDLK_n)) {
        return true;
    }
    return CGamePanel::event(gui, event);
}

bool CGameQuestionPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type != SDL_KEYDOWN) {
        return true;
    }
    if (key == SDLK_ESCAPE || key == SDLK_n) {
        clickNo(gui);
    } else if (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN || key == SDLK_HOME || key == SDLK_END) {
        const int step = std::max(1, bodyHeight - UiTheme::scaled(gui, 24));
        if (key == SDLK_PAGEUP)
            bodyScroll -= step;
        if (key == SDLK_PAGEDOWN)
            bodyScroll += step;
        if (key == SDLK_HOME)
            bodyScroll = 0;
        if (key == SDLK_END)
            bodyScroll = bodyMaximum;
        bodyScroll = std::clamp(bodyScroll, 0, bodyMaximum);
    } else if (key == SDLK_LEFT || key == SDLK_UP) {
        focusedAnswer = false;
        refreshButtons();
    } else if (key == SDLK_RIGHT || key == SDLK_DOWN) {
        focusedAnswer = true;
        refreshButtons();
    } else if (key == SDLK_TAB) {
        focusedAnswer = !focusedAnswer;
        refreshButtons();
    } else if (key == SDLK_RETURN || key == SDLK_SPACE) {
        focusedAnswer ? clickYes(gui) : clickNo(gui);
    } else if (key == SDLK_y) {
        clickYes(gui);
    }
    return true;
}

bool CGameQuestionPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType, int, int, int, int wheelY) {
    bodyScroll = std::clamp(bodyScroll - wheelY * UiTheme::scaled(gui, 64), 0, bodyMaximum);
    return true;
}
