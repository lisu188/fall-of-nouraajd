#include "handler/CHandler.h"
#include "object/CObject.h"
#include "CMap.h"

#define REGISTER(clas) std::make_pair(#clas,[]()->CGameObject*{return new clas();})

std::unordered_map<QString,std::function<CGameObject*() > > CTypeHandler::constructors{
    REGISTER ( CWeapon ),
    REGISTER ( CArmor ),
    REGISTER ( CPotion ),
    REGISTER ( CBuilding ),
    REGISTER ( CItem ),
    REGISTER ( CPlayer ),
    REGISTER ( CMonster ),
    REGISTER ( CTile ),
    REGISTER ( CInteraction ),
    REGISTER ( CSmallWeapon ),
    REGISTER ( CHelmet ),
    REGISTER ( CBoots ),
    REGISTER ( CBelt ),
    REGISTER ( CGloves ),
    REGISTER ( CEvent ),
    REGISTER ( CScroll ),
    REGISTER ( CEffect ),
    REGISTER ( CMarket )
};

#undef REGISTER

CGameObject *CTypeHandler::create ( QString name ) {
    auto it=constructors.find ( name );
    if ( it !=constructors.end() ) {
        return ( ( *it ).second ) ();
    }
    return nullptr;
}

void CTypeHandler::registerType ( QString name, std::function<CGameObject*() > constructor ) {
    constructors.insert ( std::make_pair ( name,constructor ) );
}


