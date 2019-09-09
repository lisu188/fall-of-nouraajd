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
#include "gui/panel/CGameQuestPanel.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"


extern void add_member(std::shared_ptr<Value> object, std::string key, std::string value);

extern void add_member(std::shared_ptr<Value> object, std::string key, std::shared_ptr<Value> value);

extern void add_member(std::shared_ptr<Value> object, std::string key, bool value);

extern void add_member(std::shared_ptr<Value> object, std::string key, int value);

extern void add_arr_member(std::shared_ptr<Value> object, std::string value);

extern void add_arr_member(std::shared_ptr<Value> object, std::shared_ptr<Value> value);

extern void add_arr_member(std::shared_ptr<Value> object, bool value);

extern void add_arr_member(std::shared_ptr<Value> object, int value);


namespace {
    struct register_types2 {
        register_types2() {
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CMapObject, CGameObject>();
                {
                    CTypes::register_type<CBuilding, CMapObject, CGameObject>();
                    {
                        CTypes::register_type<CWrapper<CBuilding>, CBuilding, CMapObject, CGameObject>();
                    }
                    CTypes::register_type<CEvent, CMapObject, CGameObject>();
                    {
                        CTypes::register_type<CWrapper<CEvent>, CEvent, CMapObject, CGameObject>();
                    }
                    CTypes::register_type<CItem, CMapObject, CGameObject>();
                    {
                        CTypes::register_type<CWeapon, CItem, CMapObject, CGameObject>();
                        {
                            CTypes::register_type<CSmallWeapon, CWeapon, CItem, CMapObject, CGameObject>();
                        }
                        CTypes::register_type<CArmor, CItem, CMapObject, CGameObject>();
                        CTypes::register_type<CPotion, CItem, CMapObject, CGameObject>();
                        {
                            CTypes::register_type<CWrapper<CPotion>, CPotion, CItem, CMapObject, CGameObject>();
                        }
                        CTypes::register_type<CHelmet, CItem, CMapObject, CGameObject>();
                        CTypes::register_type<CBoots, CItem, CMapObject, CGameObject>();
                        CTypes::register_type<CBelt, CItem, CMapObject, CGameObject>();
                        CTypes::register_type<CGloves, CItem, CMapObject, CGameObject>();
                        CTypes::register_type<CScroll, CItem, CMapObject, CGameObject>();
                    }

                    CTypes::register_type<CCreature, CMapObject, CGameObject>();
                    {
                        CTypes::register_type<CPlayer, CCreature, CMapObject, CGameObject>();
                        CTypes::register_type<CMonster, CCreature, CMapObject, CGameObject>();
                    }
                }
            }
        }
    } _register_types2;
}