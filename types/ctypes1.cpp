#include "CTypes.h"

void initialize1() {
    CTypes::register_type< Stats >();
    CTypes::register_type< Damage >();
    CTypes::register_type< CGameObject >();
    CTypes::register_type< CMapObject >();
    CTypes::register_type< CWeapon >();
    CTypes::register_type< CArmor >();
    CTypes::register_type< CPotion >();
    CTypes::register_type< CBuilding >();
    CTypes::register_type< CItem >();
    CTypes::register_type< CPlayer >();
    CTypes::register_type< CMonster >();
    CTypes::register_type< CTile >();

}
