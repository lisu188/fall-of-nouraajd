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
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CAnimation.h"
#include "gui/CTooltip.h"
#include "gui/object/CGameGraphicsObject.h"

namespace type_registration {
void registerGuiAnimationTypes() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CAnimation, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CStaticAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CDynamicAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CSelectionBox, CAnimation, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CTooltip, CGameGraphicsObject, CGameObject>();
}
} // namespace type_registration
