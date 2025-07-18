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
#include "core/CGame.h"
#include "CMap.h"
#include "CWrapper.h"
#include "CController.h"
#include "CList.h"
#include "CScript.h"
#include "../gui/CTextureCache.h"
#include "../gui/CTextManager.h"
#include "../gui/panel/CGameQuestionPanel.h"
#include "../gui/panel/CGameQuestPanel.h"
#include "../gui/panel/CGameLootPanel.h"
#include "../gui/panel/CGameFightPanel.h"
#include "../gui/panel/CGameCharacterPanel.h"
#include "../gui/panel/CGameInventoryPanel.h"
#include "../gui/object/CMapGraphicsObject.h"
#include "../gui/object/CStatsGraphicsObject.h"
#include "../gui/object/CConsoleGraphicsObject.h"
#include "../gui/panel/CGameTradePanel.h"
#include "../gui/panel/CGameTextPanel.h"
#include "../gui/panel/CGameDialogPanel.h"
#include "../gui/object/CWidget.h"
#include "../gui/CLayout.h"
#include "../gui/object/CProxyGraphicsObject.h"
#include "../gui/CTooltip.h"
#include "../gui/panel/CCreatureView.h"
#include "../gui/object/CSideBar.h"
#include "../object/CDialog.h"
#include "../handler/CRngHandler.h"

std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>>* CTypes::builders()
{
    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> reg;
    return &reg;
}

std::unordered_map<boost::typeindex::type_index, std::function<void(std::shared_ptr<CGameObject>,
                                                                    std::string, boost::any)>>* CTypes::setters()
{
    static std::unordered_map<boost::typeindex::type_index, std::function<void(std::shared_ptr<CGameObject>,
                                                                               std::string, boost::any)>> reg;
    return &reg;
}

std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<
                       CSerializerBase>>*
CTypes::serializers()
{
    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<
                                  CSerializerBase>> reg;
    return &reg;
}

bool CTypes::is_map_type(boost::typeindex::type_index index)
{
    return vstd::ctn(*map_types(), index);
}

bool CTypes::is_pointer_type(boost::typeindex::type_index index)
{
    return vstd::ctn(*pointer_types(), index);
}

bool CTypes::is_array_type(boost::typeindex::type_index index)
{
    return vstd::ctn(*array_types(), index);
}

std::unordered_set<boost::typeindex::type_index>* CTypes::map_types()
{
    static std::unordered_set<boost::typeindex::type_index> _map_types;
    return &_map_types;
}

std::unordered_set<boost::typeindex::type_index>* CTypes::array_types()
{
    static std::unordered_set<boost::typeindex::type_index> _array_types;
    return &_array_types;
}

std::unordered_set<boost::typeindex::type_index>* CTypes::pointer_types()
{
    static std::unordered_set<boost::typeindex::type_index> _pointer_types;
    return &_pointer_types;
}


namespace
{
    struct register_all_types
    {
        register_all_types()
        {
            // Original types1.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGame, CGameObject>();
                CTypes::register_type<CMap, CGameObject>();

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
            }

            // Original types2.cpp
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
                        {
                            CTypes::register_type<CWrapper<CScroll>, CScroll, CItem, CMapObject, CGameObject>();
                        }
                    }

