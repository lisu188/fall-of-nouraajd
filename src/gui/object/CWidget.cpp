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

#include "CWidget.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"

#include <exception>

void CWidget::setRender(std::string draw) { this->render = draw; }

std::string CWidget::getRender() { return render; }

std::string CWidget::getClick() { return click; }

void CWidget::setClick(std::string click) { this->click = click; }

void CWidget::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    auto parent = getParent();
    if (!parent || getRender().empty()) {
        return;
    }
    try {
        parent->meta()->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>, int>(
            this->getRender(), parent, gui, rect, frameTime);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring widget render callback failure:", getRender(), exception.what());
    }
}

bool CWidget::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    auto clickable = getEnabled() && !getClick().empty();
    if (button != SDL_BUTTON_LEFT || (!clickable && !clickPressed)) {
        return false;
    }

    if (type == SDL_MOUSEBUTTONDOWN) {
        clickPressed = clickable;
        if (clickable && gui) {
            gui->focusWidget(ptr<CGameGraphicsObject>());
        }
        return clickPressed;
    }

    if (type == SDL_MOUSEBUTTONUP && clickPressed) {
        clickPressed = false;
        auto rect = getLayout()->getRect(this->ptr<CGameGraphicsObject>());
        auto releasedInside = x >= 0 && y >= 0 && x < rect->w && y < rect->h;
        if (clickable && releasedInside) {
            activate(gui);
        }
        return true;
    }

    return false;
}

CWidget::CWidget() {}

bool CWidget::activate(std::shared_ptr<CGui> gui) {
    auto parent = getParent();
    if (!getEnabled() || getClick().empty() || !parent) {
        return false;
    }
    try {
        parent->meta()->invoke_method<void, CGameGraphicsObject, std::shared_ptr<CGui>>(getClick(), parent, gui);
    } catch (const std::exception &exception) {
        vstd::logger::warning("Ignoring widget click callback failure:", getClick(), exception.what());
    }
    return true;
}

bool CWidget::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (!gui || !gui->isFocused(this)) {
        return false;
    }
    if (type == SDL_KEYDOWN && (key == SDLK_RETURN || key == SDLK_KP_ENTER || key == SDLK_SPACE)) {
        return activate(gui);
    }
    return false;
}

void CTextWidget::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect || !gui->getTextManager()) {
        return;
    }
    if (!getClick().empty() && !vstd::cast<CButton>(ptr<CGameGraphicsObject>()) &&
        (getSelected() || gui->isFocused(this))) {
        UiTheme::fill(gui->getRenderer(), *rect, UiTheme::Selection);
        UiTheme::stroke(gui->getRenderer(), *rect, UiTheme::Accent);
    }
    gui->getTextManager()->drawTextStyled(text, rect, textRole, getEnabled() ? UiTheme::Text : UiTheme::Muted,
                                          centered);
}

CButton::CButton() { setBackground(""); }

void CButton::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect) {
        return;
    }
    int mouseX = 0;
    int mouseY = 0;
    const auto buttons = SDL_GetMouseState(&mouseX, &mouseY);
    const bool hovered = CUtil::isIn(rect, mouseX, mouseY);
    auto surface = getSelected() || (hovered && getEnabled()) ? UiTheme::Selection : UiTheme::Panel;
    if (hovered && getEnabled() && (buttons & SDL_BUTTON_LMASK)) {
        surface = UiTheme::Background;
    }
    UiTheme::fill(gui->getRenderer(), *rect, surface);
    UiTheme::stroke(gui->getRenderer(), *rect,
                    gui->isFocused(this) || getSelected() ? UiTheme::Accent : UiTheme::Border);
    CTextWidget::renderObject(gui, UiTheme::inset(rect, UiTheme::scaled(gui, 8)), frameTime);
}

bool CButton::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_LEFT) {
        setModal(true);
    } else if (type == SDL_MOUSEBUTTONUP && button == SDL_BUTTON_LEFT) {
        setModal(false);
    }
    return CTextWidget::mouseEvent(sharedPtr, type, button, x, y);
}

bool CTextWidget::getCentered() const { return centered; }

void CTextWidget::setCentered(bool centered) { CTextWidget::centered = centered; }

const std::string &CTextWidget::getText() const { return text; }

void CTextWidget::setText(const std::string &text) { CTextWidget::text = text; }
