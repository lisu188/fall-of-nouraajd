#include "gui/panel/CGameQuestPanel.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"
#include "gui/CTextureCache.h"

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
                CTypes::register_type<CEffect, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CEffect>, CEffect, CGameObject>();
                }

                CTypes::register_type<CMarket, CGameObject>();

                CTypes::register_type<CTrigger, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CTrigger>, CTrigger, CGameObject>();
                }

                CTypes::register_type<CQuest, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CQuest>, CQuest, CGameObject>();
                }

                CTypes::register_type<Stats, CGameObject>();
                CTypes::register_type<Damage, CGameObject>();

                CTypes::register_type<CTile, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CTile>, CTile, CGameObject>();
                }

                CTypes::register_type<CInteraction, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CInteraction>, CInteraction, CGameObject>();
                }

                CTypes::register_type<CController, CGameObject>();
                {
                    CTypes::register_type<CTargetController, CController, CGameObject>();
                    CTypes::register_type<CRandomController, CController, CGameObject>();
                    CTypes::register_type<CGroundController, CController, CGameObject>();
                    CTypes::register_type<CRangeController, CController, CGameObject>();
                    CTypes::register_type<CPlayerController, CController, CGameObject>();
                }

                CTypes::register_type<CGui, CGameObject>();
                CTypes::register_type<CTextureCache, CGameObject>();
            }
        }
    } _register_types;
}