                    CTypes::register_type<CCreature, CMapObject, CGameObject>();
                    {
                        CTypes::register_type<CPlayer, CCreature, CMapObject, CGameObject>();
                    }
                }
            }

            // Original types3.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CEffect, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CEffect>, CEffect, CGameObject>();
                }

                CTypes::register_type<CMarket, CGameObject>();
                CTypes::register_type<CDialog, CGameObject>();
                {
                    CTypes::register_type<CWrapper<CDialog>, CDialog, CGameObject>();
                }
                CTypes::register_type<CDialogOption, CGameObject>();
                CTypes::register_type<CDialogState, CGameObject>();

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

                CTypes::register_type<CTextureCache, CGameObject>();
                CTypes::register_type<CTextManager, CGameObject>();
            }

            // Original types4.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CLayout, CGameObject>();
                {
                    CTypes::register_type<CCenteredLayout, CLayout, CGameObject>();
                    CTypes::register_type<CParentLayout, CLayout, CGameObject>();
                    CTypes::register_type<CProxyGraphicsLayout, CLayout, CGameObject>();
                }
            }

            // Original types5.cpp (custom types)
            auto array_string_deserialize = [](std::shared_ptr<CGame> game, std::shared_ptr<json> object)
            {
                std::set<std::string> objects;
                for (unsigned int i = 0; i < object->size(); i++)
                {
                    objects.insert((*object)[i].get<std::string>());
                }
                return objects;
            };

            auto array_string_serialize = [](std::set<std::string> set)
            {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (std::string ob : set)
                {
                    add_arr_member(arr, ob);
                }
                return arr;
            };

            auto array_int_deserialize = [](std::shared_ptr<CGame> game, std::shared_ptr<json> object)
            {
                std::set<int> objects;
                for (unsigned int i = 0; i < object->size(); i++)
                {
                    objects.insert((*object)[i].get<int>());
                }
                return objects;
            };

            auto array_int_serialize = [](std::set<int> set)
            {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (int ob : set)
                {
                    add_arr_member(arr, ob);
                }
                return arr;
            };

            auto map_string_string_deserialize = [](std::shared_ptr<CGame> game, std::shared_ptr<json> object)
            {
                std::map<std::string, std::string> objects;
                for (auto [key, value] : object->items())
                {
                    objects[key] = value.get<std::string>();
                }
                return objects;
            };

            auto map_string_string_serialize = [](std::map<std::string, std::string> map)
            {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob : map)
                {
                    add_member(arr, ob.first, ob.second);
                }
                return arr;
            };

            auto map_string_int_deserialize = [](std::shared_ptr<CGame> game, std::shared_ptr<json> object)
            {
                std::map<std::string, int> objects;
                for (auto [key, value] : object->items())
                {
                    objects[key] = value.get<int>();
                }
                return objects;
            };

            auto map_string_int_serialize = [](std::map<std::string, int> map)
            {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob : map)
                {
                    add_member(arr, ob.first, ob.second);
                }
                return arr;
            };

            auto map_int_string_deserialize = [](std::shared_ptr<CGame> game, std::shared_ptr<json> object)
            {
                std::map<int, std::string> objects;
                for (auto [key, value] : object->items())
                {
                    objects[vstd::to_int(key).first] = value.get<std::string>();
                }
                return objects;
            };

            auto map_int_string_serialize = [](std::map<int, std::string> map)
            {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob : map)
                {
                    add_member(arr, vstd::str(ob.first), ob.second);
                }
                return arr;
            };

            auto map_int_int_deserialize = [](std::shared_ptr<CGame> game, std::shared_ptr<json> object)
            {
                std::map<int, int> objects;
                for (auto [key, value] : object->items())
                {
                    objects[vstd::to_int(key).first] = value.get<int>();
                }
                return objects;
            };

            auto map_int_int_serialize = [](std::map<int, int> map)
            {
                std::shared_ptr<json> arr = std::make_shared<json>();
                for (auto ob : map)
                {
                    add_member(arr, vstd::str(ob.first), ob.second);
                }
                return arr;
            };

            CTypes::register_custom_type<std::set<std::string>>(array_string_serialize, array_string_deserialize);
            CTypes::register_custom_type<std::set<int>>(array_int_serialize, array_int_deserialize);
            CTypes::register_custom_type<std::map<std::string, std::string>>(
                map_string_string_serialize, map_string_string_deserialize);
            CTypes::register_custom_type<std::map<std::string, int>>(map_string_int_serialize,
                                                                     map_string_int_deserialize);
            CTypes::register_custom_type<std::map<int, std::string>>(map_int_string_serialize,
                                                                     map_int_string_deserialize);
            CTypes::register_custom_type<std::map<int, int>>(map_int_int_serialize, map_int_int_deserialize);

            // Original types6.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CListInt, CGameObject>();
                CTypes::register_type<CListString, CGameObject>();
                CTypes::register_type<CMapStringString, CGameObject>();
                CTypes::register_type<CMapStringInt, CGameObject>();
                CTypes::register_type<CMapIntString, CGameObject>();
                CTypes::register_type<CMapIntInt, CGameObject>();
            }

            // Original types7.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CSlotConfig, CGameObject>();
                CTypes::register_type<CSlot, CGameObject>();
                CTypes::register_type<CScript, CGameObject>();
            }

            // Original types8.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CObjectHandler, CGameObject>();
                CTypes::register_type<CEventHandler, CGameObject>();
                CTypes::register_type<CRngHandler, CGameObject>();
            }

            // Original types9.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CGui, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CStatsGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CConsoleGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CProxyGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CSideBar, CGameGraphicsObject, CGameObject>();
                }
            }

            // Original types10.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CGamePanel, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CGameTextPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameInventoryPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameTradePanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameFightPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameQuestPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameCharacterPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameQuestionPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameDialogPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameLootPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                    }
                }
            }

            // Original types11.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>();
                    {
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

            // Original types12.cpp
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CAnimation, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CStaticAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CDynamicAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CSelectionBox, CAnimation, CGameGraphicsObject, CGameObject>();
                    }
                    CTypes::register_type<CTooltip, CGameGraphicsObject, CGameObject>();
                }
            }
        }
    } _register_all_types;
}
