#include "handler/CHandler.h"
#include "object/CObject.h"
#include "CMap.h"

CObjectHandler* ATypeHandler::getObjectHandler() {
	return dynamic_cast<CObjectHandler*> ( this->parent() );
}

#define REGISTER(clas) registerType(#clas,[]()->CGameObject*{return new clas();});

CTypeHandler::CTypeHandler() {
	REGISTER ( CWeapon )
	REGISTER ( CArmor )
	REGISTER ( CPotion )
	REGISTER ( CBuilding )
	REGISTER ( CItem )
	REGISTER ( CPlayer )
	REGISTER ( CMonster )
	REGISTER ( CTile )
	REGISTER ( CInteraction )
	REGISTER ( CSmallWeapon )
	REGISTER ( CHelmet )
	REGISTER ( CBoots )
	REGISTER ( CBelt )
	REGISTER ( CGloves )
	REGISTER ( CEvent )
	REGISTER ( CScroll )
	REGISTER ( CEffect )
}

#undef REGISTER

CGameObject *CTypeHandler::create ( QString name ) {
	auto it=constructors.find ( name );
	if ( it !=constructors.end() ) {
		return ( ( *it ).second ) ();
	}
	return nullptr;
}

CGameObject *PyTypeHandler::create ( QString name ) {
	return getObjectHandler()->getMap()->getScriptHandler()->createObject<CGameObject*> ( name );
}

QString PyTypeHandler::getHandlerName() {
	return "PyTypeHandler";
}

QString CTypeHandler::getHandlerName() {
	return "CTypeHandler";
}

void CTypeHandler::registerType ( QString name,  CGameObject* ( *constructor ) () ) {
	constructors.insert ( std::make_pair ( name,constructor ) );
}
