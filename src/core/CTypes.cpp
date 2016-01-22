#include "core/CTypes.h"
#include "CController.h"

void CTypes::initialize() {
    CTypes::register_type<CGameObject>();
    {
        CTypes::register_type<CPlugin, CGameObject>();
        CTypes::register_type<CMapPlugin, CGameObject>();
        CTypes::register_type<CGame, CGameObject>();
        CTypes::register_type<CMap, CGameObject>();

        CTypes::register_type<CEffect, CGameObject>();
        CTypes::register_type<CMarket, CGameObject>();
        CTypes::register_type<CTrigger, CGameObject>();
        CTypes::register_type<CQuest, CGameObject>();

        CTypes::register_type<Stats, CGameObject>();
        CTypes::register_type<Damage, CGameObject>();

        CTypes::register_type<CTile, CGameObject>();

        CTypes::register_type<CInteraction, CGameObject>();

        CTypes::register_type<CController, CGameObject>();
        {
            CTypes::register_type<CTargetController, CController, CGameObject>();
        }

        CTypes::register_type<CMapObject, CGameObject>();
        {
            CTypes::register_type<CBuilding, CMapObject, CGameObject>();
            CTypes::register_type<CEvent, CMapObject, CGameObject>();
            CTypes::register_type<CItem, CMapObject, CGameObject>();
            {
                CTypes::register_type<CWeapon, CItem, CMapObject, CGameObject>();
                {
                    CTypes::register_type<CSmallWeapon, CWeapon, CItem, CMapObject, CGameObject>();
                }
                CTypes::register_type<CArmor, CItem, CMapObject, CGameObject>();
                CTypes::register_type<CPotion, CItem, CMapObject, CGameObject>();
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

std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *CTypes::builders() {
    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> reg;
    return &reg;
}

std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> *CTypes::serializers() {
    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> reg;
    return &reg;
}

namespace {
    struct dummy {
        dummy() {
            CTypes::initialize();
        }
    } _dummy;
}
