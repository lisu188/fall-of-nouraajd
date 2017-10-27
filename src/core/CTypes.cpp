#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "gui/panel/CGameTradePanel.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "core/CController.h"
#include "core/CEventLoop.h"
#include "gui/panel/CGameTextPanel.h"

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
                CTypes::register_type<CMapPlugin, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CMapPlugin>, CMapPlugin, CGameObject>();
                }
                CTypes::register_type<CGame, CGameObject>();
                CTypes::register_type<CMap, CGameObject>();

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

                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CMapGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CStatsGraphicsObject, CGameGraphicsObject, CGameObject>();

                    CTypes::register_type<CGamePanel, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CGameTextPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameInventoryPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameTradePanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameFightPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameQuestPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameCharacterPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                    }
                    CTypes::register_type<CAnimation, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CStaticAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CDynamicAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                    }
                }

                CTypes::register_type<CGui, CGameObject>();
                CTypes::register_type<CTextureCache, CGameObject>();
            }

            //TODO: add also std::map<std::string,std::string> and std::string
            //TODO: repeat for int
            auto array_string_deserialize = [](std::shared_ptr<CMap> map,
                                               std::shared_ptr<Value> object) {

                std::set<std::string> objects;
                for (unsigned int i = 0; i < object->size(); i++) {
                    objects.insert((*object)[i].asString());
                }
                return objects;

            };

            auto array_string_serialize = [](std::set<std::string> set) {
                std::shared_ptr < Value > arr = std::make_shared<Value>();
                for (std::string ob:set) {
                    add_arr_member(arr, ob);
                }
                return arr;
            };
            CTypes::register_custom_serializer<std::shared_ptr<Json::Value>, std::set<std::string>>(
                    array_string_serialize, array_string_deserialize);
        }
    } _register_types;
}

std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *CTypes::builders() {
    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> reg;
    return &reg;
}

std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> *
CTypes::serializers() {
    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> reg;
    return &reg;
}

bool CTypes::is_map_type(boost::typeindex::type_index index) {
    return vstd::ctn(*map_types(), index);
}

bool CTypes::is_pointer_type(boost::typeindex::type_index index) {
    return vstd::ctn(*pointer_types(), index);
}

bool CTypes::is_array_type(boost::typeindex::type_index index) {
    return vstd::ctn(*array_types(), index);
}

std::unordered_set<boost::typeindex::type_index> *CTypes::map_types() {
    static std::unordered_set<boost::typeindex::type_index> _map_types;
    return &_map_types;
}

std::unordered_set<boost::typeindex::type_index> *CTypes::array_types() {
    static std::unordered_set<boost::typeindex::type_index> _array_types;
    return &_array_types;
}

std::unordered_set<boost::typeindex::type_index> *CTypes::pointer_types() {
    static std::unordered_set<boost::typeindex::type_index> _pointer_types;
    return &_pointer_types;
}