#include "core/CTypes.h"

void CTypes::initialize() {
    CTypes::register_type<Stats>();
    CTypes::register_type<Damage>();
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject>();
    CTypes::register_type<CWeapon>();
    CTypes::register_type<CArmor>();
    CTypes::register_type<CPotion>();
    CTypes::register_type<CBuilding>();
    CTypes::register_type<CItem>();
    CTypes::register_type<CPlayer>();
    CTypes::register_type<CMonster>();
    CTypes::register_type<CTile>();
    CTypes::register_type<CInteraction>();
    CTypes::register_type<CSmallWeapon>();
    CTypes::register_type<CHelmet>();
    CTypes::register_type<CBoots>();
    CTypes::register_type<CBelt>();
    CTypes::register_type<CGloves>();
    CTypes::register_type<CEvent>();
    CTypes::register_type<CScroll>();
    CTypes::register_type<CEffect>();
    CTypes::register_type<CMarket>();
    CTypes::register_type<CTrigger>();
    CTypes::register_type<CQuest>();
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