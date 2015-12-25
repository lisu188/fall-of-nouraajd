#include "core/CTypes.h"

void initialize2() {
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

