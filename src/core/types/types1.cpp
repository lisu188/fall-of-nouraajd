#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/panel/CGameQuestPanel.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"
#include "core/CEventLoop.h"

extern void add_member(std::shared_ptr<Value> object, std::string key, std::string value);

extern void add_member(std::shared_ptr<Value> object, std::string key, std::shared_ptr<Value> value);

extern void add_member(std::shared_ptr<Value> object, std::string key, bool value);

extern void add_member(std::shared_ptr<Value> object, std::string key, int value);

extern void add_arr_member(std::shared_ptr<Value> object, std::string value);

extern void add_arr_member(std::shared_ptr<Value> object, std::shared_ptr<Value> value);

extern void add_arr_member(std::shared_ptr<Value> object, bool value);

extern void add_arr_member(std::shared_ptr<Value> object, int value);

namespace {
    struct register_types1 {
        register_types1() {
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CSlotConfig, CGameObject>();
                CTypes::register_type<CSlot, CGameObject>();

                CTypes::register_type<CEventLoop, CGameObject>();

                CTypes::register_type<CObjectHandler, CGameObject>();
                CTypes::register_type<CEventHandler, CGameObject>();

                CTypes::register_type<CFightController, CGameObject>();
                {
                    CTypes::register_type<CPlayerFightController, CFightController, CGameObject>();
                    CTypes::register_type<CMonsterFightController, CFightController, CGameObject>();
                }

                CTypes::register_type<CGameEvent, CGameObject>();
                {
                    CTypes::register_type<CGameEventCaused, CGameEvent, CGameObject>();
                }

                CTypes::register_type<CPlugin, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CPlugin>, CPlugin, CGameObject>();
                }
                CTypes::register_type<CGame, CGameObject>();
                CTypes::register_type<CMap, CGameObject>();

            }

            //TODO: add also std::map<std::string,std::string> and std::string
            //TODO: repeat for int
            auto array_string_deserialize = [](std::shared_ptr<CGame> game,
                                               std::shared_ptr<Value> object) {

                std::set<std::string> objects;
                for (unsigned int i = 0; i < object->size(); i++) {
                    objects.insert((*object)[i].asString());
                }
                return objects;

            };

            auto array_string_serialize = [](std::set<std::string> set) {
                std::shared_ptr<Value> arr = std::make_shared<Value>();
                for (std::string ob:set) {
                    add_arr_member(arr, ob);
                }
                return arr;
            };
            CTypes::register_custom_serializer<std::shared_ptr<Json::Value>, std::set<std::string >>(
                    array_string_serialize, array_string_deserialize);
        }
    } _register_types1;
}