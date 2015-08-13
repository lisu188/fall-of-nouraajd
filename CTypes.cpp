#include "CTypes.h"

void CTypes::initialize() {
    register_type< Stats >();
    register_type< Damage >();
    register_type< CGameObject >();
    register_type< CMapObject >();
    register_type< CWeapon >();
    register_type< CArmor >();
    register_type< CPotion >();
    register_type< CBuilding >();
    register_type< CItem >();
    register_type< CPlayer >();
    register_type< CMonster >();
    register_type< CTile >();
    register_type< CInteraction >();
    register_type< CSmallWeapon >();
    register_type< CHelmet >();
    register_type< CBoots >();
    register_type< CBelt >();
    register_type< CGloves >();
    register_type< CEvent >();
    register_type< CScroll >();
    register_type< CEffect >();
    register_type< CMarket >();
    register_type< CTrigger >();
    register_type< CQuest >();
}

std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> &CTypes::builders() {
    static std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> reg;
    return reg;
}

std::unordered_map<std::pair<int, int>, std::shared_ptr<CSerializerBase> > &CTypes::serializers() {
    static std::unordered_map<std::pair<int,int>,std::shared_ptr<CSerializerBase>> reg;
    return reg;
}
