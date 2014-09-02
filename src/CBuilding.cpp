#include "CBuilding.h"
#include <QDebug>
#include "CGameScene.h"
#include <src/playerstatsview.h>
#include "CConfigurationProvider.h"
#include "CScriptEngine.h"

CBuilding::CBuilding() : CMapObject ( 0, 0, 0, 2 ) {}

CBuilding::CBuilding ( const CBuilding & ) {}

void CBuilding::onEnter() {

}

void CBuilding::onMove() {

}

void CBuilding::onCreate() {

}

void CBuilding::onDestroy() {

}

void CBuilding::loadFromJson ( std::string name ) {
	this->typeName = name;
	Json::Value config =
	    ( *CConfigurationProvider::getConfig ( "config/object.json" ) ) [name];
	this->setAnimation ( config.get ( "animation", "" ).asString() );
}

bool CBuilding::isEnabled() { return enabled; }

void CBuilding::setEnabled ( bool enabled ) { this->enabled = enabled; }
