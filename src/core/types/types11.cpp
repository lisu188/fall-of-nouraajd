/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "gui/panel/CGameLootPanel.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "core/CTypes.h"
#include "gui/CTextureCache.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CCreatureView.h"


extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, int value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::string &value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value);

extern void add_arr_member(const std::shared_ptr<json> &object, bool value);

extern void add_arr_member(const std::shared_ptr<json> &object, int value);

namespace {
    struct register_types11 {
        register_types11() {
            CTypes::register_type<CGameObject>(); {
                CTypes::register_type<CGameGraphicsObject, CGameObject>(); {
                    CTypes::register_type<CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>(); {
                        CTypes::register_type<CMapGraphicsObject, CProxyTargetGraphicsObject, CGameGraphicsObject,
                            CGameObject>();
                        CTypes::register_type<CListView, CProxyTargetGraphicsObject, CGameGraphicsObject,
                            CGameObject>();
                        CTypes::register_type<CCreatureView, CProxyTargetGraphicsObject, CGameGraphicsObject,
                            CGameObject>();
                    }
                    CTypes::register_type<CWidget, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CTextWidget, CWidget, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CButton, CTextWidget, CWidget, CGameGraphicsObject, CGameObject>();
                }
            }
        }
    } _register_types11;
}