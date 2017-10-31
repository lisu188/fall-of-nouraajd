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
    struct register_types {
        register_types() {
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
    } _register_types;
}