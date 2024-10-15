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

#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"
#include "gui/CTextureCache.h"
#include "gui/CTextManager.h"
#include "object/CDialog.h"

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, int value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::string &value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value);

extern void add_arr_member(const std::shared_ptr<json> &object, bool value);

extern void add_arr_member(const std::shared_ptr<json> &object, int value);

namespace {
    struct register_types3 {
        register_types3() {
            CTypes::register_type<CGameObject>(); {
                CTypes::register_type<CEffect, CGameObject>(); {
                    CTypes::register_type<CWrapper<CEffect>, CEffect, CGameObject>();
                }

                CTypes::register_type<CMarket, CGameObject>();
                CTypes::register_type<CDialog, CGameObject>(); {
                    CTypes::register_type<CWrapper<CDialog>, CDialog, CGameObject>();
                }
                CTypes::register_type<CDialogOption, CGameObject>();
                CTypes::register_type<CDialogState, CGameObject>();

                CTypes::register_type<CTrigger, CGameObject>(); {
                    CTypes::register_type<CWrapper<CTrigger>, CTrigger, CGameObject>();
                }

                CTypes::register_type<CQuest, CGameObject>(); {
                    CTypes::register_type<CWrapper<CQuest>, CQuest, CGameObject>();
                }

                CTypes::register_type<Stats, CGameObject>();
                CTypes::register_type<Damage, CGameObject>();

                CTypes::register_type<CTile, CGameObject>(); {
                    CTypes::register_type<CWrapper<CTile>, CTile, CGameObject>();
                }

                CTypes::register_type<CInteraction, CGameObject>(); {
                    CTypes::register_type<CWrapper<CInteraction>, CInteraction, CGameObject>();
                }

                CTypes::register_type<CController, CGameObject>(); {
                    CTypes::register_type<CTargetController, CController, CGameObject>();
                    CTypes::register_type<CRandomController, CController, CGameObject>();
                    CTypes::register_type<CGroundController, CController, CGameObject>();
                    CTypes::register_type<CRangeController, CController, CGameObject>();
                    CTypes::register_type<CPlayerController, CController, CGameObject>();
                }

                CTypes::register_type<CTextureCache, CGameObject>();
                CTypes::register_type<CTextManager, CGameObject>();
            }
        }
    } _register_types3;
}
