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
#include "core/CGame.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "gui/object/CConsoleGraphicsObject.h"
#include "gui/panel/CGameTradePanel.h"
#include "core/CTypes.h"
#include "core/CController.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/CTextureCache.h"
#include "gui/object/CWidget.h"

extern void add_member(std::shared_ptr<json> object, std::string key, std::string value);

extern void add_member(std::shared_ptr<json> object, std::string key, std::shared_ptr<json> value);

extern void add_member(std::shared_ptr<json> object, std::string key, bool value);

extern void add_member(std::shared_ptr<json> object, std::string key, int value);

extern void add_arr_member(std::shared_ptr<json> object, std::string value);

extern void add_arr_member(std::shared_ptr<json> object, std::shared_ptr<json> value);

extern void add_arr_member(std::shared_ptr<json> object, bool value);

extern void add_arr_member(std::shared_ptr<json> object, int value);


namespace {
    struct register_types4 {
        register_types4() {
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CMapGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CStatsGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CConsoleGraphicsObject, CGameGraphicsObject, CGameObject>();

                    CTypes::register_type<CGamePanel, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CGameTextPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameInventoryPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameTradePanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameFightPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameQuestPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameCharacterPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameDialogPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                    }
                    CTypes::register_type<CWidget, CGameObject>();
                    CTypes::register_type<CAnimation, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CStaticAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CDynamicAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                    }
                }
            }
        }
    } _register_types4;
}