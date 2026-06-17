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
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"
#include "gui/object/CConsoleGraphicsObject.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CMinimapGraphicsObject.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "gui/object/CProxyTargetGraphicsObject.h"
#include "gui/object/CSideBar.h"
#include "gui/object/CStatsGraphicsObject.h"

namespace type_registration {
void registerGuiTypes() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CTextureCache, CGameObject>();
    CTypes::register_type<CTextManager, CGameObject>();

    CTypes::register_type<CLayout, CGameObject>();
    CTypes::register_type<CCenteredLayout, CLayout, CGameObject>();
    CTypes::register_type<CParentLayout, CLayout, CGameObject>();
    CTypes::register_type<CProxyGraphicsLayout, CLayout, CGameObject>();

    CTypes::register_type<CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGui, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CStatsGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CConsoleGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CProxyGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CSideBar, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CMinimapGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CMapGraphicsObject, CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>();
}
} // namespace type_registration
