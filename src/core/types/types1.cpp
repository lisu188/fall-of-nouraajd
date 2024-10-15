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
#include "core/CMap.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"
#include "core/CList.h"

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, int value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::string &value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value);

extern void add_arr_member(const std::shared_ptr<json> &object, bool value);

extern void add_arr_member(const std::shared_ptr<json> &object, int value);

namespace {
    struct register_types1 {
        register_types1() {
            CTypes::register_type<CGameObject>(); {
                CTypes::register_type<CGame, CGameObject>();
                CTypes::register_type<CMap, CGameObject>();

                CTypes::register_type<CFightController, CGameObject>(); {
                    CTypes::register_type<CPlayerFightController, CFightController, CGameObject>();
                    CTypes::register_type<CMonsterFightController, CFightController, CGameObject>();
                }
                CTypes::register_type<CGameEvent, CGameObject>(); {
                    CTypes::register_type<CGameEventCaused, CGameEvent, CGameObject>();
                }
                CTypes::register_type<CPlugin, CGameObject>(); {
                    CTypes::register_type<CWrapper<CPlugin>, CPlugin, CGameObject>();
                }
            }
        }
    } _register_types1;
}
